---
name: js-security-audit
description: 全生态 JavaScript 资产安全审计技能。覆盖域名资产发现、子域名枚举、JS 文件收集、Source Map 检测、JS 美化、凭据硬编码审计、框架解析和报告生成。适用于黑盒测试场景下的前端安全评估，支持 React/Vue/Angular/小程序/传统多页等技术栈。当用户需要扫描目标网站的 JS 文件寻找凭据泄露、敏感信息暴露、Source Map 漏洞或前端框架配置暴露时触发。也用于输入公司名称自动发现其官网及子域名资产，并执行完整 JS 安全审计流程。
---

# JS 全生态安全审计

## 概述

本技能提供端到端的 JavaScript 资产安全审计能力。从域名资产发现到凭据硬编码检测，完整覆盖黑盒测试场景下的前端安全评估需求。

**输入**可以是：
- URL — `https://www.example.com`
- 域名 — `www.example.com` / `example.com`
- 公司名称 — `华为`、`示例公司`

**输出**是一份结构化审计报告，包含域名资产、JS 文件清单、凭据泄露发现和修复建议。

**典型触发场景：**
- "扫描 example.com 的 JS 文件"
- "审计 示例公司 的网站安全"
- "检查目标网站的凭据泄露"
- "发现 JS 文件中的 API key"
- "前端安全审计"
- "Source Map 漏洞检测"

---

## 完整工作流程

```
输入解析
  ├── URL → 直接使用
  └── 公司名 → Phase -1: 域名资产发现

Phase -1: 域名资产发现
  ├── 硬编码映射表查询
  ├── 通用拼音猜测 + curl 可达性验证
  └── 子域名枚举（crt.sh + subfinder + DNS 字典）
      └── 输出: domains.txt

Phase 0: 技术栈探测
  └── curl 首页 HTML → 关键词匹配框架
      └── 输出: tech_stack.txt

Phase 1: JS 资产收集
  └── 对每个域名并行执行:
      ├── Katana headless 爬取
      ├── Playwright 动态渲染（仅主域名）
      └── curl 降级（被拦截时自动触发）

Phase 2: URL 清洗与去重
  └── 去掉 query string → 过滤非 JS 资源 → 递归提取（阶梯制）

Phase 3: 批量下载
  └── curl 带伪装请求头 → MD5 命名 → URL 映射

Phase 4: Source Map 检测
  └── 对每个 JS 探测 .map 文件 → 下载还原源码

Phase 5: JS 美化（阶梯制）
  └── ≤100 全美化 / 100-300 过滤小文件 / >500 跳过

Phase 6: 凭据硬编码审计（阶梯制）
  └── v2 扫描器: 对象赋值 + 环境变量 + URL凭据 + JSON配置 + Base64熵 + 高置信度正则
      └── 误报过滤 → 高/中/低三级分类

Phase 7: 框架解析
  └── React/Vue/Angular/小程序 → 路由/API/组件/Store 提取

Phase 8: 报告生成
  └── 结构化报告（域名资产 + JS清单 + 凭据发现 + 修复建议）
```

---

## 前置依赖

```bash
# 系统级二进制工具
katana      # ProjectDiscovery 被动爬虫
ffuf        # 快速 fuzz 工具
gitleaks    # 凭据扫描
subfinder   # 子域名枚举器

# Python 虚拟环境 (推荐 /opt/sec-tools)
js-beautify     # JS 美化
trufflehog      # 深度凭据扫描
playwright      # 浏览器自动化
sourcemap       # Source Map 解析
```

未安装的工具会自动降级或跳过。

---

## 各阶段详解

### Phase -1: 域名资产发现

当输入为公司名称时触发。支持三种发现策略：

**1. 硬编码映射表**
- 内置常见大公司映射（华为、腾讯、阿里、字节、小米、比亚迪等）
- 可扩展：编辑 `scripts/discover_domains.py` 的 `mappings` 字典

**2. 通用拼音猜测**
- 提取 ASCII 字符猜测主域名（如 `example` → `www.example.com`）
- 纯中文无映射时，依赖用户手动提供 URL

**3. 子域名枚举（三层叠加）**

| 工具 | 策略 | 覆盖 |
|------|------|------|
| crt.sh | 被动收集 | 证书透明度日志，零噪音 |
| subfinder | 开源情报 | API + 搜索引擎聚合 |
| DNS 字典 | 主动爆破 | 200+ 常见前缀（api, admin, mail, vpn 等） |

DNS 字典覆盖的关键前缀：
```
www, mail, api, admin, test, dev, staging, portal, app, cdn, static
login, sso, partner, crm, erp, uat, srm, wms, vpn, data, files
```

