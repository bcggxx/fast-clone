# fast-clone

[中文版](README.md) | **English**

> **Pure vibe coding** — entirely AI-assisted, zero hand-written code.

Mirror-accelerated clone for GitHub/GitLab repos, with automatic remote reset to the official URL.

**Core value**: Download fast from mirrors, pull/push safely to official repos.

**Single-file distribution**: All configs embedded in `fastclone.py`, no external dependencies.

## Get Started

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

## Available Mirrors (13)

| key | Mirror | Type | Latency | Description |
|-----|--------|------|---------|-------------|
| `gh-proxy-org` * | gh-proxy.org | prefix proxy | 552ms | Default mirror |
| `gh-proxy-v4` | v4.gh-proxy.org | prefix proxy | 405ms | IPv4-only smart DNS |
| `gh-proxy-v6` | v6.gh-proxy.org | prefix proxy | 6906ms | IPv6/IPv4 dual-stack |
| `gh-proxy-cdn` | cdn.gh-proxy.org | prefix proxy | 125ms | Fastly CDN |
| `kkgithub` | kkgithub.com | domain replace | 47ms | — |
| `github-akams` | github.akams.cn | prefix proxy | 26ms | — |
| `gitclone` | gitclone.com | path prefix | 52ms | — |
| `github-ur1` | github.ur1.fun | domain replace | 198ms | — |
| `gh-proxy-com` | gh-proxy.com | prefix proxy | 52ms | — |
| `ghproxy-net` | ghproxy.net | prefix proxy | 5256ms | — |
| `bgithub` | bgithub.xyz | domain replace | — | Unreachable (IPv6) |
| `kgithub` | kgithub.com | domain replace | — | Unreachable (IPv6) |
| `jihulab` | jihulab.com | GitLab CN mirror | 62ms | — |

> `*` Default mirror. 2026-07-02 TCP port 443 test (3-sample average), Shenzhen China Mobile IPv4/IPv6 dual-stack.

## Auto-Protection

- **Speed monitoring**: < 1 MB/s for 3 min → abort, cleanup, switch mirror
- **Connection retry**: 3 retries per mirror, then switch on failure
- **Last-resort direct**: falls back to official repo after all mirrors fail

```bash
# Custom thresholds
fast-clone --min-speed 2 --speed-timeout 120 https://github.com/user/repo
```

## Adding / Disabling Mirrors

Edit the `_CONFIG["mirrors"]` dict in `fastclone.py`:

```python
"my-mirror": {
    "name": "my-mirror.example.com",
    "platforms": ["github"],
    "transform": "domain_replace",
    "old": "github.com",
    "new": "my-mirror.example.com",
    "test_host": "my-mirror.example.com",
    "description": "My custom mirror",
},
```

4 transform strategies:

| Strategy | Example |
|----------|---------|
| `prefix` | `https://mirror.com/{full-official-url}` |
| `domain_replace` | `github.com` → `mirror.com` |
| `path_prefix` | `https://mirror.com/github.com/owner/repo` |
| `domain_suffix` | `github.com` → `github.com.mirror.org` |

Delete an entry to disable. Change `_CONFIG["default"]` to switch the default mirror. Changes take effect on next run.

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
├── fastclone.py          # Core script (single-file, all config inside)
├── README.md             # Chinese docs
├── README.en.md          # English docs (this file)
├── LICENSE               # MIT
├── windows/
│   ├── setup.bat
│   └── fast-clone.cmd
└── linux/
    └── setup.sh
```

## Notes

1. Do not move the repo directory after install, or re-run the setup script
2. SSH URLs are cloned via HTTPS from mirrors, then remote is reset back to SSH
3. Mirror sites may change; use `--fastest` for real-time speed test
4. Edit the `_CONFIG` dict to add/remove mirrors; takes effect next run
