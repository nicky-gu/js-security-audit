#!/usr/bin/env python3
"""
域名资产发现器
功能：
1. 从公司名/初始URL发现关联主域名
2. 子域名枚举（subfinder + crt.sh + dns字典）
3. 输出所有可访问的域名列表

用法: python3 discover_domains.py <公司名或URL> [输出文件]
"""
import sys, json, re, subprocess, urllib.request, urllib.parse, socket, time

def extract_main_domain(url):
    """从URL提取主域名（如 www.example.com → example.com）"""
    domain = re.sub(r'^https?://', '', url).split('/')[0].split(':')[0]
    # 去掉 www. 前缀
    if domain.startswith('www.'):
        domain = domain[4:]
    return domain

def discover_related_domains(company_name, main_domain):
    """基于公司名和主域名发现关联域名"""
    related = set()
    
    # 基于主域名的常见变体
    base = main_domain.rsplit('.', 1)[0]  # example
    tld = main_domain.rsplit('.', 1)[1]    # com
    
    common_suffixes = ['-global', '-group', '-china', '-cn', '-auto', '-corp', 
                       '-tech', '-auto', 'group', 'global', 'china', 'cn',
                       'auto', 'tech', 'corp', 'holdings']
    common_prefixes = ['']
    
    for suffix in common_suffixes:
        if suffix.startswith('-'):
            related.add(f"{base}{suffix}.{tld}")
            related.add(f"{base}{suffix}.com")
        else:
            related.add(f"{base}{suffix}.{tld}")
    
    # 常见 TLD 变体
    for tld_variant in ['com', 'cn', 'com.cn', 'net', 'org']:
        if tld_variant != tld:
            related.add(f"{base}.{tld_variant}")
            related.add(f"www.{base}.{tld_variant}")
    
    # 硬编码大公司映射（可扩展）
    mappings = {
        '示例公司': ['example.com', 'example-global.com', 'example.cn'],
        '华为': ['huawei.com', 'huawei.cn', 'hicloud.com', 'huaweicloud.com'],
        '腾讯': ['tencent.com', 'qq.com', 'weixin.qq.com', 'tencent-cloud.com'],
        '阿里': ['alibaba.com', 'aliyun.com', 'taobao.com', 'tmall.com'],
        '字节': ['bytedance.com', 'tiktok.com', 'douyin.com', 'feishu.cn'],
        '小米': ['mi.com', 'xiaomi.com', 'miui.com'],
        '比亚迪': ['byd.com', 'bydauto.com.cn', 'byd.com.cn'],
        '吉利': ['geely.com', 'geelyauto.com.cn', 'geely.com.cn'],
    }
    
    for key, domains in mappings.items():
        if key in company_name or company_name in key:
            for d in domains:
                related.add(d)
    
    return related

def check_domain_reachable(domain, timeout=5):
    """检查域名是否可解析和访问"""
    try:
        socket.setdefaulttimeout(timeout)
        ip = socket.gethostbyname(domain)
        # 尝试 HTTP 请求
        req = urllib.request.Request(
            f"http://{domain}",
            headers={'User-Agent': 'Mozilla/5.0'},
            method='HEAD'
        )
        try:
            urllib.request.urlopen(req, timeout=timeout)
            return True, ip
        except Exception:
            return True, ip  # 可解析但HTTP可能返回非200
    except Exception:
        return False, None

def enumerate_subdomains_crtsh(domain):
    """使用 crt.sh 被动枚举子域名"""
    subdomains = set()
    try:
        url = f"https://crt.sh/?q=%.{urllib.parse.quote(domain)}&output=json"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            for entry in data:
                names = entry.get('name_value', '').split('\n')
                for name in names:
                    name = name.strip().lower()
                    if name and domain in name and '*' not in name:
                        subdomains.add(name)
    except Exception as e:
        print(f"  [crt.sh] {domain} 失败: {e}", file=sys.stderr)
    return subdomains

def enumerate_subdomains_subfinder(domain, timeout=120):
    """使用 subfinder 枚举子域名"""
    subdomains = set()
    try:
        result = subprocess.run(
            ['subfinder', '-d', domain, '-silent', '-timeout', '10', '-max-time', '2'],
            capture_output=True, text=True, timeout=timeout
        )
        for line in result.stdout.strip().split('\n'):
            line = line.strip().lower()
            if line and domain in line:
                subdomains.add(line)
    except Exception as e:
        print(f"  [subfinder] {domain} 失败: {e}", file=sys.stderr)
    return subdomains

