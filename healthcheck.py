'''
1. 读取一个 config.json 配置文件，里面写若干个要监控的服务（名称 + URL）
2. 对每个服务发 HTTP 请求，检查状态码是不是 200
3. 记录每次检查的结果到日志文件，带时间戳
4. 用 --status 参数查看最近一次所有服务的检查结果
'''

import json
import requests
import logging
import argparse
import time

logging.basicConfig(
    level=logging.INFO,
    
    format='%(asctime)s - %(message)s'
)

parser = argparse.ArgumentParser()
parser.add_argument('--status', action='store_true')
parser.add_argument('--interval', type=int)
parser.add_argument('--webhook', type=str)
args = parser.parse_args()

if args.status:
        with open('./healthcheck.log', 'r', encoding='utf-8') as f:
            content = f.read()
            print(content)
            exit()    

while True:
    
    with open('./config.json', 'r', encoding = 'utf-8') as f:
        content = f.read()
        config = json.loads(content)    # 字典
        services = config['services']   # 列表

        try:

            for s in services:              # s:字典
                r = requests.get(s['url'])

                if args.webhook:

                    if r.status_code != 200:
                        requests.post(args.webhook, json={"msg_type": "text", "content": {"text": f'{s["name"]}: 错误！'}})
                logging.info(f'{s["name"]}: {r.status_code}')
        except Exception:
            if args.webhook:
                logging.error(f'{s["name"]} ')
                requests.post(args.webhook, json={"msg_type": "text", "content": {"text": f'{s["name"]}: 错误！'}})
    if args.interval:
        time.sleep(args.interval)
    else:
        break

