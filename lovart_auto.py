"""
Lovart验证码自动获取工具 v2.0
使用Selenium或Playwright从 https://app.wyx66.com/ 获取Lovart验证码

依赖安装:
    # Playwright (推荐)
    pip install playwright
    playwright install chromium
    
    # 或者 Selenium
    pip install selenium webdriver-manager

使用示例:
    python lovart_auto.py --accounts "email1@outlook.com----pass1----client_id1----token1"
"""

import argparse
import json
import re
import time
import sys
from typing import Optional, List, Dict
from datetime import datetime

# 尝试导入Playwright
try:
    from playwright.sync_api import sync_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# 尝试导入Selenium作为备选
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


class LovartFetcher:
    """Lovart验证码获取器"""
    
    def __init__(self, base_url: str = "https://app.wyx66.com"):
        self.base_url = base_url
        self.browser = None
        self.page = None
        self.driver = None
    
    def start_with_playwright(self, headless: bool = False):
        """使用Playwright启动浏览器"""
        if not PLAYWRIGHT_AVAILABLE:
            raise Exception("Playwright未安装，请运行: pip install playwright")
        
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=headless)
        self.context = self.browser.new_context(
            viewport={'width': 1280, 'height': 720}
        )
        self.page = self.context.new_page()
        self.page.goto(self.base_url)
        print(f"✓ 浏览器已启动: {self.base_url}")
        return self
    
    def start_with_selenium(self, headless: bool = True):
        """使用Selenium启动浏览器"""
        if not SELENIUM_AVAILABLE:
            raise Exception("Selenium未安装，请运行: pip install selenium webdriver-manager")
        
        options = Options()
        if headless:
            options.add_argument('--headless')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.get(self.base_url)
        print(f"✓ 浏览器已启动: {self.base_url}")
        return self
    
    def close(self):
        """关闭浏览器"""
        if self.browser:
            self.browser.close()
            self.playwright.stop()
        if self.driver:
            self.driver.quit()
        print("✓ 浏览器已关闭")
    
    def import_accounts_text(self, accounts_text: str, mode: str = "append"):
        """
        通过文本导入账号
        
        Args:
            accounts_text: 账号文本，每行一个账号，字段用Tab或----分隔
            mode: "append" 或 "overwrite"
        """
        if not self.page and not self.driver:
            raise Exception("浏览器未启动")
        
        # 点击导入邮箱按钮
        if self.page:
            self.page.click('button:has-text("导入邮箱")')
            self.page.wait_for_timeout(500)
        else:
            self.driver.find_element(By.XPATH, "//button[contains(text(), '导入邮箱')]").click()
            time.sleep(0.5)
        
        # 输入账号文本
        if self.page:
            self.page.fill('textarea', accounts_text)
        else:
            textarea = self.driver.find_element(By.TAG_NAME, "textarea")
            textarea.clear()
            textarea.send_keys(accounts_text)
        
        # 选择导入模式
        button_text = "追加导入" if mode == "append" else "覆盖导入"
        if self.page:
            self.page.click(f'button:has-text("{button_text}")')
            self.page.wait_for_selector(f'text=成功导入', timeout=30000)
        else:
            self.driver.find_element(By.XPATH, f"//button[contains(text(), '{button_text}')]").click()
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '成功导入')]"))
            )
        
        print(f"✓ 账号导入成功")
    
    def get_accounts_list(self) -> List[Dict]:
        """获取账号列表"""
        accounts = []
        
        if self.page:
            # 使用Playwright
            rows = self.page.query_selector_all('table tbody tr')
            for row in rows:
                cells = row.query_selector_all('td')
                if len(cells) >= 6:
                    accounts.append({
                        'email': cells[1].inner_text(),
                        'password': cells[2].inner_text(),
                        'group': cells[3].inner_text(),
                        'status': cells[4].inner_text(),
                        'permission': cells[5].inner_text()
                    })
        else:
            # 使用Selenium
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 6:
                    accounts.append({
                        'email': cells[1].text,
                        'password': cells[2].text,
                        'group': cells[3].text,
                        'status': cells[4].text,
                        'permission': cells[5].text
                    })
        
        return accounts
    
    def view_account_emails(self, email: str) -> List[Dict]:
        """
        查看账号的邮件列表
        
        Args:
            email: 邮箱地址
        
        Returns:
            邮件列表
        """
        if self.page:
            # 查找并点击对应账号的查看按钮
            self.page.click('text=邮箱列表')
            self.page.wait_for_timeout(1000)
            
            # 查找账号行
            rows = self.page.query_selector_all('table tbody tr')
            for row in rows:
                if email in row.inner_text():
                    row.click('button:has-text("查看")')
                    break
            
            self.page.wait_for_timeout(2000)
            
            # 获取邮件列表
            emails = []
            email_items = self.page.query_selector_all('[class*="email-item"], [class*="mail-item"], .mail-list-item')
            for item in email_items:
                try:
                    from_elem = item.query_selector('.from, .sender')
                    subject_elem = item.query_selector('.subject')
                    time_elem = item.query_selector('.time, .date')
                    preview_elem = item.query_selector('.preview')
                    
                    emails.append({
                        'from': from_elem.inner_text() if from_elem else '',
                        'subject': subject_elem.inner_text() if subject_elem else '',
                        'time': time_elem.inner_text() if time_elem else '',
                        'preview': preview_elem.inner_text() if preview_elem else ''
                    })
                except:
                    pass
            
            return emails
        
        return []
    
    def get_lovart_code_from_emails(self, email: str) -> Optional[str]:
        """
        获取指定邮箱的Lovart验证码
        
        Args:
            email: 邮箱地址
        
        Returns:
            验证码，如果未找到返回None
        """
        emails = self.view_account_emails(email)
        
        for email_data in emails:
            from_text = email_data.get('from', '')
            subject = email_data.get('subject', '')
            preview = email_data.get('preview', '')
            
            # 检查是否是Lovart邮件
            if 'lovart' in from_text.lower() or 'lovart' in subject.lower():
                # 提取6位数字验证码
                match = re.search(r'(\d{6})', preview)
                if match:
                    return match.group(1)
        
        return None
    
    def get_all_lovart_codes(self) -> Dict[str, Optional[str]]:
        """
        获取所有账号的Lovart验证码
        
        Returns:
            字典，键为邮箱地址，值为验证码
        """
        results = {}
        
        if self.page:
            # 点击邮箱列表
            self.page.click('text=邮箱列表')
            self.page.wait_for_timeout(1000)
            
            # 获取所有账号行
            rows = self.page.query_selector_all('table tbody tr')
            
            for i, row in enumerate(rows):
                try:
                    # 获取邮箱地址
                    cells = row.query_selector_all('td')
                    if len(cells) >= 2:
                        email = cells[1].inner_text()
                        
                        # 点击查看按钮
                        view_btn = row.query_selector('button:has-text("查看")')
                        if view_btn:
                            view_btn.click()
                            self.page.wait_for_timeout(2000)
                            
                            # 查找Lovart邮件
                            code = self._extract_lovart_code_playwright()
                            results[email] = code
                            
                            # 关闭对话框
                            self.page.keyboard.press('Escape')
                            self.page.wait_for_timeout(500)
                            
                            print(f"  处理: {email} -> {code}")
                except Exception as e:
                    print(f"  处理 {email} 时出错: {e}")
        
        return results
    
    def _extract_lovart_code_playwright(self) -> Optional[str]:
        """从当前页面提取Lovart验证码 (Playwright)"""
        # 查找Lovart邮件
        email_items = self.page.query_selector_all('[class*="email-item"], [class*="mail-item"]')
        
        for item in email_items:
            from_elem = item.query_selector('.from, .sender')
            if from_elem and 'lovart' in from_elem.inner_text().lower():
                # 点击打开邮件
                item.click()
                self.page.wait_for_timeout(1000)
                
                # 获取邮件内容
                body = self.page.query_selector('[class*="email-body"], .mail-content, iframe')
                if body:
                    text = body.inner_text()
                    # 查找6位数字验证码
                    match = re.search(r'(\d{6})', text)
                    if match:
                        return match.group(1)
                
                # 返回
                self.page.keyboard.press('Escape')
                self.page.wait_for_timeout(500)
        
        return None


