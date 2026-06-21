import sqlite3
from flask import Flask, render_template

def query_db():
    conn = sqlite3.connect('healthcheck.db')
    cur = conn.cursor()
    cur.execute('select * from records')
    rows = cur.fetchall()
    return rows

app = Flask(__name__)
@app.route('/')
def home():
    rows = query_db()
    return render_template('index.html', rows=rows)

app.run(port=5000)
