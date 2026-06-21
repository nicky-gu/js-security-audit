#!/usr/bin/env python3
"""小程序 subpackages / 分包提取"""
import sys, re, os, json
from urllib.parse import urljoin

def extract_miniapp_chunks(target, outdir):
    chunks = set()
    
    # 小程序 app.json / app.config.js
    js_dir = os.path.join(outdir, "js")
    
    # 尝试获取 app.json
    import requests
    try:
        r = requests.get(urljoin(target, 'app.json'), timeout=10)
        if r.status_code == 200:
            app_config = r.json()
            # pages
            for page in app_config.get('pages', []):
                chunks.add(urljoin(target, f'{page}.js'))
            # subPackages
            for sub in app_config.get('subPackages', []):
                root = sub.get('root', '')
                for page in sub.get('pages', []):
                    chunks.add(urljoin(target, f'{root}/{page}.js'))
    except:
        pass
    
    # 从JS中提取分包引用
    if os.path.exists(js_dir):
        for fname in os.listdir(js_dir):
            fpath = os.path.join(js_dir, fname)
            try:
                with open(fpath, 'r', errors='ignore') as f:
                    content = f.read()
                # wx.navigateTo / uni.navigateTo
                navs = re.findall(r'navigateTo\s*\(\s*\{[^}]*url\s*:\s*["\']([^"\']+)["\']', content)
                for n in navs:
                    chunks.add(urljoin(target, n))
                # require 分包
                reqs = re.findall(r'require\s*\(\s*["\']([^"\']+)["\']\s*\)', content)
                for r in reqs:
                    chunks.add(urljoin(target, r))
            except:
                pass
    
    out = os.path.join(outdir, "miniapp_chunks.txt")
    with open(out, 'w') as f:
        for c in sorted(chunks):
            f.write(c + '\n')
    print(f"  提取 {len(chunks)} 个小程序页面/分包")

if __name__ == '__main__':
    extract_miniapp_chunks(sys.argv[1], sys.argv[2])
