#!/usr/bin/env python3
"""
凭据扫描后处理 - 过滤误报
分析 findings_v2 结果，去除明显误报
"""
import json, os, re
from pathlib import Path

def is_base64_like(s):
    """检查字符串是否像base64编码（高字符集多样性）"""
    if len(s) < 20:
        return False
    chars = set(s)
    # 真正的base64通常包含大量不同字符
    return len(chars) >= 15 and all(c.isalnum() or c in '+/=' for c in chars)

def is_css_class(s):
    """检查是否是CSS类名"""
    css_keywords = ['swiper', 'pagination', 'container', 'wrapper', 'slide', 'active',
                    'button', 'progressbar', 'scrollbar', 'navigation']
    return any(kw in s.lower() for kw in css_keywords)

def is_font_charset(s):
    """检查是否是字体字符集定义"""
    return s.startswith('ABCDEFG') or 'abcdef' in s.lower() and len(set(s)) > 40

def filter_high_confidence(items):
    """过滤高置信度误报"""
    filtered = []
    for item in items:
        match = item.get('match', '')
        ctx = item.get('context', '').lower()
        cred_type = item.get('cred_type', '')
        
        # 跳过CSS相关
        if 'css' in ctx or '@charset' in ctx or '<style>' in ctx:
            if cred_type in ['AWS_ACCESS_KEY', 'RECAPTCHA_KEY', 'OAUTH_TOKEN']:
                continue
        
        # 跳过swiper类名
        if is_css_class(match) and cred_type == 'OAUTH_TOKEN':
            continue
        
        # 跳过字体字符集
        if is_font_charset(match):
            continue
        
        # 跳过纯base64数据
        if is_base64_like(match) and cred_type == 'RECAPTCHA_KEY':
            continue
        
        # 跳过HTML/SVG中的匹配
        if '<svg' in ctx or '<div' in ctx or '<clipPath' in ctx:
            if cred_type in ['RECAPTCHA_KEY', 'AWS_ACCESS_KEY']:
                continue
        
        # 跳过明显是二进制/编码数据的
        if match.startswith('AKIA') and len(match) == 20:
            # 额外检查：真正的AWS key应该全是大写字母和数字
            if not re.match(r'^AKIA[A-Z0-9]{16}$', match):
                continue
        
        filtered.append(item)
    
    return filtered

def filter_url_creds(items):
    """过滤URL凭据误报"""
    filtered = []
    for item in items:
        url = item.get('match', '')
        # 跳过CDN和正常URL
        if any(domain in url for domain in ['unpkg.com', 'cdn.', 'static.', 'fonts.']):
            continue
        # 跳过社交媒体
        if 'social.opensource.org' in url:
            continue
        # 跳过分段URL（如 https://a@b）
        if url.count('/') <= 2:
            continue
        filtered.append(item)
    return filtered

def filter_entropy(items):
    """过滤高熵误报"""
    filtered = []
    for item in items:
        s = item.get('match', '')
        # 跳过字体字符集
        if is_font_charset(s):
            continue
        # 跳过重复模式
        if s.count('=') > 5 or s.count('/') > 5:
            # 可能是base64
            if is_base64_like(s):
                continue
        filtered.append(item)
    return filtered

