#!/usr/bin/env python3
"""
Playwright 自动化浏览器遍历 - 触发所有懒加载JS
用法: python3 spider_js.py <目标URL> [输出目录]
"""
import sys, os, json, re
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright

TARGET = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
OUTDIR = sys.argv[2] if len(sys.argv) > 2 else "./js-spider"
os.makedirs(OUTDIR, exist_ok=True)

js_urls = set()
visited = set()

def is_js_url(url):
    return url.endswith('.js') or url.endswith('.mjs') or '.js?' in url or 'javascript' in url

def handle_route(route, request):
    url = request.url
    if is_js_url(url):
        js_urls.add(url)
    route.continue_()

def auto_interact(page):
    """自动点击所有按钮、链接，滚动页面，填表单"""
    try:
        # 滚动到底部
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(500)
        
        # 点击所有可见的按钮和链接
        clickable = page.query_selector_all('button, a[href], [role="button"]')
        for btn in clickable[:30]:
            try:
                btn.click(force=True, timeout=2000)
                page.wait_for_timeout(300)
            except:
                pass
        
        # 尝试填表单
        inputs = page.query_selector_all('input[type="text"], input:not([type])')
        for inp in inputs[:10]:
            try:
                inp.fill("test")
            except:
                pass
        
        # 再次滚动
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(500)
    except Exception as e:
        print(f"交互错误: {e}")

def main():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                executable_path="/root/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome"
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = context.new_page()
            page.route("**/*", handle_route)
            
            print(f"[*] 开始遍历: {TARGET}")
            page.goto(TARGET, wait_until="networkidle", timeout=30000)
            auto_interact(page)
            
            # 提取页面中所有 script src
            scripts = page.query_selector_all('script[src]')
            for s in scripts:
                src = s.get_attribute('src')
                if src:
                    js_urls.add(urljoin(TARGET, src))
            
            # 提取内联JS中的URL
            inline_scripts = page.query_selector_all('script:not([src])')
            inline_js = []
            for i, s in enumerate(inline_scripts):
                text = s.inner_text()
                if text:
                    inline_js.append(text)
                    urls = re.findall(r'["\']([^"\']+\.js[^"\']*)["\']', text)
                    for u in urls:
                        js_urls.add(urljoin(TARGET, u))
            
            # 保存内联JS
            with open(f"{OUTDIR}/inline_js.json", "w") as f:
                json.dump(inline_js, f, indent=2)
            
            # 保存所有JS URL
            with open(f"{OUTDIR}/js_urls.txt", "w") as f:
                for url in sorted(js_urls):
                    f.write(url + "\n")
            
            print(f"[+] 发现 {len(js_urls)} 个JS URL")
            print(f"[+] 内联JS: {len(inline_js)} 个片段")
            print(f"[+] 结果保存到: {OUTDIR}/")
            
            browser.close()
    except Exception as e:
        print(f"[!] Playwright 遍历出错: {e}")
        # 确保输出文件存在，即使为空
        os.makedirs(OUTDIR, exist_ok=True)
        with open(f"{OUTDIR}/js_urls.txt", "w") as f:
            pass
        with open(f"{OUTDIR}/inline_js.json", "w") as f:
            json.dump([], f)
        raise

if __name__ == "__main__":
    main()
