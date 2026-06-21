#!/bin/bash
# 检查目标是否存在 Source Map 文件
# 用法: ./check_sourcemaps.sh <JS_URL列表文件>

JS_FILE="$1"
if [ -z "$JS_FILE" ]; then
    echo "用法: $0 <js_urls.txt>"
    exit 1
fi

echo "[*] 检查 Source Map 文件..."
while read url; do
    [ -z "$url" ] && continue
    map_url="${url}.map"
    status=$(curl -sI -o /dev/null -w "%{http_code}" "$map_url" --max-time 5)
    if [ "$status" = "200" ]; then
        echo "[+] Found: $map_url"
        curl -sL "$map_url" -o "/tmp/$(basename $url).map" --max-time 10
    fi
done < "$JS_FILE"

echo "[*] 使用 sourcemap 工具解析..."
for map in /tmp/*.map; do
    [ -f "$map" ] || continue
    echo "--- $(basename $map) ---"
    python3 -c "
import sourcemap, json, sys
with open('$map') as f:
    sm = sourcemap.load(f)
    print('Sources:', sm.sources[:5])
" 2>/dev/null
done
