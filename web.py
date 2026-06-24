import json
import os
import time
import logging
import sqlite3
import requests
from datetime import datetime
from flask import Flask, render_template, request, redirect, jsonify
from healthcheck import check_service, init_db, insert_record

def time_ago(iso_str):
    if not iso_str:
        return '暂无'
    try:
        t = datetime.fromisoformat(iso_str)
        diff = datetime.now() - t
        seconds = int(diff.total_seconds())
        if seconds < 10:
            return '刚刚'
        if seconds < 60:
            return f'{seconds}秒前'
        if seconds < 3600:
            return f'{seconds // 60}分钟前'
        if seconds < 86400:
            return f'{seconds // 3600}小时前'
        return f'{seconds // 86400}天前'
    except:
        return iso_str[:19]

def llm_diagnose(name, msg, latency=0):
    """调用 LLM 生成故障诊断建议"""
    api_key = os.getenv('LLM_API_KEY')
    if not api_key:
        return ''
    url = os.getenv('LLM_API_URL', 'https://opencode.ai/zen/go/v1/chat/completions')
    model = os.getenv('LLM_MODEL', 'deepseek-v4-flash')
    system_prompt = '你是一名资深运维工程师。直接诊断，不要推理过程。'
    user_prompt = f'服务 "{name}" 返回{msg}，延迟{latency}ms。原因和修复建议（一句话）：'
    try:
        resp = requests.post(url, json={
            'model': model,
            'messages': [{'role': 'system', 'content': system_prompt},
                         {'role': 'user', 'content': user_prompt}],
            'max_tokens': 1024
        }, headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}, timeout=15)
        resp.raise_for_status()
        msg = resp.json()['choices'][0]['message']
        return (msg.get('content') or msg.get('reasoning_content') or '').strip()
    except Exception as e:
        logging.warning(f'LLM 诊断失败 ({name}): {e}')
        return ''

def calc_health_score(name, status, latency):
    """计算服务健康评分 0-100"""
    score = 100
    if status != 1:
        score -= 40
    if latency:
        if latency > 2000:
            score -= 25
        elif latency > 1000:
            score -= 15
        elif latency > 500:
            score -= 8
        elif latency > 200:
            score -= 3
    conn = sqlite3.connect('healthcheck.db')
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM (SELECT status FROM records WHERE name=? ORDER BY id DESC LIMIT 10) WHERE status=0', (name,))
    recent = cur.fetchone()[0]
    conn.close()
    score -= recent * 3
    return max(0, min(100, score))

def get_latest(status=None):
    conn = sqlite3.connect('healthcheck.db')
    cur = conn.cursor()
    sql = '''
        SELECT r.name, r.url, r.status, r.msg, r.time, r.latency, r.diagnosis
        FROM records r
        JOIN (SELECT name, MAX(id) as max_id FROM records GROUP BY name) t
        ON r.name = t.name AND r.id = t.max_id
    '''
    params = ()
    if status is not None:
        sql += ' WHERE r.status = ?'
        params = (status,)
    sql += ' ORDER BY r.status ASC, r.name ASC'
    cur.execute(sql, params)
    return cur.fetchall()

