# Setup Guide

This guide takes you from a fresh computer to a running Election Management System.

- [1. Requirements](#1-requirements)
- [2. Install](#2-install)
- [3. Run](#3-run)
- [4. First login and a guided tour](#4-first-login-and-a-guided-tour)
- [5. Configuration](#5-configuration)
- [6. Running the tests](#6-running-the-tests)
- [7. Deploying to a server](#7-deploying-to-a-server)
- [8. Resetting and backing up data](#8-resetting-and-backing-up-data)
- [9. Troubleshooting](#9-troubleshooting)
- [10. Running the original Class 12 version](#10-running-the-original-class-12-version)

---

## 1. Requirements

| Item | Minimum |
|---|---|
| Operating system | Windows 10/11, macOS 12+, or Ubuntu 20.04+ |
| Python | 3.9 or later |
| Git | Any recent version (optional: you can download the ZIP instead) |
| Browser | Any modern browser (Chrome, Edge, Firefox, Safari) |
| Hardware | 2 GB RAM, 200 MB free disk space |

No database server is needed. The system uses SQLite, which is built into Python.

### Installing Python

- **Windows:** download it from [python.org/downloads](https://www.python.org/downloads/). On the first installer screen, tick **"Add python.exe to PATH"**.
- **macOS:** install the command-line tools with `xcode-select --install` (this includes Python 3 and Git), or install from python.org.
- **Ubuntu/Debian:** `sudo apt install python3 python3-venv python3-pip git`

Check that it worked:

```bash
python3 --version     # Windows: python --version
```

## 2. Install

```bash
git clone https://github.com/PriyamMishra853/Election-Management-System--Priyam-Mishra.git
cd Election-Management-System--Priyam-Mishra
```

No Git? On the GitHub page, click **Code → Download ZIP**, unzip it and open a terminal in that folder.

Create a virtual environment and install the dependencies:

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> If PowerShell blocks the activate script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try again.

## 3. Run

```bash
python run.py
```

You should see `Running on http://127.0.0.1:5000`. Open that address in your browser.

The first start automatically:
1. creates the database at `instance/ems.db`
2. creates the admin account `ADMIN001`
3. creates a **live demo election** across five districts (Nashik, Pune, Mumbai, Jalgaon, Satara), with four parties plus NOTA in each
4. creates three demo voters with the password `voter123`
5. starts the automation engine in the background

Press `Ctrl + C` in the terminal to stop the server.

## 4. First login and a guided tour

1. **Sign in as admin:** `ADMIN001` / `admin123`. You land on the Election Commission dashboard.
2. Open **Voters** and note one of the demo Voter IDs (they start with `EMS`).
3. **Schedule a test election:** click **+ Schedule election** and set it to open in a couple of minutes and close a few minutes later. Add candidates while it is still *Upcoming*.
4. **Log out** and **register a new voter** from the home page. You get a Voter ID immediately.
5. Sign in as that voter, open the live election and **cast a vote**. Copy the receipt code.
6. Open **Verify receipt** and paste the code to confirm the ballot was counted.
7. Wait for the closing time, or sign in as admin and click **Close polling now**. Within 30 seconds the results are published, and a PDF appears in the `reports/` folder.

## 5. Configuration

Every setting has a sensible default. To change one, set an environment variable before starting the app.

| Variable | Default | Purpose |
|---|---|---|
| `EMS_SECRET` | random on every start | Key that signs session cookies. **Set this in production**, otherwise everyone is logged out when the server restarts. |
| `EMS_ADMIN_PASSWORD` | `admin123` | Password for `ADMIN001`. Only used when the database is first created. |
| `EMS_DB` | `instance/ems.db` | Path to the SQLite database file. |
| `EMS_REPORTS` | `reports/` | Folder where PDF result sheets are saved. |
| `EMS_SEED_DEMO` | `1` | Set to `0` to start with no demo election or voters. |
| `EMS_SCHEDULER` | `1` | Set to `0` to turn off the background automation engine. |
| `EMS_SCHEDULER_INTERVAL` | `30` | Seconds between automation checks. |
| `HOST` / `PORT` | `127.0.0.1` / `5000` | Address the server listens on. Use `HOST=0.0.0.0` to allow other devices on your network. |

**macOS / Linux**
```bash
export EMS_SECRET="a-long-random-string"
export EMS_ADMIN_PASSWORD="choose-a-strong-password"
export EMS_SEED_DEMO=0
python run.py
```

**Windows (PowerShell)**
```powershell
$env:EMS_SECRET = "a-long-random-string"
$env:EMS_ADMIN_PASSWORD = "choose-a-strong-password"
$env:EMS_SEED_DEMO = "0"
python run.py
```

To generate a good secret: `python -c "import secrets; print(secrets.token_hex(32))"`

## 6. Running the tests

```bash
pip install -r requirements-dev.txt
pytest
```

The tests use a temporary database, so your real data is never touched. They cover registration and eligibility rules, one-vote-per-voter, ballot anonymity, receipt verification, automatic result publishing, admin access control and CSRF protection.

## 7. Deploying to a server

`python run.py` uses Flask's built-in server, which is meant for development and demos. For a real deployment, use a production WSGI server.

**Linux / macOS (Gunicorn)**
```bash
pip install gunicorn
EMS_SECRET="..." EMS_ADMIN_PASSWORD="..." gunicorn -w 2 -b 0.0.0.0:8000 "ems:create_app()"
```

**Windows (Waitress)**
```powershell
pip install waitress
waitress-serve --listen=0.0.0.0:8000 --call ems:create_app
```

Recommendations:
- Put the app behind HTTPS, for example with Nginx and a Let's Encrypt certificate.
- Always set `EMS_SECRET` and `EMS_ADMIN_PASSWORD`, and set `EMS_SEED_DEMO=0`.
- Each worker process runs its own automation thread. This is safe, because results are only ever published once, but one or two workers are plenty.
- Back up `instance/ems.db` regularly (see below).

## 8. Resetting and backing up data

| Task | How |
|---|---|
| Back up | Stop the server and copy `instance/ems.db` somewhere safe. |
| Restore | Stop the server and copy the backup over `instance/ems.db`. |
| Start fresh | Stop the server, delete `instance/ems.db` (and `reports/` if you like), then start it again. |

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| `python: command not found` | Use `python3` on macOS and Linux. On Windows, reinstall Python with **Add to PATH** ticked. |
| `ModuleNotFoundError: No module named 'flask'` | Activate the virtual environment first, then run `pip install -r requirements.txt`. |
| `Address already in use` | Another program is using port 5000 (on macOS, often AirPlay Receiver). Run `PORT=5050 python run.py` (Windows: `$env:PORT="5050"`). |
| "Invalid form token" after a restart | The session key changed. Refresh the page, and set `EMS_SECRET` so it stays the same between restarts. |
| Results didn't publish | Check that the closing time has passed and wait up to 30 seconds. Make sure `EMS_SCHEDULER` isn't set to `0`. |
| No PDF in `reports/` | Install ReportLab: `pip install reportlab`. Results still publish without it. |
| Forgot the admin password | Delete `instance/ems.db` to start over, setting `EMS_ADMIN_PASSWORD` first. Note that this erases all data. |

## 10. Running the original Class 12 version

The original desktop application is in [`legacy/`](../legacy/). It needs a MySQL server. See [legacy/README.md](../legacy/README.md) for instructions.
