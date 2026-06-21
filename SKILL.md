---
name: js-security-audit
description: 全生态 JavaScript 资产安全审计技能。覆盖域名资产发现、子域名枚举、JS 文件收集、Source Map 检测、JS 美化、凭据硬编码审计、框架解析和报告生成。适用于黑盒测试场景下的前端安全评估，支持 React/Vue/Angular/小程序/传统多页等技术栈。当用户需要扫描目标网站的 JS 文件寻找凭据泄露、敏感信息暴露、Source Map 漏洞或前端框架配置暴露时触发。也用于输入公司名称自动发现其官网及子域名资产，并执行完整 JS 安全审计流程。
---

# JS 全生态安全审计

## 概述

本技能提供端到端的 JavaScript 资产安全审计能力，从域名资产发现到凭据硬编码检测，完整覆盖黑盒测试场景下的前端安全评估需求。

**典型触发场景：**
- "扫描 example.com 的 JS 文件"
- "审计 示例公司 的网站安全"
- "检查目标网站的凭据泄露"
- "发现 JS 文件中的 API key"
- "前端安全审计"
- "Source Map 漏洞检测"

## 前置依赖

运行本技能前，确保以下工具已安装：

```bash
# 系统级二进制工具
katana      # ProjectDiscovery 被动爬虫
ffuf        # 快速 fuzz 工具
gitleaks    # 凭据扫描

# Python 虚拟环境 (推荐 /opt/sec-tools)
js-beautify     # JS 美化
trufflehog      # 深度凭据扫描
playwright      # 浏览器自动化
sourcemap       # Source Map 解析

# Go 工具 (subfinder 用于子域名枚举)
subfinder   # 子域名枚举器
```

如果工具未安装，脚本会自动降级或跳过相关阶段（如 subfinder 不可用时只用 DNS 字典爆破）。

## 核心工作流程

### 阶段 0: 输入解析与域名发现

**支持两种输入方式：**

1. **直接 URL** — 如 `https://www.example.com`
2. **公司名称** — 如 `示例公司`、`华为`、`阿里巴巴`

当输入为公司名称时，自动执行域名资产发现：
- 硬编码映射表（常见大公司）
- 通用拼音猜测（如 `www.{拼音}.com`）
- 可达性验证（curl HTTP 状态码检查）
- 子域名枚举（crt.sh + subfinder + DNS 字典爆破）

**脚本：** `scripts/discover_domains.py`

**输出：** `domains.txt`（每行一个 URL，用于后续多域名扫描）

### 阶段 1: JS 资产收集（多域名并行）

对每个发现的域名，执行三层收集：

| 层级 | 工具 | 说明 |
|------|------|------|
| 1.1 | **Katana** | headless 深度爬取，过滤浏览器日志污染 |
| 1.2 | **Playwright** | 浏览器动态渲染，捕获 SPA 异步加载的 JS |
| 1.3 | **curl 降级** | 当 headless 被 Cloudflare 拦截时，提取页面内嵌 JS |

**技术栈专用探测：** 根据探测到的框架自动调用对应提取脚本：
- React → `extract_webpack_chunks.py`
- Vue → `extract_vue_chunks.py`
- 小程序 → `extract_miniapp_chunks.py`

### 阶段 2: URL 清洗与去重

解决 Cloudflare token 导致的 URL 爆炸问题：
- 去掉 query string 后按 clean URL 去重
- 过滤 `__cf_chl_tk`、`ray=` 等 Cloudflare 参数
- 过滤 `cdn-cgi/challenge-platform` 假 URL
- 过滤 CSS/图片/字体等非 JS 资源
- 过滤 Drupal 管理路径（`/node/*/edit`、`/delete` 等）

### 阶段 3: 批量下载

使用带请求头的 curl 下载（绕过 Cloudflare 基础防护）：
```bash
curl -H "User-Agent: Mozilla/5.0 ..." -H "Referer: $TARGET" ...
```

文件按 MD5 哈希命名，保留 `js_url_map.txt` 映射关系。

### 阶段 4: Source Map 检测

对每个 JS 文件探测 `.map` 文件：
```bash
status=$(curl -sI -o /dev/null -w "%{http_code}" "${url}.map")
```

