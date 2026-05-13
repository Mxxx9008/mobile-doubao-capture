# 豆包 APP API 逆向抓包 — 项目总结

> **目标**: 捕获豆包 Android App 的聊天 API 请求/响应明文  
> **成果**: 完整解密 HTTPS 通信，识别全部 API 端点及协议架构  
> **耗时**: 约 2.5 小时  

---

## 一、技术路径全景

```
环境准备               初步侦察               SSL 突破              明文收获
   │                     │                     │                    │
   ▼                     ▼                     ▼                    ▼
Mumu 模拟器            logcat 抓日志          Frida 注入          mitmproxy
+ ADB 连接            + mitmproxy 代理       + SSL bypass        解密完整流量
                                               脚本
                        │                     │                    │
                        ▼                     ▼                    ▼
                    发现 ChatSender        绕过证书绑定         识别 API 端点
                    调用链 & 域名           TrustManager        + SSE 流式协议
                    /im/send/message        + CertificatePinner  + 7层签名体系
```

---

## 二、工具链矩阵

| 工具 | 用途 | 版本 |
|------|------|------|
| **Mumu 模拟器** | 运行 Android 12，承载豆包 App | v5.27.4 |
| **ADB** | 控制模拟器 (shell / push / logcat) | platform-tools latest |
| **mitmproxy** | 中间人代理，拦截 HTTPS 流量 | latest (pip) |
| **Frida** | 运行时动态注入，绕过 SSL Pinning | 17.9.8 |
| **objection** | Frida 的上层封装（未成功，见下文） | 1.12.4 |

---

## 三、关键难点 & 解决方案

### 难点 1：CA 证书无法安装 ❌ → Frida 绕行 ✅

| 问题 | 详情 |
|------|------|
| **现象** | Android 12 需要安装代理 CA 证书到系统信任区才能解密 HTTPS |
| **阻塞点** | Mumu 模拟器无 Root 权限 + 系统设置页面被精简（无"安装证书"入口） |
| **尝试** | mitmproxy CA 证书 → `adb push` → 无法通过设置 UI 安装 |
| **最终方案** | **放弃证书路径，改用 Frida 运行时注入** |

> 💡 **关键决策**: 与其花时间找可 root 的模拟器，不如直接从 App 进程内部解除 SSL 验证。

### 难点 2：objection 工具兼容性问题 ❌

| 问题 | 详情 |
|------|------|
| **现象** | `objection explore` 在 Git Bash 终端下崩溃 |
| **原因** | objection 依赖 `prompt_toolkit` Windows Console Buffer，与 xterm 终端不兼容 |
| **报错** | `NoConsoleScreenBufferError: Found xterm-256color, while expecting a Windows console` |
| **尝试** | `winpty` 包装、`-c` 参数传命令，均失败 |
| **最终方案** | **直接用 Python Frida API 写注入脚本**，绕过 objection |

### 难点 3：字节跳动签名体系（7 层防护）

捕获到的安全 Header：

```
x-ss-stub      → 请求指纹
x-gorgon       → 请求签名（核心）
x-helios       → 设备指纹签名
x-medusa       → 加密载荷（最大，数百字符 Base64）
x-argus        → 行为签名
x-ladon        → 会话签名
x-khronos      → 时间戳签名
x-tt-token     → 认证 Token
```

> 这意味着即使抓到了 API 端点，**自行构造请求**仍需逆向每一层签名算法。这是下一阶段的工作。

### 难点 4：GitHub 网络不可达

| 问题 | 影响 | 解决 |
|------|------|------|
| bash/curl 无法连接 github.com | 无法下载 frida-server | 用户通过浏览器（走 VPN）手动下载 |

### 难点 5：Python & 编码问题

