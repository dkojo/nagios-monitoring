#!/usr/bin/env python3
"""The proofs, one per pipeline step:

    verify.py baseline        every service has been checked and is OK
    verify.py fault <host>    plant that host's fault, then prove Nagios caught it, alerted on-call, and it recovered
    verify.py allclear        every service is OK again, and a summary of the alerts

The faults:
    web    nginx is killed            -> HTTP CRITICAL -> the event handler restarts nginx on its own
    app    the backups go stale       -> Backup age CRITICAL -> the operator runs the backup
    db     a runaway log fills /data  -> Data disk CRITICAL -> the operator removes it
    files  the TLS cert nears expiry  -> TLS cert CRITICAL -> the operator renews it
"""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

INBOX = 'http://10.43.0.20:8080/alerts'
DETECT_SLA = 45      # seconds from fault to the on-call alert
RECOVER_SLA = 60
OUT = Path(__file__).resolve().parent.parent / 'dist'

FAULTS = {
    'web': dict(service='HTTP', what='nginx killed', inject='pkill -x nginx', fix=None),
    'app': dict(service='Backup age', what='backups stale for 3 days', inject="touch -d '3 days ago' /backups/*", fix='backup'),
    'db': dict(service='Data disk', what='runaway log filling /data', inject='dd if=/dev/zero of=/data/runaway.log bs=1M count=60 status=none',
               fix='rm -f /data/runaway.log'),
    'files': dict(service='TLS cert', what='certificate 3 days from expiry', inject='make-cert 3', fix='make-cert 365'),
}


def sh(container, cmd):
    subprocess.run(['docker', 'exec', container, 'sh', '-c', cmd], check=True)


def services():
    raw = subprocess.run(['docker', 'exec', 'nagios', 'cat', '/var/lib/nagios4/status.dat'],
                         capture_output=True, text=True, check=True).stdout
    out = []
    for block in raw.split('servicestatus {')[1:]:
        kv = dict(l.strip().split('=', 1) for l in block.split('}')[0].strip().splitlines() if '=' in l)
        out.append(kv)
    return out


def alerts():
    return json.loads(urllib.request.urlopen(INBOX, timeout=5).read())


def wait_alert(kind, host, service, since, timeout):
    end = time.time() + timeout
    while time.time() < end:
        for a in alerts():
            if a['type'] == kind and a['host'] == host and a['service'] == service and a['at'] >= since:
                return a
        time.sleep(1)
    return None


def save(name, data):
    OUT.mkdir(exist_ok=True)
    (OUT / f'{name}.json').write_text(json.dumps(data))


def baseline():
    end = time.time() + 120
    while time.time() < end:
        svcs = services()
        if svcs and all(s['has_been_checked'] == '1' and s['current_state'] == '0' for s in svcs):
            break
        time.sleep(2)
    for s in svcs:
        state = 'OK' if s['current_state'] == '0' else ['', 'WARNING', 'CRITICAL', 'UNKNOWN'][int(s['current_state'])]
        print(f"  {state:<8} {s['host_name']:<6} {s['service_description']:<14} {s['plugin_output']}")
    bad = [s for s in svcs if s['current_state'] != '0' or s['has_been_checked'] != '1']
    if bad:
        print(f'FAIL  {len(bad)} service(s) not OK before any fault was planted')
        sys.exit(1)
    print(f'PASS  all {len(svcs)} services on 4 hosts are OK')


def fault(host):
    f = FAULTS[host]
    print(f'Planting the fault on {host}: {f["what"]}')
    t0 = time.time()
    sh(host, f['inject'])
    problem = wait_alert('PROBLEM', host, f['service'], t0, DETECT_SLA)
    if not problem:
        print(f'FAIL  {host}/{f["service"]}: no alert within {DETECT_SLA}s. The fault is real and on-call was never told')
        sys.exit(1)
    detect = problem['at'] - t0
    print(f'Detected in {detect:.0f}s · on-call alerted: {problem["state"]} - {problem["output"]}')
    t1 = time.time()
    if f['fix']:
        print(f'Operator fix: {f["fix"]}')
        sh(host, f['fix'])
    else:
        print('No one touches the server: waiting for the Nagios event handler')
    recovery = wait_alert('RECOVERY', host, f['service'], t1, RECOVER_SLA)
    if not recovery:
        print(f'FAIL  {host}/{f["service"]} did not recover within {RECOVER_SLA}s')
        sys.exit(1)
    heal = recovery['at'] - t1
    if not f['fix']:
        log = subprocess.run(['docker', 'exec', 'nagios', 'grep', 'SERVICE EVENT HANDLER: web;HTTP;CRITICAL;HARD', '/var/log/nagios4/nagios.log'],
                             capture_output=True, text=True).stdout.strip().splitlines()
        print(f'Event handler ran: {log[-1].split("] ", 1)[-1] if log else "not found"}')
        if not log:
            print('FAIL  recovered, but not by the event handler')
            sys.exit(1)
    print(f'Recovered in {heal:.0f}s · on-call told: RECOVERY - {recovery["output"]}')
    save(f'fault-{host}', {'detect': round(detect), 'recover': round(heal), 'self_healed': not f['fix']})
    print(f'PASS  {host}: detected in {detect:.0f}s, alerted, recovered in {heal:.0f}s' + (' with no human' if not f['fix'] else ''))


def allclear():
    time.sleep(3)
    svcs = services()
    bad = [s for s in svcs if s['current_state'] != '0']
    got = alerts()
    by = {}
    for a in got:
        by[a['type']] = by.get(a['type'], 0) + 1
    print('On-call inbox:')
    for a in got:
        print(f"  {a['type']:<9} {a['host']}/{a['service']} {a['state']}")
    results = [json.loads(p.read_text()) for p in sorted(OUT.glob('fault-*.json'))]
    if results:
        print(f"Mean time to detect: {sum(r['detect'] for r in results) / len(results):.0f}s · "
              f"self-healed: {sum(r['self_healed'] for r in results)} of {len(results)}")
    print('Alerts: ' + ', '.join(f'{v} {k}' for k, v in sorted(by.items())))
    if bad:
        print(f'FAIL  {len(bad)} service(s) still not OK: ' + ', '.join(f"{s['host_name']}/{s['service_description']}" for s in bad))
        sys.exit(1)
    print(f'PASS  all {len(svcs)} services OK again')


if __name__ == '__main__':
    cmd = sys.argv[1]
    baseline() if cmd == 'baseline' else allclear() if cmd == 'allclear' else fault(sys.argv[2])
