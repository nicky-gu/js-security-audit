#!/usr/bin/env python3
"""
域名资产发现 v2 - 全面增强版
支持：多模式输入、多源主域名发现、大规模子域名枚举

输入模式：
- URL: https://www.example.com
- 域名: www.example.com / example.com
- 公司名: 华为、示例公司

用法:
    python3 discover_domains.py <输入> [输出JSON文件]
    python3 discover_domains.py "https://www.example.com" /tmp/output.json
    python3 discover_domains.py "example.com" /tmp/output.json
    python3 discover_domains.py "华为" /tmp/output.json
"""

import sys, re, json, os, subprocess, time, socket, concurrent.futures
from urllib.parse import urlparse, quote
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from tldextract import extract as tld_extract

# ============= 配置 =============
DICT_FILE = "/opt/sec-tools/dict/subdomains_large.txt"
MAX_WORKERS = 20          # DNS 解析并发数
DNS_TIMEOUT = 5           # DNS 超时
SUBFINDER_TIMEOUT = 120   # subfinder 超时
CRT_TIMEOUT = 30          # crt.sh 超时
HTTP_TIMEOUT = 10         # HTTP 验证超时

# ============= 硬编码映射 =============
MAPPINGS = {
    '华为': ['huawei.com', 'huawei.cn'],
    '腾讯': ['tencent.com', 'qq.com'],
    '阿里': ['alibaba.com', 'aliyun.com'],
    '阿里巴巴': ['alibaba.com', 'aliyun.com'],
    '字节': ['bytedance.com', 'tiktok.com'],
    '字节跳动': ['bytedance.com', 'tiktok.com'],
    '小米': ['mi.com', 'xiaomi.com'],
    '比亚迪': ['byd.com', 'byd.com.cn'],
    '吉利': ['geely.com', 'geely.com.cn'],
    '百度': ['baidu.com', 'baidu.com.cn'],
    '京东': ['jd.com', 'jd.com.cn'],
    '美团': ['meituan.com', 'meituan.com.cn'],
    '拼多多': ['pinduoduo.com'],
    '蔚来': ['nio.cn', 'nio.com'],
    '小鹏': ['xiaopeng.com', 'xpeng.com'],
    '理想': ['lixiang.com', 'li-auto.com'],
}

# ============= 输入解析 =============
def parse_input(raw_input):
    """解析输入为模式识别"""
    raw = raw_input.strip().lower()
    
    # URL 模式
    if raw.startswith('http://') or raw.startswith('https://'):
        parsed = urlparse(raw_input.strip())
        domain = parsed.netloc.split(':')[0]  # 去掉端口
        return ('url', raw_input.strip(), domain)
    
    # 纯域名模式 (包含 . 且没有空格)
    if re.match(r'^[a-z0-9][-a-z0-9]*\.[a-z]+$', raw, re.I) or \
       re.match(r'^[a-z0-9][-a-z0-9]*\.[a-z]+\.[a-z]+$', raw, re.I) or \
       re.match(r'^[a-z0-9][-a-z0-9]*\.[a-z]+\.[a-z]+\.[a-z]+$', raw, re.I):
        return ('domain', raw_input.strip(), raw_input.strip())
    
    # 公司名模式
    return ('company', raw_input.strip(), raw_input.strip())

def extract_main_domain(domain):
    """提取注册域（如 www.example.com → example.com）"""
    ext = tld_extract(domain)
    return f"{ext.domain}.{ext.suffix}"

def remove_www(domain):
    """去掉 www. 前缀"""
    if domain.startswith('www.'):
        return domain[4:]
    return domain

def resolve_dns(subdomain):
    """DNS 解析，成功返回 IP，失败返回 None"""
    try:
        ip = socket.gethostbyname(subdomain)
        return ip
    except:
        return None

def is_ip(target):
    """检查是否为 IP 地址"""
    return re.match(r'^(\d{1,3}\.){3}\d{1,3}$', target) is not None

