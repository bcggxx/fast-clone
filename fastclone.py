#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fast-clone - mirror-accelerated git clone with auto remote reset.

Usage:
    fast-clone https://github.com/user/repo
    fast-clone --mirror kkgithub https://github.com/user/repo
    fast-clone --fastest https://github.com/user/repo
    fast-clone --list-mirrors
    fast-clone --dry-run https://github.com/user/repo

All mirror configs are embedded in _CONFIG dict - single file, no external deps.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

from i18n import L, Lh, LANG as _LANG

# ---- Windows console: force UTF-8 ----
if os.name == 'nt':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


# ===========================================================================
# CONFIG - loaded from mirror.json (next to this script)
# ===========================================================================

_CONFIG_PATH = Path(__file__).resolve().parent / 'mirror.json'


def _load_mirror_config() -> dict:
    """Load mirror configuration from mirror.json next to this script.

    Falls back to an empty-mirror config if the file is missing or corrupt,
    so the tool can still direct-clone without any mirrors available.
    """
    try:
        with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        if not isinstance(cfg, dict) or 'mirrors' not in cfg:
            raise ValueError("mirror.json missing 'mirrors' key")
        return cfg
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        sys.stderr.write(
            f"warning: failed to load mirror.json ({e}); "
            f"falling back to no mirrors\n")
        return {
            "default": "",
            "speed_threshold_kib": 1024,
            "speed_timeout_seconds": 180,
            "connect_retries": 3,
            "mirrors": {},
        }


_CONFIG = _load_mirror_config()


# ===========================================================================
# Config accessors
# ===========================================================================

def load_config() -> dict:
    return _CONFIG


def get_mirrors(config: dict) -> dict:
    return config.get('mirrors', {})


def get_default_mirror(config: dict) -> str:
    return config.get('default', 'kkgithub')


def get_speed_threshold(config: dict) -> int:
    return config.get('speed_threshold_kib', 1024)


def get_speed_timeout(config: dict) -> int:
    return config.get('speed_timeout_seconds', 180)


def get_connect_retries(config: dict) -> int:
    return config.get('connect_retries', 3)


# ===========================================================================
# URL parsing
# ===========================================================================

def parse_git_url(url: str) -> dict:
    ssh_m = re.match(r'^git@([^:]+):(.+)$', url)
    if ssh_m:
        domain = ssh_m.group(1)
        path = ssh_m.group(2).rstrip('/')
        if path.endswith('.git'):
            path = path[:-4]
        parts = path.split('/')
        repo = parts[-1] if parts else ''
        owner = '/'.join(parts[:-1]) if len(parts) >= 2 else ''
        return _make_info(url, domain, owner, repo, True)

    parsed = urlparse(url)
    domain = parsed.netloc or parsed.hostname or ''
    path = (parsed.path or '').strip('/').rstrip('/')
    if path.endswith('.git'):
        path = path[:-4]
    parts = path.split('/')
    repo = parts[-1] if parts else ''
    owner = '/'.join(parts[:-1]) if len(parts) >= 2 else ''
    return _make_info(url, domain, owner, repo, False)


def _make_info(url: str, domain: str, owner: str, repo: str, is_ssh: bool) -> dict:
    return {
        'original': url, 'domain': domain, 'owner': owner, 'repo': repo,
        'platform': _detect_platform(domain), 'is_ssh': is_ssh,
        'https_url': f'https://{domain}/{owner}/{repo}.git',
    }


def _detect_platform(domain: str) -> str:
    d = domain.lower()
    if 'github' in d:
        return 'github'
    if 'gitlab' in d or 'jihulab' in d:
        return 'gitlab'
    if 'gitee' in d:
        return 'gitee'
    return 'unknown'


# ===========================================================================
# URL transform - 4 strategies
# ===========================================================================

def apply_mirror(info: dict, mirror: dict) -> str:
    https_url = info['https_url']
    s = mirror['transform']

    if s == 'prefix':
        return mirror['prefix'] + https_url
    if s == 'domain_replace':
        return https_url.replace(mirror['old'], mirror['new'], 1)
    if s == 'path_prefix':
        clean = https_url.replace('https://', '', 1)
        d = info['domain']
        if clean.startswith(d + '/'):
            clean = clean[len(d) + 1:]
        return mirror['prefix'] + clean
    if s == 'domain_suffix':
        return https_url.replace(mirror['old'], mirror['old'] + mirror['suffix'], 1)

    raise ValueError(f"Unknown transform: {s}")


# ===========================================================================
# IPv4 / IPv6 support detection
# ===========================================================================

