#!/bin/bash
# 全生态 JS 资产收集 - 适配 React / Vue / Angular / 小程序 / RN WebView / 传统多页
# 用法: ./js-harvester.sh <目标URL|公司名称> [技术栈猜测] [输出目录]

set -e

INPUT="${1:-}"
TECH="${2:-auto}"
OUTDIR="${3:-./js-harvest-$(date +%Y%m%d_%H%M%S)}"

if [ -z "$INPUT" ]; then
    echo "用法: $0 <目标URL|公司名称> [技术栈:auto|react|vue|angular|miniapp|rn|hybrid|legacy] [输出目录]"
    echo ""
    echo "示例:"
    echo "  $0 https://www.example.com"
    echo "  $0 示例公司"
    echo "  $0 华为 vue"
    exit 1
fi

# ============================================================
# Phase -1: 自动发现 URL（如果输入不是URL）
# ============================================================
# 检查输入是否是URL
if echo "$INPUT" | grep -qE '^https?://'; then
    TARGET="$INPUT"
    echo "[Phase -1] 直接使用URL: $TARGET"
else
    echo "[Phase -1] 输入'$INPUT'不是URL，尝试发现官网..."
    COMPANY_NAME="$INPUT"
    
    # 尝试用 kimi_search 搜索（如果环境支持）
    SEARCH_RESULT=""
    if command -v python3 &>/dev/null; then
        # 调用 discover_company_url.py（不带搜索文本时返回基于名称的猜测）
        DISCOVERED=$(python3 /opt/sec-tools/scripts/discover_company_url.py "$COMPANY_NAME" 2>/dev/null | grep '\[发现\] 最佳猜测:' | sed 's/.*最佳猜测: //')
        if [ -n "$DISCOVERED" ]; then
            TARGET="$DISCOVERED"
            echo "  -> 发现候选: $TARGET"
        fi
    fi
    
    # 如果自动发现失败，用常见规则猜测
    if [ -z "$TARGET" ]; then
        # 简单拼音映射（常见大公司）
        case "$COMPANY_NAME" in
            "华为") TARGET="https://www.huawei.com" ;;
            "腾讯") TARGET="https://www.tencent.com" ;;
            "阿里"|"阿里巴巴") TARGET="https://www.alibaba.com" ;;
            "字节"|"字节跳动") TARGET="https://www.bytedance.com" ;;
            "小米") TARGET="https://www.mi.com" ;;
            "比亚迪") TARGET="https://www.byd.com" ;;
            "吉利") TARGET="https://www.geely.com" ;;
            *)
                # 通用猜测：取公司名拼音（简单处理）
                PINYIN=$(echo "$COMPANY_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/ //g' | sed 's/（//g; s/）//g')
                TARGET="https://www.${PINYIN}.com"
                echo "  -> 通用猜测: $TARGET"
                ;;
        esac
    fi
    
    # 验证 URL 是否可达
    echo "  -> 验证URL可达性..."
    HTTP_CODE=$(curl -sI -o /dev/null -w "%{http_code}" "$TARGET" --max-time 10 --connect-timeout 5 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" != "200" ] && [ "$HTTP_CODE" != "301" ] && [ "$HTTP_CODE" != "302" ]; then
        echo "  ⚠️  警告: $TARGET 返回 HTTP $HTTP_CODE"
        echo "  -> 尝试 https://www.${COMPANY_NAME}.com.cn ..."
        ALT_TARGET="https://www.${COMPANY_NAME}.com.cn"
        ALT_CODE=$(curl -sI -o /dev/null -w "%{http_code}" "$ALT_TARGET" --max-time 10 --connect-timeout 5 2>/dev/null || echo "000")
        if [ "$ALT_CODE" = "200" ] || [ "$ALT_CODE" = "301" ] || [ "$ALT_CODE" = "302" ]; then
            TARGET="$ALT_TARGET"
            echo "  ✓ 使用备选: $TARGET"
        else
            echo "  ⚠️  备选也失败，继续使用 $TARGET"
        fi
    else
        echo "  ✓ URL 可达 (HTTP $HTTP_CODE)"
    fi
fi

mkdir -p "$OUTDIR"
DOMAIN=$(echo "$TARGET" | sed -E 's|https?://||' | sed -E 's|/.*||')

# ============================================================
# Phase -0.5: 域名资产发现（关联主域名 + 子域名枚举）
# ============================================================
echo ""
echo "[Phase -0.5] 域名资产发现..."

if [ -n "$COMPANY_NAME" ] && command -v python3 &>/dev/null; then
    echo "  -> 运行域名资产发现器..."
    python3 /opt/sec-tools/scripts/discover_domains.py "$COMPANY_NAME" "$OUTDIR/domains.json" 2>&1 | tee "$OUTDIR/domains_discovery.log" || true
    
    # 读取发现的域名列表
    if [ -f "$OUTDIR/domains.txt" ]; then
        DOMAIN_COUNT=$(wc -l < "$OUTDIR/domains.txt" 2>/dev/null || echo 0)
        echo "  发现 $DOMAIN_COUNT 个域名/子域名"
    fi
else
    echo "  跳过域名发现（直接URL模式或缺少python3）"
    # 为直接URL模式也生成一个单域名列表
    echo "https://$DOMAIN" > "$OUTDIR/domains.txt"
fi

echo ""
echo "==========================================="
echo "全生态 JS 资产收集器"
echo "目标: $TARGET"
echo "技术栈: $TECH"
echo "输出: $OUTDIR"
echo "==========================================="

# ============================================================
# Phase 0: 技术栈探测
# ============================================================
echo ""
echo "[Phase 0] 技术栈探测..."

BODY=$(curl -sL "$TARGET" --max-time 15 2>/dev/null | head -c 50000 || true)

DETECTED=""
[ -n "$BODY" ] && {
    echo "$BODY" | grep -qiE "(react|__REACT__)" && DETECTED="${DETECTED} react"
    echo "$BODY" | grep -qiE "(vue|__VUE__|v-if|v-for)" && DETECTED="${DETECTED} vue"
    echo "$BODY" | grep -qiE "(ng-|angular|@angular)" && DETECTED="${DETECTED} angular"
    echo "$BODY" | grep -qiE "(miniProgram|wx\.js|weixin)" && DETECTED="${DETECTED} miniapp"
    echo "$BODY" | grep -qiE "(react-native|RN\.|__fbBatchedBridge)" && DETECTED="${DETECTED} react-native"
    echo "$BODY" | grep -qiE "(flutter|flutter_inappwebview)" && DETECTED="${DETECTED} flutter"
}

if [ -n "$DETECTED" ] && [ "$TECH" = "auto" ]; then
    TECH=$(echo "$DETECTED" | xargs | tr ' ' '+')
    echo "  探测到: $DETECTED"
else
    echo "  使用指定: $TECH"
fi

echo "$TECH" > "$OUTDIR/tech_stack.txt"

# ============================================================
# Phase 1: 多层爬虫（多域名扫描）
# ============================================================
echo ""
echo "[Phase 1] 多层爬虫收集JS..."

# 读取所有待扫描域名
SCAN_DOMAINS="$OUTDIR/domains.txt"
if [ ! -f "$SCAN_DOMAINS" ] || [ ! -s "$SCAN_DOMAINS" ]; then
    echo "https://$DOMAIN" > "$SCAN_DOMAINS"
fi

TOTAL_KATANA=0
TOTAL_CURL=0
DOMAIN_IDX=0

while read scan_url; do
    [ -z "$scan_url" ] && continue
    DOMAIN_IDX=$((DOMAIN_IDX + 1))
    scan_domain=$(echo "$scan_url" | sed -E 's|https?://||' | sed -E 's|/.*||')
    
    echo "  -> [域名 $DOMAIN_IDX] $scan_domain"
    
    # 1.1 Katana 对每个域名
    echo "      Katana..."
    katana -u "$scan_url" -headless -js-crawl -depth 3 -timeout 10 -retry 2 > "$OUTDIR/katana_js_raw_${DOMAIN_IDX}.txt" 2>/dev/null || true
    grep -E '^https?://' "$OUTDIR/katana_js_raw_${DOMAIN_IDX}.txt" > "$OUTDIR/katana_js_${DOMAIN_IDX}.txt" 2>/dev/null || true
    kcount=$(wc -l < "$OUTDIR/katana_js_${DOMAIN_IDX}.txt" 2>/dev/null || echo 0)
    TOTAL_KATANA=$((TOTAL_KATANA + kcount))
    echo "        Katana: $kcount 个JS"
    
    # 1.2 Playwright 只对主域名（避免太多浏览器实例）
    if [ "$DOMAIN_IDX" -eq 1 ]; then
        echo "      Playwright..."
        mkdir -p "$OUTDIR/playwright"
        python3 /opt/sec-tools/scripts/spider_js.py "$scan_url" "$OUTDIR/playwright" > "$OUTDIR/playwright/spider.log" 2>&1 || true
        touch "$OUTDIR/playwright/js_urls.txt"
        pwcount=$(wc -l < "$OUTDIR/playwright/js_urls.txt" 2>/dev/null || echo 0)
        echo "        Playwright: $pwcount 个JS"
    fi
    
    # 1.3 curl 降级（如果 Katana 返回太少）
    if [ "$kcount" -lt 3 ]; then
        echo "      curl 降级..."
        curl -sL -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \
             -H "Accept: text/html" \
             --max-time 15 "$scan_url" 2>/dev/null | \
        grep -oE '(src|href)="[^"]+\.js[^"]*"' | \
        sed 's/^[^"]*"//; s/"$//' | \
        sed "s|^/|https://${scan_domain}/|" | sort -u > "$OUTDIR/curl_fallback_js_${DOMAIN_IDX}.txt" || true
        ccount=$(wc -l < "$OUTDIR/curl_fallback_js_${DOMAIN_IDX}.txt" 2>/dev/null || echo 0)
        TOTAL_CURL=$((TOTAL_CURL + ccount))
        echo "        curl: $ccount 个JS"
    fi
    
    # 合并当前域名的结果到总文件
    cat "$OUTDIR/katana_js_${DOMAIN_IDX}.txt" "$OUTDIR/curl_fallback_js_${DOMAIN_IDX}.txt" 2>/dev/null >> "$OUTDIR/all_js_urls_raw.txt" || true
    
done < "$SCAN_DOMAINS"

KATANA_COUNT=$TOTAL_KATANA
echo "     Katana 总计: $KATANA_COUNT 个JS"
PW_COUNT=$(wc -l < "$OUTDIR/playwright/js_urls.txt" 2>/dev/null || echo 0)
echo "     Playwright: $PW_COUNT 个JS"
CURL_COUNT=$TOTAL_CURL
echo "     curl 降级: $CURL_COUNT 个JS"

# 1.4 技术栈专用（只对主域名）
if echo "$TECH" | grep -qi "react"; then
    echo "  -> React 专用：提取 webpack chunk..."
    python3 /opt/sec-tools/scripts/extract_webpack_chunks.py "$TARGET" "$OUTDIR" 2>/dev/null || true
fi
if echo "$TECH" | grep -qi "vue"; then
    echo "  -> Vue 专用：提取异步组件..."
    python3 /opt/sec-tools/scripts/extract_vue_chunks.py "$TARGET" "$OUTDIR" 2>/dev/null || true
fi
if echo "$TECH" | grep -qi "miniapp"; then
    echo "  -> 小程序专用..."
    python3 /opt/sec-tools/scripts/extract_miniapp_chunks.py "$TARGET" "$OUTDIR" 2>/dev/null || true
fi

# ============================================================
# Phase 2: 合并 + URL 去重清洗 + 递归提取
# ============================================================
echo ""
echo "[Phase 2] 合并与递归抓取..."

# 确保 all_js_urls_raw.txt 包含 Playwright 的结果
if [ -f "$OUTDIR/playwright/js_urls.txt" ] && [ -s "$OUTDIR/playwright/js_urls.txt" ]; then
    cat "$OUTDIR/playwright/js_urls.txt" >> "$OUTDIR/all_js_urls_raw.txt" 2>/dev/null || true
fi

# 去重并去除空行
grep -v "^$" "$OUTDIR/all_js_urls_raw.txt" 2>/dev/null | sort -u > "$OUTDIR/all_js_urls_raw.tmp" && mv "$OUTDIR/all_js_urls_raw.tmp" "$OUTDIR/all_js_urls_raw.txt" || true

# URL 清洗：去掉 query string 后去重（解决 Cloudflare token 爆炸问题）
echo "  -> URL 清洗去重..."
python3 << 'PYEOF' 2>/dev/null
import re, sys

seen = set()
filtered = []

with open('/tmp/js-harvest-example/all_js_urls_raw.txt', 'r') as f:
# NOTE: 这里的路径应该是变量，但嵌入的 python 无法直接读取 bash 变量
# 改用 stdin 方式
    pass
PYEOF

# 用 awk 实现 URL 去重（去掉 query string）
awk '
{
    url = $0
    # 去掉 query string
    if (match(url, /\?/)) {
        clean = substr(url, 1, RSTART-1)
    } else {
        clean = url
    }
    # 过滤 Cloudflare CDN 假 URL
    if (clean ~ /cdn-cgi\/challenge-platform/) next
    # 过滤非 JS 文件（CSS/图片等）- 使用 tolower 实现不区分大小写
    if (tolower(clean) ~ /\.(css|png|jpg|jpeg|gif|svg|woff|woff2|ttf|eot)$/) next
    # 过滤 Drupal admin 路径（不是 JS）
    if (clean ~ /\/(edit|delete|layout|revisions|translations|entity_clone)\/?$/) next
    if (clean ~ /\/(unmasquerade|user\/logout)\/?/) next
    if (clean ~ /\/node\/[0-9]+\/(edit|delete|layout|revisions)/) next
    # 去重
    if (!seen[clean]++) {
        print url  # 保留原始 URL（带 query）用于下载
        clean_seen[clean] = 1
    }
}
' "$OUTDIR/all_js_urls_raw.txt" | sort -u > "$OUTDIR/all_js_urls.txt"

URL_COUNT=$(wc -l < "$OUTDIR/all_js_urls.txt" 2>/dev/null || echo 0)
echo "  清洗后 URL: $URL_COUNT (原始: $(wc -l < "$OUTDIR/all_js_urls_raw.txt" 2>/dev/null || echo 0))"

# 递归阶梯制（URL越多，递归轮数越少）
if [ "$URL_COUNT" -gt 800 ]; then
    RECURSIVE_ROUNDS=0
    echo "  JS URL 数量: $URL_COUNT (>800)，跳过递归提取"
elif [ "$URL_COUNT" -gt 500 ]; then
    RECURSIVE_ROUNDS=1
    echo "  JS URL 数量: $URL_COUNT (500-800)，执行 1 轮递归"
elif [ "$URL_COUNT" -gt 200 ]; then
    RECURSIVE_ROUNDS=2
    echo "  JS URL 数量: $URL_COUNT (200-500)，执行 2 轮递归"
else
    RECURSIVE_ROUNDS=3
    echo "  JS URL 数量: $URL_COUNT (≤200)，执行 3 轮递归"
fi

if [ "$RECURSIVE_ROUNDS" -gt 0 ]; then
    for round in $(seq 1 $RECURSIVE_ROUNDS); do
        echo "  -> 递归提取第 $round 轮..."
        NEW_URLS="$OUTDIR/round${round}_js.txt"
        > "$NEW_URLS"
        
        while read jsurl; do
            [ -z "$jsurl" ] && continue
            tmpfile=$(mktemp)
            curl -sL "$jsurl" --max-time 5 -o "$tmpfile" 2>/dev/null || true
            grep -oE 'https?://[^"\x27\s)]+\.js[^"\x27\s)]*' "$tmpfile" 2>/dev/null >> "$NEW_URLS" || true
            grep -oE '"[^"\x27\s)]+\.js[^"\x27\s)]*' "$tmpfile" 2>/dev/null | sed 's|^"|https://'"$DOMAIN"'|' >> "$NEW_URLS" || true
            rm -f "$tmpfile"
        done < "$OUTDIR/all_js_urls.txt"
        
        cat "$NEW_URLS" "$OUTDIR/all_js_urls.txt" | grep -v "^$" | sort -u > "$OUTDIR/all_js_urls.tmp"
        mv "$OUTDIR/all_js_urls.tmp" "$OUTDIR/all_js_urls.txt"
        ROUND_COUNT=$(wc -l < "$OUTDIR/all_js_urls.txt" 2>/dev/null || echo 0)
        echo "     递归后: $ROUND_COUNT 个URL"
    done
fi

TOTAL_JS=$(wc -l < "$OUTDIR/all_js_urls.txt" 2>/dev/null || echo 0)
echo "  总计发现: $TOTAL_JS 个唯一JS URL"

# ============================================================
# Phase 3: 批量下载
# ============================================================
echo ""
echo "[Phase 3] 批量下载JS文件..."
mkdir -p "$OUTDIR/js"

while read url; do
    [ -z "$url" ] && continue
    hash=$(echo "$url" | md5sum | cut -d' ' -f1)
    echo "$hash $url" >> "$OUTDIR/js_url_map.txt"
    # 添加请求头绕过 Cloudflare 基础防护
    curl -sL -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \
         -H "Referer: $TARGET" \
         -H "Accept: */*" \
         -H "Accept-Language: en-US,en;q=0.9" \
         --max-time 15 --connect-timeout 5 \
         -o "$OUTDIR/js/${hash}.js" \
         "$url" 2>/dev/null || true
done < "$OUTDIR/all_js_urls.txt"

JS_FILES=$(ls "$OUTDIR/js/"*.js 2>/dev/null | wc -l)
echo "  成功下载: $JS_FILES 个JS文件"

# ============================================================
# Phase 4: Source Map
# ============================================================
echo ""
echo "[Phase 4] Source Map 检测..."
mkdir -p "$OUTDIR/sourcemaps"

SM_FOUND=0
while read url; do
    [ -z "$url" ] && continue
    sm_url="${url}.map"
    hash=$(echo "$url" | md5sum | cut -d' ' -f1)
    status=$(curl -sI -o /dev/null -w "%{http_code}" "$sm_url" --max-time 5 2>/dev/null || echo "000")
    if [ "$status" = "200" ]; then
        echo "  [+] Source Map: $sm_url"
        curl -sL "$sm_url" -o "$OUTDIR/sourcemaps/${hash}.js.map" --max-time 10 2>/dev/null || true
        SM_FOUND=$((SM_FOUND + 1))
    fi
done < "$OUTDIR/all_js_urls.txt"

echo "  Source Map: $SM_FOUND 个"

# ============================================================
# Phase 5: JS 美化 + 框架解析
# ============================================================
echo ""
echo "[Phase 5] JS 美化与解析..."
mkdir -p "$OUTDIR/js_beautified"

# Phase 5 阶梯美化策略
JS_COUNT=$(ls "$OUTDIR/js/"*.js 2>/dev/null | wc -l)

echo "  JS 文件数: $JS_COUNT"

if [ "$JS_COUNT" -gt 500 ]; then
    echo "  [阶梯5] >500 JS: 跳过美化，直接复制原文件"
    cp "$OUTDIR/js/"*.js "$OUTDIR/js_beautified/" 2>/dev/null || true
elif [ "$JS_COUNT" -gt 300 ]; then
    echo "  [阶梯4] 300-500 JS: 只美化 >50KB 核心文件"
    for f in "$OUTDIR/js/"*.js; do
        [ -f "$f" ] || continue
        bn=$(basename "$f")
        fsz=$(stat -c%s "$f" 2>/dev/null || echo 0)
        if [ "$fsz" -gt 51200 ]; then
            js-beautify -f "$f" -o "$OUTDIR/js_beautified/$bn" 2>/dev/null || true
        else
            cp "$f" "$OUTDIR/js_beautified/$bn" 2>/dev/null || true
        fi
    done
elif [ "$JS_COUNT" -gt 100 ]; then
    echo "  [阶梯3] 100-300 JS: 只美化 >10KB 文件，跳过小碎片"
    for f in "$OUTDIR/js/"*.js; do
        [ -f "$f" ] || continue
        bn=$(basename "$f")
        fsz=$(stat -c%s "$f" 2>/dev/null || echo 0)
        if [ "$fsz" -gt 10240 ]; then
            js-beautify -f "$f" -o "$OUTDIR/js_beautified/$bn" 2>/dev/null || true
        else
            cp "$f" "$OUTDIR/js_beautified/$bn" 2>/dev/null || true
        fi
    done
else
    echo "  [阶梯1-2] ≤100 JS: 全部美化"
    for f in "$OUTDIR/js/"*.js; do
        [ -f "$f" ] || continue
        bn=$(basename "$f")
        js-beautify -f "$f" -o "$OUTDIR/js_beautified/$bn" 2>/dev/null || true
    done
fi

BEAUTIFIED_COUNT=$(ls "$OUTDIR/js_beautified/"*.js 2>/dev/null | wc -l)
echo "  完成美化: $BEAUTIFIED_COUNT 个文件"

if echo "$TECH" | grep -qi "react"; then
    echo "  -> React 解析..."
    python3 /opt/sec-tools/scripts/parse_react_bundle.py "$OUTDIR/js_beautified/" "$OUTDIR/" 2>/dev/null || true
fi
if echo "$TECH" | grep -qi "vue"; then
    echo "  -> Vue 解析..."
    python3 /opt/sec-tools/scripts/parse_vue_bundle.py "$OUTDIR/js_beautified/" "$OUTDIR/" 2>/dev/null || true
fi
if echo "$TECH" | grep -qi "miniapp"; then
    echo "  -> 小程序解析..."
    python3 /opt/sec-tools/scripts/parse_miniapp.py "$OUTDIR/js_beautified/" "$OUTDIR/" 2>/dev/null || true
fi

# ============================================================
# Phase 6: 凭据审计
# ============================================================
echo ""
echo "[Phase 6] 凭据硬编码审计..."

mkdir -p "$OUTDIR/findings"
HINTS=0; HIGH=0; URL_CREDS=0; B64=0; CONFIG=0

# Phase 6 阶梯审计策略
JS_COUNT=$(ls "$OUTDIR/js/"*.js 2>/dev/null | wc -l)

HINTS=0; HIGH=0; URL_CREDS=0; B64=0; CONFIG=0

if [ "$JS_COUNT" -gt 500 ]; then
    echo "  [阶梯5] >500 JS: grep 轻量模式"
    for f in $(find "$OUTDIR/js_beautified/" -name "*.js" -maxdepth 1 | head -200); do
        grep -n -i -E '(api[_-]?key|apikey|secret|token|password|passwd|pwd|auth|bearer|access[_-]?key|client[_-]?id|client[_-]?secret|private[_-]?key|aws_access_key_id|aws_secret_access_key|github_token|slack_token|firebase|algolia|app[_-]?key|app[_-]?secret)' "$f" 2>/dev/null | head -5 >> "$OUTDIR/findings/credential_hints.txt" || true
        grep -n -i -E '(process\.env\.|window\.__[A-Z_]+__|globalConfig|appConfig|runtimeConfig)' "$f" 2>/dev/null | head -3 >> "$OUTDIR/findings/config_references.txt" || true
    done
    HINTS=$(wc -l < "$OUTDIR/findings/credential_hints.txt" 2>/dev/null || echo 0)
    CONFIG=$(wc -l < "$OUTDIR/findings/config_references.txt" 2>/dev/null || echo 0)
    HIGH=0; URL_CREDS=0; B64=0
    echo "  关键词匹配: $HINTS | 配置引用: $CONFIG"

elif [ "$JS_COUNT" -gt 300 ]; then
    echo "  [阶梯4] 300-500 JS: v2 轻量模式（仅对象赋值+环境变量+高置信度正则）"
    python3 /opt/sec-tools/scripts/scan_credentials_v2.py "$OUTDIR/js/" "$OUTDIR/findings_v2/" --light 2>/dev/null || {
        echo "  v2 失败，回退到 grep"
        for f in $(find "$OUTDIR/js/" -name "*.js" -maxdepth 1 | head -300); do
            grep -n -i -E '(api[_-]?key|secret|token|password|auth|bearer|access[_-]?key|client[_-]?secret|private[_-]?key)' "$f" 2>/dev/null | head -3 >> "$OUTDIR/findings/credential_hints.txt" || true
        done
    }
    HINTS=$(wc -l < "$OUTDIR/findings_v2/keyword.json" 2>/dev/null || echo 0)
    HIGH=$(wc -l < "$OUTDIR/findings_v2/high_conf.json" 2>/dev/null || echo 0)
    CONFIG=$(wc -l < "$OUTDIR/findings_v2/obj_assign.json" 2>/dev/null || echo 0)
    URL_CREDS=0; B64=0
    echo "  关键词: $HINTS | 高置信度: $HIGH | 配置: $CONFIG"

elif [ "$JS_COUNT" -gt 100 ]; then
    echo "  [阶梯3] 100-300 JS: v2 全量扫描，跳过 >1MB 超大文件"
    # 临时创建过滤目录
    FILTERED_DIR="$OUTDIR/js_filtered"
    mkdir -p "$FILTERED_DIR"
    for f in "$OUTDIR/js/"*.js; do
        [ -f "$f" ] || continue
        fsz=$(stat -c%s "$f" 2>/dev/null || echo 0)
        if [ "$fsz" -lt 1048576 ]; then
            cp "$f" "$FILTERED_DIR/" 2>/dev/null || true
        fi
    done
    FILTERED_COUNT=$(ls "$FILTERED_DIR/"*.js 2>/dev/null | wc -l)
    echo "    过滤后: $FILTERED_COUNT 个文件 (排除了 >1MB 的大文件)"
    python3 /opt/sec-tools/scripts/scan_credentials_v2.py "$FILTERED_DIR/" "$OUTDIR/findings_v2/" 2>/dev/null || true
    HINTS=0; HIGH=0; URL_CREDS=0; B64=0; CONFIG=0
    [ -f "$OUTDIR/findings_v2/keyword.json" ] && HINTS=$(wc -l < "$OUTDIR/findings_v2/keyword.json" 2>/dev/null || echo 0)
    [ -f "$OUTDIR/findings_v2/high_conf.json" ] && HIGH=$(wc -l < "$OUTDIR/findings_v2/high_conf.json" 2>/dev/null || echo 0)
    [ -f "$OUTDIR/findings_v2/url_cred.json" ] && URL_CREDS=$(wc -l < "$OUTDIR/findings_v2/url_cred.json" 2>/dev/null || echo 0)
    [ -f "$OUTDIR/findings_v2/base64.json" ] && B64=$(wc -l < "$OUTDIR/findings_v2/base64.json" 2>/dev/null || echo 0)
    [ -f "$OUTDIR/findings_v2/obj_assign.json" ] && CONFIG=$(wc -l < "$OUTDIR/findings_v2/obj_assign.json" 2>/dev/null || echo 0)
    echo "  关键词: $HINTS | 高置信度: $HIGH | URL凭据: $URL_CREDS | Base64: $B64 | 配置: $CONFIG"

else
    echo "  [阶梯1-2] ≤100 JS: v2 全量结构化扫描"
    python3 /opt/sec-tools/scripts/scan_credentials_v2.py "$OUTDIR/js/" "$OUTDIR/findings_v2/" 2>/dev/null || true
    HINTS=0; HIGH=0; URL_CREDS=0; B64=0; CONFIG=0
    [ -f "$OUTDIR/findings_v2/keyword.json" ] && HINTS=$(wc -l < "$OUTDIR/findings_v2/keyword.json" 2>/dev/null || echo 0)
    [ -f "$OUTDIR/findings_v2/high_conf.json" ] && HIGH=$(wc -l < "$OUTDIR/findings_v2/high_conf.json" 2>/dev/null || echo 0)
    [ -f "$OUTDIR/findings_v2/url_cred.json" ] && URL_CREDS=$(wc -l < "$OUTDIR/findings_v2/url_cred.json" 2>/dev/null || echo 0)
    [ -f "$OUTDIR/findings_v2/base64.json" ] && B64=$(wc -l < "$OUTDIR/findings_v2/base64.json" 2>/dev/null || echo 0)
    [ -f "$OUTDIR/findings_v2/obj_assign.json" ] && CONFIG=$(wc -l < "$OUTDIR/findings_v2/obj_assign.json" 2>/dev/null || echo 0)
    echo "  关键词: $HINTS | 高置信度: $HIGH | URL凭据: $URL_CREDS | Base64: $B64 | 配置: $CONFIG"
fi

# ============================================================
# Phase 7: Source Map 还原
# ============================================================
if [ "$SM_FOUND" -gt 0 ]; then
    echo ""
    echo "[Phase 7] Source Map 源码还原..."
    mkdir -p "$OUTDIR/original_sources"
    for sm in "$OUTDIR/sourcemaps/"*.js.map; do
        [ -f "$sm" ] || continue
        python3 -c "
import sourcemap, json, os
with open('$sm') as f:
    sm = sourcemap.load(f)
    for i, src in enumerate(sm.sources):
        out = os.path.join('$OUTDIR/original_sources', src.replace('/', '_'))
        try:
            content = sm.get_source(i)
            with open(out, 'w') as wf:
                wf.write(content)
        except:
            pass
" 2>/dev/null || true
    done
    SRC_COUNT=$(ls "$OUTDIR/original_sources/" 2>/dev/null | wc -l)
    echo "  还原源码: $SRC_COUNT 个文件"
fi

# ============================================================
# Phase 8: 报告
# ============================================================
echo ""
echo "[Phase 8] 生成审计报告..."

cat > "$OUTDIR/REPORT.md" << REPORT_EOF
# 全生态 JS 资产审计报告

## 基本信息
- 目标: $TARGET
- 技术栈: $TECH
- 扫描时间: $(date)

## 资产统计
| 项目 | 数量 |
|------|------|
| JS URL 总数 | $TOTAL_JS |
| JS 文件下载 | $JS_FILES |
| Source Map | $SM_FOUND |
| 还原源码 | ${SRC_COUNT:-0} |

## 凭据审计发现
| 类型 | 数量 |
|------|------|
| 关键词匹配 | $HINTS |
| 高置信度凭据 | $HIGH |
| URL中凭据 | $URL_CREDS |
| Base64候选 | $B64 |
| 配置引用 | $CONFIG |

## 关键文件
\`\`\`
$OUTDIR/all_js_urls.txt
$OUTDIR/js/
$OUTDIR/js_beautified/
$OUTDIR/findings/
\`\`\`
REPORT_EOF

echo ""
echo "==========================================="
echo "审计完成！"
echo "输出: $OUTDIR"
echo "JS文件: $JS_FILES"
echo "高置信度凭据: $HIGH"
echo "==========================================="
