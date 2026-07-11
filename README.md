# fast-clone

**中文** | [English](README.en.md)

## 📑 目录

- [🏆 为什么选择我们](#为什么选择我们)
- [📦 获取工具](#获取工具)
- [🚀 快速开始](#快速开始)
- [⚙️ 安装](#安装)
  - [Windows](#windows)
  - [Linux](#linux)
  - [前置依赖](#前置依赖)
- [🪞 可用镜像](#可用镜像)
- [🛡️ 自动保护](#自动保护)
- [➕ 新增 / 禁用镜像](#新增-禁用镜像)
- [🌐 IPv4 / IPv6 自动检测](#ipv4-ipv6-自动检测)
- [💾 测速结果缓存](#测速结果缓存)
- [⚡ GitHub Actions 每日镜像状态 Release](#github-actions-每日镜像状态-release)
- [📋 完整参数](#完整参数)
- [📁 项目结构](#项目结构)
- [🔄 后续更新](#后续更新)
- [⚠️ 注意事项](#注意事项)

> **纯 vibe coding**，全程 AI 辅助生成，未手写一行代码。

> [!NOTE]
> 镜像站加速克隆 GitHub/GitLab 仓库，克隆完成后**自动重置 remote 为官方地址**。  
> **核心价值**：从镜像站下载（快），后续 `pull`/`push` 走官方仓库（安全）。  
> **零外部依赖**：仅用 Python 标准库，镜像配置独立在 `mirror.json`，中英文文案分离在 `i18n.py`。

## 🏆 为什么选择我们

- **安全无忧** — 克隆完成后自动重置 remote 为官方地址，下载快、`pull`/`push` 安全
- **代码可审计** — 纯文本 Python 源码，无二进制、无混淆、无编译产物，代码完全公开可审查
- **零依赖** — 仅使用 Python 标准库，无需 `pip install` 任何包
- **智能保护** — 速度监控 + 自动重试 + 兜底直连，克隆失败概率极低
- **多镜像支持** — 内置 11 个镜像站，覆盖前缀代理/域名替换/路径前缀等多种策略
- **网络自适应** — 自动检测本机 IPv4/IPv6 支持，跳过不可用镜像
- **测速缓存** — 7 天内测速结果复用，避免重复测速浪费时间
- **每日状态报告** — GitHub Actions 每日自动测试镜像可达性并以 Release 发布报告
- **双语支持** — 中英文自动检测切换
- **高度可定制** — 编辑 `mirror.json` 即可增删镜像，下次运行即生效

## 获取工具

```bash
git clone https://github.com/bcggxx/fast-clone.git
```

仓库保存在本地固定位置即可，安装后不要移动目录。

## 快速开始

> [!TIP]
> 不确定哪个镜像最快？加上 `--fastest` 参数，工具会自动测速并选择延迟最低的镜像。

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

> [!IMPORTANT]
> 仓库目录**安装后不要移动**，否则需要重新运行安装脚本才能让 `fast-clone` 命令重新生效。

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

安装脚本创建 wrapper 指向 `fastclone.py` 原位，`mirror.json` 路径不变。

### 前置依赖

| 依赖 | 安装 |
|------|------|
| Python 3.7+ | [python.org](https://www.python.org/downloads/) 或包管理器 |
| Git | [git-scm.com](https://git-scm.com/downloads/) 或包管理器 |

## 可用镜像

| key | 镜像站 | 类型 | 延迟 | 说明 |
|-----|--------|------|------|------|
| `gh-proxy-org` * | gh-proxy.org | 前缀代理 | 169ms | 默认镜像 |
| `gh-proxy-v4` | v4.gh-proxy.org | 前缀代理 | 43ms | 仅 IPv4 智能解析 |
| `gh-proxy-v6` | v6.gh-proxy.org | 前缀代理 | 2253ms | IPv6/IPv4 双栈 |
| `gh-proxy-cdn` | cdn.gh-proxy.org | 前缀代理 | 93ms | Fastly CDN 加速 |
| `kkgithub` | kkgithub.com | 域名替换 | 48ms | — |
| `github-akams` | github.akams.cn | 前缀代理 | 33ms | — |
| `gitclone` | gitclone.com | 路径前缀 | 71ms | — |
| `github-ur1` | github.ur1.fun | 域名替换 | 189ms | — |
| `gh-proxy-com` | gh-proxy.com | 前缀代理 | 63ms | — |
| `ghproxy-net` | ghproxy.net | 前缀代理 | 1591ms | — |
| `jihulab` | jihulab.com | GitLab 极狐 | 106ms | — |

> `*` 为默认镜像。2026-07-06 TCP 443 端口实测，深圳移动 IPv4/IPv6 混合环境。

## 自动保护

- **速度监控**：持续 < 1 MB/s 达 3 分钟 → 自动中止、清残留、换镜像
- **连接重试**：每个镜像连接失败自动重试 3 次 → 仍失败换镜像
- **兜底直连**：全部镜像失败后，最后尝试官方仓库

```bash
# 自定义阈值
fast-clone --min-speed 2 --speed-timeout 120 https://github.com/user/repo
```

## 新增 / 禁用镜像

编辑 `mirror.json` 文件：

```json
"my-mirror": {
    "name": "my-mirror.example.com",
    "platforms": ["github"],
    "transform": "domain_replace",
    "old": "github.com",
    "new": "my-mirror.example.com",
    "test_host": "my-mirror.example.com",
    "ip": "dual",
    "description": "我的自建镜像"
}
```

`ip` 字段控制协议过滤（运行时自动检测本机 IPv4/IPv6 支持，不支持时跳过对应镜像）：

| 值 | 含义 |
|----|------|
| `dual` | 双栈，IPv4/IPv6 均可（默认） |
| `v4` | 仅 IPv4 端点 |
| `v6` | 仅 IPv6 端点 |

4 种 `transform` 策略：

| 策略 | 示例 |
|------|------|
| `prefix` | `https://mirror.com/{完整官方URL}` |
| `domain_replace` | `github.com` → `mirror.com` |
| `path_prefix` | `https://mirror.com/github.com/owner/repo` |
| `domain_suffix` | `github.com` → `github.com.mirror.org` |

删除条目即禁用。修改 `mirror.json` 顶层 `"default"` 切换默认镜像。

## IPv4 / IPv6 自动检测

启动克隆时自动探测本机网络协议支持（先探测 Cloudflare 1.1.1.1 / 2606:4700:4700::1111:443，失败则回退腾讯 DNSPod 119.29.29.29 / 2402:4e00::，避免 Cloudflare 被墙时误判），探测结果在进程内缓存：

- 不支持 IPv6 → 跳过 `ip: "v6"` 镜像（如 `gh-proxy-v6`）
- 不支持 IPv4 → 跳过 `ip: "v4"` 镜像（如 `gh-proxy-v4`、`gitclone`）
- 使用 `--mirror` 显式指定镜像时不做过滤（尊重用户选择）

## 测速结果缓存

`--fastest` 测速结果保存在 `speedcache/` 目录下，文件名为测速时间（如 `2026-07-06_055454.json`）：

- **缓存命中**：7 天内的同平台测速结果直接复用，跳过实时测速
- **自动过期**：超过 7 天的缓存视为失效，重新测速
- **清理提示**：执行克隆命令时若检测到过期缓存文件，会询问是否删除（默认 `Y` 删除，`n` 保留）

缓存仅记录延迟数据，不修改 `mirror.json` 中的可用镜像列表。

## GitHub Actions 每日镜像状态 Release

仓库内置 `.github/workflows/mirror-test.yml`，每日 UTC 08:00（北京时间 16:00）自动运行 `scripts/test_mirrors.py`，对 `mirror.json` 中每个镜像站执行 TCP 443 连通性测试，生成 Markdown 报告后以 **GitHub Release** 形式发布到仓库 Releases 页面：

- **固定 tag `mirror-status`**：每天覆盖更新同一个 Release，不堆积历史记录，Releases 页面始终展示最新一次测试结果
- **Release 正文即报告全文**：点开 Release 即可看到每个镜像的延迟与可达性表格
- **报告同时作为附件**：可下载 `mirror-test-report.md` 留存
- 该流程为只读操作，**不会修改 `mirror.json` 中的可用镜像**——镜像增删仅由人工编辑完成
- 也可在 Actions 页面手动触发（`workflow_dispatch`）立即刷新状态

> 本工具通过 `git clone` 安装而非 Release 下载，因此 Releases 页面专门用于承载每日镜像状态报告。

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
├── fastclone.py           ← 核心脚本
├── i18n.py                ← 中英文文案与语言检测
├── mirror.json            ← 镜像站配置
├── scripts/
│   └── test_mirrors.py    ← GitHub Actions 连通性测试脚本
├── .github/workflows/
│   └── mirror-test.yml    ← 每日镜像状态 Release
├── README.md
├── windows/
│   ├── setup.bat
│   └── fast-clone.cmd
└── linux/
    └── setup.sh
```

## 后续更新

fast-clone 本身也是 git 仓库，后续有更新时同步到本地：

```bash
cd /path/to/fast-clone   # 你的安装目录
git pull
```

- **无需重新安装**：`windows\setup.bat` / `linux\setup.sh` 创建的 wrapper 指向 `fastclone.py` 原位，路径不变即生效，`mirror.json` 等配置路径也不变
- **镜像列表自动更新**：上游对 `mirror.json` 的增删（如新增可用镜像、移除失效镜像）随 `git pull` 自动同步，下次运行即生效
- **自定义 `mirror.json` 冲突处理**：若你在本地新增/修改过镜像，`git pull` 可能产生冲突。建议：
  - 冲突时手动合并：保留你的自定义条目，同时接纳上游对其他条目的改动
  - 或 fork 仓库后在自有 fork 中维护自定义配置
- **测速缓存不受影响**：`speedcache/` 已加入 `.gitignore`，`git pull` 不会触碰本地缓存
- **移动过目录需重装**：若安装后移动了仓库位置，需重新运行安装脚本

## 注意事项

1. 仓库目录安装后不要移动，否则需重新运行安装脚本
2. SSH 地址通过镜像以 HTTPS 克隆，完成后 remote 设回原始 SSH
3. 镜像站可能随时变更，以 `--fastest` 实时测速为准
4. 编辑 `mirror.json` 新增/禁用镜像后，下次运行即可生效