**输出：**
- `domains.txt` — 每行一个 URL，用于后续多域名扫描
- `domains.json` — 结构化结果（主域名、关联域名、子域名列表、可达性状态）

**限制：**
- 子域名枚举速度依赖网络，完整扫描可能需要 5-15 分钟
- 部分子域名可能已废弃但 DNS 仍解析（误报）
- 内网子域名无法从公网枚举

### Phase 0: 技术栈探测

通过 curl 获取首页 HTML，关键词匹配框架：

| 框架 | 关键词 |
|------|--------|
| React | `react`, `__REACT__`, `react-router`, `webpack` |
| Vue | `vue`, `__VUE__`, `v-if`, `vue-router` |
| Angular | `ng-`, `angular`, `.module(`, `.component(` |
| 小程序 | `miniProgram`, `wx.js`, `weixin`, `swan` |
| RN | `react-native`, `RN.`, `__fbBatchedBridge` |
| Flutter | `flutter`, `flutter_inappwebview` |

技术栈写入 `tech_stack.txt`，后续阶段据此调用专用解析脚本。

### Phase 1: JS 资产收集

对每个发现的域名执行三层收集：

```
for domain in domains.txt:
    katana -u $domain -headless -js-crawl -depth 3
    if 是主域名:
        playwright 动态渲染
    if katana 返回 < 3 JS:
        curl 降级: 提取页面内嵌 <script src="...">
```

**三层防护绕过：**
1. Katana headless — 正常爬取
2. Playwright — 浏览器渲染，捕获 SPA 异步加载
3. curl 降级 — Cloudflare 拦截时自动触发，带 `User-Agent` + `Referer`

### Phase 2: URL 清洗与去重

解决 Cloudflare token 导致的 URL 爆炸：
- 去掉 query string 后按 clean URL 去重
- 过滤 `cdn-cgi/challenge-platform` 假 URL
- 过滤 CSS/图片/字体等非 JS 资源
- 过滤管理路径（`/node/*/edit`、`/delete`）
- 过滤社交媒体外链

**递归提取（阶梯制）：**
| URL 数量 | 递归轮数 |
|----------|----------|
| ≤200 | 3 轮 |
| 200-500 | 2 轮 |
| 500-800 | 1 轮 |
| >800 | 0 轮 |

### Phase 3: 批量下载

```bash
curl -H "User-Agent: Mozilla/5.0..." \
     -H "Referer: $TARGET" \
     --max-time 15 \
     "$url" -o "$OUTDIR/js/${hash}.js"
```

文件按 MD5 命名，保留 `js_url_map.txt`（hash → URL 映射）。

### Phase 4: Source Map 检测

```bash
status=$(curl -sI -o /dev/null -w "%{http_code}" "${url}.map")
```

HTTP 200 → 下载到 `sourcemaps/`，用 `sourcemap` 工具还原源码。

### Phase 5: JS 美化（阶梯制）

| JS 数量 | 策略 |
|---------|------|
| ≤100 | 全部美化 |
| 100-300 | >10KB 美化 |
| 300-500 | >50KB 美化 |
| >500 | 跳过美化 |

### Phase 6: 凭据硬编码审计（核心）

**v2 扫描器** 支持 20+ 种凭据类型，分三级置信度：

| 级别 | 方法 | 误报率 |
|------|------|--------|
| 🔴 高 | 精确正则（AKIA..., ghp_..., sk-live_...） | 极低 |
| 🟡 中 | 结构化分析（Object.assign, JSON 配置, URL 嵌入） | 低 |
| 🟢 低 | 关键词匹配（变量名含 token/key/secret） | 高 |

**扫描策略（阶梯制）：**
| JS 数量 | 策略 |
|---------|------|
| ≤100 | v2 全量 |
| 100-300 | v2 过滤 >1MB 文件 |
| 300-500 | v2 轻量（仅对象赋值+环境变量+高置信度正则） |
| >500 | grep 轻量（前 200 个文件关键词匹配） |

**误报过滤：** 自动运行 `filter_false_positives.py` 处理 Vue 变量名、模板字符串、函数参数、注释等常见误报。

### Phase 7: 框架解析

根据技术栈探测结果调用对应解析器：

| 框架 | 解析内容 |
|------|----------|
| React | webpack chunks, 组件列表, 路由, API 端点 |
| Vue | 异步组件, 路由, API 端点, Store 状态 |
| Angular | 模块, 服务, 路由, 依赖注入 |
| 小程序 | 分包, 页面路由, API 调用 |

### Phase 8: 报告生成

