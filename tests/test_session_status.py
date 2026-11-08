"""作者：Wangyuan；日期：2026-11-06。职责：合成日志验证状态、时间、计数及正文剥离。"""
import json
from pathlib import Path
import tempfile
import unittest
from session_status import summarize, load_events, epoch

NOW='2030-01-01T00:10:00Z'
def event(kind, minute=9, **fields):
    return {'timestamp':f'2030-01-01T00:{minute:02}:00Z','type':'event_msg','payload':{'type':kind,**fields}}
def response(kind, minute=9, **fields):
    return {**event(kind,minute,**fields),'type':'response_item'}
def run(events, format='codex', now=NOW):
    return summarize(events,format,now=now,fresh_seconds=180)

class SessionStatusTests(unittest.TestCase):
    def test_codex_lifecycle_and_abort(self):
        self.assertEqual(run([event('task_started'),event('task_complete')])['state'],'ended')
        self.assertEqual(run([event('task_started'),event('turn_aborted')])['state'],'stopped')
    def test_waiting_stale_and_fresh_boundary(self):
        self.assertEqual(run([response('function_call',name='request_user_input')])['state'],'waiting')
        self.assertEqual(run([event('task_started',6)])['state'],'stale')
        self.assertEqual(run([event('task_started',7)])['state'],'active')
    def test_no_private_text_model_name_path_or_arguments(self):
        secret='SYNTHETIC_PRIVATE_SENTINEL'
        events=[event('task_started'),response('function_call',name=secret,arguments=secret),
          response('message',role='assistant',channel='final',content=[{'type':'output_text','text':secret}])]
        result=run(events);self.assertEqual(result['counts']['tool_calls'],1)
        self.assertEqual(result['state'],'ended');self.assertNotIn(secret,json.dumps(result))
    def test_plan_counts_and_latest_usage_only(self):
        result=run([response('function_call',name='update_plan',arguments=json.dumps({'plan':[{'step':'SYNTHETIC','status':'completed'},{'status':'pending'}]})),
          event('token_count',info={'total_token_usage':{'total_tokens':10}})])
        self.assertEqual(result['progress'],{'completed':1,'total':2});self.assertEqual(result['tokens'],10)
        self.assertNotIn('SYNTHETIC',json.dumps(result))
    def test_future_and_out_of_order(self):
        result=run([event('task_complete',12),event('task_complete',8),event('task_started',9)])
        self.assertEqual(result['state'],'active');self.assertEqual(result['counts']['future'],1)
        self.assertEqual(result['age_seconds'],60)
    def test_chat_messages_error_and_tool_counts(self):
        def chat(role,**fields):return {'type':role,'timestamp':NOW,'message':{'role':role,**fields}}
        self.assertEqual(run([chat('user',content='synthetic'),chat('assistant',content='synthetic',stop_reason='end_turn')],'chat')['state'],'ended')
        self.assertEqual(run([chat('assistant',content=[],stop_reason='error')],'chat')['state'],'error')
        result=run([chat('assistant',content=[{'type':'tool_use','name':'TodoWrite','input':{'todos':[{'content':'private synthetic','status':'done'}]}}])],'chat')
        self.assertEqual(result['progress'],{'completed':1,'total':1});self.assertEqual(result['counts']['tool_calls'],1)
    def test_strict_timestamps_and_units(self):
        for invalid in ['2030-01-01','2030-01-01T00:00:00','2030-02-30T00:00:00Z','2030-01-01T00:00:00+01:99','2030-01-01T00:00:00+00:60',True,float('nan'),-1]:
            with self.assertRaises(ValueError):epoch(invalid)
        self.assertEqual(epoch(1000,'milliseconds'),1)
    def test_unknown_shapes_and_invalid_payloads(self):
        for rows in [[{'what':'unrelated'}],[{**event('task_started'),'timestamp':'bad'}],
                     [{'type':'event_msg','timestamp':NOW,'payload':[]}]]:
            with self.assertRaises(ValueError):run(rows)
        with self.assertRaises(ValueError):run([event('token_count',info={'total_token_usage':{'total_tokens':True}})])
    def test_explicit_jsonl_and_duplicate_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'synthetic.jsonl';p.write_text(json.dumps(event('task_started'))+'\n')
            self.assertEqual(run(load_events(p))['state'],'active')
            for text in ['{"type":"user","type":"assistant"}', '[]','NaN','{"x":1}\nBAD']:
                p.write_text(text)
                with self.assertRaises(ValueError):load_events(p)
    def test_tool_output_ignores_payload_and_unknown_records_counted(self):
        result=run([response('function_call_output',output='SYNTHETIC_SECRET'),{'type':'unsupported'}])
        self.assertEqual(result['counts']['ignored'],1);self.assertNotIn('SYNTHETIC_SECRET',json.dumps(result))

if __name__=='__main__':unittest.main()
