# Version 1: Class 12 Final Project

This folder preserves the **original Election Management System** that I built as my Class 12 final project. It was my first professional project, developed over eight months using only Python and MySQL. Both the internal and external examiners were highly satisfied with it, and I secured 100/100 in my final examinations.

The current, redesigned version lives in the root of this repository. This folder is kept for reference and history.

## What it does

- Voter and admin registration (name, Aadhaar, phone, gender)
- Voter login by Voter ID, then a vote for one of four parties (BJP, TMC, SP, AAP) with a district
- Admin dashboard: total voters, total votes, party-wise results
- View, search, update and delete voter records
- Generate a PDF of the election result (`electionresult.pdf`)

## Tech stack

Python 3 · Tkinter (GUI) · MySQL · mysql-connector-python · Pillow · ReportLab

## Files

| File | Purpose |
|---|---|
| `main.py` | The whole application: database functions and every Tkinter screen |
| `settings.py` | Colours and fonts |
| `EMSdatabase.sql` | Creates the `voting_system` database, its tables and sample voters |
| `Assets/` | Window icon and home-screen image |
| `requirements.txt` | Python packages needed |

## How to run

1. Install **MySQL Server** (5.7 or later) and **Python 3.8+**.
2. Create the database:
   ```bash
   mysql -u root -p < EMSdatabase.sql
   ```
3. Open `main.py` and replace `YOUR_MYSQL_PASSWORD` on the `mysql.connect(...)` line with your MySQL root password.
4. Install the packages and start the app **from inside this folder**, since it loads `./Assets/` by relative path:
   ```bash
   cd legacy
   pip install -r requirements.txt
   python main.py
   ```

> Note: `root.iconbitmap()` with an `.ico` file works on Windows. On macOS or Linux, comment out that line if Tkinter reports an error.

## Original requirements

- **Processor:** Intel Core i3 or higher
- **RAM:** 4 GB minimum (8 GB recommended)
- **Display:** 1366 × 768 or higher
- **OS:** Windows 10/11 or Ubuntu 20.04+
