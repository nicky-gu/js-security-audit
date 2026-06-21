#!/usr/bin/env python3
"""从React/webpack打包产物中提取chunk清单"""
import sys, re, json, os
from urllib.parse import urljoin, urlparse

def extract_webpack_chunks(target, outdir):
    import requests
    
    chunks = set()
    
    # 1. 从入口HTML提取 chunk清单
    try:
        r = requests.get(target, timeout=15)
        html = r.text
        
        # Webpack manifest 内联脚本
        manifest = re.findall(r'window\.__webpack_public_path__\s*=\s*["\']([^"\']+)', html)
        for m in manifest:
            chunks.add(m)
        
        # React SSR manifest
        ssr = re.findall(r'"main":\s*"([^"]+)"', html)
        for s in ssr:
            chunks.add(s)
        
        # 提取 script src 中的 chunk 模式
        for match in re.findall(r'<script[^>]*src="([^"]+)"', html):
            if 'chunk' in match or 'bundle' in match or any(x in match for x in ['main', 'vendor', 'polyfill', 'runtime']):
                chunks.add(urljoin(target, match))
        
        # 动态import的chunk
        for match in re.findall(r'["\']([^"\']*chunk[^"\']*\.js)', html):
            chunks.add(urljoin(target, match))
            
    except Exception as e:
        print(f"HTML提取失败: {e}")
    
    # 2. 从已下载的JS中找更多chunk
    js_dir = os.path.join(outdir, "js")
    if os.path.exists(js_dir):
        for fname in os.listdir(js_dir):
            fpath = os.path.join(js_dir, fname)
            try:
                with open(fpath, 'r', errors='ignore') as f:
                    content = f.read()
                # webpack chunk加载器
                chunk_refs = re.findall(r'["\']([^"\']*chunk[^"\']*\.js)', content)
                for ref in chunk_refs:
                    chunks.add(urljoin(target, ref))
                # __webpack_require__ 引用
                more = re.findall(r'["\']([^"\']+\.js)["\']', content)
                for m in more:
                    if any(x in m for x in ['chunk', 'bundle', 'vendor', 'main']):
                        chunks.add(urljoin(target, m))
            except:
                pass
    
    # 保存
    out = os.path.join(outdir, "webpack_chunks.txt")
    with open(out, 'w') as f:
        for c in sorted(chunks):
            f.write(c + '\n')
    print(f"  提取 {len(chunks)} 个 webpack chunk 引用")

if __name__ == '__main__':
    extract_webpack_chunks(sys.argv[1], sys.argv[2])
