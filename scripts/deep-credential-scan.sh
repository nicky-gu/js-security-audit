#!/bin/bash
# 深度凭据扫描 - 专门针对JS中的硬编码凭据
# 用法: ./deep-credential-scan.sh <JS目录>

JS_DIR="$1"
OUTDIR="${2:-./findings}"
mkdir -p "$OUTDIR"

if [ ! -d "$JS_DIR" ]; then
    echo "用法: $0 <JS目录> [输出目录]"
    exit 1
fi

echo "[*] 深度扫描JS目录: $JS_DIR"

# 1. 高置信度凭据模式
HIGH_CONF="$OUTDIR/high_confidence_credentials.txt"
> "$HIGH_CONF"

grep -ri -E \
    '(api[_-]?key["\'\s]*[:=]["\'\s]*[A-Za-z0-9_-]{16,}|'\
    'secret["\'\s]*[:=]["\'\s]*[A-Za-z0-9_-]{16,}|'\
    'token["\'\s]*[:=]["\'\s]*[A-Za-z0-9_-]{16,}|'\
    'password["\'\s]*[:=]["\'\s]*[^"\'\s]{4,}|'\
    'bearer\s+[A-Za-z0-9_\-\.]{20,}|'\
    'Basic\s+[A-Za-z0-9+/]{20,}={0,2}|'\
    'AWS_ACCESS_KEY_ID["\'\s]*[:=]["\'\s]*[A-Z0-9]{20}|'\
    'AWS_SECRET_ACCESS_KEY["\'\s]*[:=]["\'\s]*[A-Za-z0-9/]{40}|'\
    'sk-[a-zA-Z0-9]{20,}|'\
    'ghp_[a-zA-Z0-9]{36}|'\
    'github_pat_[a-zA-Z0-9_]{22,}|'\
    'xox[baprs]-[0-9]{10,}-[0-9]{10,}-[a-zA-Z0-9]{24,}|'\
    'SG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}|'\
    'key-[a-f0-9]{32})' \
    "$JS_DIR" > "$HIGH_CONF" 2>/dev/null || true

echo "[+] 高置信度: $(wc -l < "$HIGH_CONF" 2>/dev/null || echo 0) 条"

# 2. 可疑URL模式（包含凭据的URL）
grep -ri -E \
    'https?://[^/\s:]+:[^/\s:]+@[^/\s]+' \
    "$JS_DIR" > "$OUTDIR/credentials_in_urls.txt" 2>/dev/null || true

echo "[+] URL中凭据: $(wc -l < "$OUTDIR/credentials_in_urls.txt" 2>/dev/null || echo 0) 条"

# 3. 环境变量/配置注入
grep -ri -E \
    '(process\.env\.|window\.__[A-Z_]+__|globalConfig|appConfig|runtimeConfig)' \
    "$JS_DIR" > "$OUTDIR/config_references.txt" 2>/dev/null || true

echo "[+] 配置引用: $(wc -l < "$OUTDIR/config_references.txt" 2>/dev/null || echo 0) 条"

# 4. 生成汇总
cat > "$OUTDIR/summary.txt" << EOF
深度凭据扫描结果
================
时间: $(date)
扫描目录: $JS_DIR

高置信度凭据:     $(wc -l < "$HIGH_CONF" 2>/dev/null || echo 0)
URL中凭据:        $(wc -l < "$OUTDIR/credentials_in_urls.txt" 2>/dev/null || echo 0)
配置引用:         $(wc -l < "$OUTDIR/config_references.txt" 2>/dev/null || echo 0)
EOF

echo "[*] 结果保存在: $OUTDIR/"