# ============= 主域名发现 =============
def discover_main_domains(company_name, domain=None):
    """发现关联主域名"""
    domains = set()
    
    # 如果已经有域名，直接加入
    if domain and not is_ip(domain):
        domains.add(domain)
    
    # 1. 硬编码映射
    if company_name in MAPPINGS:
        for d in MAPPINGS[company_name]:
            domains.add(d)
    
    # 2. 拼音猜测（如果公司名有 ASCII 部分）
    if not domains and not is_ip(company_name):
        # 提取拼音部分
        ascii_parts = re.findall(r'[a-zA-Z]+', company_name)
        if ascii_parts:
            base = ''.join(ascii_parts).lower()
            candidates = [
                f"www.{base}.com", f"{base}.com",
                f"www.{base}.cn", f"{base}.cn",
                f"www.{base}.com.cn", f"{base}.com.cn",
                f"www.{base}.net", f"{base}.net",
                f"www.{base}.org", f"{base}.org",
            ]
            for url in candidates:
                d = remove_www(url.replace('https://', '').replace('http://', '').split('/')[0])
                domains.add(d)
    
    # 3. 变体猜测（基于已知域名的后缀/前缀）
    base_domains = list(domains)
    for d in base_domains:
        ext = tld_extract(d)
        if not ext.domain or not ext.suffix:
            continue
        base = ext.domain
        
        variants = [
            f"{base}.com.cn", f"{base}.cn", f"{base}.net", f"{base}.org",
            f"{base}-global.com", f"{base}-group.com", f"{base}-china.com",
            f"{base}-cn.com", f"{base}-corp.com", f"{base}-tech.com",
            f"{base}-auto.com", f"{base}auto.com", f"{base}china.com",
            f"{base}cn.com", f"{base}corp.com", f"{base}global.com",
            f"{base}group.com", f"{base}holdings.com", f"{base}tech.com",
        ]
        for v in variants:
            if v != d:
                domains.add(v)
    
    return domains

