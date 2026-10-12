"""Voter dashboard and the secret ballot."""
import hashlib
import secrets
import sqlite3

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from ..db import get_db, log
from ..security import login_required
from ..utils import election_status, now

bp = Blueprint("voter", __name__)


@bp.route("/dashboard")
@login_required("voter")
def dashboard():
    rows = get_db().execute("""SELECT e.*, p.voted_at FROM elections e
                               LEFT JOIN participation p ON p.election_id = e.id AND p.user_id = ?
                               ORDER BY e.start_at DESC""", (g.user["id"],)).fetchall()
    return render_template("voter/dashboard.html", elections=rows)


@bp.route("/vote/<int:eid>", methods=["GET", "POST"])
@login_required("voter")
def vote(eid):
    con = get_db()
    e = con.execute("SELECT * FROM elections WHERE id=?", (eid,)).fetchone() or abort(404)
    if election_status(e) != "live":
        flash("This election is not open for voting.", "warn")
        return redirect(url_for("voter.dashboard"))
    if con.execute("SELECT 1 FROM participation WHERE election_id=? AND user_id=?",
                   (eid, g.user["id"])).fetchone():
        flash("You have already voted in this election.", "warn")
        return redirect(url_for("voter.dashboard"))
    cands = con.execute("SELECT * FROM candidates WHERE election_id=? AND district=? "
                        "ORDER BY party='NOTA', party", (eid, g.user["district"])).fetchall()
    if request.method == "POST":
        cid = request.form.get("candidate", type=int)
        if cid not in {c["id"] for c in cands}:
            flash("Please choose a candidate.", "error")
            return render_template("voter/vote.html", e=e, cands=cands)
        code = secrets.token_hex(8)
        try:
            # Both rows are written in one transaction, but nothing links them together.
            con.execute("INSERT INTO participation (election_id,user_id,voted_at) VALUES (?,?,?)",
                        (eid, g.user["id"], now()))
            con.execute("INSERT INTO ballots (election_id,candidate_id,district,receipt) VALUES (?,?,?,?)",
                        (eid, cid, g.user["district"], hashlib.sha256(code.encode()).hexdigest()))
            log(con, g.user["voter_id"], "VOTE_CAST", f"Election #{eid}")
            con.commit()
        except sqlite3.IntegrityError:  # a second tab or double-click lost the race
            con.rollback()
            flash("You have already voted in this election.", "warn")
            return redirect(url_for("voter.dashboard"))
        return render_template("voter/receipt.html", e=e, code=code)
    return render_template("voter/vote.html", e=e, cands=cands)
