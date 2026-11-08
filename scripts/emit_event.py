#!/usr/bin/env python3
"""Send an observation event to this local dashboard. Does not call an AI model."""
import argparse
import json
import urllib.error
import urllib.request

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--port', type=int, default=8766)
p.add_argument('--agent', default='CODEX')
p.add_argument('--type', default='started', choices=['started','progress','completed','error','handoff','heartbeat'])
p.add_argument('--task', default='本地适配器联调')
p.add_argument('--message', default='测试事件：不代表真实模型调用')
p.add_argument('--progress', type=float)
p.add_argument('--tokens-delta', type=int, default=0)
args = p.parse_args()
body = dict(agent=args.agent, type=args.type, task=args.task, message=args.message, tokens_delta=args.tokens_delta)
if args.progress is not None:
    body['progress'] = args.progress
request = urllib.request.Request(f'http://127.0.0.1:{args.port}/api/ingest', data=json.dumps(body).encode(), headers={'Content-Type':'application/json'})
try:
    with urllib.request.urlopen(request, timeout=5) as response:
        state = json.load(response)
    print(json.dumps({'ok':True, 'mode':state['mode'], 'seq':state['seq'], 'last_event':state['events'][-1]}, ensure_ascii=False, indent=2))
except urllib.error.HTTPError as error:
    print(error.read().decode())
    raise SystemExit(1)
except urllib.error.URLError as error:
    print(f'无法连接本地服务：{error.reason}')
    raise SystemExit(1)
