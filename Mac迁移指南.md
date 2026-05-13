# Mac 迁移指南 — Claude Code + mobile-doubao-capture

> 从 Windows 迁移到 MacBook，完整恢复 Claude Code 环境和豆包抓包项目。

---

## 一、需要从 Windows 拷走的文件

| 文件 | Windows 路径 | 用途 |
|------|-------------|------|
| `settings.json` | `C:\Users\31760\.claude\settings.json` | API key、插件、Hook |
| `CLAUDE.md` | `C:\Users\31760\Desktop\CLAUDE.md`（备份） | 全局偏好设置 |

可以用 U 盘、网盘、微信文件传输等方式拷贝。

---

## 二、Mac 上操作步骤

### 2.1 安装 Claude Code

```bash
# 终端里跑，按官网提示安装
# https://claude.ai/code
```

### 2.2 拷入全局配置文件

```bash
# 创建 .claude 目录
mkdir -p ~/.claude

# 拷入全局 CLAUDE.md（偏好、Git 配置、回复风格）
cp ~/Desktop/CLAUDE.md ~/.claude/CLAUDE.md

# 拷入 settings.json（API key、插件、Hook）
cp ~/Desktop/settings.json ~/.claude/settings.json
```

### 2.3 修改 settings.json 里的 Hook

`settings.json` 最下面有一个 Windows 通知命令，Mac 不支持。打开文件，把最后几行：

```json
"command": "powershell -NoProfile -Command '(New-Object Media.SoundPlayer \"C:\\Windows\\Media\\Windows Notify.wav\").PlaySync()'"
```

改成：

```json
"command": "afplay /System/Library/Sounds/Glass.aiff"
```

### 2.4 克隆豆包抓包项目

```bash
git clone https://github.com/Mxxx9008/mobile-doubao-capture.git
```

### 2.5 进入项目目录

```bash
cd mobile-doubao-capture
```

---

## 三、验证效果

进入项目目录后，Claude Code 会自动加载两份 CLAUDE.md：

```
~/.claude/CLAUDE.md      → 知道你是谁、Git 配置、回复风格
./CLAUDE.md              → 知道豆包项目、ADB 端口、start_capture.sh
```

直接问 Claude Code 任何项目相关问题，它都能正确理解和执行。

---

## 四、Mac 上安装项目依赖

```bash
# Python + ADB
brew install python android-platform-tools

# Python 包
pip install frida mitmproxy

# 安装模拟器（Mumu Mac 版或 Android Studio AVD）
# 下载 frida-server，版本和 pip show frida 一致
# adb push 到模拟器
```

---

## 五、文件位置对照表

| 文件 | Windows | Mac |
|------|---------|-----|
| 全局 CLAUDE.md | `C:\Users\31760\.claude\CLAUDE.md` | `~/.claude/CLAUDE.md` |
| settings.json | `C:\Users\31760\.claude\settings.json` | `~/.claude/settings.json` |
| 项目目录 | `C:\Users\31760\mxxx-shameless` | `~/mobile-doubao-capture` |

---

## 六、快速检查清单

```
□ 拷出 settings.json 和 CLAUDE.md 到 U 盘/网盘
□ Mac 上安装 Claude Code
□ 拷入 ~/.claude/CLAUDE.md
□ 拷入 ~/.claude/settings.json
□ 修改 settings.json 里的通知命令
□ git clone 项目
□ cd 进项目目录，问 Claude Code 一句话验证
□ brew install python android-platform-tools
□ pip install frida mitmproxy
```
