# fast-clone

**中文** | [English](README.en.md)

> **纯 vibe coding**，全程 AI 辅助生成，未手写一行代码。

镜像站加速克隆 GitHub/GitLab 仓库，克隆完成后自动重置 remote 为官方地址。

**核心价值**：从镜像站下载（快），后续 pull/push 走官方仓库（安全）。

**单文件发行**：所有配置内嵌在 `fastclone.py` 中，无需外部配置文件。

## 获取工具

```bash
git clone https://github.com/bcggxx/fast-clone.git
```

仓库保存在本地固定位置即可，安装后不要移动目录。

## 快速开始

```bash
# 默认 gh-proxy.org 镜像（前缀代理，552ms）
fast-clone https://github.com/user/repo

# 自动测速选最快镜像
fast-clone --fastest https://github.com/user/repo

# 指定镜像
fast-clone --mirror github-akams https://github.com/user/repo

# 预览转换，不克隆
fast-clone -n https://github.com/user/repo

# 列出全部镜像
fast-clone -l
```

## 安装

### Windows

1. 仓库放固定目录（如 `D:\tools\fast-clone`），不要移动
2. 双击 `windows\setup.bat` 或命令行运行：

```cmd
cd fast-clone\windows
setup.bat
```

安装脚本检查 Python/Git（仅查 PATH），将 `fast-clone\windows\` 加入 PATH。之后任意终端可用 `fast-clone`。

### Linux

1. 仓库放固定目录（如 `~/tools/fast-clone`），不要移动
2. 运行安装脚本：

```bash
cd fast-clone/linux
bash setup.sh
```

安装脚本创建 wrapper 指向 `fastclone.py` 原位，`mirrors.json` 路径不变。

### 前置依赖

| 依赖 | 安装 |
|------|------|
| Python 3.7+ | [python.org](https://www.python.org/downloads/) 或包管理器 |
| Git | [git-scm.com](https://git-scm.com/downloads/) 或包管理器 |

## 可用镜像（13 个）

| key | 镜像站 | 类型 | 延迟 | 说明 |
|-----|--------|------|------|------|
| `gh-proxy-org` * | gh-proxy.org | 前缀代理 | 552ms | 默认镜像 |
| `gh-proxy-v4` | v4.gh-proxy.org | 前缀代理 | 405ms | 仅 IPv4 智能解析 |
| `gh-proxy-v6` | v6.gh-proxy.org | 前缀代理 | 6906ms | IPv6/IPv4 双栈 |
| `gh-proxy-cdn` | cdn.gh-proxy.org | 前缀代理 | 125ms | Fastly CDN 加速 |
| `kkgithub` | kkgithub.com | 域名替换 | 47ms | — |
| `github-akams` | github.akams.cn | 前缀代理 | 26ms | — |
| `gitclone` | gitclone.com | 路径前缀 | 52ms | — |
| `github-ur1` | github.ur1.fun | 域名替换 | 198ms | — |
| `gh-proxy-com` | gh-proxy.com | 前缀代理 | 52ms | — |
| `ghproxy-net` | ghproxy.net | 前缀代理 | 5256ms | — |
| `bgithub` | bgithub.xyz | 域名替换 | — | 不可达（IPv6） |
| `kgithub` | kgithub.com | 域名替换 | — | 不可达（IPv6） |
| `jihulab` | jihulab.com | GitLab 极狐 | 62ms | — |

> `*` 为默认镜像。2026-07-02 TCP 443 端口实测（3 次采样取均值），深圳移动 IPv4/IPv6 混合环境。

## 自动保护

- **速度监控**：持续 < 1 MB/s 达 3 分钟 → 自动中止、清残留、换镜像
- **连接重试**：每个镜像连接失败自动重试 3 次 → 仍失败换镜像
- **兜底直连**：全部镜像失败后，最后尝试官方仓库

```bash
# 自定义阈值
fast-clone --min-speed 2 --speed-timeout 120 https://github.com/user/repo
```

## 新增 / 禁用镜像

编辑 `fastclone.py` 中 `_CONFIG["mirrors"]` 字典：

```python
"my-mirror": {
    "name": "my-mirror.example.com",
    "platforms": ["github"],
    "transform": "domain_replace",
    "old": "github.com",
    "new": "my-mirror.example.com",
    "test_host": "my-mirror.example.com",
    "description": "我的自建镜像",
},
```

4 种 `transform` 策略：

| 策略 | 示例 |
|------|------|
| `prefix` | `https://mirror.com/{完整官方URL}` |
| `domain_replace` | `github.com` → `mirror.com` |
| `path_prefix` | `https://mirror.com/github.com/owner/repo` |
| `domain_suffix` | `github.com` → `github.com.mirror.org` |

删除条目即禁用。修改 `_CONFIG["default"]` 切换默认镜像。

## 完整参数

| 参数 | 简写 | 说明 |
|------|------|------|
| `url` | — | 官方仓库地址 |
| `--mirror` | `-m` | 指定镜像 key |
| `--fastest` | `-f` | 自动测速选最快 |
| `--list-mirrors` | `-l` | 列出全部镜像 |
| `--branch` | `-b` | 指定分支 |
| `--depth` | `-d` | 浅克隆深度 |
| `--single-branch` | — | 仅单分支 |
| `--target` | — | 目标目录名 |
| `--dry-run` | `-n` | 预览不克隆 |
| `--min-speed` | — | 最低速度 MB/s |
| `--speed-timeout` | — | 超时秒数 |
| `--help` | `-h` | 帮助 |

## 项目结构

```
fast-clone/                ← 安装后保持此目录不动
├── fastclone.py           ← 核心脚本（单文件，含全部配置）
├── README.md
├── windows/
│   ├── setup.bat
│   └── fast-clone.cmd
└── linux/
    └── setup.sh
```

## 注意事项

1. 仓库目录安装后不要移动，否则需重新运行安装脚本
2. SSH 地址通过镜像以 HTTPS 克隆，完成后 remote 设回原始 SSH
3. 镜像站可能随时变更，以 `--fastest` 实时测速为准
4. 编辑 `_CONFIG` 字典新增/禁用镜像后，下次运行即可生效