def dns_brute_subdomains(domain, wordlist=None):
    """基于字典的 DNS 爆破（轻量版）"""
    if wordlist is None:
        wordlist = ['www', 'mail', 'ftp', 'api', 'admin', 'test', 'dev', 'staging',
                    'portal', 'app', 'mobile', 'cdn', 'static', 'img', 'assets',
                    'secure', 'vpn', 'remote', 'web', 'blog', 'shop', 'store',
                    'support', 'help', 'docs', 'wiki', 'forum', 'chat', 'video',
                    'media', 'news', 'events', 'careers', 'jobs', 'hr',
                    'login', 'auth', 'sso', 'account', 'user', 'member',
                    'partner', 'vendor', 'supplier', 'b2b', 'b2c',
                    'cn', 'en', 'us', 'eu', 'asia', 'global', 'intl',
                    'server1', 'server2', 'web1', 'web2', 'db', 'backup',
                    'crm', 'erp', 'oa', 'm', 'wap', '3g', '4g', '5g',
                    'wechat', 'wx', 'mp', 'mini', 'open', 'gateway', 'gw',
                    'service', 'services', 'serv', 'svc', 'ms', 'micro',
                    'cloud', 'c', 'data', 'd', 'analytics', 'tracking', 'trace',
                    'monitor', 'mon', 'prometheus', 'grafana', 'kibana', 'elastic',
                    'jenkins', 'ci', 'cd', 'git', 'gitlab', 'github', 'repo',
                    'nexus', 'maven', 'npm', 'pypi', 'docker', 'registry',
                    'k8s', 'kube', 'kubernetes', 'cluster', 'node', 'pod',
                    'internal', 'intranet', 'private', 'corp', 'local',
                    'uat', 'pre', 'preprod', 'preview', 'beta', 'alpha', 'gamma',
                    'demo', 'sandbox', 'playground', 'try', 'lab',
                    'old', 'legacy', 'v1', 'v2', 'v3', 'version', 'release',
                    'download', 'dl', 'files', 'file', 'upload', 'up',
                    'ws', 'wsdl', 'soap', 'rest', 'graphql', 'rpc', 'grpc',
                    'health', 'status', 'ping', 'ready', 'alive', 'check',
                    'config', 'conf', 'settings', 'env', 'vars', 'secrets',
                    'api1', 'api2', 'api3', 'gateway1', 'gateway2',
                    'search', 'es', 'solr', 'lucene', 'index', 'catalog',
                    'cache', 'redis', 'memcached', 'session', 'sessions',
                    'queue', 'mq', 'kafka', 'rabbit', 'rabbitmq', 'celery',
                    'db1', 'db2', 'db3', 'mysql', 'postgres', 'mongo', 'mariadb',
                    'sql', 'oracle', 'mssql', 'cassandra', 'couch', 'neo4j',
                    'ftp', 'sftp', 'ssh', 'rdp', 'vnc', 'telnet', 'smtp',
                    'pop', 'imap', 'exchange', 'mx', 'ns', 'ns1', 'ns2',
                    'dns', 'dns1', 'dns2', 'resolver', 'bind', 'unbound',
                    'ntp', 'time', 'clock', 'snmp', 'syslog', 'log', 'logs',
                    'audit', 'auditlog', 'security', 'sec', 'soc', 'siem',
                    'firewall', 'fw', 'ids', 'ips', 'waf', 'cdn', 'edge',
                    'lb', 'loadbalancer', 'haproxy', 'nginx', 'apache', 'iis',
                    'proxy', 'proxies', 'squid', 'varnish', 'traefik', 'kong',
                    'router', 'switch', 'gateway', 'net', 'network',
                    'stage', 'staging', 'staging1', 'staging2', 'uat', 'sit',
                    'dev1', 'dev2', 'dev3', 'test1', 'test2', 'test3',
                    'qa', 'qc', 'qual', 'validation', 'verify', 'cert']
    
    subdomains = set()
    socket.setdefaulttimeout(3)
    for sub in wordlist:
        subdomain = f"{sub}.{domain}"
        try:
            socket.gethostbyname(subdomain)
            subdomains.add(subdomain)
        except socket.gaierror:
            pass
    return subdomains

