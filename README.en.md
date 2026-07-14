# fast-clone

[中文版](README.md) | **English**

## 📑 Table of Contents

- [🏆 Why Choose Us](#why-choose-us)
- [📦 Get Started](#get-started)
- [🚀 Quick Start](#quick-start)
- [⚙️ Install](#install)
  - [Windows](#windows)
  - [Linux](#linux)
  - [Prerequisites](#prerequisites)
- [🪞 Available Mirrors](#available-mirrors-11)
- [🛡️ Auto-Protection](#auto-protection)
- [➕ Adding / Disabling Mirrors](#adding-disabling-mirrors)
- [🌐 IPv4 / IPv6 Auto-Detection](#ipv4-ipv6-auto-detection)
- [💾 Speed-Test Result Cache](#speed-test-result-cache)
- [⚡ GitHub Actions Daily Mirror-Status Release](#github-actions-daily-mirror-status-release)
- [📋 Full Options](#full-options)
- [📁 Project Structure](#project-structure)
- [🔄 Keeping Your Copy Up to Date](#keeping-your-copy-up-to-date)
- [⚠️ Notes](#notes)

> **Pure vibe coding** — entirely AI-assisted, zero hand-written code.

> [!NOTE]
> Mirror-accelerated clone for GitHub/GitLab repos, with **automatic remote reset to the official URL** after cloning.  
> **Core value**: Download fast from mirrors, pull/push safely to official repos.  
> **Zero external dependencies**: Python standard library only. Mirror config lives in `mirror.json`, bilingual strings in `i18n.py`.

## 🏆 Why Choose Us

- **Safe & worry-free** — Auto-resets remote to official URL after cloning, download fast, `pull`/`push` safe
- **Auditable code** — Pure-text Python source, no binaries, no obfuscation, no compiled artifacts, fully public and reviewable
- **Zero dependencies** — Python standard library only, no `pip install` needed
- **Smart protection** — Speed monitoring + auto-retry + fallback to direct, very low failure rate
- **Multi-mirror support** — 11 built-in mirrors covering prefix proxy / domain replace / path prefix and more
- **Network adaptive** — Auto-detects IPv4/IPv6 support, skips unavailable mirrors
- **Speed-test cache** — 7-day result reuse, avoids repeated testing
- **Daily status report** — GitHub Actions tests mirror reachability daily and publishes via Release
- **Bilingual** — Auto-detects and switches between Chinese/English
- **Highly customizable** — Edit `mirror.json` to add/remove mirrors, takes effect next run

## Get Started

> [!TIP]
> Not sure which mirror is fastest? Add the `--fastest` flag and the tool will speed-test and pick the lowest-latency mirror automatically.

```bash
git clone https://github.com/bcggxx/fast-clone.git
cd fast-clone

# Windows
windows\setup.bat

# Linux
bash linux/setup.sh

# Usage
fast-clone https://github.com/user/repo
fast-clone --fastest https://github.com/user/repo
fast-clone -l                    # list all mirrors
fast-clone -n https://github.com/user/repo   # dry-run
```

## Install

> [!IMPORTANT]
> Do **not move the repo directory after install**, or re-run the setup script so the `fast-clone` command works again.

### Windows

1. Keep the repo at a fixed location (e.g. `D:\tools\fast-clone`), do not move
2. Double-click `windows\setup.bat` or run:

```cmd
cd fast-clone\windows
setup.bat
```

The script checks Python/Git (PATH only), adds `fast-clone\windows\` to PATH. Use `fast-clone` from any terminal.

### Linux

1. Keep the repo at a fixed location (e.g. `~/tools/fast-clone`), do not move
2. Run the setup script:

```bash
cd fast-clone/linux
bash setup.sh
```

Supports Debian/CentOS/Fedora/Arch. Installs to `~/.local/bin` or `/usr/local/bin` by creating a wrapper script.

### Prerequisites

| Dependency | Install |
|-----------|---------|
| Python 3.7+ | [python.org](https://www.python.org/downloads/) or package manager |
| Git | [git-scm.com](https://git-scm.com/downloads/) or package manager |

## Available Mirrors (11)

| key | Mirror | Type | Latency | Success | Description |
|-----|--------|------|---------|---------|-------------|
| `gh-proxy-org` * | gh-proxy.org | prefix proxy | 188ms | 2/3 | Default mirror |
| `gh-proxy-v4` | v4.gh-proxy.org | prefix proxy | 133ms | 3/3 | IPv4-only smart DNS |
| `gh-proxy-v6` | v6.gh-proxy.org | prefix proxy | 206ms | 3/3 | IPv6/IPv4 dual-stack |
| `gh-proxy-cdn` | cdn.gh-proxy.org | prefix proxy | 230ms | 3/3 | Fastly CDN |
| `kkgithub` | kkgithub.com | domain replace | 225ms | 1/3 | — |
| `github-akams` | github.akams.cn | prefix proxy | 34ms | 3/3 | — |
| `gitclone` | gitclone.com | path prefix | 59ms | 2/3 | — |
| `github-ur1` | github.ur1.fun | domain replace | 197ms | 3/3 | — |
| `gh-proxy-com` | gh-proxy.com | prefix proxy | 34ms | 2/3 | — |
| `ghproxy-net` | ghproxy.net | prefix proxy | 255ms | 3/3 | — |
| `jihulab` | jihulab.com | GitLab CN mirror | 52ms | 3/3 | — |

> `*` Default mirror. 2026-07-14 Windows TCP port 443 test, 3-run average.

## Auto-Protection

- **Speed monitoring**: < 1 MB/s for 3 min → abort, cleanup, switch mirror
- **Connection retry**: 3 retries per mirror, then switch on failure
- **Last-resort direct**: falls back to official repo after all mirrors fail

```bash
# Custom thresholds
fast-clone --min-speed 2 --speed-timeout 120 https://github.com/user/repo
```

## Adding / Disabling Mirrors

Edit the `mirror.json` file:

```json
"my-mirror": {
    "name": "my-mirror.example.com",
    "platforms": ["github"],
    "transform": "domain_replace",
    "old": "github.com",
    "new": "my-mirror.example.com",
    "test_host": "my-mirror.example.com",
    "ip": "dual",
    "description": "My custom mirror"
}
```

The `ip` field controls protocol filtering (the host's IPv4/IPv6 support is auto-detected at runtime; mirrors requiring an unavailable protocol are skipped):

| Value | Meaning |
|-------|---------|
| `dual` | Dual-stack, both IPv4/IPv6 (default) |
| `v4` | IPv4-only endpoint |
| `v6` | IPv6-only endpoint |

4 transform strategies:

| Strategy | Example |
|----------|---------|
| `prefix` | `https://mirror.com/{full-official-url}` |
| `domain_replace` | `github.com` → `mirror.com` |
| `path_prefix` | `https://mirror.com/github.com/owner/repo` |
| `domain_suffix` | `github.com` → `github.com.mirror.org` |

Delete an entry to disable. Change the top-level `"default"` in `mirror.json` to switch the default mirror. Changes take effect on next run.

## IPv4 / IPv6 Auto-Detection

On clone startup the host's IPv4/IPv6 support is probed in parallel — Cloudflare 1.1.1.1 / 2606:4700:4700::1111 first, falling back to Tencent DNSPod 119.29.29.29 / 2402:4e00:: on failure so a Cloudflare-only block does not cause a false negative; the result is cached for the process:

- No IPv6 → skip `ip: "v6"` mirrors (e.g. `gh-proxy-v6`)
- No IPv4 → skip `ip: "v4"` mirrors (e.g. `gh-proxy-v4`, `gitclone`)
- An explicit `--mirror` choice bypasses filtering (respects user intent)

## Speed-Test Result Cache

`--fastest` results are saved under `speedcache/`, named by test time (e.g. `2026-07-06_055454.json`):

- **Cache hit**: results for the same platform within 7 days are reused, skipping the live test
- **Auto-expiry**: caches older than 7 days are treated as stale and re-tested
- **Cleanup prompt**: when running a clone command, expired cache files trigger a delete prompt (default `Y` to delete, `n` to keep)

The cache only stores latency data; it never modifies the available mirror list in `mirror.json`.

## GitHub Actions Daily Mirror-Status Release

The repo ships `.github/workflows/mirror-test.yml`, which runs `scripts/test_mirrors.py` daily at 08:00 UTC. It performs a TCP 443 reachability check on every mirror in `mirror.json` and publishes the resulting Markdown report as a **GitHub Release** on the repo's Releases page:

- **Fixed tag `mirror-status`**: the same Release is overwritten every day, so no history piles up and the Releases page always shows the latest test run
- **Release body is the full report**: open the Release to see the latency and reachability table for every mirror
- **Report also attached as a file**: download `mirror-test-report.md` to keep a copy
- Read-only: **never overwrites the available mirrors in `mirror.json`** — mirrors are added/removed only by manual edits
- Can also be triggered manually from the Actions tab (`workflow_dispatch`) to refresh the status immediately

> This tool is installed via `git clone`, not downloaded from Releases, so the Releases page is dedicated to the daily mirror-status report.

## Full Options

| Option | Short | Description |
|--------|-------|-------------|
| `url` | — | Official repo URL |
| `--mirror` | `-m` | Specify mirror key |
| `--fastest` | `-f` | Auto-test & pick fastest mirror |
| `--list-mirrors` | `-l` | List all mirrors |
| `--branch` | `-b` | Branch to clone |
| `--depth` | `-d` | Shallow clone depth |
| `--single-branch` | — | Single branch only |
| `--target` | — | Target directory name |
| `--dry-run` | `-n` | Preview URL transform, no clone |
| `--min-speed` | — | Min speed threshold MB/s |
| `--speed-timeout` | — | Speed timeout seconds |
| `--help` | `-h` | Show help |

## Project Structure

```
fast-clone/
├── fastclone.py          # Core script
├── i18n.py               # Bilingual strings & language detection
├── mirror.json           # Mirror site configuration
├── scripts/
│   └── test_mirrors.py   # GitHub Actions connectivity test script
├── .github/workflows/
│   └── mirror-test.yml   # Daily mirror-status release
├── README.md             # Chinese docs
├── README.en.md          # English docs (this file)
├── LICENSE               # MIT
├── windows/
│   ├── setup.bat
│   └── fast-clone.cmd
└── linux/
    └── setup.sh
```

## Keeping Your Copy Up to Date

fast-clone itself is a git repo; sync upstream updates with:

```bash
cd /path/to/fast-clone   # your install directory
git pull
```

- **No reinstall needed**: the wrapper created by `windows\setup.bat` / `linux/setup.sh` points at `fastclone.py` in place, so it keeps working as long as the path is unchanged; `mirror.json` and other config paths are unaffected too
- **Mirror list auto-updates**: upstream additions/removals in `mirror.json` (new mirrors, retired dead ones) come in with `git pull` and take effect on the next run
- **Handling custom `mirror.json` conflicts**: if you have added or modified mirrors locally, `git pull` may conflict. Options:
  - Merge manually: keep your custom entries while accepting upstream changes to the others
  - Or fork the repo and maintain your custom config on your own fork
- **Speed cache untouched**: `speedcache/` is in `.gitignore`, so `git pull` never disturbs local caches
- **Moved the directory? Reinstall**: if you relocated the repo after install, re-run the setup script

## Notes

1. Do not move the repo directory after install, or re-run the setup script
2. SSH URLs are cloned via HTTPS from mirrors, then remote is reset back to SSH
3. Mirror sites may change; use `--fastest` for real-time speed test
4. Edit `mirror.json` to add/remove mirrors; takes effect next run