成功下载的 Source Map 用于后续源码还原。

### 阶段 5: JS 美化（阶梯制）

根据 JS 文件数量自动选择策略：

| JS 数量 | 策略 |
|---------|------|
| ≤100 | 全部美化 |
| 100-300 | 只美化 >10KB 文件 |
| 300-500 | 只美化 >50KB 核心文件 |
| >500 | 跳过美化，直接复制原文件 |

### 阶段 6: 凭据硬编码审计（阶梯制）

**v2 扫描器** (`scan_credentials_v2.py`) 支持 20+ 种凭据类型：

| 类别 | 凭据类型 |
|------|----------|
| 云服务商 | AWS Access Key, Azure, GCP, Alibaba Cloud |
| 代码平台 | GitHub PAT, GitLab Token, Bitbucket |
| 协作工具 | Slack Token, Discord Webhook, Teams |
| AI 服务 | OpenAI Key, Anthropic, HuggingFace |
| 支付 | Stripe Key, PayPal, Square |
| 通信 | Twilio SID/Token, SendGrid |
| 认证 | JWT, OAuth Token, Basic Auth, API Key |
| 数据库 | MongoDB URI, Redis, PostgreSQL, MySQL |
| 密钥 | RSA 私钥, EC 私钥, Ed25519 私钥 |
| 其他 | 私钥 PEM, Google API Key, Firebase |

扫描策略阶梯制：

| JS 数量 | 策略 |
|---------|------|
| ≤100 | v2 全量结构化扫描 |
| 100-300 | v2 扫描但跳过 >1MB 超大文件 |
| 300-500 | v2 轻量模式（仅对象赋值+环境变量+高置信度正则） |
| >500 | grep 轻量模式（仅关键词匹配前 200 个文件） |

**结构化分析方法：**
1. **对象赋值模式** — `Object.assign({apiKey: "..."})` 
2. **环境变量引用** — `process.env.SECRET_KEY`
3. **URL 嵌入凭据** — `https://user:pass@host`
4. **JSON 配置块** — 完整的 JSON 配置对象提取
5. **Base64 候选** — 高熵字符串检测（香农熵 > 4.8）
6. **高置信度正则** — 20+ 种精确模式匹配

**误报过滤：** `scripts/filter_false_positives.py`
- Vue 变量名（`apiKey` 作为变量名而非值）
- 模板字符串（`${apiKey}` 插值）
- 函数参数（`function(apiKey)`）
- 注释中的示例代码
- 伪值（`test123`、`example`、`demo`）

### 阶段 7: 框架解析（技术栈探测后）

根据 Phase 0 技术栈探测结果，调用对应解析器：

| 框架 | 解析脚本 | 输出 |
|------|----------|------|
| React | `parse_react_bundle.py` | 组件列表、路由、API 端点 |
| Vue | `parse_vue_bundle.py` | 路由、组件、API 端点、Store 状态 |
| Angular | `parse_angular_bundle.py` | 模块、服务、路由、依赖注入 |
| 小程序 | `parse_miniapp.py` | 页面路由、API 调用、配置 |

### 阶段 8: 报告生成

生成结构化审计报告，包含：
- 域名资产清单
- JS 文件清单
- Source Map 检测结果
- 高置信度凭据发现（红色警报）
- 中置信度发现（橙色提示）
- 低置信度发现（黄色参考）
- 框架配置暴露分析
- 修复建议

## 使用方式

### 命令行直接调用

```bash
# 方式1: 直接输入 URL
bash ~/.openclaw/workspace/skills/js-security-audit/scripts/js-harvester.sh https://www.example.com

# 方式2: 输入公司名称（自动发现域名）
bash ~/.openclaw/workspace/skills/js-security-audit/scripts/js-harvester.sh "示例公司"

# 方式3: 指定技术栈和输出目录
bash ~/.openclaw/workspace/skills/js-security-audit/scripts/js-harvester.sh "华为" vue /tmp/huawei-audit
```

### 参数说明

```
用法: js-harvester.sh <目标URL|公司名称> [技术栈] [输出目录]

技术栈选项:
  auto     自动探测（默认）
  react    React 应用
  vue      Vue 应用
  angular  Angular 应用
  miniapp  微信小程序/小程序
  rn       React Native WebView
  hybrid   混合应用
  legacy   传统多页应用
```

