import os
import hmac
import secrets
import sqlite3
from functools import wraps

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 8,
)


def get_db():
    db = sqlite3.connect("database.db")
    db.row_factory = sqlite3.Row
    return db


def init_db():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            age INTEGER,
            gender TEXT,
            disease TEXT,
            recovery_days INTEGER
        )
    """)

    columns = [row[1] for row in cursor.execute("PRAGMA table_info(patients)").fetchall()]
    if "user_id" not in columns:
        cursor.execute("ALTER TABLE patients ADD COLUMN user_id INTEGER")

    db.commit()
    db.close()


init_db()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped_view


def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


@app.context_processor
def inject_csrf_token():
    return {"csrf_token": csrf_token}


def valid_csrf():
    submitted = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    return bool(submitted and expected and hmac.compare_digest(submitted, expected))


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        if not valid_csrf():
            flash("Invalid form token. Please try again.")
            return redirect(url_for("register"))

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not email or "@" not in email:
            flash("Enter a valid email address.")
            return render_template("register.html")
        if len(password) < 8:
            flash("Password must be at least 8 characters.")
            return render_template("register.html")
        if password != confirm_password:
            flash("Passwords do not match.")
            return render_template("register.html")

        db = get_db()
        try:
            existing_users = db.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
            cursor = db.execute(
                "INSERT INTO users(email, password_hash) VALUES(?, ?)",
                (email, generate_password_hash(password)),
            )
            user_id = cursor.lastrowid

            # One-time migration: if this is the first account, claim legacy records
            # created before authentication so they do not become visible to every user.
            if existing_users == 0:
                db.execute("UPDATE patients SET user_id=? WHERE user_id IS NULL", (user_id,))

            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            db.close()
            flash("An account with that email already exists.")
            return render_template("register.html")

        db.close()
        flash("Account created. You can now log in.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        if not valid_csrf():
            flash("Invalid form token. Please try again.")
            return redirect(url_for("login"))

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        db.close()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_email"] = user["email"]
            session["csrf_token"] = secrets.token_urlsafe(32)
            session.permanent = True
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.")

    return render_template("login.html")


@app.post("/logout")
@login_required
def logout():
    if not valid_csrf():
        flash("Invalid form token. Please try again.")
        return redirect(url_for("dashboard"))
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def home():
    return render_template("index.html")


@app.route("/add", methods=["POST"])
@login_required
def add_patient():
    if not valid_csrf():
        flash("Invalid form token. Please try again.")
        return redirect(url_for("home"))

    try:
        data = request.form
        db = get_db()
        db.execute("""
            INSERT INTO patients(name, age, gender, disease, recovery_days, user_id)
            VALUES(?,?,?,?,?,?)
        """, (
            data["name"].strip(), data["age"], data["gender"].strip(),
            data["disease"].strip(), data["recovery"], session["user_id"]
        ))
        db.commit()
        db.close()
        flash("Patient added successfully.")
        return redirect(url_for("dashboard"))
    except Exception as exc:
        return f"Error: {exc}", 400


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    data = db.execute(
        "SELECT * FROM patients WHERE user_id=? ORDER BY id DESC",
        (session["user_id"],),
    ).fetchall()
    db.close()
    return render_template("dashboard.html", data=data, total=len(data))


@app.route("/chart")
@login_required
def chart():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM patients WHERE user_id=?",
        (session["user_id"],),
    ).fetchall()
    db.close()

    if not rows:
        return "No data available"

    df = pd.DataFrame([tuple(row) for row in rows])

    plt.figure(figsize=(7, 5))
    df[4].value_counts().plot(kind="bar", color="#4facfe", edgecolor="black")
    plt.title("Disease Distribution")
    plt.grid(axis="y")
    plt.tight_layout()
    plt.savefig("static/chart1.png")
    plt.close()

    plt.figure(figsize=(6, 6))
    df[3].value_counts().plot(kind="pie", autopct="%1.1f%%", startangle=90)
    plt.title("Gender Distribution")
    plt.ylabel("")
    plt.tight_layout()
    plt.savefig("static/chart2.png")
    plt.close()

    plt.figure(figsize=(7, 5))
    df[5].plot(kind="hist", bins=6, edgecolor="black")
    plt.title("Recovery Days Distribution")
    plt.grid()
    plt.tight_layout()
    plt.savefig("static/chart3.png")
    plt.close()

    return render_template("chart.html")


@app.post("/delete/<int:id>")
@login_required
def delete(id):
    if not valid_csrf():
        flash("Invalid form token. Please try again.")
        return redirect(url_for("dashboard"))

    db = get_db()
    db.execute("DELETE FROM patients WHERE id=? AND user_id=?", (id, session["user_id"]))
    db.commit()
    db.close()
    flash("Patient deleted.")
    return redirect(url_for("dashboard"))


@app.route("/edit/<int:id>")
@login_required
def edit(id):
    db = get_db()
    patient = db.execute(
        "SELECT * FROM patients WHERE id=? AND user_id=?",
        (id, session["user_id"]),
    ).fetchone()
    db.close()

    if patient is None:
        return "Patient not found", 404
    return render_template("edit.html", patient=patient)


@app.post("/update/<int:id>")
@login_required
def update(id):
    if not valid_csrf():
        flash("Invalid form token. Please try again.")
        return redirect(url_for("dashboard"))

    data = request.form
    db = get_db()
    cursor = db.execute("""
        UPDATE patients
        SET name=?, age=?, gender=?, disease=?, recovery_days=?
        WHERE id=? AND user_id=?
    """, (
        data["name"].strip(), data["age"], data["gender"].strip(),
        data["disease"].strip(), data["recovery"], id, session["user_id"]
    ))
    db.commit()
    db.close()

    if cursor.rowcount == 0:
        return "Patient not found", 404
    flash("Patient updated.")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(debug=True)