| 问题 | 解决 |
|------|------|
| `python3` 命令突然返回 exit 49 | 改用完整路径 `C:\...\python.exe` |
| GBK 编码报错无法加载 JS 脚本 | Python `open()` 显式指定 `encoding="utf-8"` |
| mitmdump GBK 编码崩溃 | `PYTHONIOENCODING=utf-8` 环境变量 |
| Git Bash 路径翻译破坏 `adb push` | `MSYS_NO_PATHCONV=1` 前缀 |

---

## 四、关键技术亮点

### ✨ 亮点 1：零 Root 完成 SSL 解密

传统方案需要 Root → 安装系统 CA 证书。本项目在 **完全无 Root** 的模拟器上，通过 Frida 动态 Hook `javax.net.ssl.SSLContext` 和 `okhttp3.CertificatePinner`，直接篡改 App 运行时的证书验证逻辑。

```javascript
// 核心思路（简化版）
SSLContext.init.implementation = function(kmf, tm, sr) {
    this.init(kmf, 假TrustManager, sr);  // 替换信任管理器
};
CertificatePinner.check.implementation = function() {
    return;  // 直接放行
};
```

### ✨ 亮点 2：SSE 流式协议发现

豆包不是用标准 LLM API（如 `/v1/chat/completions`），而是：

- **协议**: HTTP/2.0 + SSE (Server-Sent Events)
- **消息路径**: `/im/sse/send/message?flow_im_arch=v2`
- **响应方式**: 逐字流式推送（`cmd:300` 分块），最后一个 chunk 带 `is_finish=1`

```
chunk 1: "你" → chunk 2: "是" → ... → chunk 10: "" (is_finish=1)
                                    brief: "你是全世界最帅的大帅哥😜"
```

### ✨ 亮点 3：完整的可复现工具链

```
任意 Android 模拟器 + ADB 连接
    → mitmproxy 启动代理 (10.0.2.2:8080)
    → adb shell settings put global http_proxy ...
    → frida-server 推入并启动
    → Python Frida 脚本注入 SSL bypass
    → 打开 App 操作 → mitmproxy 日志查看明文
```

---

## 五、走不通的路径 (Dead Ends)

| 路径 | 阻塞原因 |
|------|----------|
| 纯 logcat 抓 HTTP 日志 | 字节自研网络库不输出到标准 logcat |
| 安装 mitmproxy CA 证书 | Mumu 设置精简，无证书安装 UI |
| 直写 `/data/misc/user/0/cacerts-added/` | 无 Root，目录不存在且无法创建 |
| objection 一键 SSL bypass | Git Bash 终端兼容性 crash |
| 腾讯应用宝 + ADB | 应用宝 AOW 引擎不暴露 ADB 端口 |

---

## 六、后续可推进方向

| 方向 | 难度 | 价值 |
|------|------|------|
| 逆向 x-gorgon/x-medusa 签名算法 | 高 | 可自行构造请求，脱离 App |
| 编写自动化对话脚本（Frida RPC） | 中 | 批量测试 prompt / 自动化对话 |
| 适配其他字节系 App（抖音、头条） | 低 | 复用同一工具链 |
| 搭建持续监听平台（docker + mitmweb） | 中 | 长期监控 API 变化 |

---

## 七、环境速查

| 组件 | 位置/命令 |
|------|-----------|
| ADB | `C:\Users\31760\platform-tools\platform-tools\adb.exe` |
| mitmdump | `C:\Users\31760\AppData\Local\Programs\Python\Python313\Scripts\mitmdump` |
| Frida Python | `C:\Users\31760\frida_inject.py` |
| Frida SSL 脚本 | `C:\Users\31760\frida_ssl_bypass.js` |
| mitmproxy 日志 | `C:\Users\31760\doubao_mitmproxy_log2.txt` |
| API 分析文档 | `C:\Users\31760\doubao_api_analysis.txt` |
| Mumu ADB 端口 | `127.0.0.1:5555` |

---

> **一句话总结**: ADB 连设备 → mitmproxy 做代理 → Frida 绕 SSL → 明文到手。全程无 Root，两小时内从零到完整抓包。