# Cached detection result: (has_ipv4, has_ipv6) or None if not yet detected.
_IP_SUPPORT: tuple[bool, bool] | None = None

# Reachability probe endpoints (TCP 443). Each protocol tries Cloudflare
# anycast first; on failure it falls back to Tencent DNSPod so that a
# Cloudflare-only block does not cause a false-negative in mainland China.
_IPV4_PROBES = ['1.1.1.1', '119.29.29.29']            # Cloudflare, Tencent DNSPod
_IPV6_PROBES = ['2606:4700:4700::1111', '2402:4e00::']  # Cloudflare, Tencent DNSPod


def _probe_ip(family: int, addr: str, timeout: float = 2.0) -> bool:
    """Try a TCP connect to a known public address of the given family."""
    try:
        s = socket.socket(family, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((addr, 443))
        s.close()
        return True
    except Exception:
        return False


def _probe_ip_any(family: int, addrs: list[str], timeout: float = 2.0) -> bool:
    """Try each address in turn; return True on the first successful connect."""
    for addr in addrs:
        if _probe_ip(family, addr, timeout):
            return True
    return False


def detect_ip_support(timeout: float = 2.0) -> tuple[bool, bool]:
    """Detect whether the current environment has working IPv4 / IPv6.

    Probes Cloudflare anycast first, falling back to Tencent DNSPod
    (119.29.29.29 / 2402:4e00::) when Cloudflare is unreachable, so a
    Cloudflare-only block does not produce a false negative. The two
    protocols are tested in parallel. Result is cached for the process.
    Returns (has_ipv4, has_ipv6).
    """
    global _IP_SUPPORT
    if _IP_SUPPORT is not None:
        return _IP_SUPPORT

    with ThreadPoolExecutor(max_workers=2) as pool:
        f4 = pool.submit(_probe_ip_any, socket.AF_INET, _IPV4_PROBES, timeout)
        f6 = pool.submit(_probe_ip_any, socket.AF_INET6, _IPV6_PROBES, timeout)
        has_v4 = f4.result()
        has_v6 = f6.result()

    # If both probes failed the network is down / blocked: do not filter
    # mirrors by IP version, let the actual clone attempt decide.
    if not has_v4 and not has_v6:
        has_v4 = has_v6 = True

    _IP_SUPPORT = (has_v4, has_v6)
    print(L('ip_detect', has_v4, has_v6))
    return _IP_SUPPORT


def filter_mirrors_by_ip(mirrors: dict, has_v4: bool, has_v6: bool) -> dict:
    """Drop mirrors that require an IP version the environment cannot use.

    A mirror's ``ip`` field is one of: ``dual`` (default, both), ``v4``
    (IPv4-only endpoint), ``v6`` (IPv6-only endpoint). When detection is
    inconclusive (both reported True) nothing is filtered.
    """
    if has_v4 and has_v6:
        return mirrors
    kept = {}
    for k, v in mirrors.items():
        ip = v.get('ip', 'dual')
        if ip == 'v4' and not has_v4:
            print(L('speed_cache_skip_v4', v.get('name', k)))
            continue
        if ip == 'v6' and not has_v6:
            print(L('speed_cache_skip_v6', v.get('name', k)))
            continue
        kept[k] = v
    return kept


# ===========================================================================
# Speed-test result cache (local, expires after 7 days)
# ===========================================================================

_CACHE_DIR = Path(__file__).resolve().parent / 'speedcache'
_CACHE_EXPIRE_DAYS = 7


def _cache_dir() -> Path:
    """Ensure the cache directory exists and return it."""
    _CACHE_DIR.mkdir(exist_ok=True)
    return _CACHE_DIR


def _cache_filename(dt: datetime.datetime) -> str:
    """Cache filename = test time (Windows-safe, no colons)."""
    return dt.strftime('%Y-%m-%d_%H%M%S') + '.json'


def _find_valid_cache(platform: str) -> dict | None:
    """Return the most recent non-expired cache entry for a platform, or None."""
    now = datetime.datetime.now()
    best: tuple[datetime.datetime, dict] | None = None
    for f in _cache_dir().glob('*.json'):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            continue
        if data.get('platform') != platform:
            continue
        tt = data.get('test_time')
        if not tt:
            continue
        try:
            test_dt = datetime.datetime.fromisoformat(tt)
        except ValueError:
            continue
        age = (now - test_dt).total_seconds()
        if age > _CACHE_EXPIRE_DAYS * 86400:
            continue  # expired
        if best is None or test_dt > best[0]:
            best = (test_dt, data)
    return best[1] if best else None


def _save_cache(platform: str, results: dict) -> Path:
    """Persist speed-test results; filename is the test timestamp."""
    now = datetime.datetime.now()
    data = {
        'test_time': now.isoformat(timespec='seconds'),
        'platform': platform,
        'results': results,
    }
    path = _cache_dir() / _cache_filename(now)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return path


def _find_expired_caches() -> list:
    """List cache files older than _CACHE_EXPIRE_DAYS (or corrupt)."""
    now = datetime.datetime.now()
    expired = []
    for f in _cache_dir().glob('*.json'):
        test_dt = None
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            tt = data.get('test_time')
            if tt:
                test_dt = datetime.datetime.fromisoformat(tt)
        except (json.JSONDecodeError, OSError, ValueError):
            pass  # corrupt file → treat as expired
        if test_dt is None:
            expired.append(f)
            continue
        age = (now - test_dt).total_seconds()
        if age > _CACHE_EXPIRE_DAYS * 86400:
            expired.append(f)
    return expired


def prompt_delete_expired_caches() -> None:
    """At startup, offer to delete expired (>7 day) cache files."""
    expired = _find_expired_caches()
    if not expired:
        return
    try:
        ans = input(L('speed_cache_delete_q', len(expired))).strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = 'n'
    if ans in ('', 'y', 'yes'):
        for f in expired:
            try:
                f.unlink()
            except OSError:
                pass
        print_ok(L('speed_cache_deleted', len(expired)))
    else:
        print_step(L('speed_cache_kept'))


# ===========================================================================
# Speed test
# ===========================================================================

def _tcp_latency(host: str, port: int = 443, timeout: float = 3.0) -> float:
    try:
        t0 = time.monotonic()
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return time.monotonic() - t0
    except Exception:
        return float('inf')


def _get_speed_results(platform: str, candidates: dict,
                       timeout: float = 3.0) -> dict:
    """Return {mirror_key: latency_seconds}. Uses cache when valid, else
    runs a live TCP test and persists the result.

    ``latency_seconds`` is ``float('inf')`` for unreachable mirrors.
    """
    # 1) Try a valid (non-expired) cache entry for this platform.
    cached = _find_valid_cache(platform)
    if cached:
        results: dict[str, float] = {}
        test_dt = cached.get('test_time', '')
        try:
            days = (datetime.datetime.now()
                    - datetime.datetime.fromisoformat(test_dt)).days
        except ValueError:
            days = 0
        for k, v in cached.get('results', {}).items():
            if k not in candidates:
                continue
            ms = v.get('latency_ms')
            results[k] = (ms / 1000.0) if ms is not None else float('inf')
        if results:
            print(L('speed_cached', test_dt, days))
            return results
        # Cache had no matching candidates → fall through to live test.

    # 2) Live TCP latency test.
    print(L('speed_testing', len(candidates)))
    results = {}
    with ThreadPoolExecutor(max_workers=min(len(candidates), 10)) as pool:
        futures = {pool.submit(_tcp_latency, v['test_host'], 443, timeout): k
                   for k, v in candidates.items()}
        for fut in as_completed(futures):
            results[futures[fut]] = fut.result()

    # 3) Persist to cache (filename = test timestamp).
    cache_results = {}
    for k, lat in results.items():
        cache_results[k] = {
            'latency_ms': round(lat * 1000, 1) if lat != float('inf') else None,
            'reachable': lat != float('inf'),
        }
    cache_path = _save_cache(platform, cache_results)
    print_step(L('speed_cache_saved', cache_path.name))

    return results


def find_fastest_mirror(info: dict, mirrors: dict, config: dict,
                        timeout: float = 3.0) -> str:
    candidates = {k: v for k, v in mirrors.items()
                  if info['platform'] in v.get('platforms', [])}
    if not candidates:
        return get_default_mirror(config)

    # Drop mirrors whose required IP version is unavailable in this env.
    has_v4, has_v6 = detect_ip_support()
    candidates = filter_mirrors_by_ip(candidates, has_v4, has_v6)
    if not candidates:
        return get_default_mirror(config)

    results = _get_speed_results(info['platform'], candidates, timeout)

    for key, lat in sorted(results.items(), key=lambda x: x[1]):
        s = f"{lat*1000:.0f}ms" if lat != float('inf') else L('speed_unreachable')
        print(f"  {key:18s}  {s}")

    best = min(results, key=results.get)
    if results[best] == float('inf'):
        fallback = get_default_mirror(config)
        print(f"\n{L('speed_all_fail', fallback)}")
        return fallback

    print(f"\n{L('speed_select', best, results[best]*1000)}")
    return best


# ===========================================================================
# Speed monitoring during clone
# ===========================================================================

_SPEED_RE = re.compile(r'(\d+[.,]?\d*)\s*(MiB|KiB)/s')
_LOCAL_PHASES = [
    # English
    'updating files', 'checking out files', 'resolving deltas',
    # Chinese (git i18n output for zh_CN / zh_TW)
    '更新文件', '检出文件', '处理 delta', '解析差异', '解析增量',
    '正在更新', '正在检出',
]
_CONN_ERRS = ['could not resolve host', 'failed to connect',
              'connection timed out', 'connection refused',
              'unable to access', 'network is unreachable',
              'no route to host', 'returned error: 502',
              'returned error: 503', 'returned error: 504',
              'remote hung up', 'early eof', 'fetch failed',
              'error: rpc failed']

# Progress display patterns (real-time clone output)
_PROGRESS_SIZE_RE = re.compile(
    r'(\d+(?:[.,]\d+)?)\s*(MiB|KiB)\s*\|\s*(\d+(?:[.,]\d+)?)\s*(MiB|KiB)/s')
_REMOTE_INFO_WORDS = [
    'enumerating', 'counting', 'compressing', 'total',
    '枚举', '计数', '压缩', '总计',
]
_PHASE_LABELS = [
    'receiving objects', '接收对象',
    'resolving deltas', '处理 delta', '解析差异', '解析增量',
    'updating files', '更新文件', 'checking out files', '检出文件',
]


def _render_progress(line: str) -> None:
    """Display human-readable clone progress from a git stderr line."""
    lower = line.lower()
    stripped = line.strip()

    # Remote info lines (enumeration, counting, compression)
    if lower.startswith('remote:'):
        if any(w in lower for w in _REMOTE_INFO_WORDS):
            text = stripped[7:].strip()
            print(f"  {text}")
        return

    # Receiving / downloading progress with size + speed
    m = _PROGRESS_SIZE_RE.search(line)
    if m:
        size_val = float(m.group(1).replace(',', '.'))
        size_unit = m.group(2)
        speed_val = float(m.group(3).replace(',', '.'))
        speed_unit = m.group(4)
        size_mb = size_val / 1024 if size_unit == 'KiB' else size_val
        print(f"\r  {L('clone_receiving')} {size_mb:.1f} MiB"
              f"  @ {speed_val:.1f} {speed_unit}/s   ",
              end='', flush=True)
        return

    # Phase completion: resolving deltas / updating files / checking out
    if any(p in lower for p in _PHASE_LABELS):
        if '100%' in stripped or '完成' in stripped or 'done' in lower:
            # Clear the progress line first, then print the phase result
            print('\r' + ' ' * 60 + '\r', end='')
            label = stripped.split(',')[0].strip()
            print_ok(label)
            return

    # Fatal/error lines — surface immediately
    if 'fatal' in lower or 'error:' in lower:
        print(f"  {stripped}")
    # Fallback: show generic one-off progress lines (not done phases)
    elif any(p in lower for p in _PHASE_LABELS):
        if len(stripped) < 100:
            label = stripped.split(',')[0].strip()
            print_step(label)


def _parse_speed(line: str) -> tuple[float | None, bool]:
    """Returns (speed_kib, is_local_phase)."""
    lower = line.lower()
    if any(p in lower for p in _LOCAL_PHASES):
        return None, True
    m = _SPEED_RE.search(line)
    if not m:
        return None, False
    v = float(m.group(1).replace(',', '.'))
    return (v * 1024 if m.group(2) == 'MiB' else v), False


def _is_connection_error(text: str) -> bool:
    t = text.lower()
    return any(ind in t for ind in _CONN_ERRS)


class SpeedMonitor:
    def __init__(self, min_kib: float, timeout_sec: float):
        self.min = min_kib
        self.timeout = timeout_sec
        self._ok = time.time()
        self._lk = threading.Lock()

    def feed(self, line: str) -> None:
        s, is_local = _parse_speed(line)
        if is_local:
            with self._lk:
                self._ok = time.time()
            return
        if s is not None and s >= self.min:
            with self._lk:
                self._ok = time.time()

    def should_abort(self) -> bool:
        with self._lk:
            return (time.time() - self._ok) > self.timeout

    @property
    def stalled(self) -> float:
        with self._lk:
            return time.time() - self._ok


def _stderr_reader(proc, monitor, collected, abort):
    show_progress = sys.stderr.isatty()
    try:
        for line in proc.stderr:
            collected.append(line)
            monitor.feed(line)
            if show_progress:
                _render_progress(line)
            if monitor.should_abort():
                abort.set()
                _safe_kill(proc)
                return
    except (ValueError, OSError):
        pass
    finally:
        # Clear any leftover \r progress line
        if show_progress:
            print('\r' + ' ' * 60 + '\r', end='')


def _safe_kill(proc) -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                           capture_output=True)
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            time.sleep(0.5)
            if proc.poll() is None:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def clone_with_monitor(mirror_url: str, target_dir: str,
                       clone_args: list, min_kib: float,
                       timeout_sec: float) -> dict:
    cmd = ['git', 'clone', '--progress'] + clone_args + [mirror_url]
    if target_dir:
        cmd.append(target_dir)

    print_step(f"git {' '.join(cmd[1:])}")
    print()

    mon = SpeedMonitor(min_kib, timeout_sec)
    collected: list[str] = []
    abort = threading.Event()

    try:
        kw: dict = {'stderr': subprocess.PIPE, 'stdout': subprocess.DEVNULL,
                    'text': True, 'encoding': 'utf-8', 'errors': 'replace'}
        if os.name != 'nt':
            kw['preexec_fn'] = os.setsid

        proc = subprocess.Popen(cmd, **kw)
        t = threading.Thread(target=_stderr_reader,
                             args=(proc, mon, collected, abort), daemon=True)
        t.start()

        while proc.poll() is None:
            if mon.should_abort() or abort.is_set():
                print_err(L('speed_low', min_kib/1024, mon.stalled))
                _safe_kill(proc)
                t.join(timeout=2)
                return {'status': 'speed_timeout', 'stalled': mon.stalled}
            time.sleep(0.5)

        t.join(timeout=2)
        rc = proc.returncode

        if rc == 0:
            return {'status': 'ok'}

        full = ''.join(collected)
        if _is_connection_error(full):
            errs = [l.strip() for l in collected
                    if 'error' in l.lower() or 'fatal' in l.lower()]
            reason = '\n'.join(errs) if errs else full[-500:]
            return {'status': 'connection_error', 'reason': reason}

        reason = '\n'.join(l.strip() for l in collected[-5:] if l.strip())
        return {'status': 'other_error', 'code': rc, 'reason': reason}

    except FileNotFoundError:
        return {'status': 'other_error', 'code': -1, 'reason': L('git_not_found')}
    except Exception as e:
        return {'status': 'other_error', 'code': -1, 'reason': str(e)}


