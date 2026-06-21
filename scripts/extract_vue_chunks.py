#!/usr/bin/env python3
"""Vue 异步组件 chunk 提取"""
import sys, re, os
from urllib.parse import urljoin

def extract_vue_chunks(target, outdir):
    chunks = set()
    
    js_dir = os.path.join(outdir, "js")
    if os.path.exists(js_dir):
        for fname in os.listdir(js_dir):
            fpath = os.path.join(js_dir, fname)
            try:
                with open(fpath, 'r', errors='ignore') as f:
                    content = f.read()
                
                # Vue 异步组件 import()
                vue_async = re.findall(r'import\s*\(\s*["\']([^"\']+)["\']\s*\)', content)
                for v in vue_async:
                    chunks.add(urljoin(target, v))
                
                # Vue 路由懒加载
                route_async = re.findall(r'component:\s*\(\s*\)\s*=>\s*import\s*\(\s*["\']([^"\']+)["\']\s*\)', content)
                for r in route_async:
                    chunks.add(urljoin(target, r))
                
                # Vue 动态组件
                dyn = re.findall(r'resolveComponent\s*\(\s*["\']([^"\']+)["\']\s*\)', content)
                for d in dyn:
                    chunks.add(urljoin(target, d))
                    
            except:
                pass
    
    out = os.path.join(outdir, "vue_chunks.txt")
    with open(out, 'w') as f:
        for c in sorted(chunks):
            f.write(c + '\n')
    print(f"  提取 {len(chunks)} 个 Vue 异步组件 chunk")

if __name__ == '__main__':
    extract_vue_chunks(sys.argv[1], sys.argv[2])
