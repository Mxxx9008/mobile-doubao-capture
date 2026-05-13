# 豆包 APP API 逆向抓包 — 项目总结

> **目标**: 捕获豆包 Android App 的聊天 API 请求/响应明文  
> **成果**: 完整解密 HTTPS 通信，识别全部 API 端点及协议架构；实现参考文献自动提取与多会话管理  
> **耗时**: Day 1 约 2.5h + Day 2 约 3h  

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
| **Python** | 数据解析脚本 (`extract_references.py`) | 3.13 |

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

## 七、Day 2：参考文献提取与多会话管理 (2026-05-13)

### 7.1 SSE 协议深度解析

Day 1 已发现 SSE 协议，Day 2 进一步挖掘了两种关键 `cmd` 的数据结构：

#### cmd:50200 — 参考文献事件

```
downlink_body.bot_reply_loading_update_notify.ext
  ├── search_references   ← JSON 字符串，内含 text_card[]
  │     └── text_card: { id, title, url, sitename, summary, ... }
  ├── search_queries      ← JSON 字符串数组，搜索关键词
  ├── agent_intention     ← "browsing" / "chat" 等模式标识
  ├── message_id          ← 消息唯一 ID
  └── conversation_id     ← 对话框 ID
```

#### cmd:300 — 回答文本流

```
downlink_body.fetch_chunk_message_downlink_body
  ├── message_id          ← 消息 ID（与 50200 关联）
  ├── content             ← JSON 字符串 { text: "..." }
  ├── ext.mult_query      ← 用户问题文本
  └── is_finish           ← 流结束标志
```

### 7.2 参考文献自动提取管道

`extract_references.py` 实现了完整的解析 → 去重 → 分组 → 输出管道：

```
mitmproxy 捕获文件 (.txt)
    → 逐行解析 SSE data: {...} JSON
    → 提取 cmd:50200 → search_references + search_queries + agent_intention
    → 提取 cmd:300 → answer text + mult_query
    → URL 去重 (每次问答内)
    → 按 conversation_id 分组
    → 写入 doubao_conv_{conversation_id}.json
```

**输出 JSON 结构**（与样本文件格式一致）：
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "conversation_id": "...",
    "updated_at": "2026-05-13T...",
    "conversations": [
      {
        "task_id": "...",
        "question": "用户问题",
        "mode": "browsing",
        "search_keywords": ["关键词1", "关键词2"],
        "search_sources": [
          {"title": "...", "url": "...", "sitename": "...", "summary": "..."}
        ],
        "search_summary": "搜索 N 个关键词，参考 M 篇资料",
        "answer": "豆包的回答全文...",
        "total_references": 16,
        "statistics": {
          "sitename_counts": {"新浪财经": 3, "知乎": 2, ...},
          "brands": ["苹果", "Apple", "iPhone"],
          "token_usage": { "total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0 }
        }
      }
    ]
  }
}
```

### 7.3 多会话文件管理策略

| 场景 | 行为 |
|------|------|
| 新对话框 | 创建新 JSON 文件 `doubao_conv_{cid}.json` |
| 同一对话框多次提问 | 新 QA 追加到已有文件的 `conversations[]`，不重复添加相同 `task_id` |
| 多次抓包同一会话 | 自动合并，按 `task_id` 去重，`updated_at` 刷新 |

### 7.4 品牌 & 来源统计

- **品牌识别**: 从参考文献的 `title` + `summary` 中匹配预定义的品牌关键词列表（苹果/Apple/iPhone/华为/大疆/DJI/小米/三星 等）
- **来源统计**: 按 `sitename` 聚合，生成 `{ "知乎": 5, "新浪财经": 3, ... }` 分布

### 7.5 捕获到的算法 Bug

extract_references.py 使用 `int(mid)` 排序时，遇大 ID 会引发 OverflowError。用字符串直接比较替代 `sorted(msg_refs.keys(), key=int)` 已规避，但 Python int 对大数仍友好。

### 7.6 Frida 注入稳定性

| 问题 | 原因 | 解决 |
|------|------|------|
| `frida.attach("com.larus.nova")` 失败 | 包名无法解析 | 改用 PID 注入 (`frida_inject.py`) |
| `frida.attach(pid)` PermissionDeniedError | frida-server 以 shell 用户运行 | `adb root` + 重启 frida-server |
| Frida 注入 600s 后超时 | Frida 默认超时机制 | 新对话前需重新注入 Frida |

### 7.7 实际输出成果

两次抓包产生 2 个会话文件，共 4 条 QA：

| 文件 | 会话 ID | 问题 | 参考文献数 |
|------|--------|------|-----------|
| `doubao_conv_6834621451355906.json` | 6834621451355906 | iPhone 16 Pro 使用体验 | 16 |
| | | MacBook Air M5 | 10 |
| `doubao_conv_38425770128159746.json` | 38425770128159746 | 战斗机拌面的由来 | 17 |
| | | 战斗机拌面的起源 | 19 |

---

## 八、GitHub 版本管理

全部项目文件已推送至 **Mxxx9008/mobile-doubao-capture**：

| 文件 | 说明 |
|------|------|
| `frida_ssl_bypass.js` | Frida JavaScript SSL 绕过脚本 |
| `frida_inject.py` | Python Frida 注入器（按 PID） |
| `frida_attach.py` | Python Frida 注入器（按包名） |
| `extract_references.py` | 参考文献提取管道 |
| `doubao_api_analysis.txt` | API 协议分析笔记 |
| `doubao_conv_*.json` | 会话 JSON 输出文件 |
| `.gitignore` | 排除大型捕获文件 |

> 捕获的 `.txt` 原始文件不提交（单个可达数十 MB），仅保留解析后的 JSON。

---

## 九、环境速查

| 组件 | 位置/命令 |
|------|-----------|
| ADB | `C:\Users\31760\platform-tools\platform-tools\adb.exe` |
| mitmdump | `C:\Users\31760\AppData\Local\Programs\Python\Python313\Scripts\mitmdump` |
| Frida 注入脚本 | `C:\Users\31760\frida_inject.py` |
| Frida SSL 脚本 | `C:\Users\31760\frida_ssl_bypass.js` |
| 参考文献提取 | `C:\Users\31760\extract_references.py` |
| API 分析文档 | `C:\Users\31760\doubao_api_analysis.txt` |
| Mumu ADB 端口 | `127.0.0.1:5555` |
| GitHub 仓库 | `Mxxx9008/mobile-doubao-capture` |

---

> **一句话总结**: Day 1 — ADB 连设备 → mitmproxy 做代理 → Frida 绕 SSL → 明文到手；Day 2 — SSE 深度解析 → 参考文献自动提取 → 多会话 JSON 管理 → GitHub 版本化。全程无 Root，两个半天内从零到完整可复现工具链。
