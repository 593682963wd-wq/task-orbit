#!/usr/bin/env python3
"""作者：Wangyuan；日期：2026-10-29。职责：合成演示与显式任务事件观察，不调用模型。"""
import argparse
import copy
import json
import math
import os
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
AGENTS = [
    ('PILOT', '任务指挥', '#78f4d0', '拆解目标 · 调度协作', 0, 8),
    ('SCOUT', '情报侦察', '#e9bc71', '检索来源 · 交叉核验', 3, 18),
    ('CODEX', '代码工程', '#78b5ff', '构建逻辑 · 实现接口', 11, 35),
    ('FORGE', '界面铸造', '#b6a0ff', '视觉构建 · 交互打磨', 15, 38),
    ('SENTINEL', '质量哨兵', '#e6ec98', '检查边界 · 验证结果', 30, 47),
    ('SCRIBE', '知识记录', '#f39aba', '整理结论 · 编写文档', 39, 54),
    ('RELAY', '集成中继', '#71d9ec', '连接模块 · 校验事件', 46, 58),
    ('ARCHIVE', '成果归档', '#c1cedd', '汇总产物 · 生成快照', 54, 64),
]
SCENARIOS = {
    'build': ['拆解需求与验收边界', '收集公开技术资料', '实现核心数据与接口', '构建响应式操作界面', '执行功能与边界检查', '编写使用说明与差距', '检查模块集成', '汇总本地演示产物'],
    'research': ['制定研究问题', '检索公开原始来源', '整理结构化证据', '绘制研究关系视图', '交叉核对引用与结论', '撰写研究简报', '合并结论与引用', '归档简报与来源'],
    'incident': ['划定排查范围', '收集可用故障线索', '复现并定位问题', '制作状态观察界面', '验证修复与回归', '记录原因与处理步骤', '校验恢复状态', '整理故障复盘'],
}


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class State:
    def __init__(self):
        self.lock = threading.RLock()
        self.seq = 0
        self.mode = 'demo'
        self.speed = 1
        self.paused = False
        self.reset('构建下一代 Agent 控制中心', 'build', initial=19)

    def fresh_agents(self):
        self.agents = [dict(id=a[0], role=a[1], color=a[2], description=a[3],
                            status='idle', progress=0, task='等待任务', tokens=0,
                            last_seen=None) for a in AGENTS]

    def event(self, agent, kind, message, source):
        self.seq += 1
        self.events.append(dict(seq=self.seq, at=stamp(), agent=agent,
                                type=kind, message=message, source=source))
        self.events = self.events[-180:]

    def reset(self, title, scenario, initial=0):
        with self.lock:
            self.mode, self.paused = 'demo', False
            self.elapsed, self.scenario, self.title = initial, scenario, title
            self.started_at = stamp()
            self.events = []
            self.fresh_agents()
            self.event('PILOT', 'started', f'演示任务已建立：{title}', 'demo')
            self.update_demo()

    def update_demo(self):
        for i, agent in enumerate(self.agents):
            start, end = AGENTS[i][4:]
            p = max(0, min(100, int((self.elapsed - start) / (end - start) * 100)))
            status = 'done' if p == 100 else ('working' if self.elapsed >= start else 'idle')
            if status != agent['status']:
                kind = 'completed' if status == 'done' else 'started'
                self.event(agent['id'], kind,
                           ('完成：' if status == 'done' else '开始：') + SCENARIOS[self.scenario][i], 'demo')
                if status == 'working' and i:
                    self.event(AGENTS[i-1][0], 'handoff', f'协作交接 → {agent["id"]}', 'demo')
            agent.update(status=status, progress=p, task=SCENARIOS[self.scenario][i],
                         tokens=int(p * (12 + i * 4.5)), last_seen=stamp() if status != 'idle' else None)

    def tick(self, delta):
        with self.lock:
            if self.mode == 'demo' and not self.paused and self.elapsed < 64:
                self.elapsed = min(64, self.elapsed + delta * self.speed)
                self.update_demo()

    def snapshot(self):
        with self.lock:
            agents = copy.deepcopy(self.agents)
            for a in agents:
                if self.mode == 'live' and a['last_seen'] and a['status'] == 'working':
                    seen = datetime.fromisoformat(a['last_seen']).timestamp()
                    if time.time() - seen > 20:
                        a['status'] = 'stale'
            done = sum(a['status'] == 'done' for a in agents)
            return dict(mode=self.mode, paused=self.paused, speed=self.speed,
                        title=self.title, scenario=self.scenario, elapsed=round(self.elapsed, 1),
                        started_at=self.started_at, now=stamp(), seq=self.seq,
                        agents=agents, events=copy.deepcopy(self.events),
                        metrics=dict(tokens=sum(a['tokens'] for a in agents),
                                     active=sum(a['status'] == 'working' for a in agents),
                                     completed=done, progress=round(sum(a['progress'] for a in agents)/8),
                                     handoffs=sum(e['type'] == 'handoff' for e in self.events)))

    def control(self, body):
        if 'mode' in body and body['mode'] not in ('demo', 'live'):
            raise ValueError('mode 必须为 demo 或 live')
        if 'speed' in body and (type(body['speed']) not in (int, float) or body['speed'] not in (0.5, 1, 2)):
            raise ValueError('speed 支持 0.5、1、2')
        if 'paused' in body and (body.get('mode', self.mode) != 'demo' or type(body['paused']) is not bool):
            raise ValueError('只有演示模式支持 paused 布尔值')
        with self.lock:
            if 'mode' in body:
                if body['mode'] not in ('demo', 'live'):
                    raise ValueError('mode 必须为 demo 或 live')
                if body['mode'] != self.mode:
                    if body['mode'] == 'live':
                        self.mode, self.paused, self.elapsed = 'live', False, 0
                        self.title, self.started_at = '等待外部 Agent 事件', stamp()
                        self.events = []
                        self.fresh_agents()
                    else:
                        self.reset('构建下一代 Agent 控制中心', 'build')
            if 'paused' in body:
                if self.mode != 'demo' or not isinstance(body['paused'], bool):
                    raise ValueError('只有演示模式支持 paused 布尔值')
                self.paused = body['paused']
            if 'speed' in body:
                if body['speed'] not in (0.5, 1, 2) or isinstance(body['speed'], bool):
                    raise ValueError('speed 支持 0.5、1、2')
                self.speed = body['speed']

    def ingest(self, body):
        # Validate the whole event before mutating state.
        ident, kind = body.get('agent'), body.get('type')
        if ident not in [a[0] for a in AGENTS]:
            raise ValueError('未知 agent；请使用既有席位 ID')
        if kind not in ('started', 'progress', 'completed', 'error', 'handoff', 'heartbeat'):
            raise ValueError('不支持的事件类型')
        for key, limit in [('message', 400), ('task', 160)]:
            if key in body and (not isinstance(body[key], str) or len(body[key]) > limit):
                raise ValueError(f'{key} 必须为不超过 {limit} 字的文本')
        p = body.get('progress')
        if p is not None and (type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 100):
            raise ValueError('progress 必须为 0 到 100 的有限数字')
        tokens = body.get('tokens_delta', 0)
        if type(tokens) is not int or not 0 <= tokens <= 10_000_000:
            raise ValueError('tokens_delta 必须为 0 到 10000000 的整数')
        with self.lock:
            if self.mode != 'live':
                raise ValueError('请先切换外部模式；演示与外部事件不能混用')
            agent = next(a for a in self.agents if a['id'] == ident)
            if kind == 'started':
                agent.update(status='working', progress=0)
            elif kind == 'progress':
                agent['status'] = 'working'
            elif kind == 'completed':
                agent.update(status='done', progress=100)
            elif kind == 'error':
                agent['status'] = 'error'
            if p is not None and kind != 'completed':
                agent['progress'] = round(p)
            if 'task' in body:
                agent['task'] = body['task']
                self.title = body['task'] or self.title
            agent['tokens'] += tokens
            agent['last_seen'] = stamp()
            self.event(ident, kind, body.get('message') or f'{ident} · {kind}', 'external')


