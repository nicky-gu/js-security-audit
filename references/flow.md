# JS 安全审计 8 阶段流程详细说明

## Phase -0.5: 域名资产发现

### 输入解析
- URL 模式: `https://www.example.com` → 直接使用
- 公司名模式: `示例公司` → 触发自动发现

### 域名发现流程
```
输入公司名
  │
  ├─→ 硬编码映射表查询（示例公司→example.com）
  │   命中 → 使用映射域名
  │   未命中 → 通用拼音猜测（www.{拼音}.com）
  │
  ├─→ curl 可达性验证（HTTP 200/301/302）
  │   成功 → 使用主域名
  │   失败 → 尝试 .com.cn 备选
  │
  └─→ 关联域名变体生成
      ├── 后缀变体: -global, -group, -china, -cn, -auto, -tech
      ├── TLD 变体: .com, .cn, .com.cn, .net, .org
      └── 可达性验证（只保留能解析的）
```

### 子域名枚举
三层叠加策略：
1. **crt.sh** — 证书透明度日志被动收集（零噪音）
2. **subfinder** — 开源情报收集（API + 搜索引擎）
3. **DNS 字典爆破** — 200+ 常见子域名前缀（轻量验证）

DNS 字典覆盖：www, mail, api, admin, test, dev, staging, portal, app, cdn, static, login, sso, partner, crm, erp, uat, srm, wms, transmission, edi, itsm...

### 输出
- `domains.txt` — 每行一个 URL，用于后续多域名扫描
- `domains.json` — 结构化结果（包含主域名、关联域名、子域名列表）

---

## Phase 0: 技术栈探测

通过 curl 获取首页 HTML，关键词匹配：
- **React**: `react`, `__REACT__`, `react-router`, `webpack`
- **Vue**: `vue`, `__VUE__`, `v-if`, `v-for`, `vue-router`
- **Angular**: `ng-`, `angular`, `@angular`, `.module(`, `.component(`
- **小程序**: `miniProgram`, `wx.js`, `weixin`, `swan`, `my.get`
- **React Native**: `react-native`, `RN.`, `__fbBatchedBridge`
- **Flutter**: `flutter`, `flutter_inappwebview`

技术栈自动写入 `tech_stack.txt`，后续阶段据此调用专用解析脚本。

---

## Phase 1: JS 资产收集（多域名并行）

### 多域名扫描逻辑
```
for each domain in domains.txt:
    ├─→ Katana 深度爬取（3层深度，10秒超时）
    │   成功 → 记录 JS URL
    │   被 Cloudflare 拦截 → 返回 0
    │
    ├─→ Playwright 动态渲染（仅主域名，避免过多浏览器实例）
    │   捕获 SPA 异步加载的 JS
    │   拦截 → 返回 0
    │
    └─→ curl 降级（当 Katana < 3 个 JS 时触发）
        提取页面内嵌的 <script src="..."> 和 href
        相对路径补全为绝对 URL
```

### Cloudflare 处理
- headless 浏览器被 Cloudflare 挑战页拦截（返回 5 秒等待页面）
- curl 模式带 `User-Agent` + `Referer` 可绕过基础防护
- 重度防护目标需手动提供 Cookie

### 技术栈专用提取
根据 Phase 0 探测结果自动调用：
- `extract_webpack_chunks.py` — 提取 webpack 异步 chunk 文件名
- `extract_vue_chunks.py` — 提取 Vue 异步组件 JS 路径
- `extract_miniapp_chunks.py` — 提取小程序分包路径

---

## Phase 2: URL 清洗与去重

### 问题背景
Cloudflare 挑战页会给每个请求附加 token 参数：
```
__cf_chl_tk=azMeGd_oIDOqoJKhMtkcYdG.Fg9rt6LlP0.a8l9o6G8-1782040776-1.0.1.1-csxXhbZzZrqB849E_WfPKBKrhBoig76w20ua8yxl08A
ray=a0f29e84ee4f8f74
```
导致同一 JS 文件重复出现几百次。

### 清洗规则
1. **去掉 query string** 后按 clean URL 去重
2. **过滤 Cloudflare 路径**: `cdn-cgi/challenge-platform/*`
3. **过滤非 JS 资源**: `.css`, `.png`, `.jpg`, `.woff`, `.ttf`（大小写不敏感）
4. **过滤管理路径**: `/node/*/edit`, `/delete`, `/layout`, `/unmasquerade`
5. **过滤社交媒体**: `linkedin.com`, `instagram.com`, `youtube.com`, `weibo.com`, `bilibili.com`, `xiaohongshu.com`

### 递归提取（阶梯制）
| URL 数量 | 策略 |
|----------|------|
| ≤200 | 3 轮递归（从已下载 JS 中提取更多 JS URL） |
| 200-500 | 2 轮递归 |
| 500-800 | 1 轮递归 |
| >800 | 跳过递归（防止无限膨胀） |

---

## Phase 3: 批量下载

### 下载策略
- 使用带请求头的 curl 绕过 Cloudflare 基础防护
- 文件按 MD5 哈希命名（避免文件名冲突和路径遍历）
- 保留 `js_url_map.txt`（哈希 → 原始 URL 映射）
- 15 秒超时，5 秒连接超时

### 请求头
```bash
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
Referer: $TARGET
Accept: */*
Accept-Language: en-US,en;q=0.9
```

---

## Phase 4: Source Map 检测

对每个下载的 JS 文件：
1. 探测 `${url}.map` 的 HTTP 状态码
2. 状态码 200 → 下载并保存到 `sourcemaps/`
3. 使用 `sourcemap` 工具还原原始源码

