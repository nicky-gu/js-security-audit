#!/usr/bin/env python3
"""解析 React bundle，提取路由、API端点、状态管理配置"""
import sys, re, os, json

def parse_react_bundle(js_dir, outdir):
    findings = {
        "routes": set(),
        "api_endpoints": set(),
        "graphql_queries": set(),
        "redux_actions": set(),
        "env_vars": set(),
    }
    
    if not os.path.exists(js_dir):
        return
    
    for fname in os.listdir(js_dir):
        fpath = os.path.join(js_dir, fname)
        try:
            with open(fpath, 'r', errors='ignore') as f:
                content = f.read()
            
            # React Router 路由
            routes = re.findall(r'path\s*:\s*["\']([^"\']+)["\']', content)
            findings["routes"].update(routes)
            
            # API 端点
            apis = re.findall(r'["\'](https?://[^"\']+/api/[^"\']*)["\']', content)
            findings["api_endpoints"].update(apis)
            # 相对API路径
            rel_apis = re.findall(r'["\'](/api/[^"\']*)["\']', content)
            findings["api_endpoints"].update(rel_apis)
            
            # GraphQL
            gql = re.findall(r'(query|mutation)\s+\w+\s*\{', content)
            findings["graphql_queries"].update(gql)
            
            # Redux actions
            actions = re.findall(r'type\s*:\s*["\']([A-Z_]+)["\']', content)
            findings["redux_actions"].update(actions)
            
            # 环境变量
            envs = re.findall(r'process\.env\.([A-Z_]+)', content)
            findings["env_vars"].update(envs)
            
        except:
            pass
    
    # 保存
    out = os.path.join(outdir, "react_analysis.json")
    result = {k: sorted(list(v)) for k, v in findings.items()}
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    total = sum(len(v) for v in result.values())
    print(f"  React分析: {total} 条发现")
    for k, v in result.items():
        if v:
            print(f"    {k}: {len(v)}")

if __name__ == '__main__':
    parse_react_bundle(sys.argv[1], sys.argv[2])
