#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Daily mirror connectivity test (used by GitHub Actions).

Reads mirror.json, functionally tests each mirror's ability to serve a real
git clone, and emits a bilingual (Chinese + English) Markdown report. This
script is read-only: it NEVER modifies mirror.json.

Functional probe
----------------
For each mirror the probe builds the same clone URL fast-clone itself would
use (via parse_git_url + apply_mirror) against a small, stable public repo,
then issues an HTTP GET on

    <mirror_url>/info/refs?service=git-upload-pack

the very first request a `git clone` makes. A mirror is reported as
*reachable* only when the response is HTTP 200 **and** its body begins with
the git smart-http advertisement prefix ``001e# service=git-upload-pack``.

This catches mirrors that pass a plain TCP-443 handshake but cannot actually
serve a clone (HTTP 404 / 402 / 502 / HTML error pages) — which a pure TCP
test would wrongly report as healthy.

Usage:
    python scripts/test_mirrors.py [--timeout 8]

Environment:
    GITHUB_STEP_SUMMARY  if set, the report is also appended there.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# Resolve project root (parent of scripts/) and make fastclone importable so
# the probe reuses the exact URL transform the real clone would use.
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
from fastclone import parse_git_url, apply_mirror  # noqa: E402

MIRROR_JSON = _ROOT / 'mirror.json'
REPORT_FILE = _ROOT / 'mirror-test-report.md'

# Small, stable public repos used as functional clone probes. One per platform
# fast-clone knows how to accelerate.
_PROBE_REPOS = {
    'github': 'https://github.com/octocat/Hello-World',
    'gitlab': 'https://gitlab.com/gitlab-org/gitlab',
}

# git smart-http info/refs advertisement always starts with this pkt-line.
_GIT_ADV_PREFIX = b'001e# service=git-upload-pack'

_UA = 'fast-clone-mirror-test/1.0'


def _detect_runner_ipv6() -> bool:
    """Best-effort IPv6 connectivity probe (Cloudflare anycast :443)."""
    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(('2606:4700:4700::1111', 443))
        s.close()
        return True
    except Exception:
        return False


# Probe the runner's real IPv6 capability instead of assuming "no".
RUNNER_HAS_IPV6 = _detect_runner_ipv6()


def load_mirrors() -> dict:
    with open(MIRROR_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)


def tcp_latency(host: str, port: int = 443, timeout: float = 5.0):
    """Return (latency_ms, error). latency_ms is None on failure."""
    t0 = time.monotonic()
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return round((time.monotonic() - t0) * 1000, 1), None
    except Exception as e:
        return None, str(e)[:80]


def http_probe(url: str, timeout: float):
    """GET ``url`` (following redirects), reading a small body prefix.

    Returns (status, latency_ms, body_prefix, error). ``status`` is None when
    the request failed at the network level; an HTTP error code (4xx/5xx) is
    returned as-is with the error body available in ``body_prefix``.
    """
    req = urllib.request.Request(url, headers={'User-Agent': _UA})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            prefix = resp.read(64)
            return (resp.getcode(),
                    round((time.monotonic() - t0) * 1000, 1), prefix, None)
    except urllib.error.HTTPError as e:
        prefix = b''
        try:
            prefix = e.read(64)
        except Exception:
            pass
        return (e.code, round((time.monotonic() - t0) * 1000, 1), prefix, None)
    except Exception as e:
        return None, None, b'', str(e)[:80]