# ===========================================================================
# Core clone flow with auto-retry & mirror switching
# ===========================================================================

def clone_with_fallback(info: dict, url: str, args: argparse.Namespace,
                        config: dict, mirror_keys: list) -> int:
    mirrors = get_mirrors(config)
    min_kib = get_speed_threshold(config)
    speed_to = get_speed_timeout(config)
    max_retry = get_connect_retries(config)

    if args.min_speed is not None:
        min_kib = int(args.min_speed * 1024)
    if args.speed_timeout is not None:
        speed_to = args.speed_timeout

    td = args.target if args.target else info['repo']
    tp = Path(td).resolve()

    base = []
    if args.branch:
        base.extend(['-b', args.branch])
    if args.depth:
        base.extend(['--depth', str(args.depth)])
    if args.single_branch:
        base.append('--single-branch')

    if not mirror_keys:
        print_warn(L('no_mirrors_for_plat', info['platform']))
        print_step(L('direct_clone'))
        run_git(['clone', '--progress'] + base + [url])
        return 0 if tp.exists() else 1

    tried = []
    conn_errs = 0

    for i, mk in enumerate(mirror_keys):
        if mk not in mirrors:
            continue
        mir = mirrors[mk]
        mu = apply_mirror(info, mir)
        tried.append(mk)

        if i > 0:
            print_separator()
            print(L('mirror_switch', i+1, len(mirror_keys), mir['name']))

        retry = max_retry
        while retry > 0:
            if tp.exists():
                print_step(L('cleanup', tp))
                shutil.rmtree(tp, ignore_errors=True)

            res = clone_with_monitor(
                mu, args.target if args.target else '',
                base, min_kib, speed_to)

            st = res['status']

            if st == 'ok':
                print_ok(L('clone_success', mir['name']))
                if not args.no_set_url and tp.exists():
                    _set_remote(tp, url)
                return 0

            if st == 'speed_timeout':
                print_warn(L('speed_bad', min_kib/1024,
                           res.get('stalled', speed_to)))
                break

            if st == 'connection_error':
                retry -= 1
                conn_errs += 1
                reason = res.get('reason', '')
                if retry > 0:
                    print_warn(L('conn_retry', max_retry-retry, max_retry))
                    print(f"      {L('reason')}: {reason[:200]}")
                    time.sleep(1)
                else:
                    print_err(L('conn_exhausted', mk, max_retry))
                    break
            else:
                print_err(L('clone_fail_code', res.get('code'),
                          res.get('reason', '?')[:300]))
                break

    print_separator()
    print_err(L('clone_failed_all'))
    if conn_errs:
        print_warn(L('conn_count', conn_errs))
    print_step(L('tried_mirrors', ', '.join(tried)))
    print()
    print_step(L('final_direct'))
    run_git(['clone', '--progress'] + base + [url])
    return 1


