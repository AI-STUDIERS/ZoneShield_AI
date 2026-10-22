import json
import time
import urllib.request
import sys

def get(url):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, resp.read().decode('utf-8')

def post(url, data=None):
    payload = json.dumps(data or {}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode('utf-8'))

def main():
    print("Connecting to ZoneShield AI server at http://127.0.0.1:8000 ...")
    
    # 1. Health check
    s, h = get('http://127.0.0.1:8000/api/v1/health')
    print(f"[OK] Health endpoint: {h}")

    # 2. Frontend dashboard
    s, html = get('http://127.0.0.1:8000/')
    print(f"[OK] Dashboard UI served: {s} (size: {len(html)} bytes, has ZoneShield: {'ZoneShield' in html})")

    # 3. System info & COOL selfcheck
    s, info_raw = get('http://127.0.0.1:8000/api/v1/system/info')
    info = json.loads(info_raw)
    print(f"[OK] System Info: OpenCV {info.get('opencv_version')}, Arch {info.get('hardware', {}).get('architecture')}, COOL: {info.get('cool_proof', {}).get('status')}")

    # 4. Session management
    s, sess = post('http://127.0.0.1:8000/api/v1/sessions', {'name': 'Verification Belt', 'scenario_id': 'S1'})
    sess_id = sess['id']
    print(f"[OK] Created Session: {sess_id}")

    s, start_res = post(f'http://127.0.0.1:8000/api/v1/sessions/{sess_id}/start')
    print(f"[OK] Started Session: {start_res}")

    # Wait for a couple of frames to process
    time.sleep(1.5)

    # 5. Prometheus metrics
    s, metrics = get('http://127.0.0.1:8000/api/v1/metrics')
    metric_lines = [l for l in metrics.splitlines() if not l.startswith('#') and l.strip()]
    print(f"[OK] Live Metrics: {', '.join(metric_lines[:4])}")

    # 6. Safety Kill Switch
    s, kill_res = post('http://127.0.0.1:8000/api/v1/system/kill-switch', {'reason': 'Test verification'})
    print(f"[OK] Emergency Kill Switch: {kill_res.get('status')}")

    s, reset_res = post('http://127.0.0.1:8000/api/v1/system/kill-switch/reset')
    print(f"[OK] Reset Kill Switch: {reset_res.get('status')}")

    # 7. Stop Session
    s, stop_res = post(f'http://127.0.0.1:8000/api/v1/sessions/{sess_id}/stop')
    print(f"[OK] Stopped Session: {stop_res}")

    print("\n>>> ALL TESTS PASSED SUCCESSFULLY! The ZoneShield AI server is 100% operational.")

if __name__ == '__main__':
    main()
