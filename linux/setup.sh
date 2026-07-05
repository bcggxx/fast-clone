#!/usr/bin/env bash
# fast-clone Linux 安装脚本 (Debian / CentOS / Fedora / Arch)
#
# 安装方式: 创建 wrapper 脚本指向项目目录中的 fastclone.py，
# 保证 SCRIPT_DIR 始终解析到项目根目录，mirror.json 路径不变。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "============================================================"
echo "            fast-clone 安装程序 (Linux)"
echo "============================================================"
echo ""
echo "项目目录: $TOOL_DIR"
echo ""

# ============================================
# 1. 检查 Python3 (仅 PATH)
# ============================================
echo "[1/4] 检查 Python 环境 ..."

PYTHON=""
if command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    if python --version 2>&1 | grep -q "Python 3"; then
        PYTHON="python"
    fi
fi

if [ -z "$PYTHON" ]; then
    echo "  [错误] 未在 PATH 中找到 Python 3.7+。"
    echo ""
    echo "  请先安装 Python 3.7+:"
    echo ""
    echo "    Debian/Ubuntu:  sudo apt install -y python3"
    echo "    CentOS/RHEL 7:  sudo yum install -y python3"
    echo "    CentOS/RHEL 8+: sudo dnf install -y python3"
    echo "    Fedora:         sudo dnf install -y python3"
    echo "    Arch:           sudo pacman -S python"
    echo ""
    echo "  如果已安装但仍提示找不到，请确认 python3 在 PATH 中:"
    echo "    which python3"
    echo "    echo \$PATH"
    exit 1
fi

PYVER=$("$PYTHON" --version 2>&1)
echo "  [OK] $PYVER"

# ============================================
# 2. 检查 Git (仅 PATH)
# ============================================
echo ""
echo "[2/4] 检查 Git 环境 ..."

if command -v git &>/dev/null; then
    GITVER=$(git --version 2>&1)
    echo "  [OK] $GITVER"
else
    echo "  [错误] 未在 PATH 中找到 Git。"
    echo ""
    echo "  请先安装 Git:"
    echo ""
    echo "    Debian/Ubuntu:  sudo apt install -y git"
    echo "    CentOS/RHEL 7:  sudo yum install -y git"
    echo "    CentOS/RHEL 8+: sudo dnf install -y git"
    echo "    Fedora:         sudo dnf install -y git"
    echo "    Arch:           sudo pacman -S git"
    exit 1
fi

# ============================================
# 3. 创建 wrapper 脚本（不复制 fastclone.py）
# ============================================
echo ""
echo "[3/4] 安装 fast-clone ..."
echo ""
echo "  安装方式: 创建 wrapper 脚本，指向项目目录中的 fastclone.py"
echo "  优点: mirror.json 保持原位，修改即时生效"
echo ""
echo "  选择安装位置:"
echo "    [1] ~/.local/bin     (用户级，无需 sudo，推荐)"
echo "    [2] /usr/local/bin   (系统级，需 sudo)"
echo "    [3] 暂不安装，手动使用"
echo ""
read -rp "  请选择 [1-3]: " CHOICE

case "$CHOICE" in
    2)
        BIN="/usr/local/bin/fast-clone"
        TMP_WRAPPER=$(mktemp)
        cat > "$TMP_WRAPPER" << WRAPPER_EOF
#!/usr/bin/env bash
# fast-clone wrapper — 指向 $TOOL_DIR/fastclone.py
exec "$PYTHON" "$TOOL_DIR/fastclone.py" "\$@"
WRAPPER_EOF
        echo ""
        echo "  安装到 $BIN ..."
        if [ -w /usr/local/bin ]; then
            mv "$TMP_WRAPPER" "$BIN"
            chmod +x "$BIN"
        else
            sudo mv "$TMP_WRAPPER" "$BIN"
            sudo chmod +x "$BIN"
        fi
        echo "  [OK] fast-clone → $BIN"
        echo "       实际执行: $PYTHON $TOOL_DIR/fastclone.py"
        ;;
    3)
        BIN=""
        echo ""
        echo "  跳过安装。手动使用方式:"
        echo "    $PYTHON $TOOL_DIR/fastclone.py [参数] [仓库地址]"
        echo ""
        echo "  或创建别名 (添加到 ~/.bashrc):"
        echo "    alias fast-clone='$PYTHON $TOOL_DIR/fastclone.py'"
        ;;
    *)
        BIN="$HOME/.local/bin/fast-clone"
        mkdir -p "$HOME/.local/bin"
        echo ""
        echo "  安装到 $BIN ..."
        cat > "$BIN" << WRAPPER_EOF
#!/usr/bin/env bash
# fast-clone wrapper — 指向 $TOOL_DIR/fastclone.py
exec "$PYTHON" "$TOOL_DIR/fastclone.py" "\$@"
WRAPPER_EOF
        chmod +x "$BIN"
        echo "  [OK] fast-clone → $BIN"
        echo "       实际执行: $PYTHON $TOOL_DIR/fastclone.py"
        ;;
esac

# ============================================
# 4. 验证 & 完成
# ============================================
echo ""
echo "[4/4] 验证安装 ..."
echo ""

if [ -n "${BIN:-}" ] && [ "$CHOICE" != "3" ]; then
    if [ "$CHOICE" != "2" ] && [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo "  [注意] ~/.local/bin 不在 PATH 中"
        echo "  请将以下行添加到 ~/.bashrc 或 ~/.zshrc:"
        echo ""
        echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo ""
    fi
    "$BIN" --list-mirrors
else
    "$PYTHON" "$TOOL_DIR/fastclone.py" --list-mirrors
fi

echo ""
echo "============================================================"
echo "                     安装完成!"
echo "============================================================"
echo ""
echo "用法:"
echo "  fast-clone https://github.com/user/repo"
echo "  fast-clone --fastest https://github.com/user/repo"
echo "  fast-clone --list-mirrors"
echo "  fast-clone --dry-run https://github.com/user/repo"
echo ""
echo "项目数据目录 (请勿删除): $TOOL_DIR"
echo "  fastclone.py — 核心脚本"
echo "  i18n.py      — 中英文文案"
echo "  mirror.json  — 镜像站配置（编辑此文件即可增删镜像）"
echo "  README.md    — 使用说明"
echo ""
