"""Pages anyone can see: home, published results and receipt verification."""
import hashlib

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for

from ..automation import build_pdf, tally, turnout
from ..db import get_db
from ..security import current_user

bp = Blueprint("public", __name__)


def _visible_election(eid):
    """Results are public once published; admins can watch the live count."""
    e = get_db().execute("SELECT * FROM elections WHERE id=?", (eid,)).fetchone() or abort(404)
    user = current_user()
    return e, bool(e["results_published"] or (user and user["role"] == "admin"))


@bp.route("/")
def index():
    con = get_db()
    elections = con.execute("SELECT * FROM elections ORDER BY start_at DESC").fetchall()
    stats = con.execute("""SELECT (SELECT COUNT(*) FROM users WHERE role='voter') voters,
                           (SELECT COUNT(*) FROM elections) elections,
                           (SELECT COUNT(*) FROM ballots) ballots""").fetchone()
    return render_template("public/index.html", elections=elections, stats=stats)


@bp.route("/results/<int:eid>")
def results(eid):
    e, visible = _visible_election(eid)
    if not visible:
        flash("Results are published automatically when polling closes.", "warn")
        return redirect(url_for("public.index"))
    con = get_db()
    return render_template("public/results.html", e=e, t=tally(con, eid), turnout=turnout(con, eid))


@bp.route("/results/<int:eid>.pdf")
def results_pdf(eid):
    e, visible = _visible_election(eid)
    if not visible:
        abort(403)
    return send_file(build_pdf(get_db(), e), mimetype="application/pdf",
                     download_name=f"election_{eid}_results.pdf")


@bp.route("/verify", methods=["GET", "POST"])
def verify():
    found = None
    if request.method == "POST":
        code = request.form.get("receipt", "").strip().lower()
        row = get_db().execute("""SELECT e.title FROM ballots b JOIN elections e ON e.id = b.election_id
                                  WHERE b.receipt=?""",
                               (hashlib.sha256(code.encode()).hexdigest(),)).fetchone()
        found = row["title"] if row else False
    return render_template("public/verify.html", found=found)