def main():
    if len(sys.argv) < 2:
        print("用法: python3 discover_domains.py <公司名或URL> [输出文件]")
        sys.exit(1)
    
    input_str = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    # 判断输入是 URL 还是公司名
    if input_str.startswith('http'):
        main_domain = extract_main_domain(input_str)
        company_name = main_domain.split('.')[0]
    else:
        company_name = input_str
        # 尝试拼音猜测主域名
        # 对于中文公司名，如果没有硬编码映射，使用通用猜测
        ascii_name = re.sub(r'[^\x00-\x7f]', '', company_name).lower().replace(' ', '')
        if ascii_name:
            main_domain = f"{ascii_name}.com"
        else:
            # 纯中文且不在映射中，使用占位符（后续会被硬编码映射覆盖或失败）
            main_domain = "unknown.com"
    
    # 检查硬编码映射，如果匹配则使用映射中的第一个域名作为主域名
    mappings = {
        '华为': ['huawei.com', 'huawei.cn'],
        '腾讯': ['tencent.com', 'qq.com'],
        '阿里': ['alibaba.com', 'aliyun.com'],
        '字节': ['bytedance.com', 'tiktok.com'],
        '小米': ['mi.com', 'xiaomi.com'],
        '比亚迪': ['byd.com', 'byd.com.cn'],
        '吉利': ['geely.com', 'geely.com.cn'],
    }
    for key, domains in mappings.items():
        if key in company_name or company_name in key:
            main_domain = domains[0]
            break
    
    print(f"[*] 输入: {input_str}")
    print(f"[*] 主域名: {main_domain}")
    print(f"[*] 公司名: {company_name}")
    
    # 阶段1: 发现关联主域名
    print(f"\n[阶段1] 发现关联主域名...")
    related_domains = discover_related_domains(company_name, main_domain)
    
    # 验证可达性
    valid_domains = []
    for domain in sorted(related_domains):
        reachable, ip = check_domain_reachable(domain)
        if reachable:
            print(f"  [✓] {domain} → {ip}")
            valid_domains.append(domain)
        else:
            print(f"  [✗] {domain} (不可达)")
    
    if not valid_domains:
        print(f"  [!] 未找到可达的关联域名，使用主域名: {main_domain}")
        valid_domains = [main_domain]
    
    # 阶段2: 子域名枚举
    print(f"\n[阶段2] 子域名枚举...")
    all_subdomains = set()
    
    for domain in valid_domains:
        print(f"  -> 枚举 {domain} ...")
        
        # 2.1 crt.sh
        print(f"      [crt.sh]...", end='', flush=True)
        crt_sh = enumerate_subdomains_crtsh(domain)
        print(f" {len(crt_sh)} 个")
        all_subdomains.update(crt_sh)
        
        # 2.2 subfinder
        print(f"      [subfinder]...", end='', flush=True)
        sf = enumerate_subdomains_subfinder(domain)
        print(f" {len(sf)} 个")
        all_subdomains.update(sf)
        
        # 2.3 DNS 字典爆破
        print(f"      [DNS字典]...", end='', flush=True)
        dns = dns_brute_subdomains(domain)
        print(f" {len(dns)} 个")
        all_subdomains.update(dns)
    
    # 去重并过滤
    final_subdomains = set()
    for sub in all_subdomains:
        sub = sub.lower().strip()
        if sub and '.' in sub:
            # 过滤掉 IP 和通配符
            if '*' not in sub and not re.match(r'\d+\.\d+\.\d+\.\d+', sub):
                final_subdomains.add(sub)
    
    print(f"\n[*] 总计发现 {len(final_subdomains)} 个唯一子域名/域名")
    
    # 输出
    results = {
        'input': input_str,
        'company_name': company_name,
        'main_domain': main_domain,
        'related_domains': valid_domains,
        'all_subdomains': sorted(final_subdomains)
    }
    
    print(f"\n[关联主域名] ({len(valid_domains)} 个):")
    for d in valid_domains:
        print(f"  - {d}")
    
    print(f"\n[子域名] ({len(final_subdomains)} 个):")
    for sub in sorted(final_subdomains)[:50]:  # 只显示前50
        print(f"  - {sub}")
    if len(final_subdomains) > 50:
        print(f"  ... 以及另外 {len(final_subdomains) - 50} 个")
    
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n[+] 结果已保存: {output_file}")
    
    # 同时输出纯文本列表（每行一个URL，用于脚本后续处理）
    if output_file:
        txt_file = output_file.replace('.json', '.txt')
        with open(txt_file, 'w') as f:
            for sub in sorted(final_subdomains):
                f.write(f"https://{sub}\n")
        print(f"[+] URL列表已保存: {txt_file}")

if __name__ == '__main__':
    main()
