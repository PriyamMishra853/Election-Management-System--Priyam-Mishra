"""SQLite schema, connections, audit logging and first-run seeding."""
import os
import secrets
import sqlite3
from datetime import datetime, timedelta

from flask import current_app, g
from werkzeug.security import generate_password_hash

from .utils import DISTRICTS, TS, now

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, voter_id TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
  aadhaar TEXT UNIQUE NOT NULL, phone TEXT UNIQUE NOT NULL, gender TEXT NOT NULL,
  dob TEXT NOT NULL, district TEXT NOT NULL, password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'voter', active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS elections (
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT,
  start_at TEXT NOT NULL, end_at TEXT NOT NULL,
  results_published INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS candidates (
  id INTEGER PRIMARY KEY, election_id INTEGER NOT NULL REFERENCES elections(id) ON DELETE CASCADE,
  name TEXT NOT NULL, party TEXT NOT NULL, district TEXT NOT NULL);
-- Ballots are anonymous: no link to the voter is stored.
CREATE TABLE IF NOT EXISTS ballots (
  id INTEGER PRIMARY KEY, election_id INTEGER NOT NULL REFERENCES elections(id) ON DELETE CASCADE,
  candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
  district TEXT NOT NULL, receipt TEXT UNIQUE NOT NULL);
-- Records only THAT someone voted, enforcing one vote per election.
CREATE TABLE IF NOT EXISTS participation (
  election_id INTEGER NOT NULL REFERENCES elections(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  voted_at TEXT NOT NULL, PRIMARY KEY (election_id, user_id));
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY, at TEXT NOT NULL, actor TEXT NOT NULL,
  action TEXT NOT NULL, detail TEXT);
"""


def connect(path=None):
    con = sqlite3.connect(path or current_app.config["DATABASE"], timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def get_db():
    """One connection per request, closed automatically at teardown."""
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(_exc=None):
    con = g.pop("db", None)
    if con is not None:
        con.close()


def log(con, actor, action, detail=""):
    con.execute("INSERT INTO audit (at, actor, action, detail) VALUES (?,?,?,?)",
                (now(), actor, action, detail))


def new_voter_id(con):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no look-alike characters (0/O, 1/I)
    while True:
        vid = "EMS" + "".join(secrets.choice(alphabet) for _ in range(7))
        if not con.execute("SELECT 1 FROM users WHERE voter_id=?", (vid,)).fetchone():
            return vid


def init_app(app):
    os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)
    con = connect(app.config["DATABASE"])
    con.executescript(SCHEMA)
    if not con.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
        con.execute("""INSERT INTO users (voter_id,name,aadhaar,phone,gender,dob,district,
                       password_hash,role,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    ("ADMIN001", "Chief Election Officer", "000000000000", "0000000000",
                     "Other", "1980-01-01", "Mumbai",
                     generate_password_hash(app.config["ADMIN_PASSWORD"]), "admin", now()))
        if app.config["SEED_DEMO"]:
            seed_demo(con)
    con.commit()
    con.close()
    app.teardown_appcontext(close_db)


def seed_demo(con):
    """Demo data: one live election, plus voters carried over from the original project."""
    start = (datetime.now() - timedelta(hours=1)).strftime(TS)
    end = (datetime.now() + timedelta(days=2)).strftime(TS)
    cur = con.execute("INSERT INTO elections (title,description,start_at,end_at,created_at) "
                      "VALUES (?,?,?,?,?)", ("Maharashtra Municipal Election 2026",
                      "Demo election created automatically on first run.", start, end, now()))
    eid = cur.lastrowid
    parties = [("BJP", "Rohan Patil"), ("TMC", "Sneha Kulkarni"), ("SP", "Arjun Deshmukh"),
               ("AAP", "Meera Joshi")]
    for d in DISTRICTS:
        for party, name in parties:
            con.execute("INSERT INTO candidates (election_id,name,party,district) VALUES (?,?,?,?)",
                        (eid, f"{name} ({d[:3]})", party, d))
        con.execute("INSERT INTO candidates (election_id,name,party,district) VALUES (?,?,?,?)",
                    (eid, "None of the Above", "NOTA", d))
    demo = [("Ishaan Mishra", "645342409033", "2166179911", "Male", "Pune"),
            ("Divyansh Mehta", "347204658818", "6171805230", "Male", "Mumbai"),
            ("Saswat Sharma", "645638851948", "5593172687", "Male", "Nashik")]
    for name, aadhaar, phone, gender, district in demo:
        con.execute("""INSERT INTO users (voter_id,name,aadhaar,phone,gender,dob,district,
                       password_hash,role,created_at) VALUES (?,?,?,?,?,?,?,?,'voter',?)""",
                    (new_voter_id(con), name, aadhaar, phone, gender, "1999-05-10", district,
                     generate_password_hash("voter123"), now()))
    log(con, "system", "SEED", "Demo election and voters created")
