#!/bin/bash
# JS资产收集与凭据硬编码审计 - 自动化流水线
# 用法: ./js-audit.sh <目标URL>

set -e

TARGET="$1"
if [ -z "$TARGET" ]; then
    echo "用法: $0 <目标URL>"
    echo "示例: $0 https://example.com"
    exit 1
fi

DOMAIN=$(echo "$TARGET" | sed -E 's|https?://||' | sed -E 's|/.*||')
OUTDIR="./js-audit-${DOMAIN}-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTDIR"

echo "========================================"
echo "目标: $TARGET"
echo "输出目录: $OUTDIR"
echo "========================================"

# ---- Step 1: Katana 深度爬取 JS ----
echo "[1/6] Katana 深度爬取所有JS链接..."
katana -u "$TARGET" -jc -jsl -o "$OUTDIR/katana_js_urls.txt" -silent 2>/dev/null || true

# ---- Step 2: 下载所有JS ----
echo "[2/6] 下载所有JS文件..."
mkdir -p "$OUTDIR/js"
if [ -f "$OUTDIR/katana_js_urls.txt" ]; then
    cat "$OUTDIR/katana_js_urls.txt" | while read url; do
        [ -z "$url" ] && continue
        fname=$(echo "$url" | md5sum | cut -d' ' -f1).js
        curl -sL "$url" -o "$OUTDIR/js/$fname" --max-time 10 2>/dev/null || true
    done
fi
JS_COUNT=$(ls "$OUTDIR/js/" 2>/dev/null | wc -l)
echo "  下载了 $JS_COUNT 个JS文件"

# ---- Step 3: JS 美化 ----
echo "[3/6] JS 美化处理..."
mkdir -p "$OUTDIR/js_beautified"
for f in "$OUTDIR/js/"*.js; do
    [ -f "$f" ] || continue
    bn=$(basename "$f")
    js-beautify -f "$f" -o "$OUTDIR/js_beautified/$bn" 2>/dev/null || true
done

# ---- Step 4: 提取内联JS和配置 ----
echo "[4/6] 提取页面中的内联JS和配置..."
python3 /opt/sec-tools/scripts/extract_inline_js.py "$TARGET" "$OUTDIR" 2>/dev/null || true

# ---- Step 5: 凭据硬编码扫描 ----
echo "[5/6] 凭据硬编码扫描..."
mkdir -p "$OUTDIR/findings"

# 关键词扫描
PATTERNS="(api[_-]?key|apikey|secret|token|password|passwd|pwd|auth|bearer|access[_-]?key|client[_-]?id|client[_-]?secret|private[_-]?key|aws_access_key_id|aws_secret_access_key|github_token|slack_token|firebase|algolia)"

grep -ri -E "$PATTERNS" "$OUTDIR/js/" 2>/dev/null > "$OUTDIR/findings/credential_hints.txt" || true
grep -ri -E "$PATTERNS" "$OUTDIR/js_beautified/" 2>/dev/null >> "$OUTDIR/findings/credential_hints.txt" || true

# 高价值目标（base64 编码的可能性）
grep -ri -E "[A-Za-z0-9+/]{20,}={0,2}" "$OUTDIR/js_beautified/" 2>/dev/null | \
    grep -iE "$PATTERNS" > "$OUTDIR/findings/base64_candidates.txt" || true

# ---- Step 6: 生成报告 ----
echo "[6/6] 生成报告..."
HINTS=$(wc -l < "$OUTDIR/findings/credential_hints.txt" 2>/dev/null || echo 0)
B64=$(wc -l < "$OUTDIR/findings/base64_candidates.txt" 2>/dev/null || echo 0)

cat > "$OUTDIR/REPORT.md" << REPORT_EOF
# JS 资产审计报告
- 目标: $TARGET
- 时间: $(date)
- JS文件总数: $JS_COUNT

## 发现汇总

### 凭据相关线索
$HINTS 条匹配

### Base64 编码候选
$B64 条匹配

## 下一步建议
1. 检查 \`findings/credential_hints.txt\` 中的高价值条目
2. 对 beautified JS 进行手动代码审计
3. 检查 Source Map 文件 (.js.map)
4. 检查 webpack 打包中的模块路径泄露
REPORT_EOF

echo ""
echo "========================================"
echo "审计完成！输出目录: $OUTDIR"
echo ""
echo "关键文件:"
echo "  - $OUTDIR/findings/credential_hints.txt     ← 凭据线索"
echo "  - $OUTDIR/findings/base64_candidates.txt     ← Base64编码候选"
echo "  - $OUTDIR/REPORT.md                           ← 汇总报告"
echo "========================================"
