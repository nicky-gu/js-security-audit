#!/usr/bin/env python3
"""
深度凭据扫描 v2.2 - 极速版
直接读取文件内容，结构化分析 + 正则为辅
优化：避免回溯，大文件截断，减少正则数量
"""
import sys, re, os, json, math
from pathlib import Path

MAX_FILE_SIZE = 1024 * 1024  # 1MB截断
ENTROPY_THRESHOLD = 4.8

# 核心高置信度模式（简化，避免回溯）
CORE_PATTERNS = [
    (r'(?:AKIA|ASIA|AROA|AIDA)[A-Z0-9]{16}', 'AWS_ACCESS_KEY'),
    (r'ghp_[a-zA-Z0-9]{36}', 'GITHUB_PAT'),
    (r'github_pat_[a-zA-Z0-9_]{22,}', 'GITHUB_FINE_PAT'),
    (r'xox[baprs]-[a-zA-Z0-9\-]+', 'SLACK_TOKEN'),
    (r'sk-[a-zA-Z0-9]{20,}', 'OPENAI_KEY'),
    (r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*', 'JWT'),
    (r'-----BEGIN [A-Z ]*PRIVATE KEY-----', 'PRIVATE_KEY'),
    (r'-----BEGIN CERTIFICATE-----', 'CERTIFICATE'),
    (r'SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}', 'SENDGRID_KEY'),
    (r'sk_(live|test)_[0-9a-zA-Z]{24,}', 'STRIPE_KEY'),
    (r'[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}', 'OAUTH_TOKEN'),
    (r'Basic\s+[A-Za-z0-9+/]{20,}={0,2}', 'BASIC_AUTH'),
    (r'bearer\s+[A-Za-z0-9_\-\.]{20,}', 'BEARER_TOKEN'),
    (r'6L[0-9A-Za-z_-]{38}', 'RECAPTCHA_KEY'),
    (r'key-[0-9a-f]{32}', 'MAILGUN_KEY'),
]

def shannon_entropy(s):
    if not s or len(s) < 8:
        return 0
    e = 0
    for x in set(s):
        p = float(s.count(x)) / len(s)
        if p > 0:
            e += -p * math.log(p, 2)
    return e

def scan_file(filepath, filename, light_mode=False):
    """扫描单个文件，返回结果列表"""
    results = []
    
    try:
        size = os.path.getsize(filepath)
        with open(filepath, 'r', errors='ignore') as f:
            content = f.read(MAX_FILE_SIZE) if size > MAX_FILE_SIZE else f.read()
    except:
        return results
    
    if not content:
        return results
    
    # 1. 高置信度正则（逐个匹配，避免同时编译）
    for pattern_str, cred_type in CORE_PATTERNS:
        try:
            for m in re.finditer(pattern_str, content, re.IGNORECASE):
                line_num = content[:m.start()].count('\n') + 1
                line_start = content.rfind('\n', 0, m.start()) + 1
                line_end = content.find('\n', m.end())
                line = content[line_start:line_end].strip()[:150]
                results.append({
                    'type': 'HIGH_CONF',
                    'cred_type': cred_type,
                    'file': filename,
                    'line': line_num,
                    'match': m.group()[:80],
                    'context': line
                })
        except:
            pass
    
    # 2. URL中的凭据
    for m in re.finditer(r'https?://[^\s\'"<>]+', content):
        url = m.group()
        if '@' in url and ':' in url.split('@')[0]:
            line_num = content[:m.start()].count('\n') + 1
            # 隐藏密码
            safe_url = re.sub(r'(https?://)[^:]+:[^@]+@', r'\1***:***@', url)
            results.append({
                'type': 'URL_CRED',
                'file': filename,
                'line': line_num,
                'match': safe_url[:200]
            })
    
    # 3. 环境变量引用
    for m in re.finditer(r'(?:process\.env|import\.meta\.env)\.([A-Z_][A-Z0-9_]*)', content):
        line_num = content[:m.start()].count('\n') + 1
        results.append({
            'type': 'ENV_REF',
            'file': filename,
            'line': line_num,
            'match': m.group(1)
        })
    
    # 4. 对象属性赋值（apiKey: "xxx" 等）
    for m in re.finditer(r'([a-zA-Z_$][\w$]*)\s*[:=]\s*["\']([A-Za-z0-9_\-\.+/=]{16,})["\']', content):
        key = m.group(1).lower()
        if any(kw in key for kw in ['key', 'secret', 'token', 'password', 'auth']):
            line_num = content[:m.start()].count('\n') + 1
            results.append({
                'type': 'OBJ_ASSIGN',
                'file': filename,
                'line': line_num,
                'match': f"{m.group(1)}: {m.group(2)[:40]}..."
            })
    
    # 5. Base64候选（限制数量）
    count = 0
    for m in re.finditer(r'[A-Za-z0-9+/]{40,}={0,2}', content):
        if count >= 10:
            break
        s = m.group()
        if len(set(s)) < 10:
            continue
        ctx_start = max(0, m.start() - 60)
        ctx_end = min(len(content), m.end() + 60)
        ctx = content[ctx_start:ctx_end].lower()
        if any(kw in ctx for kw in ['key', 'secret', 'token', 'auth']):
            line_num = content[:m.start()].count('\n') + 1
            results.append({
                'type': 'BASE64',
                'file': filename,
                'line': line_num,
                'match': s[:40] + '...'
            })
            count += 1
    
    # 6. 高熵字符串（只在包含可疑关键词的行中检查）
    lines = content.split('\n')
    for i, line in enumerate(lines, 1):
        lower = line.lower()
        if not any(kw in lower for kw in ['key', 'secret', 'token', 'auth', 'password']):
            continue
        for m in re.finditer(r'["\']([A-Za-z0-9_\-\.+/=]{20,})["\']', line):
            s = m.group(1)
            if len(s) >= 16 and len(set(s)) >= 10:
                ent = shannon_entropy(s)
                if ent >= ENTROPY_THRESHOLD:
                    results.append({
                        'type': 'HIGH_ENTROPY',
                        'file': filename,
                        'line': i,
                        'match': s[:60],
                        'entropy': round(ent, 2)
                    })
    
    # 7. JSON配置块
    for m in re.finditer(r'window\.__[A-Z_]+__\s*=\s*({.*?});', content, re.DOTALL):
        cfg = m.group(1)[:400]
        results.append({
            'type': 'JSON_CONFIG',
            'file': filename,
            'line': content[:m.start()].count('\n') + 1,
            'match': cfg
        })
    
    # 8. 关键词匹配
    kw_pattern = re.compile(r'\b(api[_-]?key|apikey|secret|token|password|passwd|pwd|auth|bearer|jwt|oauth|credential)\b', re.I)
    for i, line in enumerate(lines, 1):
        if kw_pattern.search(line):
            results.append({
                'type': 'KEYWORD',
                'file': filename,
                'line': i,
                'match': line.strip()[:200]
            })
    
    return results

def main(js_dir, outdir, light_mode=False):
    findings_dir = os.path.join(outdir, "findings_v2")
    os.makedirs(findings_dir, exist_ok=True)
    
    js_files = sorted(Path(js_dir).glob('*.js'))
    total = len(js_files)
    print(f"  扫描 {total} 个 JS 文件...")
    
    all_results = []
    for idx, js_file in enumerate(js_files, 1):
        if idx % 50 == 0 or idx == 1 or idx == total:
            print(f"    进度: {idx}/{total}")
        
        results = scan_file(str(js_file), js_file.name, light_mode=light_mode)
        all_results.extend(results)
    
    # 保存完整JSON
    with open(os.path.join(findings_dir, 'all_findings.json'), 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    # 按类型分类统计
    stats = {}
    by_type = {}
    for r in all_results:
        t = r['type']
        stats[t] = stats.get(t, 0) + 1
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(r)
    
    # 保存分类结果
    for t, items in by_type.items():
        with open(os.path.join(findings_dir, f'{t.lower()}.json'), 'w', encoding='utf-8') as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    
    # 生成报告
    report_path = os.path.join(findings_dir, 'report_v2.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# JS 凭据扫描报告 v2\n\n")
        f.write(f"扫描文件数: {total}\n")
        f.write(f"总发现数: {len(all_results)}\n\n")
        
        f.write("## 统计\n\n")
        for t, count in sorted(stats.items(), key=lambda x: -x[1]):
            f.write(f"- **{t}**: {count}\n")
        f.write("\n")
        
        # 高置信度发现
        if 'HIGH_CONF' in by_type:
            f.write("## ⚠️ 高置信度凭据\n\n")
            for item in by_type['HIGH_CONF'][:50]:
                f.write(f"- `[{item['cred_type']}]` {item['file']}:{item['line']}\n")
                f.write(f"  - 匹配: `{item['match']}`\n")
                f.write(f"  - 上下文: `{item['context']}`\n\n")
        
        # URL凭据
        if 'URL_CRED' in by_type:
            f.write("## 🔗 URL中凭据\n\n")
            for item in by_type['URL_CRED'][:30]:
                f.write(f"- {item['file']}:{item['line']} `{item['match']}`\n")
            f.write("\n")
        
        # 高熵字符串
        if 'HIGH_ENTROPY' in by_type:
            f.write("## 🔐 高熵字符串\n\n")
            for item in by_type['HIGH_ENTROPY'][:30]:
                f.write(f"- {item['file']}:{item['line']} entropy={item['entropy']} `{item['match']}`\n")
            f.write("\n")
        
        # 环境变量
        if 'ENV_REF' in by_type:
            f.write("## 🔧 环境变量引用\n\n")
            envs = sorted(set(item['match'] for item in by_type['ENV_REF']))
            for e in envs[:50]:
                f.write(f"- `{e}`\n")
            f.write("\n")
        
        # JSON配置
        if 'JSON_CONFIG' in by_type:
            f.write("## 📦 运行时配置\n\n")
            for item in by_type['JSON_CONFIG'][:10]:
                f.write(f"- {item['file']}:{item['line']}\n")
                f.write(f"  ```\n  {item['match'][:300]}\n  ```\n\n")
    
    # 打印摘要
    print(f"\n  ========== 扫描结果摘要 ==========")
    for t, count in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {t}: {count}")
    print(f"  =================================")
    print(f"\n  报告保存至: {report_path}")
    
    if 'HIGH_CONF' in by_type:
        print(f"\n  ⚠️  发现 {len(by_type['HIGH_CONF'])} 个高置信度凭据!")
        for item in by_type['HIGH_CONF'][:5]:
            print(f"    - [{item['cred_type']}] {item['file']}:{item['line']}")

if __name__ == '__main__':
    LIGHT_MODE = '--light' in sys.argv
    if LIGHT_MODE:
        sys.argv.remove('--light')
    
    if len(sys.argv) < 3:
        print(f"用法: {sys.argv[0]} <JS目录> <输出目录> [--light]")
        print(f"  --light: 轻量模式，仅运行高置信度正则+对象赋值+环境变量")
        sys.exit(1)
    
    main(sys.argv[1], sys.argv[2], light_mode=LIGHT_MODE)
