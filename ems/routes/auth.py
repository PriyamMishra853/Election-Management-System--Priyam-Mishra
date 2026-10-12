"""Voter self-registration, sign in and sign out."""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import get_db, log, new_voter_id
from ..security import validate_person
from ..utils import now

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        errs = validate_person(f)
        if f.get("password") != f.get("confirm"):
            errs.append("Passwords do not match.")
        con = get_db()
        if not errs and con.execute("SELECT 1 FROM users WHERE aadhaar=? OR phone=?",
                                    (f["aadhaar"], f["phone"])).fetchone():
            errs.append("A voter with this Aadhaar or phone is already registered.")
        if errs:
            for e in errs:
                flash(e, "error")
            return render_template("auth/register.html", form=f)
        vid = new_voter_id(con)
        con.execute("""INSERT INTO users (voter_id,name,aadhaar,phone,gender,dob,district,
                       password_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (vid, f["name"].strip(), f["aadhaar"], f["phone"], f["gender"], f["dob"],
                     f["district"], generate_password_hash(f["password"]), now()))
        log(con, vid, "REGISTER", f"Voter registered in {f['district']}")
        con.commit()
        flash(f"Registration approved automatically. Your Voter ID is {vid}. Keep it safe.", "ok")
        return redirect(url_for("auth.login", vid=vid))
    return render_template("auth/register.html", form={})


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        con = get_db()
        vid = request.form.get("voter_id", "").strip().upper()
        user = con.execute("SELECT * FROM users WHERE voter_id=? AND active=1", (vid,)).fetchone()
        if not user or not check_password_hash(user["password_hash"], request.form.get("password", "")):
            log(con, vid or "?", "LOGIN_FAILED")
            con.commit()
            flash("Invalid Voter ID or password.", "error")
            return render_template("auth/login.html", vid=vid)
        session.clear()  # new session on login prevents session fixation
        session["uid"] = user["id"]
        log(con, vid, "LOGIN")
        con.commit()
        nxt = request.args.get("next", "")
        if nxt.startswith("/") and not nxt.startswith("//"):
            return redirect(nxt)
        return redirect(url_for("admin.home" if user["role"] == "admin" else "voter.dashboard"))
    return render_template("auth/login.html", vid=request.args.get("vid", ""))


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("public.index"))