Source Map 泄露意味着攻击者可还原压缩后的 JS 为完整源码，获取业务逻辑和内部 API 路径。

---

## Phase 5: JS 美化（阶梯制）

js-beautify 将压缩后的 JS 还原为可读格式，便于人工审查和正则匹配。

| JS 数量 | 策略 | 说明 |
|---------|------|------|
| ≤100 | 全部美化 | 完整性优先 |
| 100-300 | >10KB 美化 | 跳过小碎片（通常是库文件） |
| 300-500 | >50KB 美化 | 只处理核心 bundle |
| >500 | 跳过美化 | 直接复制原文件，用轻量扫描 |

---

## Phase 6: 凭据硬编码审计（核心）

### v2 扫描器架构
`scan_credentials_v2.py` 采用"结构化分析为主，正则为辅"的策略：

#### 1. 对象赋值模式（OBJ_ASSIGN）
扫描 JS 文件中的对象赋值语句：
```javascript
Object.assign(config, {apiKey: "sk-abc123"})
config = {secret: "my-secret"}
```

#### 2. 环境变量引用（ENV_REF）
```javascript
process.env.API_KEY
window.__ENV__.secret
```

#### 3. URL 嵌入凭据（URL_CRED）
```javascript
fetch("https://user:pass@api.example.com/data")
```

#### 4. JSON 配置块（JSON_CONFIG）
提取完整的 JSON 对象：
```javascript
{"apiKey": "sk-abc123", "endpoint": "https://api.example.com"}
```

#### 5. Base64 候选（BASE64）
基于香农熵检测高熵字符串：
- 熵值 > 4.8 标记为候选
- 上下文验证（前后是否有关键词如 `token`, `key`, `secret`）
- 过滤短字符串（<20 字符）

#### 6. 高置信度正则（HIGH_CONF）
20+ 种精确模式：
```
AWS Access Key: AKIA[A-Z0-9]{16}
GitHub PAT: ghp_[a-zA-Z0-9]{36}
Slack Token: xox[baprs]-[a-zA-Z0-9\-]+
OpenAI Key: sk-[a-zA-Z0-9]{20,}
JWT: eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*
```

### 阶梯制扫描策略

| JS 数量 | 策略 | 说明 |
|---------|------|------|
| ≤100 | v2 全量 | 所有分析方法全部执行 |
| 100-300 | v2 过滤大文件 | 跳过 >1MB 文件（避免内存问题） |
| 300-500 | v2 轻量模式 | 仅对象赋值+环境变量+高置信度正则 |
| >500 | grep 轻量 | 只关键词匹配前 200 个文件 |

### 误报过滤
`filter_false_positives.py` 处理常见误报：
- Vue 变量名：`apiKey` 作为变量名而非实际值
- 模板字符串：`${apiKey}` 插值（值来自外部）
- 函数参数：`function(apiKey)` 形式参数
- 注释示例：`// apiKey: "example"` 被截断的注释
- 伪值：`test123`、`example`、`demo`、`placeholder`

---

## Phase 7: 框架解析

### 解析内容
根据技术栈探测结果，解析源码中的：
- **路由列表** — 所有前端路由路径
- **API 端点** — 后端 API 地址和参数
- **组件列表** — 前端组件名称和依赖关系
- **Store 状态** — Vuex/Pinia 状态树结构
- **配置暴露** — 运行时配置（如 Nuxt 的 `window.__NUXT__`）

### 典型发现
```javascript
// Nuxt 运行时配置暴露
window.__NUXT__ = {
  config: {
    apiUrl: "https://api.example.com",
    kfUrl: "https://support.example.com",
    gio: {projectId: "xxx", trackToken: "xxx"}
  }
}
```

---

## Phase 8: 报告生成

### 报告结构
```markdown
# JS 安全审计报告

## 执行摘要
- 目标域名: xxx
- 发现域名: xxx 个
- JS 文件: xxx 个
- 高置信度凭据: xxx 个
- 中置信度发现: xxx 个
- Source Map: xxx 个

## 域名资产
### 关联主域名
### 子域名清单

## JS 文件清单

## 高置信度凭据（需立即修复）

## 中置信度发现（建议审查）

## 低置信度发现（参考）

## 框架配置暴露

## 修复建议
```

### 严重程度分级
- **🔴 高置信度** — 精确正则匹配（如 `AKIA...` AWS Key），100% 确认
- **🟡 中置信度** — 结构化分析发现（如 `Object.assign({apiKey: "..."})`），需人工验证
- **🟢 低置信度** — 关键词匹配（如变量名 `apiKey`），大概率误报

---

## 异常处理

### 超时处理
- Katana: 单域名 10 秒超时
- curl: 单文件 15 秒超时
- 整体脚本: 后台模式运行，避免 30 分钟 exec 超时

### 内存保护
- JS 文件 >1MB 跳过美化
- 超大文件跳过 Python 扫描（避免内存溢出）
- 使用流式读取而非一次性加载

### 降级策略
| 场景 | 降级方案 |
|------|----------|
| subfinder 未安装 | 只用 DNS 字典爆破 |
| katana 被拦截 | 自动切换 curl 降级 |
| curl 被 403 | 提示用户手动提供 Cookie |
| js-beautify 未安装 | 跳过美化，直接扫描原文件 |
| playwright 下载浏览器失败 | 跳过动态渲染，依赖 katana + curl |
| 文件过多 | 阶梯制减少递归/美化/扫描深度 |
