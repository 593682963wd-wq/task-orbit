"""作者：Wangyuan；日期：2026-11-08。职责：验证源地址和日志时间回归。"""

from email.message import Message
from pathlib import Path
from types import SimpleNamespace
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from server import Handler, origin_key
from session_status import summarize


class ReleaseRegressionTests(unittest.TestCase):
    def allowed(self, headers, port=80, env=None):
        handler = object.__new__(Handler)
        handler.server = SimpleNamespace(server_address=('127.0.0.1', port))
        handler.headers = Message()
        for key, value in headers.items():
            handler.headers[key] = value
        errors = []
        handler.send = lambda code, body: errors.append(code)
        with patch.dict(os.environ, env or {}, clear=True):
            result = handler.allowed()
        return result, errors

    def test_default_port_is_equivalent(self):
        for host in ['127.0.0.1', '127.0.0.1:80', 'localhost', 'localhost:80']:
            self.assertTrue(self.allowed({'Host': host, 'Origin': 'http://' + host})[0])
        self.assertFalse(self.allowed({'Host': '127.0.0.1:81'})[0])

    def test_explicit_https_proxy_origin_and_rejection(self):
        env = {'ALLOWED_HOSTS': 'ring.example', 'PUBLIC_ORIGIN': 'https://ring.example:443'}
        self.assertTrue(self.allowed({'Host': 'ring.example', 'Origin': 'https://ring.example'}, 8080, env)[0])
        self.assertFalse(self.allowed({'Host': 'ring.example', 'Origin': 'https://other.example'}, 8080, env)[0])
        self.assertFalse(self.allowed({'Host': 'other.example', 'Origin': 'https://ring.example'}, 8080, env)[0])

    def test_origins_do_not_accept_paths_or_credentials(self):
        for value in ['https://example.test/path', 'https://user@example.test', 'null', 'file:///tmp/a']:
            self.assertIsNone(origin_key(value))
        self.assertEqual(origin_key('http://LOCALHOST:80'), 'http://localhost')

    def test_metadata_time_is_validated_for_both_formats(self):
        for format, types in [('codex', ['session_meta', 'turn_context']), ('chat', ['custom-title', 'model_change'])]:
            for kind in types:
                data = [{'type': kind, 'timestamp': '2030-01-01T00:12:00Z'}]
                result = summarize(data, format, now='2030-01-01T00:10:00Z', fresh_seconds=180)
                self.assertEqual(result['counts']['future'], 1)
                self.assertEqual(result['counts']['recognized'], 0)
                with self.assertRaises(ValueError):
                    summarize([{'type': kind, 'timestamp': 'bad'}], format, now='2030-01-01T00:10:00Z', fresh_seconds=180)

    def test_missing_metadata_time_preserves_compatibility(self):
        result = summarize([{'type': 'session_meta'}], 'codex', now='2030-01-01T00:10:00Z', fresh_seconds=180)
        self.assertEqual(result['state'], 'unknown')
        self.assertEqual(result['counts']['recognized'], 1)

    def test_docker_publish_defaults_to_loopback(self):
        # 假Docker只记录真实脚本参数，不创建容器；验证默认与显式覆盖行为。
        script = Path(__file__).resolve().parents[1] / 'deploy.sh'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docker = root / 'docker'
            docker.write_text('#!/bin/bash\ncase "$1" in\ninfo) exit 0;;\ncontainer) exit 1;;\nrun) printf "%s\\n" "$@" > "$CAPTURE";;\ninspect) echo true;;\nesac\n')
            docker.chmod(0o755)
            (root / 'sleep').write_text('#!/bin/bash\nexit 0\n')
            (root / 'sleep').chmod(0o755)
            capture = root / 'args.txt'
            env = {'PATH': f'{root}:/usr/bin:/bin', 'HOME': str(root), 'CAPTURE': str(capture), 'HOST_PORT': '54321', 'CONTAINER_PORT': '8080'}
            for address in [None, '192.0.2.15']:
                active = dict(env)
                if address is not None:
                    active['BIND_ADDRESS'] = address
                result = subprocess.run(['/bin/bash', str(script), 'start'], env=active, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                args = capture.read_text().splitlines()
                self.assertEqual(args[args.index('-p') + 1], f'{address or "127.0.0.1"}:54321:8080')


if __name__ == '__main__':
    unittest.main()
