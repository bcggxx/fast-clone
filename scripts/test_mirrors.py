#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Daily mirror connectivity test (used by GitHub Actions).

Reads mirror.json, tests each mirror's TCP 443 reachability, and emits a
bilingual (Chinese + English) Markdown report. This script is read-only: it
NEVER modifies mirror.json.

Usage:
    python scripts/test_mirrors.py [--timeout 5]

Environment:
    GITHUB_STEP_SUMMARY  if set, the report is also appended there.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# Resolve mirror.json relative to the project root (parent of scripts/).
MIRROR_JSON = Path(__file__).resolve().parent.parent / 'mirror.json'
REPORT_FILE = Path(__file__).resolve().parent.parent / 'mirror-test-report.md'

# GitHub Actions ubuntu runners have no IPv6 connectivity.
RUNNER_HAS_IPV6 = False


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


def test_mirror(key: str, mirror: dict, timeout: float):
    ip = mirror.get('ip', 'dual')
    if ip == 'v6' and not RUNNER_HAS_IPV6:
        return key, mirror, None, 'skipped (runner has no IPv6)'
    host = mirror.get('test_host', '')
    if not host:
        return key, mirror, None, 'no test_host configured'
    lat, err = tcp_latency(host, 443, timeout)
    return key, mirror, lat, err


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
    lines.append(f'Runner IPv6 支持 / Runner IPv6 support: {"是 / yes" if RUNNER_HAS_IPV6 else "否 / no"}')
    lines.append(f'测试镜像数 / Mirrors tested: {len(mirrors)}')
    lines.append('')
    lines.append('| key | 镜像 / mirror | ip | 延迟 / latency | 状态 / status |')
    lines.append('|-----|--------|----|---------|--------|')

    reachable = 0
    unreachable = 0
    skipped = 0
    results = []

    with ThreadPoolExecutor(max_workers=min(len(mirrors), 10)) as pool:
        futures = {pool.submit(test_mirror, k, v, timeout): k
                   for k, v in mirrors.items()}
        for fut in as_completed(futures):
            results.append(fut.result())

    # Sort by key for stable output.
    results.sort(key=lambda r: r[0])

    for key, mirror, lat, err in results:
        ip = mirror.get('ip', 'dual')
        name = mirror.get('name', key)
        if lat is not None:
            status = '可达 reachable'
            lat_str = f'{lat} ms'
            reachable += 1
        elif err and err.startswith('skipped'):
            status = '跳过 skipped'
            lat_str = '—'
            skipped += 1
        else:
            status = f'不可达 unreachable ({err})' if err else '不可达 unreachable'
            lat_str = '—'
            unreachable += 1
        lines.append(f'| `{key}` | {name} | {ip} | {lat_str} | {status} |')

    lines.append('')
    lines.append(f'**汇总 / Summary**: {reachable} 可达 reachable, {unreachable} 不可达 unreachable, '
                 f'{skipped} 跳过 skipped')
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

    # Exit non-zero if more than half are unreachable (excluding skipped),
    # so the workflow run shows a visible failure for alerting.
    tested = reachable + unreachable
    if tested > 0 and unreachable / tested > 0.5:
        print(f'\nWARNING: {unreachable}/{tested} mirrors unreachable',
              file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
