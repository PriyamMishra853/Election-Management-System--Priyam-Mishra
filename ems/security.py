"""Authentication, role checks, CSRF protection and input validation."""
import secrets
from functools import wraps

from flask import abort, flash, g, redirect, request, session, url_for

from .db import get_db
from .utils import DISTRICTS, age


def current_user():
    uid = session.get("uid")
    if uid is None:
        return None
    return get_db().execute("SELECT * FROM users WHERE id=? AND active=1", (uid,)).fetchone()


def login_required(role=None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                flash("Please sign in first.", "warn")
                return redirect(url_for("auth.login", next=request.path))
            if role and user["role"] != role:
                abort(403)
            g.user = user
            return fn(*args, **kwargs)
        return wrapper
    return deco


def csrf_protect():
    session.setdefault("csrf", secrets.token_hex(16))
    if request.method == "POST" and request.form.get("csrf") != session["csrf"]:
        abort(400, "Invalid form token. Refresh the page and try again.")


def validate_person(f, need_password=True):
    errs = []
    if len(f.get("name", "").strip()) < 3:
        errs.append("Name must be at least 3 characters.")
    if not (f.get("aadhaar", "").isdigit() and len(f["aadhaar"]) == 12):
        errs.append("Aadhaar must be exactly 12 digits.")
    if not (f.get("phone", "").isdigit() and len(f["phone"]) == 10):
        errs.append("Phone must be exactly 10 digits.")
    if f.get("gender") not in ("Male", "Female", "Other"):
        errs.append("Select a gender.")
    if f.get("district") not in DISTRICTS:
        errs.append("Select a district.")
    try:
        if age(f.get("dob", "")) < 18:
            errs.append("Voters must be at least 18 years old.")
    except ValueError:
        errs.append("Enter a valid date of birth.")
    if need_password and len(f.get("password", "")) < 6:
        errs.append("Password must be at least 6 characters.")
    return errs
