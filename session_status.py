"""作者：Wangyuan；日期：2026-11-06。职责：仅从显式JSONL推导会话状态、时间与计数。"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import math
from pathlib import Path
import re
from typing import Any

MAX_BYTES = 2 * 1024 * 1024
MAX_EVENTS = 20000
ISO = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$')


def epoch(value: Any, timestamp_unit: str = 'seconds') -> float:
    """时间须明确时区或显式数值单位；不猜测本地时区。"""
    if timestamp_unit not in {'seconds', 'milliseconds'}:
        raise ValueError('时间单位须为seconds或milliseconds')
    if type(value) in (int, float) and math.isfinite(value):
        result = value / 1000 if timestamp_unit == 'milliseconds' else value
    elif isinstance(value, str) and ISO.fullmatch(value):
        if value[-1] != 'Z' and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
            raise ValueError('时区偏移无效')
        try: result = dt.datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
        except ValueError as exc: raise ValueError('时间戳无效') from exc
    else: raise ValueError('时间戳须为显式时区ISO或有限数值')
    if not 0 <= result < 253402300800: raise ValueError('时间戳超出范围')
    return result


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    """重复字段拒绝，避免状态字段被后值覆盖。"""
    result = {}
    for key, value in items:
        if key in result: raise ValueError('重复JSON字段')
        result[key] = value
    return result


def _json(text: str) -> Any:
    """只解码严格JSON，不执行输入内容。"""
    if not isinstance(text, str): raise ValueError('JSON参数须为字符串')
    def invalid(value: str) -> None: raise ValueError('非有限JSON数值')
    try: return json.loads(text, object_pairs_hook=_pairs, parse_constant=invalid)
    except (ValueError, RecursionError) as exc: raise ValueError('JSON无效') from exc


def load_events(path: str | Path) -> list[dict[str, Any]]:
    """读取唯一显式普通文件；不发现账号、目录或默认日志。"""
    path = Path(path)
    if not path.is_file(): raise ValueError('输入须为普通文件')
    with path.open('rb') as stream: data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES: raise ValueError('JSONL不可超过2MiB')
    try: lines = data.decode('utf-8-sig').splitlines()
    except UnicodeDecodeError as exc: raise ValueError('JSONL须为UTF-8') from exc
    events = [_json(line) for line in lines if line.strip()]
    if not events or len(events) > MAX_EVENTS or any(not isinstance(e, dict) for e in events):
        raise ValueError('JSONL须含1至20000个对象')
    return events


def _plan(value: Any) -> list[str]:
    """仅保留状态枚举，丢弃步骤文字。"""
    if not isinstance(value, list) or len(value) > 1000: raise ValueError('计划格式无效')
    result = []
    for item in value:
        if not isinstance(item, dict) or item.get('status', 'pending') not in {'pending', 'in_progress', 'completed', 'done'}:
            raise ValueError('计划状态无效')
        result.append(item.get('status', 'pending'))
    return result


def _has_text(parts: Any) -> bool:
    """只判断正文是否存在，绝不将正文带入结果。"""
    if isinstance(parts, str): return bool(parts.strip())
    return isinstance(parts, list) and any(isinstance(p, dict) and p.get('type') in {'text', 'input_text', 'output_text'} and isinstance(p.get('text'), str) and bool(p['text'].strip()) for p in parts)


def finish(task: dict[str, Any], now: float, fresh_seconds: int) -> dict[str, Any]:
    """按显式新鲜度标记过期；已结束仅代表最后一轮记录。"""
    stamp = task.pop('_stamp')
    plan = task.pop('_plan')
    task['age_seconds'] = int(now - stamp) if stamp is not None else None
    if task['state'] in {'active', 'waiting'} and (stamp is None or now - stamp > fresh_seconds): task['state'] = 'stale'
    task['updated_at'] = dt.datetime.fromtimestamp(stamp, dt.timezone.utc).isoformat().replace('+00:00', 'Z') if stamp is not None else None
    task['progress'] = {'completed': sum(x in {'completed', 'done'} for x in plan), 'total': len(plan)} if plan else None
    task['notice'] = '显式日志的最近记录推断；不是后台心跳、发送回执或整个项目验收。'
    return task


def summarize(events: list[dict[str, Any]], format: str, *, now: Any, fresh_seconds: int, timestamp_unit: str = 'seconds') -> dict[str, Any]:
    """复用两种来源的状态分支，输出白名单统计，不输出身份或正文。"""
    if format not in {'codex', 'chat'}: raise ValueError('格式须为codex或chat')
    if type(fresh_seconds) is not int or not 1 <= fresh_seconds <= 86400: raise ValueError('新鲜度须为1至86400秒')
    now = epoch(now, timestamp_unit)
    if not isinstance(events, list) or not 1 <= len(events) <= MAX_EVENTS or any(not isinstance(e, dict) for e in events): raise ValueError('事件须为非空对象数组')
    task = {'format': format, 'state': 'unknown', '_stamp': None, '_plan': [], 'tokens': None,
            'counts': {'records': len(events), 'recognized': 0, 'ignored': 0, 'future': 0, 'messages': 0, 'tool_calls': 0}}
    ordered = []
    for index, event in enumerate(events):
        typ = event.get('type')
        supported = typ in ({'event_msg', 'response_item', 'session_meta', 'turn_context'} if format == 'codex' else {'user', 'assistant', 'message', 'custom-title', 'model_change'})
        if not supported:
            task['counts']['ignored'] += 1; continue
        if typ in {'session_meta', 'turn_context', 'custom-title', 'model_change'}:
            # 无时间的兼容元数据可计数，已提供的时间必须通过同一校验。
            if 'timestamp' in event:
                stamp = epoch(event['timestamp'], timestamp_unit)
                if stamp > now:
                    task['counts']['future'] += 1
                    continue
            task['counts']['recognized'] += 1; continue
        stamp = epoch(event.get('timestamp'), timestamp_unit)
        if stamp > now: task['counts']['future'] += 1; continue
        ordered.append((stamp, index, event))
    for stamp, _, event in sorted(ordered):
        typ = event.get('type'); payload = event.get('payload') if format == 'codex' else event.get('message')
        if not isinstance(payload, dict): raise ValueError('事件payload/message须为对象')
        recognized = True
        if format == 'codex':
            kind = payload.get('type')
            if typ == 'event_msg' and kind in ('task_started', 'user_message'):
                task['state'] = 'active'; task['_plan'] = []; task['_stamp'] = stamp
                task['counts']['messages'] += kind == 'user_message'
            elif typ == 'event_msg' and kind == 'task_complete': task['state'] = 'ended'; task['_stamp'] = stamp
            elif typ == 'event_msg' and kind in ('turn_aborted', 'task_aborted'): task['state'] = 'stopped'; task['_stamp'] = stamp
            elif typ == 'response_item' and kind in ('function_call', 'custom_tool_call'):
                name = payload.get('name', '')
                if not isinstance(name, str): raise ValueError('工具名格式无效')
                task['state'] = 'waiting' if 'request_user_input' in name else 'active'; task['_stamp'] = stamp
                task['counts']['tool_calls'] += 1
                if name.endswith('update_plan'):
                    args = _json(payload.get('arguments', '{}'))
                    if not isinstance(args, dict): raise ValueError('计划参数须为对象')
                    task['_plan'] = _plan(args.get('plan', []))
            elif typ == 'response_item' and kind == 'message' and payload.get('role') == 'assistant' and payload.get('channel') in ('commentary', 'final'):
                task['counts']['messages'] += 1
                if _has_text(payload.get('content')):
                    task['_stamp'] = stamp; task['state'] = 'ended' if payload['channel'] == 'final' else 'active'
            elif typ == 'response_item' and kind in ('function_call_output', 'custom_tool_call_output'):
                task['_stamp'] = stamp
                if task['state'] == 'unknown': task['state'] = 'active'
            elif typ == 'event_msg' and kind == 'token_count':
                info = payload.get('info') or {}; usage = info.get('total_token_usage', {}) if isinstance(info, dict) else None
                if not isinstance(usage, dict): raise ValueError('用量格式无效')
                tokens = usage.get('total_tokens')
                if tokens is not None and (type(tokens) is not int or not 0 <= tokens <= 9007199254740991): raise ValueError('tokens须为非负安全整数')
                task['tokens'] = tokens
            else: recognized = False
        else:
            role = payload.get('role') or (typ if typ in ('assistant', 'user') else None)
            content = payload.get('content')
            if role == 'user':
                task['counts']['messages'] += 1
                if _has_text(content) and not any(isinstance(p, dict) and p.get('type') == 'tool_result' for p in (content if isinstance(content, list) else [])):
                    task['state'] = 'active'; task['_stamp'] = stamp
            elif role == 'assistant':
                task['counts']['messages'] += 1; task['_stamp'] = stamp; task['state'] = 'active'
                stop = payload.get('stop_reason') or payload.get('stopReason')
                if _has_text(content) and stop in ('end_turn', 'stop', 'stop_sequence'): task['state'] = 'ended'
                if event.get('isApiErrorMessage') or stop == 'error': task['state'] = 'error'
                for part in content if isinstance(content, list) else []:
                    if isinstance(part, dict) and part.get('type') in ('tool_use', 'toolCall'):
                        task['counts']['tool_calls'] += 1
                        if part.get('name') == 'TodoWrite':
                            args = part.get('input') or part.get('arguments') or {}
                            if not isinstance(args, dict): raise ValueError('计划参数须为对象')
                            task['_plan'] = _plan(args.get('todos', []))
            else: recognized = False
        task['counts']['recognized' if recognized else 'ignored'] += 1
    if not task['counts']['recognized'] and not task['counts']['future']: raise ValueError('未识别出指定格式的事件')
    return finish(task, now, fresh_seconds)


def main() -> None:
    """显式CLI只读一个文件，只向stdout输出摘要。"""
    parser = argparse.ArgumentParser(description='离线会话状态与计数，不输出正文')
    parser.add_argument('source', type=Path)
    parser.add_argument('--format', choices=['codex', 'chat'], required=True)
    parser.add_argument('--now', required=True)
    parser.add_argument('--fresh-seconds', type=int, required=True)
    parser.add_argument('--timestamp-unit', choices=['seconds', 'milliseconds'], default='seconds')
    args = parser.parse_args()
    try: result = summarize(load_events(args.source), args.format, now=args.now, fresh_seconds=args.fresh_seconds, timestamp_unit=args.timestamp_unit)
    except (OSError, ValueError) as exc: parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__': main()
