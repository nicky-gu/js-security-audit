#!/usr/bin/env python3
import sys, re, os, json, base64
from urllib.parse import urljoin

def extract_config(js_text):
    """提取可能的配置对象"""
    configs = []
    patterns = [
        r'window\.__\w+__\s*=\s*({.*?})',
        r'\bconfig\s*=\s*({.*?})',
        r'\bCONFIG\s*=\s*({.*?})',
        r'const\s+\w+Config\s*=\s*({.*?})',
    ]
    for p in patterns:
        matches = re.findall(p, js_text, re.DOTALL)
        configs.extend(matches)
    return configs

def decode_base64_candidates(text):
    """尝试解码base64编码的内容"""
    results = []
    candidates = re.findall(r'[A-Za-z0-9+/]{20,}={0,2}', text)
    for c in candidates:
        if len(c) < 20 or len(c) % 4 != 0:
            continue
        try:
            decoded = base64.b64decode(c).decode('utf-8', errors='ignore')
            if len(decoded) > 5 and any(k in decoded.lower() for k in ['key', 'token', 'secret', 'pass', 'auth']):
                results.append((c, decoded))
        except:
            pass
    return results

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else ""
    outdir = sys.argv[2] if len(sys.argv) > 2 else "./"
    
    js_dir = os.path.join(outdir, "js")
    if not os.path.exists(js_dir):
        return
    
    findings = []
    for fname in os.listdir(js_dir):
        if not fname.endswith('.js'):
            continue
        fpath = os.path.join(js_dir, fname)
        with open(fpath, 'r', errors='ignore') as f:
            content = f.read()
        
        configs = extract_config(content)
        b64 = decode_base64_candidates(content)
        
        if configs or b64:
            findings.append({
                "file": fname,
                "configs": configs[:5],
                "base64_decoded": b64[:5]
            })
    
    findings_dir = os.path.join(outdir, "findings")
    os.makedirs(findings_dir, exist_ok=True)
    with open(os.path.join(findings_dir, "inline_configs.json"), "w") as f:
        json.dump(findings, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
