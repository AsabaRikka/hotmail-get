"""
Lovart验证码自动获取工具
使用浏览器自动化从 https://app.wyx66.com/ 获取Lovart验证码

依赖安装:
    pip install playwright
    playwright install chromium
"""

import json
import re
import time
from typing import Optional, List, Dict
from datetime import datetime

# 如果使用Playwright
try:
    from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("警告: Playwright未安装，请运行: pip install playwright")


class LovartCodeFetcher:
    def __init__(self, base_url: str = "https://app.wyx66.com"):
        self.base_url = base_url
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
    
    def start_browser(self, headless: bool = False):
        """启动浏览器"""
        if not PLAYWRIGHT_AVAILABLE:
            raise Exception("Playwright未安装")
        
        playwright = sync_playwright().start()
        self.browser = playwright.chromium.launch(headless=headless)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.goto(self.base_url)
        print("浏览器已启动")
    
    def close_browser(self):
        """关闭浏览器"""
        if self.browser:
            self.browser.close()
            print("浏览器已关闭")
    
    def import_accounts(self, accounts: List[Dict]):
        """
        导入账号到系统
        
        Args:
            accounts: 账号列表，每项包含 email, password, client_id, refresh_token
        """
        if not self.page:
            raise Exception("浏览器未启动")
        
        # 点击导入邮箱按钮
        self.page.click('button:has-text("导入邮箱")')
        self.page.wait_for_selector('textarea')
        
        # 构建导入数据
        lines = []
        for acc in accounts:
            line = f"{acc['email']}\t{acc['password']}\t{acc['client_id']}\t{acc['refresh_token']}"
            lines.append(line)
        
        # 粘贴数据
        self.page.fill('textarea', '\n'.join(lines))
        
        # 点击追加导入或覆盖导入
        self.page.click('button:has-text("追加导入")')
        
        # 等待导入完成
        self.page.wait_for_selector('text=成功导入', timeout=30000)
        print(f"成功导入 {len(accounts)} 个账号")
    
    def refresh_account(self, email: str):
        """
        刷新单个账号的邮件
        
        Args:
            email: 邮箱地址
        """
        if not self.page:
            raise Exception("浏览器未启动")
        
        # 找到账号行并点击刷新
        # 这里需要根据实际UI实现
        pass
    
    def get_emails(self, email: str, folder: str = "inbox") -> List[Dict]:
        """
        获取账号的邮件列表
        
        Args:
            email: 邮箱地址
            folder: 文件夹名称 (inbox/sent/draft等)
        
        Returns:
            邮件列表
        """
        if not self.page:
            raise Exception("浏览器未启动")
        
        # 点击邮箱列表
        self.page.click('text=邮箱列表')
        self.page.wait_for_load_state('networkidle')
        
        # 查找并点击对应账号的查看按钮
        rows = self.page.query_selector_all('table tr')
        for row in rows:
            if email in row.inner_text():
                row.click('button:has-text("查看")')
                break
        
        # 等待邮件加载
        self.page.wait_for_selector('text=收件箱', timeout=10000)
        
        # 获取邮件列表
        emails = []
        email_items = self.page.query_selector_all('[class*="email-item"], [class*="mail-item"]')
        for item in email_items:
            emails.append({
                'from': item.query_selector('.from, .sender').inner_text() if item.query_selector('.from, .sender') else '',
                'subject': item.query_selector('.subject').inner_text() if item.query_selector('.subject') else '',
                'time': item.query_selector('.time, .date').inner_text() if item.query_selector('.time, .date') else '',
                'preview': item.query_selector('.preview').inner_text() if item.query_selector('.preview') else ''
            })
        
        return emails
    
    def get_lovart_code(self, email: str) -> Optional[str]:
        """
        获取指定邮箱的Lovart验证码
        
        Args:
            email: 邮箱地址
        
        Returns:
            验证码，如果未找到返回None
        """
        if not self.page:
            raise Exception("浏览器未启动")
        
        # 获取邮件
        emails = self.get_emails(email)
        
        # 查找Lovart邮件
        for email_data in emails:
            if 'lovart' in email_data['from'].lower() or 'lovart' in email_data['subject'].lower():
                # 点击查看邮件详情
                # 这里需要实现点击邮件查看详情
                
                # 从邮件内容中提取验证码
                # 验证码通常是6位数字
                match = re.search(r'(\d{6})', email_data['preview'])
                if match:
                    return match.group(1)
        
        return None
    
    def get_all_lovart_codes(self) -> Dict[str, Optional[str]]:
        """
        获取所有账号的Lovart验证码
        
        Returns:
            字典，键为邮箱地址，值为验证码
        """
        if not self.page:
            raise Exception("浏览器未启动")
        
        results = {}
        
        # 点击邮箱列表
        self.page.click('text=邮箱列表')
        self.page.wait_for_load_state('networkidle')
        
        # 获取所有账号行
        rows = self.page.query_selector_all('table tbody tr')
        
        for row in rows:
            # 获取邮箱地址
            email_cell = row.query_selector('td:nth-child(2)')
            if email_cell:
                email = email_cell.inner_text()
            
            # 点击查看按钮
            view_btn = row.query_selector('button:has-text("查看")')
            if view_btn:
                view_btn.click()
                self.page.wait_for_timeout(2000)
                
                # 查找Lovart邮件
                code = self._extract_lovart_code_from_page()
                results[email] = code
                
                # 关闭对话框
                self.page.keyboard.press('Escape')
                self.page.wait_for_timeout(500)
        
        return results
    
    def _extract_lovart_code_from_page(self) -> Optional[str]:
        """从当前页面提取Lovart验证码"""
        # 查找Lovart邮件
        email_items = self.page.query_selector_all('[class*="email-item"], [class*="mail-item"]')
        
        for item in email_items:
            from_text = item.query_selector('.from, .sender')
            if from_text and 'lovart' in from_text.inner_text().lower():
                # 点击打开邮件
                item.click()
                self.page.wait_for_timeout(1000)
                
                # 获取邮件内容
                body = self.page.query_selector('[class*="email-body"], .mail-content')
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


def main():
    """主函数 - 演示如何使用"""
    if not PLAYWRIGHT_AVAILABLE:
        print("错误: Playwright未安装")
        print("请运行: pip install playwright")
        return
    
    fetcher = LovartCodeFetcher()
    
    # 示例账号数据 (需要替换为实际数据)
    accounts = [
        {
            "email": "example1@hotmail.com",
            "password": "password1",
            "client_id": "client_id_1",
            "refresh_token": "refresh_token_1"
        },
        {
            "email": "example2@hotmail.com",
            "password": "password2",
            "client_id": "client_id_2",
            "refresh_token": "refresh_token_2"
        }
    ]
    
    print("=" * 50)
    print("Lovart验证码自动获取工具")
    print("=" * 50)
    
    try:
        # 启动浏览器
        fetcher.start_browser(headless=False)
        
        # 导入账号
        fetcher.import_accounts(accounts)
        
        # 获取所有验证码
        codes = fetcher.get_all_lovart_codes()
        
        print("\n结果:")
        for email, code in codes.items():
            print(f"  {email}: {code}")
    
    except Exception as e:
        print(f"错误: {e}")
    
    finally:
        fetcher.close_browser()


if __name__ == "__main__":
    main()