### 输出目录结构

```
js-harvest-YYYYMMDD_HHMMSS/
├── domains.txt              # 发现的域名列表
├── domains.json             # 域名发现的结构化结果
├── domains_discovery.log    # 域名发现日志
├── tech_stack.txt           # 探测到的技术栈
├── katana_js_1.txt          # Katana 收集的 JS URL
├── playwright/
│   ├── js_urls.txt          # Playwright 动态捕获的 JS
│   └── spider.log           # Playwright 日志
├── all_js_urls.txt          # 合并去重后的 JS URL 列表
├── js/                      # 下载的原始 JS 文件
├── js_beautified/           # 美化后的 JS 文件
├── sourcemaps/              # 下载的 Source Map 文件
├── findings_v2/
│   ├── report_v2.md         # 凭据审计报告
│   ├── keyword.json         # 关键词匹配结果
│   ├── high_conf.json       # 高置信度凭据
│   ├── url_cred.json        # URL 嵌入凭据
│   ├── base64.json          # Base64 候选
│   └── obj_assign.json      # 对象赋值配置
└── framework_analysis/      # 框架解析结果
```

## 脚本清单

### 核心脚本

| 脚本 | 用途 |
|------|------|
| `js-harvester.sh` | 主脚本，编排完整 8 阶段流程 |
| `discover_domains.py` | 域名资产发现（关联域名 + 子域名枚举） |
| `discover_company_url.py` | 公司名到 URL 映射（辅助脚本） |
| `spider_js.py` | Playwright 浏览器动态爬取 |
| `extract_inline_js.py` | 提取页面内联 JS 和事件处理程序 |

### 凭据扫描

| 脚本 | 用途 |
|------|------|
| `scan_credentials_v2.py` | 深度凭据扫描 v2（结构化分析） |
| `filter_false_positives.py` | 误报过滤器 |
| `deep-credential-scan.sh` | 深度扫描（Semgrep + TruffleHog） |

### 框架解析

| 脚本 | 用途 |
|------|------|
| `extract_webpack_chunks.py` | React webpack chunk 提取 |
| `extract_vue_chunks.py` | Vue 异步组件提取 |
| `extract_miniapp_chunks.py` | 小程序分包提取 |
| `parse_react_bundle.py` | React 源码解析 |
| `parse_vue_bundle.py` | Vue 源码解析 |
| `parse_miniapp.py` | 小程序源码解析 |

### 辅助工具

| 脚本 | 用途 |
|------|------|
| `check_sourcemaps.sh` | Source Map 可用性检测 |
| `js-audit.sh` | 快速单域名审计（轻量版） |

## 参考文档

详细技术说明参考 `references/` 目录：
- `references/flow.md` — 完整 8 阶段流程详细说明
- `references/credential-types.md` — 支持的凭据类型清单
- `references/thresholds.md` — 阶梯制阈值策略详解
- `references/cloudflare-bypass.md` — Cloudflare 防护绕过策略

## 常见问题

**Q: 扫描被 Cloudflare 拦截怎么办？**
A: 脚本会自动降级为 curl 模式提取页面内嵌 JS。对于重度防护的目标，建议手动提供 Cookie 或使用 --cookie 参数。

**Q: 扫描时间太长？**
A: 脚本内置阶梯制策略，URL/JS 数量越多会自动减少递归轮数和扫描深度。也可手动指定技术栈避免框架解析阶段。

**Q: 误报太多？**
A: v2 扫描器已内置误报过滤，扫描完成后会自动运行 `filter_false_positives.py`。如仍有过滤需求，可在 references/credential-types.md 中添加自定义过滤规则。

**Q: 如何只收集域名资产不扫描？**
A: 单独运行 `discover_domains.py`：
```bash
python3 ~/.openclaw/workspace/skills/js-security-audit/scripts/discover_domains.py "示例公司" /tmp/example_domains.json
```

## 安全声明

本技能仅用于授权的安全测试和漏洞评估。使用前应获得目标网站所有者的明确书面授权。未经授权的扫描可能违反法律法规。
