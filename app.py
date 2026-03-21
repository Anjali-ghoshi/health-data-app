from flask import Flask, render_template, request, redirect, url_for
import mysql.connector
import pandas as pd
import matplotlib

# Fix for matplotlib error in Flask
matplotlib.use('Agg')
import matplotlib.pyplot as plt

app = Flask(__name__)

# Database connection
import sqlite3

db = sqlite3.connect('database.db', check_same_thread=False)
cursor = db.cursor()

# Create table if not exists
cursor.execute('''
CREATE TABLE IF NOT EXISTS patients(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    age INTEGER,
    gender TEXT,
    disease TEXT,
    recovery_days INTEGER
)
''')

db.commit()

# Home page
@app.route('/')
def home():
    return render_template("index.html")

# Add patient
@app.route('/add', methods=['POST'])
def add_patient():
    try:
        data = request.form
        cursor = db.cursor()

        cursor.execute("""
        INSERT INTO patients(name, age, gender, disease, recovery_days)
        VALUES(?,?,?,?,?)
        """, (data['name'], data['age'], data['gender'], data['disease'], data['recovery']))

        db.commit()
        cursor.close()

        return redirect(url_for('dashboard'))

    except Exception as e:
        return f"Error: {e}"

# Dashboard
@app.route('/dashboard')
def dashboard():
    cursor = db.cursor()
    cursor.execute("SELECT * FROM patients")
    data = cursor.fetchall()
    cursor.close()

    total = len(data)
    return render_template("dashboard.html", data=data, total=total)

# Charts (FIXED)
@app.route('/chart')
def chart():
    cursor = db.cursor()
    cursor.execute("SELECT * FROM patients")
    rows = cursor.fetchall()
    cursor.close()

    if len(rows) == 0:
        return "No data available"

    df = pd.DataFrame(rows)

    # -------------------------------
    # Chart 1: Disease Distribution
    # -------------------------------
    plt.figure(figsize=(7,5))
    df[4].value_counts().plot(
        kind='bar',
        color='#4facfe',
        edgecolor='black'
    )
    plt.title("📊 Disease Distribution", fontsize=14)
    plt.xlabel("Disease")
    plt.ylabel("Number of Patients")
    plt.xticks(rotation=30)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig('static/chart1.png')
    plt.close()

    # -------------------------------
    # Chart 2: Gender Distribution
    # -------------------------------
    plt.figure(figsize=(6,6))
    df[3].value_counts().plot(
        kind='pie',
        autopct='%1.1f%%',
        colors=['#ff6b6b','#4dabf7'],
        startangle=90,
        shadow=True
    )
    plt.title("👥 Gender Distribution", fontsize=14)
    plt.ylabel("")
    plt.tight_layout()
    plt.savefig('static/chart2.png')
    plt.close()

    # -------------------------------
    # Chart 3: Recovery Days
    # -------------------------------
    plt.figure(figsize=(7,5))
    df[5].plot(
        kind='hist',
        bins=6,
        color='#51cf66',
        edgecolor='black'
    )
    plt.title("⏱ Recovery Days Distribution", fontsize=14)
    plt.xlabel("Days")
    plt.ylabel("Frequency")
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig('static/chart3.png')
    plt.close()

    return render_template("chart.html")
# Delete
@app.route('/delete/<int:id>')
def delete(id):
    cursor = db.cursor()
    cursor.execute("DELETE FROM patients WHERE id=?", (id,))
    db.commit()
    cursor.close()

    return redirect(url_for('dashboard'))

# Edit
@app.route('/edit/<int:id>')
def edit(id):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM patients WHERE id=?", (id,))
    data = cursor.fetchone()
    cursor.close()

    return render_template("edit.html", patient=data)

# Update
@app.route('/update/<int:id>', methods=['POST'])
def update(id):
    data = request.form
    cursor = db.cursor()

    cursor.execute("""
    UPDATE patients 
    SET name=?, age=?, gender=?, disease=?, recovery_days=?
    WHERE id=?
    """, (data['name'], data['age'], data['gender'], data['disease'], data['recovery'], id))

    db.commit()
    cursor.close()

    return redirect(url_for('dashboard'))

# Run app
if __name__ == "__main__":
    app.run(debug=True)
