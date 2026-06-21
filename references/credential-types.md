# 支持的凭据类型清单

## 云服务商

| 类型 | 模式 | 示例 |
|------|------|------|
| AWS Access Key | `AKIA\|ASIA\|AROA\|AIDA[A-Z0-9]{16}` | AKIAIOSFODNN7EXAMPLE |
| AWS Secret Key | `aws_secret_access_key` 附近高熵字符串 | wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY |
| Azure Key | `[a-zA-Z0-9]{52}` | dGhpcyBpcyBhIHRlc3Qga2V5 |
| GCP Key | `AIza[0-9A-Za-z_-]{35}` | AIzaSyDaGmWKa4JsflHGTbJa... |
| Alibaba Cloud | `LTAI[A-Za-z0-9]{12,20}` | LTAI4Fxxxxxxxxxxxxx |
| Tencent Cloud | 环境变量引用 | TENCENT_SECRET_ID |

## 代码平台

| 类型 | 模式 | 示例 |
|------|------|------|
| GitHub PAT (classic) | `ghp_[a-zA-Z0-9]{36}` | ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx |
| GitHub Fine PAT | `github_pat_[a-zA-Z0-9_]{22,}` | github_pat_11ABC... |
| GitHub OAuth | `gho_[a-zA-Z0-9]{36}` | gho_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx |
| GitLab Token | `glpat-[a-zA-Z0-9\-]{20,}` | glpat-xxxxxxxxxxxxxxxxxxxx |
| Bitbucket | 环境变量引用 | BITBUCKET_APP_PASSWORD |

## 协作工具

| 类型 | 模式 | 示例 |
|------|------|------|
| Slack Token | `xox[baprs]-[a-zA-Z0-9\-]+` | `xoxb-EXAMPLE-TOKEN-REDACTED` |
| Slack Webhook | `https://hooks.slack.com/services/T[a-zA-Z0-9_]{8}/B[a-zA-Z0-9_]{10}/[a-zA-Z0-9_]{24}` | `https://hooks.slack.com/services/TEXAMPLE00/BEXAMPLE00/EXAMPLE-REDACTED` |
| Discord Webhook | `https://discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9_\-]+` | https://discord.com/api/webhooks/123456789/abcdef... |
| Microsoft Teams | 环境变量引用 | TEAMS_WEBHOOK_URL |

## AI 服务

| 类型 | 模式 | 示例 |
|------|------|------|
| OpenAI API Key | `sk-[a-zA-Z0-9]{20,}` | sk-abc123def456ghi789jkl012mno345pqr678stu9vwx0yz |
| Anthropic | 环境变量引用 | ANTHROPIC_API_KEY |
| HuggingFace | `hf_[a-zA-Z0-9]{30,}` | hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx |
| Cohere | 环境变量引用 | COHERE_API_KEY |
| Google AI | `AIza[0-9A-Za-z_-]{35}` | AIzaSyDaGmWKa4JsflHGTbJa... |

## 支付网关

| 类型 | 模式 | 示例 |
|------|------|------|
| Stripe Key | `sk_live_[a-zA-Z0-9]{24,}` 或 `pk_live_[a-zA-Z0-9]{24,}` | `sk_live_REDACTED_EXAMPLE` |
| Stripe Test | `sk_test_[a-zA-Z0-9]{24,}` | `sk_test_REDACTED_EXAMPLE` |
| PayPal | 环境变量引用 | PAYPAL_CLIENT_SECRET |
| Square | 环境变量引用 | SQUARE_ACCESS_TOKEN |

## 通信服务

| 类型 | 模式 | 示例 |
|------|------|------|
| Twilio SID | `AC[a-zA-Z0-9]{32}` | ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx |
| Twilio Token | `[a-zA-Z0-9]{32}` | xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx |
| SendGrid | `SG\.[a-zA-Z0-9]{22}\.[a-zA-Z0-9]{43}` | SG.xxxxxxxxxxxxxxxxxxxxxx.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx |
| Mailgun | 环境变量引用 | MAILGUN_API_KEY |

## 认证令牌