def verify_domains(domains, timeout=HTTP_TIMEOUT):
    """验证域名是否可达（HTTP 或 DNS）"""
    valid = []
    for domain in domains:
        # 先 DNS 解析
        ip = resolve_dns(domain)
        if ip:
            # 再尝试 HTTP 访问
            try:
                req = Request(f"http://{domain}", method='HEAD',
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
                resp = urlopen(req, timeout=timeout)
                valid.append({'domain': domain, 'ip': ip, 'http': resp.status})
            except HTTPError as e:
                valid.append({'domain': domain, 'ip': ip, 'http': e.code})
            except:
                valid.append({'domain': domain, 'ip': ip, 'http': None})
    return valid

# ============= 子域名枚举 =============
def load_subdomain_dict():
    """加载 DNS 字典"""
    if os.path.exists(DICT_FILE):
        with open(DICT_FILE, 'r') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    # 内置字典（如果文件不存在）
    return [
        'www', 'mail', 'api', 'admin', 'test', 'dev', 'staging', 'portal', 'app',
        'cdn', 'static', 'login', 'sso', 'partner', 'crm', 'erp', 'uat', 'vpn',
        'data', 'files', 'images', 'media', 'docs', 'wiki', 'support', 'help',
        'blog', 'news', 'careers', 'jobs', 'hr', 'finance', 'account', 'pay',
        'shop', 'store', 'search', 'service', 'download', 'upload', 'ftp', 'ssh',
        'gateway', 'proxy', 'firewall', 'lb', 'k8s', 'docker', 'registry',
        'jenkins', 'gitlab', 'git', 'jira', 'confluence', 'intranet', 'extranet',
        'internal', 'external', 'public', 'private', 'secure', 'access', 'auth',
        'identity', 'key', 'secret', 'user', 'customer', 'client',
        'sales', 'marketing', 'analytics', 'monitor', 'log', 'audit', 'policy',
        'documentation', 'doc', 'ref', 'knowledge', 'kb', 'faq', 'helpdesk',
        'ticket', 'issue', 'bug', 'incident', 'event', 'alert', 'error', 'request',
        'work', 'project', 'task', 'case', 'board', 'pipeline', 'release',
        'deploy', 'build', 'ci', 'cd', 'staging', 'prod', 'production', 'live',
        'beta', 'alpha', 'rc', 'preview', 'experiment', 'lab', 'playground',
        'sandbox', 'space', 'workspace', 'team', 'group', 'department', 'org',
        'business', 'subdomain', 'third', 'third-party', 'partner', 'associate',
        'vendor', 'supplier', 'provider', 'integrator', 'reseller', 'distributor',
        'dealer', 'agent', 'representative', 'area', 'region', 'global', 'cn',
        'china', 'us', 'usa', 'uk', 'eu', 'asia', 'jp', 'kr', 'de', 'fr', 'au',
        'north', 'south', 'east', 'west', 'central', 'hq', 'headquarter', 'office',
        'factory', 'plant', 'workshop', 'warehouse', 'logistics', 'supply', 'chain',
        'purchase', 'procurement', 'buyer', 'vendor', 'supplier', 'source',
        'material', 'component', 'parts', 'assembly', 'production', 'manufacturing',
        'mfg', 'engineering', 'eng', 'design', 'rd', 'research', 'development',
        'tech', 'technology', 'innovation', 'quality', 'qc', 'qa', 'inspection',
        'test', 'testing', 'verification', 'validation', 'compliance', 'regulatory',
        'legal', 'ip', 'patent', 'trademark', 'copyright', 'standard', 'spec',
        'specification', 'drawing', 'blueprint', 'model', 'prototype', 'sample',
        'pilot', 'trial', 'batch', 'lot', 'serial', 'barcode', 'rfid', 'iot',
        'sensor', 'device', 'machine', 'equipment', 'tool', 'fixture', 'mold',
        'die', 'casting', 'forge', 'stamp', 'weld', 'paint', 'coat', 'surface',
        'heat', 'treatment', 'machine', 'cnc', 'lathe', 'mill', 'drill', 'press',
        'robot', 'automation', 'auto', 'plc', 'scada', 'mes', 'dcs', 'erp', 'aps',
        'wms', 'tms', 'oms', 'srm', 'qms', 'lims', 'cms', 'ems', 'bms', 'fms',
        'hcm', 'hrm', 'crm', 'scm', 'plm', 'pdm', 'capp', 'cam', 'cad', 'cae',
        'catia', 'ug', 'proe', 'solidworks', 'autocad', 'revit', 'bim', 'gis',
        'nav', 'gps', 'tracking', 'fleet', 'vehicle', 'car', 'truck', 'ship',
        'container', 'cargo', 'freight', 'shipping', 'transport', 'transit',
        'dispatch', 'route', 'warehouse', 'wh', 'dc', 'distribution', 'fulfillment',
        'inventory', 'stock', 'shelf', 'rack', 'bin', 'pallet', 'carton', 'box',
        'package', 'parcel', 'mail', 'express', 'courier', 'delivery', 'logistics',
        'supply', 'demand', 'forecast', 'plan', 'schedule', 'planning', 'scheduling',
        'mps', 'mrp', 'drp', 'crp', 'srp', 'aps', 'lp', 'mip', 'sdp', 'vrp',
        'tsp', 'csp', 'psp', 'rsp', 'lsp', 'isp', 'asp', 'csp', 'msp', 'ssp',
        'cloud', 'paas', 'saas', 'iaas', 'faas', 'baas', 'daas', 'maas', 'naas',
        'xaas', 'api', 'openapi', 'rest', 'graphql', 'grpc', 'soap', 'rpc',
        'websocket', 'sse', 'mqtt', 'amqp', 'kafka', 'redis', 'mysql', 'postgres',
        'mongodb', 'cassandra', 'neo4j', 'elasticsearch', 'solr', 'sphinx',
        'memcached', 'rabbitmq', 'activemq', 'zeromq', 'nats', 'pulsar', 'rocketmq',
        'etcd', 'consul', 'zookeeper', 'nacos', 'eureka', 'ribbon', 'hystrix',
        'feign', 'zuul', 'gateway', 'sentinel', 'skywalking', 'pinpoint',
        'cat', 'zipkin', 'jaeger', 'prometheus', 'grafana', 'kibana', 'elk',
        'beats', 'filebeat', 'metricbeat', 'packetbeat', 'heartbeat', 'auditbeat',
        'logstash', 'fluentd', 'fluentbit', 'vector', 'telegraf', 'collector',
        'exporter', 'agent', 'daemon', 'probe', 'scanner', 'sensor', 'agent',
        'client', 'node', 'worker', 'executor', 'runner', 'scheduler', 'cron',
        'timer', 'trigger', 'event', 'handler', 'processor', 'consumer', 'producer',
    ]

def enumerate_crtsh(main_domain, timeout=CRT_TIMEOUT):
    """crt.sh 证书透明度日志收集"""
    results = set()
    try:
        url = f"https://crt.sh/?q=%.{main_domain}&output=json"
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urlopen(req, timeout=timeout)
        data = json.loads(resp.read().decode('utf-8'))
        for entry in data:
            if 'name_value' in entry:
                for name in entry['name_value'].split('\n'):
                    name = name.strip().lower()
                    if name and not name.startswith('*') and name.endswith(main_domain):
                        results.add(name)
                    elif name.startswith('*.'):
                        results.add(name[2:])
        return results
    except Exception as e:
        print(f"  [crt.sh] {main_domain} 失败: {e}")
        return results

def enumerate_subfinder(main_domain, timeout=SUBFINDER_TIMEOUT):
    """subfinder 子域名枚举"""
    results = set()
    try:
        result = subprocess.run(
            ['subfinder', '-d', main_domain, '-silent', '-all'],
            capture_output=True, text=True, timeout=timeout
        )
        for line in result.stdout.strip().split('\n'):
            line = line.strip().lower()
            if line:
                results.add(line)
        return results
    except Exception as e:
        print(f"  [subfinder] {main_domain} 失败: {e}")
        return results

def enumerate_dns_brute(main_domain, words, max_workers=MAX_WORKERS):
    """DNS 字典爆破"""
    results = set()
    subdomains = [f"{w}.{main_domain}" for w in words]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_sub = {executor.submit(resolve_dns, sub): sub for sub in subdomains}
        for future in concurrent.futures.as_completed(future_to_sub):
            sub = future_to_sub[future]
            try:
                ip = future.result()
                if ip:
                    results.add(sub)
            except:
                pass
    return results

def enumerate_permutations(main_domain, words):
    """排列组合生成额外子域名"""
    results = set()
    
    # 常见组合模式
    patterns = ['{a}-{b}', '{a}{b}', '{a}_{b}', '{a}-{b}-v1', '{a}-{b}-v2',
                '{a}-{b}-prod', '{a}-{b}-test', '{a}-{b}-dev',
                'v1-{a}-{b}', 'v2-{a}-{b}', 'api-{a}-{b}',
                '{a}-{b}-cn', '{a}-{b}-us', '{a}-{b}-eu',
                '{a}-{b}-1', '{a}-{b}-2', '{a}-{b}-01', '{a}-{b}-02']
    
    # Top 50 高频前缀
    top_words = ['www', 'mail', 'api', 'admin', 'test', 'dev', 'staging', 'portal',
                 'app', 'cdn', 'static', 'login', 'sso', 'vpn', 'data', 'files',
                 'images', 'media', 'docs', 'wiki', 'support', 'help', 'blog',
                 'news', 'careers', 'jobs', 'hr', 'finance', 'pay', 'shop',
                 'store', 'search', 'service', 'download', 'upload', 'ftp',
                 'gateway', 'proxy', 'firewall', 'lb', 'k8s', 'docker',
                 'jenkins', 'gitlab', 'git', 'jira', 'intranet', 'extranet',
                 'internal', 'external', 'public', 'private', 'secure',
                 'access', 'auth', 'identity', 'key', 'secret', 'user',
                 'customer', 'client', 'sales', 'marketing', 'analytics',
                 'monitor', 'log', 'audit', 'policy', 'documentation']
    
    for a in top_words:
        for b in top_words:
            if a != b:
                for p in patterns:
                    sub = p.format(a=a, b=b)
                    results.add(f"{sub}.{main_domain}")
    
    return results

def enumerate_recursive(subdomains, main_domain, words, max_depth=2):
    """递归子域名枚举（从已发现的子域名继续）"""
    all_found = set(subdomains)
    current = set(subdomains)
    
    for depth in range(1, max_depth + 1):
        next_level = set()
        for sub in current:
            # 从 subdomain.main.com 中，对 subdomain 部分继续枚举
            prefix = sub.replace(f".{main_domain}", "")
            for w in words[:50]:  # 限制递归范围，避免爆炸
                new_sub = f"{w}.{sub}"
                if new_sub not in all_found and new_sub.endswith(main_domain):
                    next_level.add(new_sub)
        
        if not next_level:
            break
        
        # 验证新发现的子域名
        valid = set()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_sub = {executor.submit(resolve_dns, sub): sub for sub in next_level}
            for future in concurrent.futures.as_completed(future_to_sub):
                sub = future_to_sub[future]
                try:
                    if future.result():
                        valid.add(sub)
                except:
                    pass
        
        all_found.update(valid)
        current = valid
        print(f"  [递归深度{depth}] 发现 {len(valid)} 个新子域名")
    
    return all_found

def classify_subdomain(subdomain):
    """子域名分类"""
    sub = subdomain.lower().split('.')[0]
    
    production = ['www', 'app', 'api', 'cdn', 'static', 'shop', 'store', 'portal', 'public', 'prod']
    testing = ['test', 'dev', 'staging', 'uat', 'beta', 'alpha', 'rc', 'preview', 'demo', 'pilot', 'experiment', 'lab', 'sandbox', 'playground']
    management = ['admin', 'manage', 'manager', 'dashboard', 'console', 'control', 'panel', 'backend', 'system', 'sys', 'monitor', 'ops', 'administrator', 'root', 'super', 'master']
    api = ['api', 'openapi', 'rest', 'graphql', 'grpc', 'ws', 'websocket', 'service', 'services', 'gateway', 'proxy', 'bff', 'middleware', 'endpoint', 'endpoints', 'rpc', 'webhook', 'callback', 'notify', 'notification', 'push', 'pull', 'subscribe', 'publish', 'event', 'stream', 'sse', 'mqtt', 'amqp', 'kafka', 'redis', 'mq', 'queue', 'bus', 'pipe', 'pipeline']
    infrastructure = ['vpn', 'ftp', 'ssh', 'sftp', 'rdp', 'gateway', 'proxy', 'firewall', 'lb', 'loadbalancer', 'dns', 'ntp', 'dhcp', 'smtp', 'imap', 'pop', 'mail', 'mx', 'ns', 'ns1', 'ns2', 'ns3', 'whois', 'rwhois', 'dns1', 'dns2', 'resolver', 'cdn', 'cache', 'edge', 'node', 'origin', 'mirror', 'repo', 'repository', 'artifact', 'registry', 'harbor', 'nexus', 'artifactory', 'maven', 'npm', 'pypi', 'docker', 'container', 'k8s', 'kubernetes', 'swarm', 'rancher', 'openshift', 'istio', 'envoy', 'traefik', 'nginx', 'apache', 'haproxy', 'varnish', 'squid', 'memcached', 'redis', 'mysql', 'postgres', 'mongodb', 'elasticsearch', 'kafka', 'zookeeper', 'etcd', 'consul', 'vault', 'nacos', 'eureka', 'prometheus', 'grafana', 'kibana', 'logstash', 'fluentd', 'beats', 'collector', 'agent', 'probe', 'sensor', 'scanner', 'monitor', 'alert', 'notification', 'pager', 'ticketing', 'jira', 'confluence', 'wiki', 'git', 'gitlab', 'github', 'bitbucket', 'gitea', 'gogs', 'jenkins', 'ci', 'cd', 'pipeline', 'build', 'deploy', 'release', 'artifact', 'binary', 'package', 'library', 'module', 'component']
    
    if sub in production: return 'production'
    if sub in testing: return 'testing'
    if sub in management: return 'management'
    if sub in api: return 'api'
    if sub in infrastructure: return 'infrastructure'
    return 'other'

# ============= 主流程 =============
def main():
    if len(sys.argv) < 2:
        print("用法: discover_domains.py <输入> [输出JSON]")
        print("  输入: URL(https://www.example.com) / 域名(www.example.com) / 公司名(华为)")
        sys.exit(1)
    
    raw_input = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    print("=" * 60)
    print(f"域名资产发现 v2")
    print(f"输入: {raw_input}")
    print("=" * 60)
    
    # 解析输入
    mode, _, domain_or_name = parse_input(raw_input)
    print(f"[模式] {mode}")
    
    if mode == 'url':
        main_domain = extract_main_domain(domain_or_name)
        company_name = ''
    elif mode == 'domain':
        main_domain = extract_main_domain(domain_or_name)
        company_name = ''
    else:
        company_name = domain_or_name
        main_domain = ''
    
    print(f"[主域名] {main_domain}")
    print(f"[公司名] {company_name}")
    print("")
    
    # ============= Phase 1: 主域名发现 =============
    print("[阶段1] 主域名资产发现...")
    
    if mode == 'company':
        # 公司名模式：发现关联主域名
        discovered_domains = discover_main_domains(company_name)
        print(f"  候选域名: {len(discovered_domains)} 个")
        
        # 验证可达性
        print("  验证可达性...")
        valid_domains = verify_domains(discovered_domains)
        
        # 选择第一个可达的作为主域名
        if valid_domains:
            main_domain = valid_domains[0]['domain']
            print(f"  [主域名] {main_domain} (IP: {valid_domains[0]['ip']})")
        else:
            print("  [警告] 所有候选域名都不可达，尝试使用第一个候选")
            if discovered_domains:
                main_domain = list(discovered_domains)[0]
    else:
        # URL/域名模式：直接验证
        ip = resolve_dns(main_domain)
        if ip:
            print(f"  [主域名] {main_domain} (IP: {ip})")
        else:
            print(f"  [警告] {main_domain} DNS 不可解析")
        valid_domains = [{'domain': main_domain, 'ip': ip or 'N/A', 'http': None}]
    
    print(f"  有效主域名: {len(valid_domains)} 个")
    for d in valid_domains[:5]:
        status = d.get('http', 'N/A')
        print(f"    {d['domain']} → {d['ip']} (HTTP: {status})")
    print("")
    
    # ============= Phase 2: 子域名枚举 =============
    print("[阶段2] 子域名枚举...")
    print(f"  目标主域名: {main_domain}")
    
    all_subdomains = set()
    
    # 2.1 crt.sh
    print("  [crt.sh] 证书透明度日志...")
    crt_results = enumerate_crtsh(main_domain)
    print(f"    发现 {len(crt_results)} 个")
    all_subdomains.update(crt_results)
    
    # 2.2 subfinder
    print("  [subfinder] 开源情报收集...")
    subfinder_results = enumerate_subfinder(main_domain)
    print(f"    发现 {len(subfinder_results)} 个")
    all_subdomains.update(subfinder_results)
    
    # 2.3 DNS 字典爆破
    print("  [DNS字典] 加载字典...")
    words = load_subdomain_dict()
    print(f"    字典大小: {len(words)} 个前缀")
    
    print("  [DNS字典] 爆破中...")
    dns_results = enumerate_dns_brute(main_domain, words)
    print(f"    发现 {len(dns_results)} 个")
    all_subdomains.update(dns_results)
    
    # 2.4 排列组合
    print("  [排列组合] 生成组合子域名...")
    perm_results = enumerate_permutations(main_domain, words)
    print(f"    生成 {len(perm_results)} 个候选...")
    # 验证排列组合（只验证一部分，避免太慢）
    perm_sample = list(perm_results)[:200]  # 限制样本量
    valid_perms = set()
    for p in perm_sample:
        if resolve_dns(p):
            valid_perms.add(p)
    print(f"    验证通过 {len(valid_perms)} 个")
    all_subdomains.update(valid_perms)
    
    # 2.5 递归子域名枚举
    print("  [递归枚举] 深度2...")
    recursive_results = enumerate_recursive(all_subdomains, main_domain, words, max_depth=2)
    print(f"    递归后总计 {len(recursive_results)} 个")
    all_subdomains = recursive_results
    
    print(f"  子域名去重后: {len(all_subdomains)} 个")
    print("")
    
    # ============= Phase 3: 验证与分类 =============
    print("[阶段3] 验证与分类...")
    
    verified = []
    for sub in sorted(all_subdomains):
        ip = resolve_dns(sub)
        if ip:
            verified.append({
                'subdomain': sub,
                'ip': ip,
                'category': classify_subdomain(sub)
            })
    
    # 分类统计
    categories = {}
    for v in verified:
        cat = v['category']
        categories[cat] = categories.get(cat, 0) + 1
    
    print(f"  DNS 可解析: {len(verified)} 个")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {count}")
    print("")
    
    # ============= 输出 =============
    result = {
        'input': raw_input,
        'mode': mode,
        'main_domain': main_domain,
        'company_name': company_name,
        'valid_domains': valid_domains,
        'subdomains': {
            'total_unique': len(all_subdomains),
            'dns_resolvable': len(verified),
            'by_category': categories,
            'list': verified,
        },
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"[输出] 结果已保存到 {output_file}")
    
    # 打印摘要
    print("=" * 60)
    print("摘要")
    print("=" * 60)
    print(f"主域名: {main_domain}")
    print(f"关联主域名: {len(valid_domains)} 个")
    print(f"唯一子域名: {len(all_subdomains)}")
    print(f"DNS 可解析: {len(verified)}")
    print("")
    print("Top 20 子域名:")
    for v in verified[:20]:
        print(f"  {v['subdomain']} → {v['ip']} [{v['category']}]")
    
    # 打印 domains.txt 格式（用于后续扫描）
    print("")
    print("domains.txt 格式:")
    urls = set()
    for d in valid_domains:
        urls.add(f"https://{d['domain']}")
    for v in verified:
        urls.add(f"https://{v['subdomain']}")
    for url in sorted(urls):
        print(f"  {url}")

if __name__ == '__main__':
    main()