def main(findings_dir):
    # 读取原始结果
    all_path = os.path.join(findings_dir, 'all_findings.json')
    with open(all_path, 'r', encoding='utf-8') as f:
        all_results = json.load(f)
    
    # 分类
    by_type = {}
    for r in all_results:
        t = r['type']
        by_type.setdefault(t, []).append(r)
    
    # 过滤
    if 'HIGH_CONF' in by_type:
        by_type['HIGH_CONF'] = filter_high_confidence(by_type['HIGH_CONF'])
    
    if 'URL_CRED' in by_type:
        by_type['URL_CRED'] = filter_url_creds(by_type['URL_CRED'])
    
    if 'HIGH_ENTROPY' in by_type:
        by_type['HIGH_ENTROPY'] = filter_entropy(by_type['HIGH_ENTROPY'])
    
    # 生成过滤后报告
    report_path = os.path.join(findings_dir, 'report_filtered.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# JS 凭据扫描报告 v2（过滤后）\n\n")
        f.write(f"扫描文件数: 304\n\n")
        
        # 统计
        f.write("## 统计\n\n")
        for t in ['HIGH_CONF', 'URL_CRED', 'HIGH_ENTROPY', 'ENV_REF', 'OBJ_ASSIGN', 'BASE64', 'JSON_CONFIG', 'KEYWORD']:
            if t in by_type:
                f.write(f"- **{t}**: {len(by_type[t])}\n")
        f.write("\n")
        
        # 真正的高置信度发现
        if 'HIGH_CONF' in by_type and by_type['HIGH_CONF']:
            f.write("## ⚠️ 高置信度凭据（已过滤误报）\n\n")
            for item in by_type['HIGH_CONF'][:30]:
                f.write(f"- `[{item['cred_type']}]` {item['file']}:{item['line']}\n")
                f.write(f"  - 匹配: `{item['match']}`\n")
                f.write(f"  - 上下文: `{item['context'][:100]}`\n\n")
        
        # URL凭据
        if 'URL_CRED' in by_type and by_type['URL_CRED']:
            f.write("## 🔗 URL中凭据（已过滤）\n\n")
            for item in by_type['URL_CRED']:
                f.write(f"- {item['file']}:{item['line']} `{item['match']}`\n")
            f.write("\n")
        
        # 高熵
        if 'HIGH_ENTROPY' in by_type and by_type['HIGH_ENTROPY']:
            f.write("## 🔐 高熵字符串（已过滤）\n\n")
            for item in by_type['HIGH_ENTROPY'][:20]:
                f.write(f"- {item['file']}:{item['line']} entropy={item.get('entropy', '?')} `{item['match']}`\n")
            f.write("\n")
        
        # 环境变量
        if 'ENV_REF' in by_type and by_type['ENV_REF']:
            f.write("## 🔧 环境变量引用\n\n")
            envs = sorted(set(item['match'] for item in by_type['ENV_REF']))
            for e in envs[:50]:
                f.write(f"- `{e}`\n")
            f.write("\n")
        
        # 对象赋值
        if 'OBJ_ASSIGN' in by_type and by_type['OBJ_ASSIGN']:
            f.write("## 📝 对象属性赋值\n\n")
            for item in by_type['OBJ_ASSIGN'][:30]:
                f.write(f"- {item['file']}:{item['line']} `{item['match']}`\n")
            f.write("\n")
        
        # Base64
        if 'BASE64' in by_type and by_type['BASE64']:
            f.write("## 🧬 Base64候选\n\n")
            for item in by_type['BASE64'][:20]:
                f.write(f"- {item['file']}:{item['line']} `{item['match']}`\n")
            f.write("\n")
    
    # 打印摘要
    print("=" * 50)
    print("过滤后结果摘要")
    print("=" * 50)
    
    for t in ['HIGH_CONF', 'URL_CRED', 'HIGH_ENTROPY', 'ENV_REF', 'OBJ_ASSIGN', 'BASE64']:
        if t in by_type:
            print(f"  {t}: {len(by_type[t])}")
    
    print(f"\n  过滤后报告: {report_path}")
    
    if 'HIGH_CONF' in by_type and by_type['HIGH_CONF']:
        print(f"\n  ⚠️  发现 {len(by_type['HIGH_CONF'])} 个真正的高置信度凭据:")
        for item in by_type['HIGH_CONF'][:10]:
            print(f"    - [{item['cred_type']}] {item['file']}:{item['line']} = {item['match'][:60]}")
    else:
        print("\n  ✅ 未发现真正的高置信度凭据泄露")

if __name__ == '__main__':
    main('/tmp/js-harvest-20260621_171542/findings_v2')
