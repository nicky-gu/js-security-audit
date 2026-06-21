#!/usr/bin/env python3
"""解析小程序JS，提取页面路由、云函数、API调用"""
import sys, re, os, json

def parse_miniapp(js_dir, outdir):
    findings = {
        "pages": set(),
        "cloud_functions": set(),
        "api_calls": set(),
        "wx_apis": set(),
        "config_vars": set(),
    }
    
    if not os.path.exists(js_dir):
        return
    
    for fname in os.listdir(js_dir):
        fpath = os.path.join(js_dir, fname)
        try:
            with open(fpath, 'r', errors='ignore') as f:
                content = f.read()
            
            # 小程序页面路由 (Page({...}))
            if 'Page({' in content or 'Component({' in content:
                findings["pages"].add(fname)
            
            # 云函数调用
            cloud = re.findall(r'wx\.cloud\.callFunction\s*\(\s*\{[^}]*name\s*:\s*["\']([^"\']+)["\']', content)
            findings["cloud_functions"].update(cloud)
            
            # 通用API调用
            apis = re.findall(r'["\'](https?://[^"\']+)["\']', content)
            findings["api_calls"].update(apis)
            
            # 微信小程序API
            wx_apis = re.findall(r'wx\.(\w+)', content)
            findings["wx_apis"].update(wx_apis)
            
            # 配置变量
            configs = re.findall(r'app\.(\w+)\s*[:=]', content)
            findings["config_vars"].update(configs)
            
            # uni-app 特有
            uni_apis = re.findall(r'uni\.(\w+)', content)
            findings["wx_apis"].update(uni_apis)
            
        except:
            pass
    
    out = os.path.join(outdir, "miniapp_analysis.json")
    result = {k: sorted(list(v)) for k, v in findings.items()}
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    total = sum(len(v) for v in result.values())
    print(f"  小程序分析: {total} 条发现")
    for k, v in result.items():
        if v:
            print(f"    {k}: {len(v)}")

if __name__ == '__main__':
    parse_miniapp(sys.argv[1], sys.argv[2])