def http_status(url: str, timeout: float):
    """GET ``url`` and return (status, error). status is None on network error."""
    req = urllib.request.Request(url, headers={'User-Agent': _UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), None
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return None, str(e)[:80]


def _probe_clone(mirror: dict, platform: str, timeout: float) -> dict:
    """Functional probe: GET info/refs through the mirror's transform.

    Returns a dict with keys ``latency_ms``, ``status`` (one of
    reachable / network / http_error / error / skipped) and ``note``.
    """
    sample = _PROBE_REPOS.get(platform)
    if not sample:
        return {'latency_ms': None, 'status': 'skipped',
                'note': f'no probe repo for platform {platform!r}'}
    try:
        info = parse_git_url(sample)
        base = apply_mirror(info, mirror)
    except Exception as e:
        return {'latency_ms': None, 'status': 'error',
                'note': f'transform failed: {e}'}
    url = base.rstrip('/') + '/info/refs?service=git-upload-pack'
    status, lat, prefix, err = http_probe(url, timeout)
    if status is None:
        return {'latency_ms': None, 'status': 'network',
                'note': err or 'network error'}
    if status == 200 and prefix.startswith(_GIT_ADV_PREFIX):
        return {'latency_ms': lat, 'status': 'reachable', 'note': None}
    snip = prefix[:40].decode('utf-8', 'replace').replace('\n', ' ').strip()
    return {'latency_ms': lat, 'status': 'http_error',
            'note': f'HTTP {status}: {snip!r}'}


def test_mirror(key: str, mirror: dict, timeout: float) -> dict:
    """Probe one mirror. Returns a result dict (see _probe_clone) plus key/mirror."""
    ip = mirror.get('ip', 'dual')
    if ip == 'v6' and not RUNNER_HAS_IPV6:
        return {'key': key, 'mirror': mirror, 'latency_ms': None,
                'status': 'skipped', 'note': 'runner has no IPv6'}

    host = mirror.get('test_host', '')
    if not host:
        return {'key': key, 'mirror': mirror, 'latency_ms': None,
                'status': 'error', 'note': 'no test_host configured'}

    platforms = mirror.get('platforms', [])
    probe_platform = next((p for p in platforms if p in _PROBE_REPOS), None)

    if probe_platform:
        res = _probe_clone(mirror, probe_platform, timeout)
        if res['status'] == 'reachable':
            return {'key': key, 'mirror': mirror, **res}
        if res['status'] == 'network':
            # Network-level failure: fall back to TCP so a working mirror is
            # not hidden by a transient HTTP-level issue.
            tlat, terr = tcp_latency(host, 443, timeout)
            return {'key': key, 'mirror': mirror, 'latency_ms': tlat,
                    'status': 'tcp_only' if tlat is not None else 'unreachable',
                    'note': terr or res['note']}
        # http_error: the site responded but cannot serve a real clone. For
        # platforms where the sample repo may simply not be mirrored (e.g.
        # gitlab), confirm the site itself responds before declaring the
        # mirror fully unreachable.
        if probe_platform != 'github':
            hstat, herr = http_status(f'https://{host}/', timeout)
            if hstat is not None and hstat < 400:
                tlat, _ = tcp_latency(host, 443, timeout)
                return {'key': key, 'mirror': mirror, 'latency_ms': tlat,
                        'status': 'site_up',
                        'note': f'site responds (HTTP {hstat}); sample repo not mirrored'}
        # Site is up but the clone endpoint failed (404/402/502/...): treat
        # as unreachable so it counts towards the failure tally.
        return {'key': key, 'mirror': mirror, 'latency_ms': res['latency_ms'],
                'status': 'unreachable', 'note': res['note']}

    # No sample repo for this platform: TCP reachability only.
    tlat, terr = tcp_latency(host, 443, timeout)
    if tlat is not None:
        return {'key': key, 'mirror': mirror, 'latency_ms': tlat,
                'status': 'tcp_only', 'note': 'no functional probe available'}
    return {'key': key, 'mirror': mirror, 'latency_ms': None,
            'status': 'unreachable', 'note': terr}


_STATUS_LABEL = {
    'reachable':   '可达 reachable',
    'tcp_only':    'TCP 可达 tcp-only',
    'site_up':     '站点可达 site-up',
    'unreachable': '不可达 unreachable',
    'skipped':     '跳过 skipped',
    'error':       '错误 error',
}


def main() -> int:
    timeout = 5.0
    if '--timeout' in sys.argv:
        i = sys.argv.index('--timeout')
        if i + 1 < len(sys.argv):
            timeout = float(sys.argv[i + 1])

    cfg = load_mirrors()
    mirrors = cfg.get('mirrors', {})
    if not mirrors:
        print('No mirrors found in mirror.json', file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    lines = [f'# 镜像连通性测试 / Mirror Connectivity Test — {now}', '']
    lines.append(f'Runner IPv6 支持 / Runner IPv6 support: '
                 f'{"是 / yes" if RUNNER_HAS_IPV6 else "否 / no"}')
    lines.append(f'测试镜像数 / Mirrors tested: {len(mirrors)}')
    lines.append('')
    lines.append('> 本次测试对每个镜像请求真实的 `info/refs?service=git-upload-pack` '
                 '（即 `git clone` 的首个请求），仅当返回 HTTP 200 且响应体以 git 协议通告开头时才记为可达。')
    lines.append('>')
    lines.append('> Each mirror is probed with a real `info/refs?service=git-upload-pack` '
                 'request (the first request `git clone` makes); a mirror is reachable only '
                 'on HTTP 200 with a git smart-http advertisement body.')
    lines.append('')
    lines.append('| key | 镜像 / mirror | ip | 延迟 / latency | 状态 / status |')
    lines.append('|-----|--------|----|---------|--------|')

    counts = {'reachable': 0, 'tcp_only': 0, 'site_up': 0,
              'unreachable': 0, 'skipped': 0, 'error': 0}
    results = []

    with ThreadPoolExecutor(max_workers=min(len(mirrors), 10)) as pool:
        futures = {pool.submit(test_mirror, k, v, timeout): k
                   for k, v in mirrors.items()}
        for fut in as_completed(futures):
            results.append(fut.result())

    # Sort by key for stable output.
    results.sort(key=lambda r: r['key'])

    for r in results:
        mirror = r['mirror']
        ip = mirror.get('ip', 'dual')
        name = mirror.get('name', r['key'])
        status = r['status']
        counts[status] = counts.get(status, 0) + 1
        label = _STATUS_LABEL.get(status, status)
        note = r.get('note')
        if note:
            label = f'{label} ({note})'
        lat = r.get('latency_ms')
        lat_str = f'{lat} ms' if lat is not None else '—'
        lines.append(f'| `{r["key"]}` | {name} | {ip} | {lat_str} | {label} |')

    lines.append('')
    lines.append(
        f'**汇总 / Summary**: '
        f'{counts["reachable"]} 可达 reachable, '
        f'{counts["site_up"] + counts["tcp_only"]} 部分可达 partial, '
        f'{counts["unreachable"] + counts["error"]} 不可达 unreachable, '
        f'{counts["skipped"]} 跳过 skipped')
    lines.append('')
    lines.append('> 本报告由 GitHub Actions 每日自动生成，不会修改 mirror.json —— 可用镜像列表仅由人工编辑变更。')
    lines.append('>')
    lines.append('> This report is generated daily by GitHub Actions. It does NOT modify mirror.json — available mirrors are only changed by manual edits.')

    report = '\n'.join(lines)

    # Write report file (used as the GitHub Release body and asset).
    REPORT_FILE.write_text(report, encoding='utf-8')
    print(report)
    print(f'\nReport written to {REPORT_FILE}')

    # Append to GitHub Actions step summary if available.
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as f:
            f.write(report + '\n')

    # Exit non-zero when more than half of the actually-tested mirrors are
    # unreachable, so the workflow run shows a visible failure for alerting.
    # (Skipped mirrors — e.g. IPv6-only on an IPv4 runner — do not count.)
    tested = (counts['reachable'] + counts['tcp_only'] + counts['site_up']
              + counts['unreachable'] + counts['error'])
    failed = counts['unreachable'] + counts['error']
    if tested > 0 and failed / tested > 0.5:
        print(f'\nWARNING: {failed}/{tested} mirrors unreachable',
              file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