def _set_remote(tp: Path, url: str) -> None:
    r = run_git(['-C', str(tp), 'remote', 'set-url', 'origin', url],
                capture_output=True, text=True)
    if r.returncode == 0:
        v = run_git(['-C', str(tp), 'remote', 'get-url', 'origin'],
                    capture_output=True, text=True)
        print_ok(f"remote 'origin' -> {v.stdout.strip()}")
    else:
        print_warn(L('remote_fail', tp, url))


def _resolve_mirror_list(args, info, config):
    mirrors = get_mirrors(config)
    plat = info['platform']
    cand = {k: v for k, v in mirrors.items()
            if plat in v.get('platforms', [])}

    # Filter out mirrors that need an IP version this env cannot use.
    # Only applies to the auto-selected fallback list, not to an explicit
    # --mirror choice (the user picked it deliberately).
    if not args.mirror:
        has_v4, has_v6 = detect_ip_support()
        cand = filter_mirrors_by_ip(cand, has_v4, has_v6)

    if args.fastest:
        fastest = find_fastest_mirror(info, cand, config, args.timeout)
        return [fastest] + [k for k in cand if k != fastest]

    if args.mirror:
        if args.mirror not in mirrors:
            die(L('unknown_mirror', args.mirror, ', '.join(mirrors)))
        return [args.mirror] + [k for k in cand if k != args.mirror]

    d = get_default_mirror(config)
    return ([d] if d in cand else []) + [k for k in cand if k != d]


