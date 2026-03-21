from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sqlite3

app = Flask(__name__)

# -------------------------------
# Database Function (SAFE)
# -------------------------------
def get_db():
    return sqlite3.connect('database.db')

# Create table (runs once)
db = get_db()
cursor = db.cursor()
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
db.close()

# -------------------------------
# Home
# -------------------------------
@app.route('/')
def home():
    return render_template("index.html")

# -------------------------------
# Add Patient
# -------------------------------
@app.route('/add', methods=['POST'])
def add_patient():
    try:
        data = request.form
        db = get_db()
        cursor = db.cursor()

        cursor.execute("""
        INSERT INTO patients(name, age, gender, disease, recovery_days)
        VALUES(?,?,?,?,?)
        """, (data['name'], data['age'], data['gender'], data['disease'], data['recovery']))

        db.commit()
        db.close()

        return redirect(url_for('dashboard'))

    except Exception as e:
        return f"Error: {e}"

# -------------------------------
# Dashboard
# -------------------------------
@app.route('/dashboard')
def dashboard():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM patients")
    data = cursor.fetchall()

    db.close()

    total = len(data)
    return render_template("dashboard.html", data=data, total=total)

# -------------------------------
# Charts
# -------------------------------
@app.route('/chart')
def chart():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM patients")
    rows = cursor.fetchall()

    db.close()

    if len(rows) == 0:
        return "No data available"

    df = pd.DataFrame(rows)

    # Chart 1
    plt.figure(figsize=(7,5))
    df[4].value_counts().plot(kind='bar', color='#4facfe', edgecolor='black')
    plt.title("📊 Disease Distribution")
    plt.grid(axis='y')
    plt.tight_layout()
    plt.savefig('static/chart1.png')
    plt.close()

    # Chart 2
    plt.figure(figsize=(6,6))
    df[3].value_counts().plot(
        kind='pie',
        autopct='%1.1f%%',
        colors=['#ff6b6b','#4dabf7'],
        startangle=90
    )
    plt.title("👥 Gender Distribution")
    plt.ylabel("")
    plt.tight_layout()
    plt.savefig('static/chart2.png')
    plt.close()

    # Chart 3
    plt.figure(figsize=(7,5))
    df[5].plot(kind='hist', bins=6, color='#51cf66', edgecolor='black')
    plt.title("⏱ Recovery Days Distribution")
    plt.grid()
    plt.tight_layout()
    plt.savefig('static/chart3.png')
    plt.close()

    return render_template("chart.html")

# -------------------------------
# Delete
# -------------------------------
@app.route('/delete/<int:id>')
def delete(id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM patients WHERE id=?", (id,))
    db.commit()
    db.close()

    return redirect(url_for('dashboard'))

# -------------------------------
# Edit
# -------------------------------
@app.route('/edit/<int:id>')
def edit(id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM patients WHERE id=?", (id,))
    data = cursor.fetchone()

    db.close()

    return render_template("edit.html", patient=data)

# -------------------------------
# Update
# -------------------------------
@app.route('/update/<int:id>', methods=['POST'])
def update(id):
    data = request.form
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
    UPDATE patients 
    SET name=?, age=?, gender=?, disease=?, recovery_days=?
    WHERE id=?
    """, (data['name'], data['age'], data['gender'], data['disease'], data['recovery'], id))

    db.commit()
    db.close()

    return redirect(url_for('dashboard'))

# -------------------------------
# Run
# -------------------------------
if __name__ == "__main__":
    app.run(debug=True)