| 类型 | 模式 | 示例 |
|------|------|------|
| JWT | `eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*` | eyJhbGciOiJIUzI1NiIs... |
| OAuth Token | `ya29\.[a-zA-Z0-9_-]+` | ya29.a0AfH6SMB... |
| Bearer Token | `Bearer\s+[a-zA-Z0-9_\-\.]+` | Bearer eyJhbGciOiJIUzI1Ni... |
| Basic Auth (base64) | `Basic\s+[A-Za-z0-9+/]{20,}={0,2}` | Basic dXNlcjpwYXNz |
| API Key (通用) | `api[_-]?key\s*[:=]\s*["\'][a-zA-Z0-9_\-]{16,}["\']` | api_key: "xxxxxxxxxxxxxxxx" |

## 数据库

| 类型 | 模式 | 示例 |
|------|------|------|
| MongoDB URI | `mongodb(\+srv)?://[^:]+:[^@]+@` | mongodb://user:pass@host:27017/db |
| Redis URI | `redis://:[^@]+@` | redis://:pass@host:6379 |
| PostgreSQL | `postgresql://[^:]+:[^@]+@` | postgresql://user:pass@host/db |
| MySQL | `mysql://[^:]+:[^@]+@` | mysql://user:pass@host/db |
| JDBC | `jdbc:[^:]+://[^:]+:[^@]+@` | jdbc:mysql://user:pass@host/db |

## 加密密钥

| 类型 | 模式 | 示例 |
|------|------|------|
| RSA 私钥 | `-----BEGIN RSA PRIVATE KEY-----` | PEM 格式 |
| EC 私钥 | `-----BEGIN EC PRIVATE KEY-----` | PEM 格式 |
| Ed25519 | `-----BEGIN OPENSSH PRIVATE KEY-----` | PEM 格式 |
| PGP 私钥 | `-----BEGIN PGP PRIVATE KEY-----` | PEM 格式 |
| 通用私钥 | `-----BEGIN PRIVATE KEY-----` | PEM 格式 |
| SSH Key | `ssh-rsa\s+` 或 `ssh-ed25519\s+` | ssh-rsa AAAA... |

## 其他

| 类型 | 模式 | 示例 |
|------|------|------|
| Firebase Key | `AAAA[A-Za-z0-9_-]{7}:[A-Za-z0-9_-]{140}` | AAAA... |
| Google API Key | `AIza[0-9A-Za-z_-]{35}` | AIzaSyDaGmWKa4JsflHGTbJa... |
| Amplitude | `amp_[a-zA-Z0-9]{32}` | amp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx |
| Mixpanel | 环境变量引用 | MIXPANEL_TOKEN |
| Sentry DSN | `https://[a-zA-Z0-9]+@[a-zA-Z0-9]+\.ingest\.sentry\.io/\d+` | https://key@project.ingest.sentry.io/1234567 |
| New Relic | 环境变量引用 | NEW_RELIC_LICENSE_KEY |
| Datadog | 环境变量引用 | DATADOG_API_KEY |

## 检测策略说明

### 高置信度 vs 中置信度

**高置信度**（精确正则匹配）：
- 模式高度特异，误报率极低
- 如 AWS Key 的 `AKIA` 前缀 + 16 位大写字母数字
- 如 GitHub PAT 的 `ghp_` 前缀 + 36 位字符
- 这些模式几乎不可能是变量名或注释

**中置信度**（结构化分析）：
- 通过 AST 或正则提取对象赋值中的字符串值
- 如 `Object.assign({apiKey: "sk-abc123"})`
- 需要结合上下文判断，可能误报（如 `apiKey: null`）
- 误报过滤器会处理大部分误报场景

### 低置信度（关键词匹配）

仅作为参考，大概率误报：
- 变量名包含 `key`、`token`、`secret` 等关键词
- 函数参数名（`function(apiKey)`）
- 模板字符串中的变量名（`${apiKey}`）
- 注释中的示例代码片段

### 误报处理

`filter_false_positives.py` 会过滤：
1. **Vue 变量名** — 组件 data 中定义的变量名被识别为值
2. **模板字符串** — ES6 模板字符串中的变量名不是实际值
3. **函数参数** — 形式参数名不是实际值
4. **注释** — 代码注释中的示例片段
5. **伪值** — `test123`、`example`、`demo`、`placeholder`、`null`、`undefined`
6. **短字符串** — 长度 < 8 的字符串（不可能是凭据）
7. **常见值** — `true`、`false`、`0`、`1`、`on`、`off`