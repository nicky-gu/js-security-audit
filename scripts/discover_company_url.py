#!/usr/bin/env python3
"""
公司名称 → 官网 URL 发现工具
支持：直接搜索、常见公司映射、拼音猜测
"""
import sys, subprocess, re, json

# 常见公司名到官网的映射（缓存常用结果）
# 注意：此列表仅包含公开信息可见的大型企业，用于快速映射
# 如需添加私有目标，请通过环境变量或配置文件扩展
KNOWN_COMPANIES = {
    "华为": "https://www.huawei.com",
    "huawei": "https://www.huawei.com",
    "腾讯": "https://www.tencent.com",
    "tencent": "https://www.tencent.com",
    "阿里巴巴": "https://www.alibaba.com",
    "alibaba": "https://www.alibaba.com",
    "字节跳动": "https://www.bytedance.com",
    "bytedance": "https://www.bytedance.com",
    "百度": "https://www.baidu.com",
    "baidu": "https://www.baidu.com",
    "京东": "https://www.jd.com",
    "jd": "https://www.jd.com",
    "美团": "https://www.meituan.com",
    "meituan": "https://www.meituan.com",
    "拼多多": "https://www.pinduoduo.com",
    "pinduoduo": "https://www.pinduoduo.com",
    "小米": "https://www.mi.com",
    "xiaomi": "https://www.mi.com",
    "蔚来": "https://www.nio.cn",
    "nio": "https://www.nio.cn",
    "小鹏": "https://www.xiaopeng.com",
    "xpeng": "https://www.xiaopeng.com",
    "理想": "https://www.lixiang.com",
    "lixiang": "https://www.lixiang.com",
    "比亚迪": "https://www.byd.com",
    "byd": "https://www.byd.com",
}

def url_exists(url, timeout=10):
    """检查 URL 是否可达"""
    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", 
             "--connect-timeout", str(timeout), "--max-time", str(timeout),
             "-L", "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
             url],
            capture_output=True, text=True, timeout=timeout+5
        )
        code = result.stdout.strip()
        return code in ["200", "301", "302", "307", "308"]
    except:
        return False

def discover_url(name):
    """根据公司名称发现官网 URL"""
    name = name.strip()
    
    # 1. 直接查映射表
    if name in KNOWN_COMPANIES:
        url = KNOWN_COMPANIES[name]
        print(f"[映射] {name} -> {url}")
        return url
    
    # 2. 尝试常见模式猜测
    candidates = []
    
    # 2.1 直接拼音 + .com / .com.cn
    import urllib.parse
    encoded = urllib.parse.quote(name)
    
    # 简单拼音转换（取首字母或全拼，这里简化处理）
    # 实际上可以用 pypinyin，但为了减少依赖，先简单处理
    pinyin_guesses = [
        name.lower().replace(" ", ""),
    ]
    
    for p in pinyin_guesses:
        candidates.append(f"https://www.{p}.com")
        candidates.append(f"https://www.{p}.com.cn")
        candidates.append(f"https://{p}.com")
        candidates.append(f"https://{p}.com.cn")
    
    # 3. 尝试验证候选 URL
    print(f"[猜测] 尝试验证 {len(candidates)} 个候选...")
    for url in candidates:
        if url_exists(url):
            print(f"[成功] {name} -> {url}")
            return url
    
    # 4. 如果都失败，返回最可能的猜测
    best_guess = candidates[0] if candidates else None
    print(f"[警告] 无法确认 URL，返回最佳猜测: {best_guess}")
    return best_guess

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: discover_company_url.py <公司名称>")
        sys.exit(1)
    
    name = sys.argv[1]
    url = discover_url(name)
    print(url)
