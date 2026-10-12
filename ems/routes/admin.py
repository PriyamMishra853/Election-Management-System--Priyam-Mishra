"""Election Commission (admin) tools."""
import csv
import io
import secrets
from datetime import datetime, timedelta

from flask import (Blueprint, Response, abort, current_app, flash, g, redirect,
                   render_template, request, url_for)
from werkzeug.security import generate_password_hash

from ..automation import publish_due_results, turnout
from ..db import get_db, log
from ..security import login_required, validate_person
from ..utils import DISTRICTS, TS, election_status, now

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@login_required("admin")
def home():
    con = get_db()
    elections = con.execute("""SELECT e.*,
                               (SELECT COUNT(*) FROM ballots b WHERE b.election_id = e.id) votes,
                               (SELECT COUNT(*) FROM candidates c WHERE c.election_id = e.id) ncand
                               FROM elections e ORDER BY start_at DESC""").fetchall()
    stats = con.execute("""SELECT (SELECT COUNT(*) FROM users WHERE role='voter') voters,
                           (SELECT COUNT(*) FROM users WHERE role='voter' AND active=0) blocked,
                           (SELECT COUNT(*) FROM ballots) ballots""").fetchone()
    audit = con.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 8").fetchall()
    return render_template("admin/dashboard.html", elections=elections, stats=stats, audit=audit)


@bp.route("/elections/new", methods=["GET", "POST"])
@login_required("admin")
def election_new():
    if request.method == "POST":
        f = request.form
        if not f.get("title") or not f.get("start_at") or not f.get("end_at") or f["end_at"] <= f["start_at"]:
            flash("Title is required and the closing time must be after the opening time.", "error")
            return render_template("admin/election_form.html", form=f)
        con = get_db()
        cur = con.execute("INSERT INTO elections (title,description,start_at,end_at,created_at) "
                          "VALUES (?,?,?,?,?)",
                          (f["title"].strip(), f.get("description", ""), f["start_at"], f["end_at"], now()))
        if f.get("nota"):
            for d in DISTRICTS:
                con.execute("INSERT INTO candidates (election_id,name,party,district) VALUES (?,?,?,?)",
                            (cur.lastrowid, "None of the Above", "NOTA", d))
        log(con, g.user["voter_id"], "ELECTION_CREATED", f["title"])
        con.commit()
        flash("Election scheduled. Voting opens and closes by itself, and results publish automatically.", "ok")
        return redirect(url_for("admin.election_detail", eid=cur.lastrowid))
    start = (datetime.now() + timedelta(minutes=5)).strftime(TS)
    end = (datetime.now() + timedelta(days=1)).strftime(TS)
    return render_template("admin/election_form.html", form={"start_at": start, "end_at": end, "nota": "1"})


@bp.route("/elections/<int:eid>", methods=["GET", "POST"])
@login_required("admin")
def election_detail(eid):
    con = get_db()
    e = con.execute("SELECT * FROM elections WHERE id=?", (eid,)).fetchone() or abort(404)
    state = election_status(e)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add" and state == "upcoming":
            name, party, dist = (request.form.get(k, "").strip() for k in ("name", "party", "district"))
            if name and party and dist in DISTRICTS:
                con.execute("INSERT INTO candidates (election_id,name,party,district) VALUES (?,?,?,?)",
                            (eid, name, party.upper(), dist))
                log(con, g.user["voter_id"], "CANDIDATE_ADDED", f"{name} ({party}) in {dist}")
            else:
                flash("Fill in every candidate field.", "error")
        elif action == "remove" and state == "upcoming":
            con.execute("DELETE FROM candidates WHERE id=? AND election_id=?",
                        (request.form.get("cid", type=int), eid))
            log(con, g.user["voter_id"], "CANDIDATE_REMOVED", f"Election #{eid}")
        elif action == "close" and state == "live":
            con.execute("UPDATE elections SET end_at=? WHERE id=?", (now(), eid))
            log(con, g.user["voter_id"], "ELECTION_CLOSED_EARLY", e["title"])
        elif action == "delete" and state != "live":
            con.execute("DELETE FROM elections WHERE id=?", (eid,))
            log(con, g.user["voter_id"], "ELECTION_DELETED", e["title"])
            con.commit()
            return redirect(url_for("admin.home"))
        else:
            flash("That change isn't allowed once voting has started.", "warn")
        con.commit()
        # Publish straight away if the election just closed, instead of waiting for the next tick.
        publish_due_results(current_app.config["DATABASE"], current_app.config["REPORTS_DIR"])
        return redirect(url_for("admin.election_detail", eid=eid))
    cands = con.execute("SELECT * FROM candidates WHERE election_id=? ORDER BY district, party",
                        (eid,)).fetchall()
    return render_template("admin/election_detail.html", e=e, cands=cands, turnout=turnout(con, eid))


