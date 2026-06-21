#!/usr/bin/env python3
"""解析 Vue bundle，提取路由、API、Vuex/Pinia状态"""
import sys, re, os, json

def parse_vue_bundle(js_dir, outdir):
    findings = {
        "routes": set(),
        "api_endpoints": set(),
        "vuex_actions": set(),
        "pinia_stores": set(),
        "components": set(),
        "env_vars": set(),
    }
    
    if not os.path.exists(js_dir):
        return
    
    for fname in os.listdir(js_dir):
        fpath = os.path.join(js_dir, fname)
        try:
            with open(fpath, 'r', errors='ignore') as f:
                content = f.read()
            
            # Vue Router 路由
            routes = re.findall(r'path\s*:\s*["\']([^"\']+)["\']', content)
            findings["routes"].update(routes)
            
            # Vue Router 命名路由
            named = re.findall(r'name\s*:\s*["\']([^"\']+)["\']', content)
            findings["routes"].update(named)
            
            # API 端点 (axios / fetch)
            apis = re.findall(r'["\'](https?://[^"\']+/api/[^"\']*)["\']', content)
            findings["api_endpoints"].update(apis)
            rel_apis = re.findall(r'["\'](/api/[^"\']*)["\']', content)
            findings["api_endpoints"].update(rel_apis)
            
            # Vuex actions / mutations
            vuex = re.findall(r'(dispatch|commit)\s*\(\s*["\']([A-Z_]+)["\']', content)
            findings["vuex_actions"].update([v[1] for v in vuex])
            
            # Pinia stores
            pinia = re.findall(r'use\w+Store\s*\(\s*["\']([^"\']+)["\']\s*\)', content)
            findings["pinia_stores"].update(pinia)
            
            # 组件引用
            comps = re.findall(r'components?\s*:\s*\{[^}]*"?\'?([A-Z][a-zA-Z]+)', content)
            findings["components"].update(comps)
            
            # 环境变量
            envs = re.findall(r'import\.meta\.env\.([A-Z_]+)', content)
            findings["env_vars"].update(envs)
            
        except:
            pass
    
    out = os.path.join(outdir, "vue_analysis.json")
    result = {k: sorted(list(v)) for k, v in findings.items()}
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    total = sum(len(v) for v in result.values())
    print(f"  Vue分析: {total} 条发现")
    for k, v in result.items():
        if v:
            print(f"    {k}: {len(v)}")

if __name__ == '__main__':
    parse_vue_bundle(sys.argv[1], sys.argv[2])
