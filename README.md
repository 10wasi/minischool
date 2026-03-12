# Mini School Management (Python / Flask)

A full **Python** web app using **Flask** and **SQLite**. Same features as before: teacher and student dashboards, students, tasks, complaints with replies, and attendance flow charts.

## Setup

1. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   venv\Scripts\activate    # Windows
   # or: source venv/bin/activate   # macOS/Linux
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the app:**
   ```bash
   python app.py
   ```

4. Open **http://127.0.0.1:5000** in your browser.

## Deploy on Railway (or similar)

- **nixpacks.toml** and **railway.toml** in the repo tell Railway to run:  
  `gunicorn -w 1 -b 0.0.0.0:$PORT app:app`  
  so the app uses a production server (no dev-server warning).
- If you still see the Flask dev-server warning, set the **Start Command** in Railway yourself:  
  **Project → your service → Settings → Deploy → Start Command** → set to:  
  `gunicorn -w 1 -b 0.0.0.0:$PORT app:app`  
  then redeploy.
- Local runs are unchanged: `python app.py` still uses the dev server on port 5000.

## Features

- **Login / Signup** – Teacher accounts; student accounts are created by teachers when adding a student (optional email/password).
- **Teacher dashboard** – Total students, pending tasks, low attendance count, open complaints, attendance flow chart, student/task management, complaint replies.
- **Student dashboard** – Own attendance flow, tasks (mark complete), submit complaints, view teacher replies.
- **Data** – Stored in `school.db` (SQLite) in the project folder. Delete this file to reset all data.

## Project structure

```
app.py              # Flask app, routes, database
requirements.txt    # Flask
static/
  styles.css        # UI styles
templates/
  index.html        # Login
  signup.html       # Teacher signup
  dashboard.html    # Teacher dashboard
  student.html      # Student dashboard
school.db           # Created on first run (SQLite)
```