@bp.route("/voters")
@login_required("admin")
def voters():
    q = request.args.get("q", "").strip()
    like = f"%{q}%"
    rows = get_db().execute("""SELECT * FROM users WHERE role='voter' AND
                               (voter_id LIKE ? OR name LIKE ? OR aadhaar LIKE ? OR phone LIKE ?)
                               ORDER BY created_at DESC""", (like, like, like, like)).fetchall()
    return render_template("admin/voters.html", voters=rows, q=q)


@bp.route("/voters/export.csv")
@login_required("admin")
def voters_csv():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Voter ID", "Name", "Aadhaar", "Phone", "Gender", "DOB", "District", "Active", "Registered"])
    for r in get_db().execute("SELECT * FROM users WHERE role='voter' ORDER BY voter_id"):
        w.writerow([r["voter_id"], r["name"], r["aadhaar"], r["phone"], r["gender"], r["dob"],
                    r["district"], r["active"], r["created_at"]])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=voters.csv"})


@bp.route("/voters/<int:uid>", methods=["GET", "POST"])
@login_required("admin")
def voter_edit(uid):
    con = get_db()
    u = con.execute("SELECT * FROM users WHERE id=? AND role='voter'", (uid,)).fetchone() or abort(404)
    if request.method == "POST":
        f = request.form
        action = f.get("action")
        if action == "toggle":
            con.execute("UPDATE users SET active=1-active WHERE id=?", (uid,))
            log(con, g.user["voter_id"], "VOTER_BLOCKED" if u["active"] else "VOTER_UNBLOCKED", u["voter_id"])
        elif action == "delete":
            con.execute("DELETE FROM users WHERE id=?", (uid,))
            log(con, g.user["voter_id"], "VOTER_DELETED", u["voter_id"])
            con.commit()
            return redirect(url_for("admin.voters"))
        elif action == "reset":
            pw = secrets.token_urlsafe(6)
            con.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(pw), uid))
            log(con, g.user["voter_id"], "PASSWORD_RESET", u["voter_id"])
            flash(f"Temporary password for {u['voter_id']}: {pw}", "ok")
        else:
            errs = validate_person(f, need_password=False)
            if not errs and con.execute("SELECT 1 FROM users WHERE (aadhaar=? OR phone=?) AND id<>?",
                                        (f["aadhaar"], f["phone"], uid)).fetchone():
                errs.append("Aadhaar or phone already belongs to another voter.")
            for e in errs:
                flash(e, "error")
            if not errs:
                con.execute("UPDATE users SET name=?,aadhaar=?,phone=?,gender=?,dob=?,district=? WHERE id=?",
                            (f["name"].strip(), f["aadhaar"], f["phone"], f["gender"], f["dob"],
                             f["district"], uid))
                log(con, g.user["voter_id"], "VOTER_UPDATED", u["voter_id"])
                flash("Voter updated.", "ok")
        con.commit()
        return redirect(url_for("admin.voter_edit", uid=uid))
    return render_template("admin/voter_edit.html", u=u)


@bp.route("/audit")
@login_required("admin")
def audit():
    rows = get_db().execute("SELECT * FROM audit ORDER BY id DESC LIMIT 500").fetchall()
    return render_template("admin/audit.html", rows=rows)