# ===========================================================================
# Terminal output helpers
# ===========================================================================

class Color:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    RED = '\033[91m'

    @staticmethod
    def enable() -> bool:
        if os.name == 'nt':
            try:
                import ctypes
                k = ctypes.windll.kernel32
                h = k.GetStdHandle(-11)
                m = ctypes.c_ulong()
                k.GetConsoleMode(h, ctypes.byref(m))
                k.SetConsoleMode(h, m.value | 0x0004)
                return True
            except Exception:
                return False
        return sys.stdout.isatty()

    @staticmethod
    def c(text: str, code: str) -> str:
        return f"{code}{text}{Color.RESET}" if Color._enabled else text


Color._enabled = Color.enable()


def print_separator():
    print(Color.c(f"\n{'='*55}", Color.CYAN))


def print_header(title: str):
    print(Color.c(f"\n{'='*55}", Color.CYAN))
    print(Color.c(f"  {title}", Color.BOLD))
    print(Color.c(f"{'='*55}", Color.CYAN))


def print_step(msg: str):
    print(Color.c(f"  -> {msg}", Color.CYAN))


def print_ok(msg: str):
    print(Color.c(f"  OK {msg}", Color.GREEN))


def print_warn(msg: str):
    print(Color.c(f"  !  {msg}", Color.YELLOW))