STATE = State()


def origin_key(value):
    """规范化完整HTTP源，默认端口等价，路径与用户信息均拒绝。"""
    try:
        parsed = urlparse(value)
        if (parsed.scheme not in {'http', 'https'} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in {'', '/'} or parsed.params or parsed.query or parsed.fragment):
            return None
        port = parsed.port
        host = parsed.hostname.lower()
        host = f'[{host}]' if ':' in host else host
        if port is not None and port != {'http': 80, 'https': 443}[parsed.scheme]:
            host += f':{port}'
        return f'{parsed.scheme}://{host}'
    except (TypeError, ValueError):
        return None


class Handler(BaseHTTPRequestHandler):
    server_version = 'NeuralStarRing/1.0'

    def log_message(self, fmt, *args):
        pass

    def send(self, code, payload, content_type='application/json; charset=utf-8'):
        data = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)

    def allowed(self):
        port = self.server.server_address[1]
        hosts = (f'127.0.0.1:{port}', f'localhost:{port}', *filter(None, os.environ.get('ALLOWED_HOSTS', '').split(',')))
        origins = {origin_key(f'http://{h.strip()}') for h in hosts}
        origins.discard(None)
        if origin_key('http://' + self.headers.get('Host', '')) not in origins:
            self.send(403, {'error': '仅接受本机 Host'})
            return False
        origin = self.headers.get('Origin')
        public_origin = os.environ.get('PUBLIC_ORIGIN')
        if public_origin:
            configured = origin_key(public_origin)
            if not configured:
                self.send(500, {'error': 'PUBLIC_ORIGIN 必须是完整HTTP源地址'})
                return False
            origins.add(configured)
        if origin and origin_key(origin) not in origins:
            self.send(403, {'error': '仅接受本地同源请求'})
            return False
        return True

    def do_GET(self):
        if not self.allowed():
            return
        path = urlparse(self.path).path
        if path == '/healthz':
            return self.send(200, dict(status='ok', app='neural-star-ring', model_calls=False))
        if path in ('/api/state', '/api/export'):
            return self.send(200, STATE.snapshot())
        names = {'/': 'index.html', '/style.css': 'style.css', '/app.js': 'app.js', '/ring.js': 'ring.js'}
        if path == '/favicon.ico':
            return self.send(204, b'', 'image/x-icon')
        if path not in names:
            return self.send(404, {'error': '页面不存在'})
        file = ROOT / 'static' / names[path]
        types = {'.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript'}
        self.send(200, file.read_bytes(), types[file.suffix] + '; charset=utf-8')

    def do_POST(self):
        if not self.allowed():
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 8192:
                return self.send(413, {'error': '请求需为 1 到 8192 字节'})
            if self.headers.get_content_type() != 'application/json':
                return self.send(415, {'error': '需要 application/json'})
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError('JSON 必须为对象')
            path = urlparse(self.path).path
            if path == '/api/mission':
                title, scenario = body.get('title'), body.get('scenario', 'build')
                if not isinstance(title, str) or not title.strip() or len(title) > 100:
                    raise ValueError('任务标题需为 1 到 100 字')
                if not isinstance(scenario, str) or scenario not in SCENARIOS:
                    raise ValueError('未知演示场景')
                STATE.reset(title.strip(), scenario)
            elif path == '/api/control':
                STATE.control(body)
            elif path == '/api/ingest':
                STATE.ingest(body)
            else:
                return self.send(404, {'error': '接口不存在'})
            self.send(200, STATE.snapshot())
        except (ValueError, TypeError, UnicodeError) as e:
            self.send(400, {'error': str(e)})


def run(port: int, host: str = '127.0.0.1') -> None:
    """运行显式配置的服务，不操纵桌面。"""
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    stop = threading.Event()

    def clock():
        previous = time.monotonic()
        while not stop.wait(0.25):
            now = time.monotonic()
            STATE.tick(now - previous)
            previous = now

    threading.Thread(target=clock, daemon=True).start()
    print(f'任务事件星环  http://127.0.0.1:{port}', flush=True)
    print('本机演示，未连接模型。Ctrl+C 停止。', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', 8766)))
    parser.add_argument('--host', default=os.environ.get('HOST', '127.0.0.1'))
    args = parser.parse_args()
    run(args.port, args.host)
