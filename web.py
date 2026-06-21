import sqlite3
from flask import Flask, render_template, request

def query_db(status):
    conn = sqlite3.connect('healthcheck.db')
    cur = conn.cursor()
    if status is not None:
        cur.execute('select * from records where status = ?', (status,))
    else:  
        cur.execute('select * from records')
    rows = cur.fetchall()
    return rows

app = Flask(__name__)
@app.route('/')
def home():
    status = request.args.get('status')
    rows = query_db(int(status) if status is not None else None)
    return render_template('index.html', rows=rows)

if __name__ == '__main__':
    app.run(port=5000)
