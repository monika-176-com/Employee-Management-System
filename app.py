# app.py
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect,url_for,flash, session, send_file
from flask_mysqldb import MySQL
import pandas as pd
import matplotlib.pyplot as plt
from reportlab.pdfgen import canvas
import io
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'selfish@2006'

# MySQL Config
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'selfish@2006'
app.config['MYSQL_DB'] = 'employee_db'

mysql = MySQL(app)

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        cur = mysql.connection.cursor()
        username = request.form['username']
        password = request.form['password']
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
        user = cur.fetchone()
        cur.close()
        if user:
            session['username'] = username
            session['role'] = user[3]
            return redirect('/dashboard')
        else:
            return "Invalid Credentials"
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect('/')
    return render_template('dashboard.html', role=session['role'])

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        cur = mysql.connection.cursor()
        try:
            cur.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                        (username, password, role))
            mysql.connection.commit()
        except Exception as e:
            cur.close()
            return f"Error: {str(e)}"
        cur.close()
        return redirect('/')
    return render_template('register.html')


@app.route('/employees')
def employees():
    if 'username' not in session:
        return redirect('/')
    if session['role'] not in ['admin', 'hr']:
        return "Access denied. You are not authorized to view this page."
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM employees")
    data = cur.fetchall()
    cur.close()
    return render_template('employees.html', employees=data)


@app.route('/export/excel')
def export_excel():
    if 'username' not in session or session['role'] not in ['admin', 'hr']:
        return "Access denied. You are not authorized to download this file."
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM employees")
    rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=['ID', 'Name', 'Department', 'Salary'])
    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return send_file(output, download_name="employees.xlsx", as_attachment=True)


@app.route('/export/pdf')
def export_pdf():
    if 'username' not in session or session['role'] not in ['admin', 'hr']:
        return "Access denied. You are not authorized to download this file."
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM employees")
    rows = cur.fetchall()
    cur.close()

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)
    p.setFont("Helvetica", 12)
    p.drawString(100, 800, "Employee Report")
    y = 780
    for row in rows:
        p.drawString(50, y, f"{row[0]} - {row[1]} - {row[2]} - {row[3]}")
        y -= 20
    p.save()
    buffer.seek(0)
    return send_file(buffer, download_name='employees.pdf', as_attachment=True)


import os

@app.route('/salary_chart')
def salary_chart():
    if 'username' not in session or session['role'] not in ['admin', 'hr']:
        return "Access denied. You are not authorized to view this chart."
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT name, salary FROM employees")
    data = cursor.fetchall()
    cursor.close()

    df = pd.DataFrame(data, columns=['Name', 'Salary'])

    # Create static folder if it doesn't exist
    static_dir = os.path.join(app.root_path, 'static')
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)

    # Plot and save
    plt.figure(figsize=(10, 6))
    plt.bar(df['Name'], df['Salary'], color='skyblue')
    plt.title('Employee Salary Chart')
    plt.xlabel('Employee')
    plt.ylabel('Salary')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    chart_path = os.path.join(static_dir, 'salary_chart.png')
    plt.savefig(chart_path)
    plt.close()

    return render_template('salary_chart.html', chart_url='static/salary_chart.png')

@app.route('/plot')
def plot_salary_chart():
    if 'username' not in session or session['role'] not in ['admin', 'hr']:
        return "Access denied. Only admin or HR can mark attendance."
    cur = mysql.connection.cursor()
    cur.execute("SELECT name, salary FROM employees")
    data = cur.fetchall()
    cur.close()
    names = [row[0] for row in data]
    salaries = [row[1] for row in data]

    # ✅ Ensure static folder exists
    static_dir = os.path.join(app.root_path, 'static')
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)

    plt.figure(figsize=(10, 6))
    plt.bar(names, salaries, color='skyblue')
    plt.xlabel('Employee')
    plt.ylabel('Salary')
    plt.title('Employee Salary Chart')
    plt.tight_layout()

    # ✅ Save in static folder
    chart_path = os.path.join(static_dir, 'salary_chart.png')
    plt.savefig(chart_path)
    plt.close()

    return render_template('dashboard.html', chart='salary_chart.png', role=session['role'])


@app.route('/attendance', methods=['GET', 'POST'])
def mark_attendance():
    if 'username' not in session or session['role'] not in ['admin', 'hr']:
        return "Access denied. Only admin or HR can mark attendance."
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        date = request.form['date']
        for key, status in request.form.items():
            if key.startswith('emp_'):
                emp_id = key.split('_')[1]
                cur.execute("INSERT INTO attendance (employee_id, date, status) VALUES (%s, %s, %s)",
                            (emp_id, date, status))
        mysql.connection.commit()
        cur.close()
        return "Attendance marked!"
    cur.execute("SELECT id, name FROM employees")
    employees = cur.fetchall()
    cur.close()
    return render_template('attendance.html', employees=employees)
@app.route('/attendance/view')
def view_attendance():
    if 'username' not in session:
        return redirect('/')
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT e.name, a.date, a.status 
        FROM attendance a JOIN employees e ON a.employee_id = e.id 
        ORDER BY a.date DESC
    """)
    logs = cur.fetchall()
    return render_template('attendance_logs.html', logs=logs)


if __name__ == '__main__':
    app.run(debug=True)