def get_summary():
    conn = sqlite3.connect('healthcheck.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status=1 THEN 1 ELSE 0 END) as ok,
            SUM(CASE WHEN status=0 THEN 1 ELSE 0 END) as fail
        FROM records
        WHERE id IN (SELECT MAX(id) FROM records GROUP BY name)
    ''')
    row = cur.fetchone()
    return {'total': row[0], 'ok': row[1] or 0, 'fail': row[2] or 0}


app = Flask(__name__)

@app.route('/')
def home():
    conn = sqlite3.connect('healthcheck.db')
    cur = conn.cursor()
    init_db(cur)
    conn.close()

    status = request.args.get('status')
    rows = get_latest(int(status) if status is not None else None)
    summary = get_summary()

    # 获取异常服务的诊断建议
    conn2 = sqlite3.connect('healthcheck.db')
    cur2 = conn2.cursor()
    cur2.execute('''
        SELECT r.name, r.url, r.status, r.msg, r.time, r.latency, r.diagnosis
        FROM records r
        JOIN (SELECT name, MAX(id) as max_id FROM records GROUP BY name) t
        ON r.name = t.name AND r.id = t.max_id
        WHERE r.status = 0
    ''')
    failed = cur2.fetchall()
    conn2.close()

    # 计算每个服务的健康评分
    scores = {}
    for r in rows:
        scores[r[0]] = calc_health_score(r[0], r[2], r[5])

    return render_template('index.html', rows=rows, summary=summary, time_ago=time_ago, failed=failed, scores=scores)

@app.route('/check')
def manual_check():
    with open('config.json', encoding='utf-8') as f:
        services = json.load(f)['services']
    conn = sqlite3.connect('healthcheck.db')
    cur = conn.cursor()
    init_db(cur)

    webhook_url = os.getenv('WEBHOOK_URL')
    for s in services:
        t0 = time.time()
        ok, msg = check_service(s)
        latency = int((time.time() - t0) * 1000)

        diagnosis = ''
        if not ok:
            diagnosis = llm_diagnose(s['name'], str(msg), latency)
            if webhook_url:
                text = f'{s["name"]}: 错误！\n诊断: {diagnosis}' if diagnosis else f'{s["name"]}: 错误！'
                requests.post(webhook_url, json={"msg_type": "text", "content": {"text": text}})

        insert_record(cur, s['name'], s['url'], ok, msg, latency, diagnosis)

    conn.commit()
    # 清理旧数据，每个服务只保留最近 100 条
    for s in services:
        cur.execute('DELETE FROM records WHERE name = ? AND id NOT IN (SELECT id FROM records WHERE name = ? ORDER BY id DESC LIMIT 100)', (s['name'], s['name']))
    conn.commit()
    return redirect('/')

import json as json_lib

@app.route('/api/services', methods=['POST'])
def add_service():
    data = request.get_json()
    name = data.get('name', '').strip()
    url = data.get('url', '').strip()
    if not name or not url:
        return jsonify({'success': False, 'error': '名称和URL不能为空'}), 400

    with open('config.json', encoding='utf-8') as f:
        config = json_lib.load(f)

    for s in config['services']:
        if s['name'] == name:
            s['url'] = url
            break
    else:
        config['services'].append({'name': name, 'url': url})

    with open('config.json', 'w', encoding='utf-8') as f:
        json_lib.dump(config, f, ensure_ascii=False, indent=4)

    # 对新服务执行一次检查
    t0 = time.time()
    ok, msg = check_service({'name': name, 'url': url})
    latency = int((time.time() - t0) * 1000)

    conn = sqlite3.connect('healthcheck.db')
    cur = conn.cursor()
    init_db(cur)
    diagnosis = ''
    if not ok:
        diagnosis = llm_diagnose(name, str(msg), latency)
    insert_record(cur, name, url, ok, msg, latency, diagnosis)
    conn.commit()
    cur.execute('DELETE FROM records WHERE name = ? AND id NOT IN (SELECT id FROM records WHERE name = ? ORDER BY id DESC LIMIT 100)', (name, name))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'name': name})

@app.route('/api/services/<name>', methods=['DELETE'])
def delete_service(name):
    with open('config.json', encoding='utf-8') as f:
        config = json_lib.load(f)
    config['services'] = [s for s in config['services'] if s['name'] != name]
    with open('config.json', 'w', encoding='utf-8') as f:
        json_lib.dump(config, f, ensure_ascii=False, indent=4)
    conn = sqlite3.connect('healthcheck.db')
    cur = conn.cursor()
    cur.execute('DELETE FROM records WHERE name = ?', (name,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/diagnosis')
def diagnosis():
    conn = sqlite3.connect('healthcheck.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT r.name, r.url, r.msg, r.time, r.diagnosis
        FROM records r
        JOIN (SELECT name, MAX(id) as max_id FROM records GROUP BY name) t
        ON r.name = t.name AND r.id = t.max_id
        WHERE r.status = 0
    ''')
    rows = cur.fetchall()
    conn.close()
    return render_template('diagnosis.html', rows=rows, time_ago=time_ago)

@app.route('/debug/env')
def debug_env():
    import os
    return jsonify({
        'LLM_API_KEY_set': bool(os.getenv('LLM_API_KEY')),
        'LLM_API_KEY_preview': os.getenv('LLM_API_KEY', '')[:8] + '...' if os.getenv('LLM_API_KEY') else None,
        'LLM_API_URL': os.getenv('LLM_API_URL', '(默认)'),
    })

@app.route('/api/history')
def api_history():
    conn = sqlite3.connect('healthcheck.db')
    cur = conn.cursor()
    cur.execute('SELECT DISTINCT name FROM records')
    names = [r[0] for r in cur.fetchall()]
    data = {}
    for name in names:
        cur.execute('SELECT status, latency, time FROM records WHERE name = ? ORDER BY id ASC', (name,))
        records = cur.fetchall()
        data[name] = [{'status': r[0], 'latency': r[1], 'time': r[2][:16] if r[2] else ''} for r in records]
    conn.close()
    return jsonify(data)

if __name__ == '__main__':
    app.run(port=4000, debug=True)
