"""Configuration. Every value can be overridden with an environment variable."""
import os
import secrets

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Config:
    # Set EMS_SECRET in production so sessions survive a restart.
    SECRET_KEY = os.environ.get("EMS_SECRET", secrets.token_hex(32))
    DATABASE = os.environ.get("EMS_DB", os.path.join(BASE_DIR, "instance", "ems.db"))
    REPORTS_DIR = os.environ.get("EMS_REPORTS", os.path.join(BASE_DIR, "reports"))
    # Used only when the admin account is first created.
    ADMIN_PASSWORD = os.environ.get("EMS_ADMIN_PASSWORD", "admin123")
    SEED_DEMO = os.environ.get("EMS_SEED_DEMO", "1") == "1"
    SCHEDULER_ENABLED = os.environ.get("EMS_SCHEDULER", "1") == "1"
    SCHEDULER_INTERVAL = int(os.environ.get("EMS_SCHEDULER_INTERVAL", "30"))
