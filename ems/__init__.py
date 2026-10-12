"""Election Management System: application factory."""
from flask import Flask, render_template, session

from .config import Config


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    from . import automation, db, security
    from .routes import admin, auth, public, voter
    from .utils import DISTRICTS, election_status, fmt_dt

    db.init_app(app)
    app.before_request(security.csrf_protect)
    app.add_template_filter(fmt_dt, "dt")

    @app.context_processor
    def inject_globals():
        return {"me": security.current_user(), "csrf": session.get("csrf"),
                "status": election_status, "DISTRICTS": DISTRICTS}

    for bp in (public.bp, auth.bp, voter.bp, admin.bp):
        app.register_blueprint(bp)

    def error_page(e):
        return render_template("errors.html", e=e), e.code

    for code in (400, 403, 404):
        app.register_error_handler(code, error_page)

    if app.config["SCHEDULER_ENABLED"]:
        automation.start_scheduler(app)
    return app
