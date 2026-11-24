"""Exercise the actual packaged application over loopback in isolated demo data."""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def verify(executable):
    events = []
    def request(origin, method='GET', path='/api/state', body=None, token=None, expected=200, headers=None):
        extra = {'Content-Type': 'application/json'} if body is not None else {}
        if token:
            extra['X-Panel-Token'] = token
        extra.update(headers or {})
        req = urllib.request.Request(origin + path, method=method,
              data=json.dumps(body).encode() if body is not None else None, headers=extra)
        try:
            response = urllib.request.urlopen(req, timeout=4)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            data = response.read()
            assert response.status == expected, (path, response.status, data)
            events.append({'method': method, 'path': path, 'status': response.status})
            return json.loads(data) if response.headers['Content-Type'].startswith('application/json') else data

    with tempfile.TemporaryDirectory(prefix='driplite-studio-') as folder:
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        origin = 'http://127.0.0.1:' + str(port)
        command = [str(executable), '--demo', '--no-browser', '--data', folder, '--port', str(port)]
        def start():
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                for _ in range(200):
                    if process.poll() is not None:
                        raise RuntimeError('Application exited early: ' + str(process.communicate()))
                    try:
                        state = request(origin)
                        assert state['product'] == 'driplite-studio' and state['demo']
                        return process, state
                    except (OSError, urllib.error.URLError):
                        time.sleep(0.1)
                raise RuntimeError('Panel did not become ready')
            except BaseException:
                process.terminate()
                process.communicate(timeout=10)
                raise
        def stop(process, state):
            request(origin, 'POST', '/api/stop', {'revision': state['revision']}, state['token'])
            out, err = process.communicate(timeout=15)
            events.append({'command': command, 'stdout': out, 'stderr': err, 'exit_status': process.returncode})
            assert process.returncode == 0 and not err
        process, state = start()
        try:
            assert len(state['catalog']['modules']) == 44
            assert sum(len(m['fields']) for m in state['catalog']['modules']) == 163
            assert state['values']['auto-clicker.cps'] == 25
            assert state['values']['chest-stealer.silent'] == 1
            assert state['values']['chest-stealer.filter'] == 0
            assert state['values']['chest-stealer.speed'] == 0
            assert abs(state['values']['strafe.range'] - 3.0) < 0.001
            assert state['values']['strafe.delay'] == 1
            assert state['values']['bridge-assist.require-sneak'] == 1
            assert state['values']['bridge-assist.blatant'] == 0
            assert abs(state['values']['fast-break.speed'] - 1.25) < 0.001
            assert abs(state['values']['freelook.sensitivity'] - 0.9) < 0.001
            assert state['values']['fireballs.color-red'] == 1
            assert abs(state['values']['fireballs.opacity'] - 0.9) < 0.001
            assert abs(state['values']['fireballs.size'] - 1.3) < 0.001
            assert state['values']['hit-select.hurt-time'] == 0
            assert state['values']['chat.color-red'] == 1
            assert abs(state['values']['chat.background-red'] - 0.2627) < 0.001
            assert state['values']['auto-totem.delay'] == 80
            assert state['values']['auto-totem.health'] == 8
            assert state['values']['auto-totem.switch-back'] == 0
            assert state['values']['auto-soup.health'] == 13
            assert state['values']['auto-soup.delay'] == 1
            assert state['values']['auto-soup.randomize'] == 1
            assert state['values']['refill.speed'] == 10
            assert state['values']['sprint-reset.chance'] == 45
            assert state['values']['fake-lag.mode'] == 2
            assert state['values']['name-tags.color-red'] == 1
            assert abs(state['values']['chams.visible-color-red'] - 0.8588) < 0.001
            assert abs(state['values']['player-esp.box-color-blue'] - 0.48) < 0.001
            assert abs(state['values']['outlines.color-blue'] - 0.9373) < 0.001
            assert abs(state['values']['hud.color-r'] - 0.415) < 0.001
            assert abs(state['values']['hud.color-g'] - 0.415) < 0.001
            assert abs(state['values']['hud.color-b'] - 0.415) < 0.001
            assert abs(state['values']['hud.opacity'] - 1.1) < 0.001
            assert state['values']['hud.watermark'] == 1
            assert state['values']['hud.background'] == 1
            assert state['values']['hud.obfuscate'] == 0
            assert abs(state['values']['hud.scale'] - 1.136) < 0.01
            assert state['values']['triggerbot.mode'] == 1
            assert b'Driplite Studio' in request(origin, path='/')
            assert b'config_editor' not in request(origin, path='/app.js')
            assert request(origin, path='/style.css')
            duplicate = subprocess.run(command, capture_output=True, text=True, timeout=20)
            events.append({'label': 'singleton', 'command': command, 'stdout': duplicate.stdout,
                           'stderr': duplicate.stderr, 'exit_status': duplicate.returncode})
            assert duplicate.returncode == 0
            request(origin, 'POST', '/api/patch', {'revision': 0, 'values': {'auto-clicker.cps': 30}}, expected=403)
            request(origin, 'POST', '/api/patch', {'revision': 0, 'values': {'auto-clicker.cps': 30}},
                    state['token'], expected=403, headers={'Origin': 'http://example.invalid'})
            state = request(origin, 'POST', '/api/patch', {'revision': 0, 'values': {'auto-clicker.cps': 30}}, state['token'])
            assert state['values']['auto-clicker.cps'] == 30
            request(origin, 'POST', '/api/reset', {'revision': 0}, state['token'], expected=400)
            state = request(origin, 'POST', '/api/profile-save', {'revision': 1, 'name': 'integration'}, state['token'])
            state = request(origin, 'POST', '/api/undo', {'revision': 1}, state['token'])
            assert state['values']['auto-clicker.cps'] == 25
            events.append({'BASELINE': 25, 'MODIFIED': 30, 'ROLLBACK': 25})
            state = request(origin, 'POST', '/api/profile-load', {'revision': 2, 'name': 'integration'}, state['token'])
            assert state['values']['auto-clicker.cps'] == 30
            stop(process, state)
            process, state = start()
            assert state['values']['auto-clicker.cps'] == 30 and 'integration' in state['profiles']
            state = request(origin, 'POST', '/api/reset', {'revision': state['revision']}, state['token'])
            assert state['values']['auto-clicker.cps'] == 25
            stop(process, state)
        finally:
            if process.poll() is None:
                process.terminate()
                process.communicate(timeout=15)
    result = {'passed': True, 'native_execution': False, 'events': events,
              'checks': ['packaged HTTP UI', '44 modules/163 fields', 'HUD defaults', 'Visual color defaults',
                         'Bridge/FastBreak/Freelook/Fireballs/HitSelect/Strafe/ChestStealer defaults',
                         'Chat color defaults', 'Auto Totem defaults', 'Auto Soup defaults',
                         'Refill speed default', 'Sprint Reset chance default', 'Fake Lag mode default',
                         'triggerbot mode default', 'singleton', 'request validation', '25 -> 30 -> 25', 'named profiles',
                         'restart persistence', 'graceful shutdown']}
    output = ROOT / 'evidence/studio_verification.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'passed': True, 'checks': result['checks'], 'record': str(output)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, default=ROOT / 'dist/Driplite-Studio.exe')
    args = parser.parse_args()
    verify(args.exe.resolve())
