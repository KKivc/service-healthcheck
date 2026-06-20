'''
1. 读取一个 config.json 配置文件，里面写若干个要监控的服务（名称 + URL）
2. 对每个服务发 HTTP 请求，检查状态码是不是 200
3. 记录每次检查的结果到日志文件，带时间戳
4. 用 --status 参数查看所有服务的检查结果
'''

import json
import requests
import logging
import argparse
import time


last_status = {}

def check_service(service):
     
     """
     检查单个服务
     返回：是否成功、状态码/错误信息
     """
     

     try:
        r = requests.get(service['url'])
        if r.status_code == 200:
                return True, r.status_code
        else:
                return False, r.status_code
     except Exception as e:          # 若url错误没有状态码
        return False, str(e)


if __name__ == '__main__':
 
    logging.basicConfig(
        level=logging.INFO,
        filename='./healthcheck.log',
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

            for s in services:          # 字典
                last = last_status.get(s["name"])
                status,msg = check_service(s)
                if last is None or last != status:      # 若上一次是空的/状态发生改变
                    last_status[s['name']] = status  # 记录当前状态

                    if status :
                        logging.info(f'{s["name"]}: {msg}')
                    else:
                        logging.error(f'{s["name"]}: {msg}')

                        if args.webhook:
                            requests.post(args.webhook, json={"msg_type": "text", "content": {"text": f'{s["name"]}: 错误！'}})

            if args.interval:
                time.sleep(args.interval)
            else:
                break
