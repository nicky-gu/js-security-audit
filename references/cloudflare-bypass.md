# Cloudflare 防护绕过策略

## 防护层级识别

### 第一层：基础 CDN（无防护）
- 特征：正常 HTTP 200 响应，HTML 完整
- 应对：直接 katana + playwright 即可

### 第二层：Bot 管理（Browser Integrity Check）
- 特征：返回 403 或 "Please enable cookies" 页面
- 应对：curl 带 `User-Agent` + `Referer` 可绕过

### 第三层：Challenge 挑战（Managed Challenge）
- 特征：返回 5 秒等待页面，JavaScript 计算 token
- 应对：headless 浏览器被拦截，curl 降级提取页面内嵌 JS

### 第四层：IUAM（I'm Under Attack Mode）
- 特征：强制 5 秒延迟，所有请求都经过验证
- 应对：需要真实浏览器访问获取 Cookie，然后传给脚本

### 第五层：Custom WAF 规则
- 特征：根据行为模式（如请求频率、User-Agent 组合）拦截
- 应对：调整请求头，模拟真实浏览器行为

---

## 绕过策略

### 策略 1：请求头伪装（基础）

```bash
curl -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \
     -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8" \
     -H "Accept-Language: en-US,en;q=0.9" \
     -H "Accept-Encoding: gzip, deflate, br" \
     -H "Referer: https://www.google.com/" \
     -H "Connection: keep-alive" \
     -H "Upgrade-Insecure-Requests: 1" \
     -H "Sec-Fetch-Dest: document" \
     -H "Sec-Fetch-Mode: navigate" \
     -H "Sec-Fetch-Site: cross-site" \
     --compressed \
     "https://target.com"
```

### 策略 2：Cookie 传递（重度防护）

当目标启用 IUAM 或重度 Challenge 时：

1. 使用真实浏览器访问目标网站，通过 Cloudflare 验证
2. 从浏览器开发者工具复制 Cookie（特别是 `cf_clearance` 和 `__cf_bm`）
3. 将 Cookie 传递给脚本：

```bash
# 设置环境变量
export CF_COOKIE="cf_clearance=xxx; __cf_bm=yyy"

# 修改 js-harvester.sh 中的 curl 命令，添加 Cookie 头
-H "Cookie: $CF_COOKIE"
```

### 策略 3：代理池（分布式）

当 IP 被限制时：

```bash
# 使用代理
export HTTP_PROXY="http://proxy:port"
export HTTPS_PROXY="http://proxy:port"
```

### 策略 4：请求速率控制

避免被 WAF 的速率限制拦截：

```bash
# 在 curl 中添加延迟
sleep 0.5
```

js-harvester.sh 已内置 `--max-time` 和连接超时，但如需额外限速，可在循环中添加 `sleep`。

---

## 自动降级机制

脚本已内置自动降级：

```
Katana (headless) → 被拦截 → 0 个 JS
  ↓
Playwright (headless) → 被拦截 → 0 个 JS
  ↓
curl 降级 → 成功 → 4 个 JS（页面内嵌 JS）
```

curl 降级能获取的 JS：
- 首页 HTML 中 `<script src="...">` 引用的 JS
- 无法获取 SPA 异步加载的 JS（因为需要执行 JS 才能触发）

**局限性：**
- 对于重度 SPA 应用（如 React/Vue），curl 降级只能获取初始 bundle，无法获取懒加载的 chunk
- 对于需要登录才能访问的 JS，curl 降级无法获取（需要 Cookie）

---

## 手动增强建议

### 对于重度 SPA 应用

1. 使用浏览器扩展（如 SingleFile）保存完整页面
2. 提取页面中的 JS 引用
3. 手动补充到 `all_js_urls.txt` 中

### 对于需要登录的页面

1. 使用浏览器登录目标网站
2. 导出 Cookie（使用 `EditThisCookie` 扩展）
3. 将 Cookie 写入 `cookies.txt`：
   ```
   # Netscape HTTP Cookie File
   .target.com	TRUE	/	TRUE	0	cf_clearance	xxx
   ```
4. 修改脚本使用 `curl -b cookies.txt`

### 对于 API 端点发现

如果前端 JS 被重度混淆，尝试：
1. 浏览器开发者工具 → Network 面板 → XHR/Fetch
2. 观察 API 请求模式
3. 直接扫描 API 文档（如 `/api/docs`, `/swagger.json`）

---

## 常见错误处理

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| `curl: (52) Empty reply from server` | Cloudflare 断开连接 | 添加 Cookie 或降低请求频率 |
| `curl: (56) Recv failure` | 连接被重置 | 检查代理设置，或尝试不同 IP |
| `403 Forbidden` | WAF 拦截 | 添加 Cookie 或更换 User-Agent |
| `429 Too Many Requests` | 速率限制 | 降低请求频率，添加延迟 |
| `522 Connection Timed Out` | Cloudflare 无法连接源站 | 目标服务器问题，非防护问题 |

---

## 工具推荐

| 工具 | 用途 | 命令 |
|------|------|------|
| curl | 基础请求 | `curl -v -H "User-Agent: ..." URL` |
| wget | 递归下载 | `wget --mirror --page-requisites URL` |
| burp | 代理拦截 | 设置浏览器代理为 Burp |
| mitmproxy | 流量分析 | `mitmproxy` |
| browser-cookies | 提取 Cookie | `browser-cookies extract target.com` |

---

## 测试验证

验证是否绕过 Cloudflare：

```bash
# 测试 1：基础请求
curl -sI "https://target.com" | head -5
# 期望：HTTP/2 200（不是 403 或 503）

# 测试 2：带请求头
curl -sI -H "User-Agent: Mozilla/5.0..." "https://target.com" | head -5

# 测试 3：带 Cookie
curl -sI -H "Cookie: cf_clearance=xxx" "https://target.com" | head -5

# 测试 4：下载 JS
curl -sL -H "User-Agent: Mozilla/5.0..." "https://target.com/app.js" | head -20
# 期望：JS 代码（不是 "Please enable JavaScript" 页面）
```
