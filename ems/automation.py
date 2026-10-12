"""The automation engine: vote counting, result publishing and PDF reports.

A background thread checks every few seconds for elections whose polling window
has closed and publishes their results. Nobody has to press a button.
"""
import io
import os
import threading
import time
from datetime import datetime

from .db import connect, log
from .utils import DISTRICTS, now


def tally(con, eid):
    rows = con.execute("""
        SELECT c.id, c.name, c.party, c.district, COUNT(b.id) AS votes
        FROM candidates c LEFT JOIN ballots b ON b.candidate_id = c.id
        WHERE c.election_id = ? GROUP BY c.id ORDER BY c.district, votes DESC""", (eid,)).fetchall()
    by_district = {}
    for r in rows:
        by_district.setdefault(r["district"], []).append(dict(r))
    winners = {}
    for d, cands in by_district.items():
        contenders = [c for c in cands if c["party"] != "NOTA"]
        top = max((c["votes"] for c in contenders), default=0)
        leaders = [c for c in contenders if c["votes"] == top and top > 0]
        winners[d] = leaders[0] if len(leaders) == 1 else None  # None = tie or no votes
    seats, party_votes = {}, {}
    for w in winners.values():
        if w:
            seats[w["party"]] = seats.get(w["party"], 0) + 1
    for r in rows:
        party_votes[r["party"]] = party_votes.get(r["party"], 0) + r["votes"]
    return {"districts": by_district, "winners": winners, "seats": seats,
            "party_votes": party_votes, "total": sum(r["votes"] for r in rows)}


def turnout(con, eid):
    voted = dict(con.execute("""SELECT u.district, COUNT(*) FROM participation p
                                JOIN users u ON u.id = p.user_id WHERE p.election_id = ?
                                GROUP BY u.district""", (eid,)).fetchall())
    registered = dict(con.execute("SELECT district, COUNT(*) FROM users "
                                  "WHERE role='voter' AND active=1 GROUP BY district").fetchall())
    return [{"district": d, "voted": voted.get(d, 0), "registered": registered.get(d, 0),
             "pct": round(100 * voted.get(d, 0) / registered[d], 1) if registered.get(d) else 0}
            for d in DISTRICTS]


def build_pdf(con, e):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    t = tally(con, e["id"])
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=e["title"])
    ss = getSampleStyleSheet()
    story = [Paragraph(e["title"] + " — Official Results", ss["Title"]),
             Paragraph(f"Polling: {e['start_at'].replace('T', ' ')} to {e['end_at'].replace('T', ' ')}"
                       f" &nbsp;|&nbsp; Total ballots: {t['total']}", ss["Normal"]), Spacer(1, 12)]
    style = TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")])
    summary = [["Party", "Seats won", "Total votes"]] + [
        [p, t["seats"].get(p, 0), v] for p, v in sorted(t["party_votes"].items(), key=lambda x: -x[1])]
    story += [Paragraph("Party summary", ss["Heading2"]), Table(summary, style=style), Spacer(1, 12)]
    for d, cands in t["districts"].items():
        w = t["winners"][d]
        winner = f"{w['name']} ({w['party']})" if w else "Undecided (tie or no votes)"
        story.append(Paragraph(f"{d}: Winner {winner}", ss["Heading3"]))
        story.append(Table([["Candidate", "Party", "Votes"]] +
                           [[c["name"], c["party"], c["votes"]] for c in cands], style=style))
        story.append(Spacer(1, 8))
    story.append(Paragraph(f"Generated automatically on {datetime.now():%d %b %Y %H:%M}", ss["Italic"]))
    doc.build(story)
    buf.seek(0)
    return buf


def publish_due_results(db_path, reports_dir):
    """Publish results (and save a PDF) for every election whose polling has closed."""
    con = connect(db_path)
    try:
        due = con.execute("SELECT * FROM elections WHERE results_published=0 AND end_at<=?",
                          (now(),)).fetchall()
        for e in due:
            claimed = con.execute("UPDATE elections SET results_published=1 "
                                  "WHERE id=? AND results_published=0", (e["id"],)).rowcount
            if not claimed:  # another worker got there first
                continue
            try:
                os.makedirs(reports_dir, exist_ok=True)
                path = os.path.join(reports_dir, f"election_{e['id']}_results.pdf")
                with open(path, "wb") as f:
                    f.write(build_pdf(con, e).read())
                detail = f"Results auto-published for '{e['title']}'; report saved to {path}"
            except ImportError:
                detail = f"Results auto-published for '{e['title']}' (install reportlab for PDF reports)"
            log(con, "system", "RESULTS_PUBLISHED", detail)
            con.commit()
    finally:
        con.close()


_started = False


def start_scheduler(app):
    global _started
    if _started:
        return
    _started = True

    def loop():
        while True:
            try:
                publish_due_results(app.config["DATABASE"], app.config["REPORTS_DIR"])
            except Exception:  # keep the scheduler alive no matter what
                app.logger.exception("automation tick failed")
            time.sleep(app.config["SCHEDULER_INTERVAL"])

    threading.Thread(target=loop, name="ems-scheduler", daemon=True).start()
