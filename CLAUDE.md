# mobile-doubao-capture

豆包 Android App 参考文献自动抓取工具。
Frida 绕过 SSL Pinning → mitmproxy 截获 HTTPS 明文 → Python 解析 SSE 流 → 按对话框分组输出 JSON。

## 环境

- ADB: `127.0.0.1:5555` (Mumu 模拟器)
- 代理: `10.0.2.2:8080` (模拟器内宿主机地址)
- frida-server: `/data/local/tmp/frida-server`，版本必须和 `pip show frida` 一致
- Windows 下所有 Python 命令需要 `PYTHONIOENCODING=utf-8` 前缀，Mac/Linux 不需要

## 日常使用

```bash
bash start_capture.sh
# 开模拟器 → 开豆包 → 跑脚本 → 聊天 → 按回车 → JSON 到手
```

## 核心文件

| 文件 | 作用 |
|------|------|
| `start_capture.sh` | 一键启动（ADB + frida-server + mitmproxy + 注入 + 提取） |
| `frida_keepalive.py` | 附加到豆包进程，注入 SSL bypass，持久运行不超时 |
| `frida_ssl_bypass.js` | Frida JS 脚本，Hook SSLContext + CertificatePinner |
| `extract_references.py` | 解析 mitmproxy 捕获文件，提取参考文献，输出 JSON |
| `frida_inject.py` | 备用注入器（spawn 方式） |
| `frida_attach.py` | 备用注入器（包名 attach） |

## 常见坑

- **frida-server 版本不匹配**：`pip show frida` 查版本，下完全一致的 server
- **adb root 失败**：Mumu 支持 root，其他模拟器不一定
- **Frida 注入超时**：`frida_keepalive.py` 持久运行不会超时，用这个
- **关模拟器后不能上网**：代理没恢复，`adb shell settings put global http_proxy :0`
- **中文乱码**：Windows 专属，加 `PYTHONIOENCODING=utf-8`

## 迁移到 Mac

- `brew install python android-platform-tools`
- `pip install frida mitmproxy`
- 装 Mumu Mac 版或 Android Studio AVD
- frida-server 版本和架构要和模拟器匹配
- 全局 CLAUDE.md 从 Windows `~/.claude/` 拷到 Mac 同路径
