#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
i18n - bilingual (Simplified Chinese / English) text for fast-clone.

All user-visible strings live here. Access via L(key, *args).
Language is auto-detected from the system; override with FASTCLONE_LANG=zh|en.
"""

from __future__ import annotations

import os


# ===========================================================================
# System language detection
# ===========================================================================

def detect_language() -> str:
    """Detect system language. Returns 'zh' (Simplified Chinese) or 'en'."""
    # Allow explicit override via environment variable
    env_lang = os.environ.get('FASTCLONE_LANG', '').lower().strip()
    if env_lang in ('zh', 'cn', 'chinese', 'zh-cn', 'zh_cn', 'zh-hans'):
        return 'zh'
    if env_lang in ('en', 'english'):
        return 'en'

    zh_cn_lid = 0x0804  # zh-CN (Simplified Chinese) only

    # ---- Windows: try multiple locale / UI language APIs ----
    if os.name == 'nt':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32

            # 1) User default UI language (most accurate for display language)
            lid = kernel32.GetUserDefaultUILanguage()
            if lid == zh_cn_lid:
                return 'zh'

            # 2) System default UI language (fallback)
            try:
                slid = kernel32.GetSystemDefaultUILanguage()
                if slid == zh_cn_lid:
                    return 'zh'
            except Exception:
                pass

            # 3) User locale — extract primary language from LCID
            try:
                lcid = kernel32.GetUserDefaultLCID()
                if (lcid & 0x03FF) == 0x04:  # LANG_CHINESE
                    # Only zh-CN sublang (0x02); exclude zh-TW/HK/SG/MO
                    if ((lcid >> 10) & 0x3F) == 0x02:
                        return 'zh'
            except Exception:
                pass

            # 4) System locale
            try:
                slcid = kernel32.GetSystemDefaultLCID()
                if (slcid & 0x03FF) == 0x04:
                    if ((slcid >> 10) & 0x3F) == 0x02:
                        return 'zh'
            except Exception:
                pass
        except Exception:
            pass

    # ---- Unix / environment variables ----
    for var in ('LC_ALL', 'LC_MESSAGES', 'LANG', 'LANGUAGE'):
        v = os.environ.get(var, '')
        if v.lower().startswith(('zh_cn', 'zh-cn', 'zh_hans', 'zh-hans', 'chinese_simplified')):
            return 'zh'

    # ---- Python locale module ----
    # NOTE: locale.getdefaultlocale() is deprecated since Python 3.11,
    # removed in 3.15. Use locale.getlocale() instead (returns current
    # locale set via setlocale; falls back to (None, None) if unset).
    try:
        import locale
        loc = locale.getlocale()[0]
        if loc and loc.lower().startswith(('zh_cn',)):
            return 'zh'
    except Exception:
        pass

    # Default to Simplified Chinese: this tool ships CN mirror accelerators
    # (gh-proxy, kkgithub, gitclone ...) and primarily targets CN users.
    # Set FASTCLONE_LANG=en to force English output.
    return 'zh'


LANG = detect_language()


# ===========================================================================
# Bilingual text table
# ===========================================================================

_T = {
    'mirror_list_title':    {'zh': '可用镜像站', 'en': 'Available Mirrors'},
    'mirror_default':       {'zh': '默认', 'en': 'Default'},
    'mirror_threshold':     {'zh': '阈值', 'en': 'Threshold'},
    'mirror_timeout':       {'zh': '超时', 'en': 'Timeout'},
    'mirror_retries':       {'zh': '重试', 'en': 'Retries'},
    'mirror_usage1':        {'zh': '用法: fast-clone --mirror <名称> <仓库地址>',
                             'en': 'Usage: fast-clone --mirror <name> <repo-url>'},

    'repo_info':            {'zh': '仓库信息', 'en': 'Repository Info'},
    'repo_platform':        {'zh': '平台', 'en': 'Platform'},
    'repo_name':            {'zh': '仓库', 'en': 'Repository'},
    'repo_official':        {'zh': '官方地址', 'en': 'Official URL'},
    'repo_preferred':       {'zh': '首选镜像', 'en': 'Preferred Mirror'},
    'repo_fallback':        {'zh': '备用镜像', 'en': 'Fallback Mirrors'},
    'repo_target':          {'zh': '目标目录', 'en': 'Target Dir'},
    'repo_branch':          {'zh': '分支', 'en': 'Branch'},
    'repo_depth':           {'zh': '浅克隆', 'en': 'Shallow Clone'},

    'clone_start':          {'zh': '开始克隆', 'en': 'Cloning'},
    'clone_success':        {'zh': '克隆成功 (镜像: {})', 'en': 'Clone success (mirror: {})'},
    'clone_receiving':      {'zh': '接收对象', 'en': 'Receiving objects'},

    'speed_low':            {'zh': '下载速度持续低于 {} MB/s 已达 {} 秒，自动中止',
                             'en': 'Speed below {} MB/s for {}s, aborting'},
    'speed_bad':            {'zh': '速度不达标 ({} MB/s)，停滞 {:.0f}s',
                             'en': 'Speed below threshold ({} MB/s), stalled {:.0f}s'},
    'conn_retry':           {'zh': '连接失败，重试 ({}/{})',
                             'en': 'Connection failed, retry ({}/{})'},
    'conn_exhausted':       {'zh': '镜像 {} 连接失败 {} 次，切换',
                             'en': 'Mirror {} failed {} times, switching'},
    'conn_count':           {'zh': '共 {} 次连接错误', 'en': '{} total connection errors'},
    'mirror_switch':        {'zh': '切换到镜像 [{}/{}]: {}',
                             'en': 'Switching to mirror [{}/{}]: {}'},

    'remote_fail':          {'zh': '重置 remote 失败，请手动: git -C {} remote set-url origin {}',
                             'en': 'Failed to set remote, run: git -C {} remote set-url origin {}'},

    'speed_testing':        {'zh': '正在测速 {} 个镜像站 ...',
                             'en': 'Testing {} mirrors ...'},
    'speed_unreachable':    {'zh': '不可达', 'en': 'unreachable'},
    'speed_all_fail':       {'zh': '所有镜像均不可达，回退到默认: {}',
                             'en': 'All mirrors unreachable, fallback: {}'},
    'speed_select':         {'zh': '自动选择: {} ({:.0f}ms)',
                             'en': 'Auto-selected: {} ({:.0f}ms)'},
    'speed_cached':         {'zh': '使用缓存测速结果 ({}，{} 天前)',
                             'en': 'Using cached speed test ({}，{} days ago)'},
    'speed_cache_delete_q': {'zh': '检测到 {} 个过期缓存文件 (>7 天)，是否删除? [Y/n]: ',
                             'en': 'Found {} expired cache file(s) (>7 days). Delete? [Y/n]: '},
    'speed_cache_deleted':  {'zh': '已删除 {} 个过期缓存文件',
                             'en': 'Deleted {} expired cache file(s)'},
    'speed_cache_kept':     {'zh': '保留过期缓存文件',
                             'en': 'Kept expired cache file(s)'},
    'speed_cache_saved':    {'zh': '测速结果已缓存: {}',
                             'en': 'Speed test result cached: {}'},
    'speed_cache_skip_v6':  {'zh': '跳过 {} (当前环境不支持 IPv6)',
                             'en': 'Skip {} (IPv6 not supported in current env)'},
    'speed_cache_skip_v4':  {'zh': '跳过 {} (当前环境不支持 IPv4)',
                             'en': 'Skip {} (IPv4 not supported in current env)'},
    'ip_detect':            {'zh': '检测网络协议支持: IPv4={} IPv6={}',
                             'en': 'Network protocol support: IPv4={} IPv6={}'},

    'dry_run_title':        {'zh': 'URL 转换预览', 'en': 'URL Transform Preview'},
    'dry_run_msg':          {'zh': '--dry-run，未执行实际克隆', 'en': '--dry-run, no clone performed'},
    'dry_run_unknown':      {'zh': '--dry-run，将直接 git clone 原始地址',
                             'en': '--dry-run, will git clone original URL directly'},

    'unknown_platform':     {'zh': '未能识别平台: {}', 'en': 'Unknown platform: {}'},
    'unknown_mirror':       {'zh': "未知镜像 '{}'，可用: {}", 'en': "Unknown mirror '{}', available: {}"},
    'direct_clone':         {'zh': '直接 git clone ...', 'en': 'Direct git clone ...'},
    'cleanup':              {'zh': '清理残留: {}', 'en': 'Cleaning up: {}'},
    'check_network':        {'zh': '请检查网络连接，或稍后重试。', 'en': 'Check network, try again later.'},
    'tried_mirrors':        {'zh': '已尝试: {}', 'en': 'Tried: {}'},
    'git_not_found':        {'zh': 'git 命令未找到', 'en': 'git command not found'},
    'no_mirrors_for_plat':  {'zh': "平台 '{}' 没有配置任何镜像站",
                             'en': "No mirrors for platform '{}'"},
    'final_direct':         {'zh': '最后一次尝试: 直接从官方仓库克隆 ...',
                             'en': 'Last attempt: direct clone from official ...'},
    'clone_failed_all':     {'zh': '所有镜像均已尝试，克隆失败',
                             'en': 'All mirrors exhausted, clone failed'},
    'reason':               {'zh': '原因', 'en': 'Reason'},
    'clone_fail_code':      {'zh': '克隆失败 (code={}): {}', 'en': 'Clone failed (code={}): {}'},

    # setup
    'setup_title':          {'zh': 'fast-clone 安装程序', 'en': 'fast-clone Setup'},
    'setup_check_git':      {'zh': '检查 Git 环境 ...', 'en': 'Checking Git ...'},
    'setup_git_ok':         {'zh': '找到 Git {}', 'en': 'Found Git {}'},
    'setup_git_missing':    {'zh': '未在 PATH 中找到 Git。请安装 Git:\n  https://git-scm.com/downloads/\nGit 安装程序默认自动添加 PATH。',
                             'en': 'Git not found in PATH. Please install Git:\n  https://git-scm.com/downloads/\nThe Git installer adds itself to PATH automatically.'},
    'setup_path_title':     {'zh': '将 fast-clone 添加到系统 PATH', 'en': 'Add fast-clone to system PATH'},
    'setup_path_prompt':    {'zh': '选择添加方式:\n  [1] 用户 PATH (推荐，无需管理员权限)\n  [2] 系统 PATH (需管理员权限)\n  [3] 暂不添加，手动使用\n请选择 [1-3]: ',
                             'en': 'Choose install method:\n  [1] User PATH (recommended, no admin)\n  [2] System PATH (requires admin)\n  [3] Skip, use manually\nSelect [1-3]: '},
    'setup_user_ok':        {'zh': '已添加到用户 PATH', 'en': 'Added to User PATH'},
    'setup_system_ok':      {'zh': '已添加到系统 PATH', 'en': 'Added to System PATH'},
    'setup_path_already':   {'zh': '{} 已在 PATH 中，无需重复添加', 'en': '{} already in PATH, nothing to add'},
    'setup_path_fail':      {'zh': '添加失败，请手动将以下目录添加到 PATH:\n  {}',
                             'en': 'Failed to add. Manually add this to PATH:\n  {}'},
    'setup_verify':         {'zh': '验证安装 ...', 'en': 'Verifying ...'},
    'setup_done':           {'zh': '安装完成!', 'en': 'Setup Complete!'},
    'setup_usage':          {'zh': '用法:\n  fast-clone https://github.com/user/repo\n  fast-clone --fastest https://github.com/user/repo\n  fast-clone --list-mirrors\n\n编辑 mirror.json 可新增/禁用镜像。',
                             'en': 'Usage:\n  fast-clone https://github.com/user/repo\n  fast-clone --fastest https://github.com/user/repo\n  fast-clone --list-mirrors\n\nEdit mirror.json to add/remove mirrors.'},
    'setup_manual':         {'zh': '手动使用方式:\n  python "{}" [参数] [仓库地址]\n\n或创建别名:\n  doskey fast-clone=python "{}" $*',
                             'en': 'Manual usage:\n  python "{}" [args] [repo-url]\n\nOr create alias:\n  doskey fast-clone=python "{}" $*'},
    'setup_new_terminal':   {'zh': '新终端窗口可直接使用 fast-clone 命令。当前终端需重新打开。',
                             'en': 'Open a new terminal to use the fast-clone command.'},
    'setup_press_enter':    {'zh': '按 Enter 退出 ...',
                             'en': 'Press Enter to exit ...'},
}


def L(key: str, *args) -> str:
    """Look up a bilingual string by key, formatted with args."""
    text = _T.get(key, {}).get(LANG) or _T.get(key, {}).get('en', key)
    return text.format(*args) if args else text


def Lh(zh: str, en: str) -> str:
    """Inline bilingual helper for one-off strings (e.g. argparse help)."""
    return zh if LANG == 'zh' else en
