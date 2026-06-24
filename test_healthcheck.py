import sqlite3
from healthcheck import check_service, init_db, insert_record
from unittest.mock import patch, Mock

def test_success():
    with patch('healthcheck.requests.get') as fake_get:
        fake_get.return_value = Mock(status_code = 200)
        s, r = check_service({'name': 'abc', 'url': 'http://www.abc.com'})
        assert s == True and r == 200

def test_error():
    with patch('healthcheck.requests.get') as fake_get:
        fake_get.return_value = Mock(status_code = 500)
        s, r = check_service({'name': 'abc', 'url': 'http://www.abc.com'})
        assert s == False and r == 500

def test_exception():
    with patch('healthcheck.requests.get') as fake_get:
        fake_get.side_effect = Exception('连接错误')
        s, r = check_service({'name': 'abc', 'url': 'http://www.abc.com'})
        assert s == False and r == '连接错误'

def test_init_db():
    conn = sqlite3.connect(':memory:')      # :memory: 一个保留关键词,创建一个临时数据库
    cur = conn.cursor()
    init_db(cur)
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='records'")
    result = cur.fetchone()     # 取第一行信息
    assert result[0] == 'records'

def test_insert_records():
    conn = sqlite3.connect(':memory:')
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY, name VARCHAR(10), url tinytext, status TINYINT, msg TINYTEXT, time DATE, latency INTEGER)')
    insert_record(cur, name='abc', url='http', status=1, msg=200, latency=45)
    cur.execute("select * from records")
    result = cur.fetchall()
    assert result[0][1] == 'abc'