def parse_accounts(accounts_str: str) -> List[Dict]:
    """
    解析账号字符串
    
    Args:
        accounts_str: 账号字符串，格式: email----password----client_id----refresh_token
    
    Returns:
        账号列表
    """
    accounts = []
    lines = accounts_str.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 支持Tab或----分隔
        if '\t' in line:
            parts = line.split('\t')
        else:
            parts = line.split('----')
        
        if len(parts) >= 4:
            accounts.append({
                'email': parts[0].strip(),
                'password': parts[1].strip(),
                'client_id': parts[2].strip(),
                'refresh_token': parts[3].strip()
            })
    
    return accounts


def accounts_to_text(accounts: List[Dict]) -> str:
    """将账号列表转换为导入文本"""
    lines = []
    for acc in accounts:
        line = f"{acc['email']}\t{acc['password']}\t{acc['client_id']}\t{acc['refresh_token']}"
        lines.append(line)
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Lovart验证码自动获取工具')
    parser.add_argument('--accounts', '-a', type=str, help='账号文本，每行一个账号，字段用Tab或----分隔')
    parser.add_argument('--file', '-f', type=str, help='账号文件路径')
    parser.add_argument('--headless', action='store_true', default=False, help='无头模式运行浏览器')
    parser.add_argument('--output', '-o', type=str, help='输出文件路径')
    parser.add_argument('--mode', '-m', choices=['append', 'overwrite'], default='append', help='导入模式')
    
    args = parser.parse_args()
    
    # 获取账号数据
    accounts_text = ""
    if args.accounts:
        accounts_text = args.accounts
    elif args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            accounts_text = f.read()
    else:
        print("错误: 请提供账号数据 (--accounts 或 --file)")
        return
    
    # 解析账号
    accounts = parse_accounts(accounts_text)
    if not accounts:
        print("错误: 未解析到有效账号")
        return
    
    print("=" * 60)
    print("Lovart验证码自动获取工具")
    print("=" * 60)
    print(f"账号数量: {len(accounts)}")
    print(f"导入模式: {args.mode}")
    print("-" * 60)
    
    # 创建获取器
    fetcher = LovartFetcher()
    
    try:
        # 启动浏览器
        if PLAYWRIGHT_AVAILABLE:
            fetcher.start_with_playwright(headless=args.headless)
        elif SELENIUM_AVAILABLE:
            fetcher.start_with_selenium(headless=args.headless)
        else:
            print("错误: 请安装 Playwright 或 Selenium")
            print("pip install playwright  # 推荐")
            print("pip install selenium webdriver-manager")
            return
        
        # 导入账号
        import_text = accounts_to_text(accounts)
        fetcher.import_accounts_text(import_text, mode=args.mode)
        
        # 等待邮件刷新
        print("\n等待邮件刷新...")
        time.sleep(5)
        
        # 获取所有验证码
        print("\n开始获取Lovart验证码...")
        results = fetcher.get_all_lovart_codes()
        
        # 输出结果
        print("\n" + "=" * 60)
        print("结果:")
        print("=" * 60)
        for email, code in results.items():
            status = code if code else "未找到"
            print(f"  {email}: {status}")
        
        # 保存结果
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\n结果已保存到: {args.output}")
    
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        fetcher.close()


if __name__ == "__main__":
    main()