输出结构化报告，包含：
- 域名资产清单（关联域名 + 子域名）
- JS 文件清单
- Source Map 检测结果
- 高/中/低三级凭据发现
- 框架配置暴露分析
- 修复建议

---

## 使用方式

### 命令行调用

```bash
# 方式1: 直接输入 URL
bash js-harvester.sh https://www.example.com

# 方式2: 输入域名（自动子域名枚举）
bash js-harvester.sh "example.com"

# 方式3: 输入公司名称（自动域名发现 + 子域名枚举）
bash js-harvester.sh "示例公司"

# 方式4: 指定技术栈和输出目录
bash js-harvester.sh "华为" vue /tmp/huawei-audit
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
├── domains.json             # 结构化域名结果
├── tech_stack.txt           # 探测到的技术栈
├── all_js_urls.txt          # 合并去重后的 JS URL
├── js/                      # 下载的原始 JS 文件
├── js_beautified/           # 美化后的 JS 文件
├── sourcemaps/              # Source Map 文件
├── findings_v2/
│   ├── report_v2.md         # 凭据审计报告
│   ├── all_findings.json    # 完整发现列表
│   ├── high_conf.json       # 高置信度凭据
│   ├── obj_assign.json      # 对象赋值配置
│   └── ...
└── framework_analysis/      # 框架解析结果
```

### 单独使用域名发现

```bash
# 只收集域名资产，不执行 JS 扫描
python3 scripts/discover_domains.py "示例公司" /tmp/output.json

# 输入域名直接枚举子域名
python3 scripts/discover_domains.py "example.com" /tmp/output.json

# 输出格式
{
  "input": "example.com",
  "mode": "domain",
  "main_domain": "example.com",
  "valid_domains": [{"domain": "example.com", "ip": "1.2.3.4", "http": 200}],
  "subdomains": {
    "total_unique": 150,
    "dns_resolvable": 45,
    "by_category": {
      "production": 5,
      "testing": 8,
      "api": 12,
      "infrastructure": 3,
      "management": 2,
      "other": 15
    },
    "list": [
      {"subdomain": "api.example.com", "ip": "1.2.3.5", "category": "api"},
      ...
    ]
  }
}
```

---

## 脚本清单

### 核心脚本

| 脚本 | 用途 |
|------|------|
| `js-harvester.sh` | ⭐ 主脚本，编排完整 8 阶段流程 |
| `discover_domains.py` | 域名资产发现（关联域名 + 子域名枚举） |
| `discover_company_url.py` | 公司名到 URL 快速映射（辅助） |
| `spider_js.py` | Playwright 浏览器动态爬取 |

### 凭据扫描

| 脚本 | 用途 |
|------|------|
| `scan_credentials_v2.py` | 深度凭据扫描 v2（结构化分析） |
| `filter_false_positives.py` | 误报过滤器 |
| `deep-credential-scan.sh` | Semgrep + TruffleHog 深度扫描 |

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
| `extract_inline_js.py` | 提取页面内联 JS |
| `check_sourcemaps.sh` | Source Map 可用性检测 |
| `js-audit.sh` | 快速单域名审计（轻量版） |

---

## 参考文档

- `references/flow.md` — 完整 8 阶段流程详细说明
- `references/credential-types.md` — 支持的凭据类型清单（20+ 种）
- `references/thresholds.md` — 阶梯制阈值策略详解
- `references/cloudflare-bypass.md` — Cloudflare 防护绕过策略

---

## 常见问题

**Q: 输入公司名后域名发现失败？**
A: v2 支持三种输入模式：URL、域名、公司名。对于未映射的公司，使用 URL 或域名模式：`js-harvester.sh https://www.target.com` 或 `js-harvester.sh target.com`

**Q: 扫描被 Cloudflare 拦截？**
A: 脚本会自动降级为 curl 模式。对于重度防护目标，手动提供 Cookie：`export CF_COOKIE="cf_clearance=xxx; __cf_bm=yyy"`

**Q: 子域名枚举太慢？**
A: DNS 字典爆破是主要耗时点。可编辑脚本减少字典大小，或只使用 crt.sh + subfinder 跳过 DNS 爆破。

**Q: 误报太多？**
A: v2 扫描器已内置误报过滤。重点关注 🔴 高置信度发现，🟡 中置信度需人工验证，🟢 低置信度仅作参考。

**Q: 如何只收集域名不扫描 JS？**
A: 单独运行 `discover_domains.py`（见上方"单独使用域名发现"）。

---

## 安全声明

本技能仅用于授权的安全测试和漏洞评估。使用前应获得目标网站所有者的明确书面授权。未经授权的扫描可能违反法律法规。