def print_err(msg: str):
    print(Color.c(f"  X  {msg}", Color.RED))


def die(msg: str, code: int = 1):
    print_err(msg)
    sys.exit(code)


def run_git(args: list, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(['git'] + args, **kw)


# ===========================================================================
# Setup mode (called by setup.bat)
# ===========================================================================

def _cmd_setup() -> int:
    """Interactive setup: check Git, add to PATH, verify."""
    script = Path(__file__).resolve()
    tool_dir = script.parent
    win_dir = tool_dir / 'windows'

    print_header(L('setup_title'))
    print()

    # 1. Check Git
    print_step(L('setup_check_git'))
    try:
        r = subprocess.run(['git', '--version'], capture_output=True, text=True)
        if r.returncode == 0:
            print_ok(L('setup_git_ok', r.stdout.strip().split()[-1]))
        else:
            print_err(L('setup_git_missing'))
            input(L('setup_press_enter'))
            return 1
    except FileNotFoundError:
        print_err(L('setup_git_missing'))
        input(L('setup_press_enter'))
        return 1

    # 2. PATH install
    print()
    print_header(L('setup_path_title'))
    print(f"  {str(win_dir)}")
    print()
    choice = input(L('setup_path_prompt')).strip()
    print()

    if choice == '3':
        print_step(L('setup_manual', str(script), str(script)))
        print()
        print_header(L('setup_verify'))
        run_git(['--version'])
        return 0

    target = str(win_dir)
    if choice == '2':
        r = subprocess.run(['setx', '/M', 'PATH',
                            f"{os.environ.get('PATH','')};{target}"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            print_ok(L('setup_system_ok'))
        else:
            print_warn(L('setup_path_fail', target))
    else:
        r = subprocess.run(['setx', 'PATH',
                            f"{os.environ.get('PATH','')};{target}"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            print_ok(L('setup_user_ok'))
        else:
            print_warn(L('setup_path_fail', target))

    # 3. Verify
    print()
    print_header(L('setup_verify'))
    print()
    config = load_config()
    mirrors = get_mirrors(config)
    default = get_default_mirror(config)
    for key, m in mirrors.items():
        print(f"  {Color.c(key, Color.BOLD):20s} {m['name']}")
    th = get_speed_threshold(config) / 1024
    print(f"\n  {L('mirror_default')}: {default}  |  "
          f"{L('mirror_threshold')}: {th:.0f} MB/s")

    # 4. Done
    print()
    print_header(L('setup_done'))
    print(f"\n{L('setup_usage')}")
    print()

    if choice == '3':
        pass
    else:
        print_step(L('setup_new_terminal'))

    return 0


# ===========================================================================
# Main
# ===========================================================================

def main() -> int:
    config = load_config()
    mirrors = get_mirrors(config)
    default = get_default_mirror(config)
    speed_mb = get_speed_threshold(config) / 1024
    speed_to = get_speed_timeout(config)
    retries = get_connect_retries(config)

    epilog = f"""\
{L('mirror_usage1')}
  fast-clone --mirror github-akams https://github.com/user/repo
  fast-clone --fastest https://github.com/user/repo
  fast-clone -b main --depth 1 https://github.com/user/repo
  fast-clone --list-mirrors
  fast-clone --dry-run https://github.com/user/repo

{L('mirror_list_title')} ({default}):  gh-proxy-org, kkgithub, gitclone, github-akams, github-ur1, gh-proxy-v4, gh-proxy-v6, gh-proxy-cdn, gh-proxy-com, ghproxy-net, jihulab

{L('mirror_threshold')}: {speed_mb:.0f} MB/s  |  {L('mirror_timeout')}: {speed_to}s  |  {L('mirror_retries')}: {retries}x
"""

    parser = argparse.ArgumentParser(
        prog='fast-clone',
        description=L('mirror_list_title'),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog,
    )

    h_url = {'zh': '官方仓库地址 (如 https://github.com/user/repo)',
             'en': 'Official repo URL (e.g. https://github.com/user/repo)'}

    parser.add_argument('url', nargs='?', help=Lh(h_url['zh'], h_url['en']))

    h_mirror = {'zh': f'指定镜像站 (默认: {default})', 'en': f'Specify mirror (default: {default})'}
    h_fastest = {'zh': '自动测速并选择延迟最低的镜像站', 'en': 'Auto-test and pick fastest mirror'}
    h_timeout = {'zh': '测速超时秒数 (默认: 3)', 'en': 'Speed-test timeout seconds (default: 3)'}
    h_minspeed = {'zh': f'最低下载速度 MB/s (默认: {speed_mb:.0f})', 'en': f'Min speed MB/s (default: {speed_mb:.0f})'}
    h_speedto = {'zh': f'超时秒数 (默认: {speed_to})', 'en': f'Speed timeout seconds (default: {speed_to})'}
    h_list = {'zh': '列出所有可用镜像站', 'en': 'List all available mirrors'}
    h_branch = {'zh': '克隆指定分支', 'en': 'Branch to clone'}
    h_depth = {'zh': '浅克隆深度', 'en': 'Shallow clone depth'}
    h_single = {'zh': '仅克隆单个分支', 'en': 'Clone single branch only'}
    h_target = {'zh': '目标目录名', 'en': 'Target directory name'}
    h_noset = {'zh': '不重置 remote (调试用)', 'en': 'Do not reset remote (debug)'}
    h_dry = {'zh': '预览 URL 转换，不实际克隆', 'en': 'Preview URL transform, no clone'}

    parser.add_argument('--mirror', '-m', default=None, help=Lh(h_mirror['zh'], h_mirror['en']))
    parser.add_argument('--fastest', '-f', action='store_true', help=Lh(h_fastest['zh'], h_fastest['en']))
    parser.add_argument('--timeout', '-t', type=float, default=3.0, help=Lh(h_timeout['zh'], h_timeout['en']))
    parser.add_argument('--min-speed', type=float, help=Lh(h_minspeed['zh'], h_minspeed['en']))
    parser.add_argument('--speed-timeout', type=int, help=Lh(h_speedto['zh'], h_speedto['en']))
    parser.add_argument('--list-mirrors', '-l', action='store_true', help=Lh(h_list['zh'], h_list['en']))
    parser.add_argument('--branch', '-b', help=Lh(h_branch['zh'], h_branch['en']))
    parser.add_argument('--depth', '-d', type=int, help=Lh(h_depth['zh'], h_depth['en']))
    parser.add_argument('--single-branch', action='store_true', help=Lh(h_single['zh'], h_single['en']))
    parser.add_argument('--target', help=Lh(h_target['zh'], h_target['en']))
    parser.add_argument('--no-set-url', action='store_true', help=Lh(h_noset['zh'], h_noset['en']))
    parser.add_argument('--dry-run', '-n', action='store_true', help=Lh(h_dry['zh'], h_dry['en']))
    parser.add_argument('--setup', action='store_true',
                        help=argparse.SUPPRESS)

    args, extra = parser.parse_known_args()
    args.extra = extra

    # --setup (called by setup.bat)
    if args.setup:
        return _cmd_setup()

    # --list-mirrors
    if args.list_mirrors:
        print_header(L('mirror_list_title'))
        print()
        for key, m in mirrors.items():
            print(f"  {Color.c(key, Color.BOLD)}")
            print(f"    {'name':10s}: {m['name']}")
            print(f"    {'platforms':10s}: {', '.join(m.get('platforms', []))}")
            print(f"    {'desc':10s}: {m['description']}")
            print()
        th = get_speed_threshold(config)/1024
        print(f"{L('mirror_default')}: {default}  |  "
              f"{L('mirror_threshold')}: {th:.0f} MB/s  |  "
              f"{L('mirror_timeout')}: {get_speed_timeout(config)}s  |  "
              f"{L('mirror_retries')}: {get_connect_retries(config)}x")
        return 0

    if not args.url:
        parser.print_help()
        return 1

    info = parse_git_url(args.url)

    if info['platform'] == 'unknown':
        print_warn(L('unknown_platform', args.url))
        if args.dry_run:
            print_step(L('dry_run_unknown'))
            return 0
        print_step(L('direct_clone'))
        run_git(_build_clone_args(args, args.url))
        return 0

    # Offer to clean up speed-test cache files older than 7 days.
    prompt_delete_expired_caches()

    mirror_keys = _resolve_mirror_list(args, info, config)

    print_header(L('repo_info'))
    print(f"  {L('repo_platform') + ':':12s} {info['platform']}")
    print(f"  {L('repo_name') + ':':12s} {info['owner']}/{info['repo']}")
    print(f"  {L('repo_official') + ':':12s} {info['original']}")
    fm = mirrors.get(mirror_keys[0], {})
    print(f"  {L('repo_preferred') + ':':12s} {fm.get('name', mirror_keys[0])} ({mirror_keys[0]})")
    if len(mirror_keys) > 1:
        tail = ' ...' if len(mirror_keys) > 4 else ''
        print(f"  {L('repo_fallback') + ':':12s} {', '.join(mirror_keys[1:4])}{tail}")
    if args.target:
        print(f"  {L('repo_target') + ':':12s} {args.target}")
    if args.branch:
        print(f"  {L('repo_branch') + ':':12s} {args.branch}")
    if args.depth:
        print(f"  {L('repo_depth') + ':':12s} depth={args.depth}")

    if args.dry_run:
        print_header(L('dry_run_title'))
        for mk in mirror_keys[:5]:
            if mk in mirrors:
                print(f"  {mk:18s} -> {apply_mirror(info, mirrors[mk])}")
        print_step(L('dry_run_msg'))
        return 0

    print_header(L('clone_start'))
    return clone_with_fallback(info, args.url, args, config, mirror_keys)


def _build_clone_args(args, url):
    a = ['clone', '--progress']
    if args.branch:
        a.extend(['-b', args.branch])
    if args.depth:
        a.extend(['--depth', str(args.depth)])
    if args.single_branch:
        a.append('--single-branch')
    a.append(url)
    if args.target:
        a.append(args.target)
    a.extend(args.extra)
    return a


if __name__ == '__main__':
    sys.exit(main())
