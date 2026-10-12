"""End-to-end tests for the main voter and admin flows.  Run: pytest"""
import os
import re
import sqlite3
from datetime import date, datetime, timedelta

import pytest

from ems import create_app
from ems.automation import publish_due_results
from ems.utils import TS


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db"),
                       "REPORTS_DIR": str(tmp_path / "reports"), "SEED_DEMO": False,
                       "SCHEDULER_ENABLED": False, "ADMIN_PASSWORD": "admin123"})


@pytest.fixture
def client(app):
    return app.test_client()


def token(client):
    client.get("/")
    with client.session_transaction() as s:
        return s["csrf"]


def register(client, **overrides):
    data = {"name": "Test Voter", "aadhaar": "123456789012", "phone": "9876543210",
            "gender": "Female", "dob": "2000-01-01", "district": "Pune",
            "password": "secret1", "confirm": "secret1"}
    data.update(overrides)
    data["csrf"] = token(client)
    return client.post("/register", data=data, follow_redirects=True)


def login(client, voter_id, password):
    return client.post("/login", data={"voter_id": voter_id, "password": password,
                                       "csrf": token(client)}, follow_redirects=True)


def make_election(app, start, end, district="Pune"):
    con = sqlite3.connect(app.config["DATABASE"])
    t = datetime.now()
    eid = con.execute("INSERT INTO elections (title,start_at,end_at,created_at) VALUES (?,?,?,?)",
                      ("Test Election", (t + start).strftime(TS), (t + end).strftime(TS),
                       t.strftime(TS))).lastrowid
    cid = con.execute("INSERT INTO candidates (election_id,name,party,district) VALUES (?,?,?,?)",
                      (eid, "Candidate A", "AAA", district)).lastrowid
    con.commit()
    con.close()
    return eid, cid


def registered_voter(client):
    resp = register(client)
    return re.search(rb"Voter ID is (EMS[A-Z0-9]{7})", resp.data).group(1).decode()


def test_registration_issues_voter_id(client):
    assert registered_voter(client).startswith("EMS")


def test_underage_and_duplicate_registration_rejected(client):
    young = date(date.today().year - 10, 1, 1).isoformat()
    assert b"at least 18" in register(client, dob=young).data
    registered_voter(client)
    assert b"already registered" in register(client, phone="9999999999").data


def test_vote_once_with_anonymous_ballot_and_receipt(app, client):
    eid, cid = make_election(app, timedelta(hours=-1), timedelta(hours=1))
    login(client, registered_voter(client), "secret1")
    resp = client.post(f"/vote/{eid}", data={"candidate": cid, "csrf": token(client)})
    assert b"Vote recorded" in resp.data
    code = re.search(rb'class="receipt">([0-9a-f]{16})<', resp.data).group(1).decode()

    again = client.post(f"/vote/{eid}", data={"candidate": cid, "csrf": token(client)},
                        follow_redirects=True)
    assert b"already voted" in again.data

    con = sqlite3.connect(app.config["DATABASE"])
    assert con.execute("SELECT COUNT(*) FROM ballots").fetchone()[0] == 1
    columns = {row[1] for row in con.execute("PRAGMA table_info(ballots)")}
    assert "user_id" not in columns  # the ballot cannot be traced back to the voter
    con.close()

    verified = client.post("/verify", data={"receipt": code, "csrf": token(client)})
    assert b"Ballot found" in verified.data


def test_cannot_vote_before_polling_opens(app, client):
    eid, cid = make_election(app, timedelta(hours=1), timedelta(hours=2))
    login(client, registered_voter(client), "secret1")
    resp = client.post(f"/vote/{eid}", data={"candidate": cid, "csrf": token(client)},
                       follow_redirects=True)
    assert b"not open for voting" in resp.data


def test_results_publish_automatically_after_close(app, client):
    eid, _ = make_election(app, timedelta(hours=-2), timedelta(hours=-1))
    assert client.get(f"/results/{eid}").status_code == 302  # hidden until published
    publish_due_results(app.config["DATABASE"], app.config["REPORTS_DIR"])
    assert b"Official results" in client.get(f"/results/{eid}").data
    assert os.path.exists(os.path.join(app.config["REPORTS_DIR"], f"election_{eid}_results.pdf"))


def test_admin_area_is_protected(client):
    assert client.get("/admin/").status_code == 302
    login(client, registered_voter(client), "secret1")
    assert client.get("/admin/").status_code == 403


def test_admin_can_schedule_election(client):
    login(client, "ADMIN001", "admin123")
    t = datetime.now()
    resp = client.post("/admin/elections/new", follow_redirects=True, data={
        "title": "City Council", "start_at": (t + timedelta(days=1)).strftime(TS),
        "end_at": (t + timedelta(days=2)).strftime(TS), "nota": "1", "csrf": token(client)})
    assert b"Election scheduled" in resp.data and b"None of the Above" in resp.data


def test_post_without_csrf_token_is_rejected(client):
    assert client.post("/login", data={"voter_id": "x", "password": "y"}).status_code == 400
