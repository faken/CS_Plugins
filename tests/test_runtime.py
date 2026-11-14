"""Behavior tests against Bash 3.2; no firmware or vehicle is executed."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler
import socketserver

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'packages/welcome-light/lib/runtime.sh'


class StateMachine(unittest.TestCase):
    def run_steps(self, script):
        with tempfile.TemporaryDirectory() as d:
            calls = Path(d) / 'calls'
            env = dict(os.environ, CALLS=str(calls))
            preamble = '''
set -eu
. "$1"
api() {
    printf '%s %s %s\\n' "$1" "$2" "${4:-}" >> "$CALLS"
    [ "${FAIL:-}" != "$1" ]
}
reset_state
'''
            result = subprocess.run(['/bin/bash', '-c', preamble + script, 'test', str(RUNTIME)],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return calls.read_text().splitlines() if calls.exists() else []

    def test_unlock_once_then_restore(self):
        calls = self.run_steps('''
step 0 true 15 P true false
step 1 true 15 P false false
step 2 true 15 P false false
step 15 true 15 P false false
step 16 true 15 P false false
''')
        self.assertEqual([c.split()[0] for c in calls], ['PUT', 'DELETE'])
        self.assertEqual(json.loads(calls[0].split(' ', 2)[2]),
                         {'value': 'ParkingLights', 'hold': False})

    def test_startup_unlocked_and_disabled_do_not_actuate(self):
        self.assertEqual(self.run_steps('''
step 0 true 15 P false false
step 1 false 15 P true false
step 2 false 15 P false false
'''), [])

    def test_invalid_telemetry_cancels_arming(self):
        for field in ['gear', 'locked', 'present']:
            args = dict(gear='P', locked='true', present='false')
            args[field] = 'unknown'
            self.assertEqual(self.run_steps(f'''
step 0 true 15 P true false
step 1 true 15 {args['gear']} {args['locked']} {args['present']}
step 2 true 15 P false false
'''), [])

    def test_release_on_driving_occupancy_lock_disable_or_telemetry_loss(self):
        for state in ['true 15 D false false', 'true 15 P false true',
                      'true 15 P true false', 'false 15 P false false',
                      'true 15 unknown false false', 'true 15 P unknown false']:
            calls = self.run_steps('''
step 0 true 15 P true false
step 1 true 15 P false false
step 2 ''' + state + '\n')
            self.assertEqual([c.split()[0] for c in calls], ['PUT', 'DELETE'])

    def test_cooldown_then_rearm(self):
        calls = self.run_steps('''
step 0 true 5 P true false
step 1 true 5 P false false
step 6 true 5 P false false
step 7 true 5 P true false
step 8 true 5 P false false
step 36 true 5 P true false
step 37 true 5 P false false
''')
        self.assertEqual([c.split()[0] for c in calls], ['PUT', 'DELETE', 'PUT'])

    def test_failed_put_also_releases(self):
        calls = self.run_steps('''
step 0 true 15 P true false
FAIL=PUT
if step 1 true 15 P false false; then exit 8; fi
[ "$active" = 0 ]
''')
        self.assertEqual([c.split()[0] for c in calls], ['PUT', 'DELETE'])

    def test_failed_release_stays_pending(self):
        calls = self.run_steps('''
step 0 true 5 P true false
step 1 true 5 P false false
FAIL=DELETE
if step 6 true 5 P false false; then exit 8; fi
[ "$active" = 1 ]
FAIL=
step 7 true 5 P false false
[ "$active" = 0 ]
''')
        self.assertEqual([c.split()[0] for c in calls], ['PUT', 'DELETE', 'DELETE'])

    def test_bad_duration_uses_bounded_default(self):
        self.run_steps('''
step 0 true invalid P true false
step 1 true invalid P false false
[ "$deadline" = 16 ]
''')


class UnixHTTP(socketserver.UnixStreamServer):
    pass


class Transport(unittest.TestCase):
    def test_actual_curl_socket_auth_body_and_http_failure(self):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_PUT(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
                requests.append((self.path, self.headers.get('Authorization'), body))
                self.send_response(200 if self.path.startswith('/v1/dv/') else 503)
                self.end_headers()
            def log_message(self, *args):
                pass

        with tempfile.TemporaryDirectory(prefix='wl-', dir='/private/tmp') as d:
            sock = str(Path(d) / 'api.sock')
            try:
                server = UnixHTTP(sock, Handler)
            except PermissionError as exc:
                self.skipTest("Sandbox denied Unix socket binding: " + str(exc))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                env = dict(os.environ, CSDK_API_SOCKET=sock, CSDK_TOKEN='test-token')
                result = subprocess.run(['/bin/bash', '-c', '''
set -eu
. "$1"
api PUT /dv/GUI_halloweenLightSwitchRequest --data-binary '{"value":"ParkingLights","hold":false}'
if api PUT /unavailable; then exit 9; fi
''', 'test', str(RUNTIME)], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(requests[0][0], '/v1/dv/GUI_halloweenLightSwitchRequest')
                self.assertEqual(requests[0][1], 'Bearer test-token')
                self.assertEqual(json.loads(requests[0][2])['value'], 'ParkingLights')
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == '__main__':
    unittest.main()
