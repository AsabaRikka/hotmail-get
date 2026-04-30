"""
Lovart验证码自动获取工具 v3.0 (Selenium版本)
用于从 https://app.wyx66.com/ 网站自动获取邮箱中的Lovart验证码

依赖安装:
    pip install selenium webdriver-manager
    
    # Chrome浏览器需要安装ChromeDriver
    # webdriver-manager会自动处理

使用示例:
    # 1. 导入账号
    python lovart_selenium.py --import "email@outlook.com----password----client_id----token"
    
    # 2. 获取验证码
    python lovart_selenium.py --get-code "email@outlook.com"
    
    # 3. 从文件导入
    python lovart_selenium.py --file accounts.txt
"""

import argparse
import json
import re
import time
import sys
import os
from typing import Optional, List, Dict
from datetime import datetime

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("错误: Selenium未安装")
    print("请运行: pip install selenium webdriver-manager")


class LovartSeleniumFetcher:
    """使用Selenium的Lovart验证码获取器"""
    
    def __init__(self, base_url: str = "https://app.wyx66.com"):
        self.base_url = base_url
        self.driver = None
        self.wait = None
        # 设置持久化数据目录
        self.user_data_dir = os.path.join(os.getcwd(), "chrome_profile")
        if not os.path.exists(self.user_data_dir):
            os.makedirs(self.user_data_dir)
    
    def start(self, headless: bool = False, user_data_dir: str = None):
        """启动浏览器"""
        if not SELENIUM_AVAILABLE:
            raise Exception("Selenium未安装")
        
        options = Options()
        if headless:
            options.add_argument('--headless=new')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
        
        # 使用持久化配置目录
        target_dir = user_data_dir if user_data_dir else self.user_data_dir
        options.add_argument(f'--user-data-dir={target_dir}')
        options.add_argument('--profile-directory=Default')
        
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1280,720')
        
        if user_data_dir:
            options.add_argument(f'--user-data-dir={user_data_dir}')
        options.add_argument('--remote-allow-origins=*')
        
        # 增加防检测参数
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--disable-blink-features=AutomationControlled')
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            
            # 移除 webdriver 特征
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                """
            })
        except Exception as e:
            print(f"使用webdriver-manager启动失败，尝试普通启动: {e}")
            self.driver = webdriver.Chrome(options=options)
            
        self.driver.get(self.base_url)
        
        self.wait = WebDriverWait(self.driver, 20)
        print(f"✓ 浏览器已启动")
        
        # 等待页面加载
        time.sleep(3)
        return self
    
    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            print("✓ 浏览器已关闭")
    
    def wait_and_click(self, locator, timeout: int = 20):
        """等待并点击元素"""
        try:
            element = self.wait.until(EC.element_to_be_clickable(locator))
            element.click()
            time.sleep(0.5)
            return element
        except Exception as e:
            print(f"点击失败: {e}")
            return None
    
    def import_accounts(self, accounts_text: str, mode: str = "append"):
        """
        导入账号
        
        Args:
            accounts_text: 账号文本，每行一个账号
            mode: "append" 或 "overwrite"
        """
        # 点击导入邮箱按钮
        selectors = [
            "//button[contains(text(), '导入邮箱')]",
            "//button[contains(., '导入邮箱')]",
            "//span[contains(text(), '导入邮箱')]/parent::button",
            "//button[contains(text(), '导入')]"
        ]
        
        import_btn = None
        for selector in selectors:
            try:
                import_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                if import_btn:
                    break
            except:
                continue
        
        if not import_btn:
            raise Exception("无法找到'导入邮箱'按钮")
            
        import_btn.click()
        time.sleep(1.5)
        
        # 输入账号文本
        textarea = self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "textarea")))
        textarea.clear()
        textarea.send_keys(accounts_text)
        
        # 选择导入模式
        button_text = "追加导入" if mode == "append" else "覆盖导入"
        confirm_selectors = [
            f"//button[contains(text(), '{button_text}')]",
            f"//button[contains(., '{button_text}')]",
            f"//span[contains(text(), '{button_text}')]/parent::button"
        ]
        
        confirm_btn = None
        for selector in confirm_selectors:
            try:
                confirm_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                if confirm_btn:
                    break
            except:
                continue
        
        if not confirm_btn:
            raise Exception(f"无法找到'{button_text}'按钮")
            
        confirm_btn.click()
        
        # 等待导入完成
        time.sleep(3)
        print(f"✓ 账号导入成功")
    
    def get_accounts_list(self) -> List[Dict]:
        """获取账号列表"""
        accounts = []
        
        try:
            # 切换到邮箱列表视图
            self.driver.find_element(By.XPATH, "//span[contains(text(), '邮箱列表')]").click()
            time.sleep(2)
            
            # 获取表格行
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
        except Exception as e:
            print(f"获取账号列表失败: {e}")
        
        return accounts
    
    def view_email_detail(self, email: str) -> List[Dict]:
        """
        查看账号邮件
        
        Args:
            email: 邮箱地址
        
        Returns:
            邮件列表
        """
        emails = []
        
        try:
            # 查找账号行
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 2 and email in cells[1].text:
                    # 点击查看按钮
                    view_btn = cells[5].find_element(By.XPATH, ".//button[contains(text(), '查看')]")
                    view_btn.click()
                    time.sleep(2)
                    
                    # 获取邮件列表
                    email_items = self.driver.find_elements(By.CSS_SELECTOR, "[class*='email-item'], [class*='mail-item']")
                    
                    for item in email_items:
                        try:
                            from_elem = item.find_element(By.CSS_SELECTOR, ".from, .sender")
                            subject_elem = item.find_element(By.CSS_SELECTOR, ".subject")
                            preview_elem = item.find_element(By.CSS_SELECTOR, ".preview")
                            
                            emails.append({
                                'from': from_elem.text,
                                'subject': subject_elem.text,
                                'preview': preview_elem.text
                            })
                        except:
                            pass
                    
                    break
        except Exception as e:
            print(f"查看邮件失败: {e}")
        
        return emails
    
    def get_lovart_code(self, email: str) -> Optional[str]:
        """
        获取指定邮箱的Lovart验证码
        
        Args:
            email: 邮箱地址
        
        Returns:
            验证码，如果未找到返回None
        """
        emails = self.view_email_detail(email)
        
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
    
    def get_all_codes(self) -> Dict[str, Optional[str]]:
        """获取所有账号的验证码"""
        results = {}
        
        try:
            # 切换到邮箱列表
            self.driver.find_element(By.XPATH, "//span[contains(text(), '邮箱列表')]").click()
            time.sleep(2)
            
            # 获取所有账号行
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            
            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 2:
                        email = cells[1].text
                        
                        # 点击查看按钮
                        view_btn = cells[5].find_element(By.XPATH, ".//button[contains(text(), '查看')]")
                        view_btn.click()
                        time.sleep(2)
                        
                        # 查找Lovart邮件
                        code = self._extract_lovart_code()
                        results[email] = code
                        
                        # 关闭对话框
                        self.driver.switch_to.default_content()
                        time.sleep(0.5)
                        
                        print(f"  {email}: {code}")
                except Exception as e:
                    print(f"  处理失败: {e}")
        except Exception as e:
            print(f"获取验证码失败: {e}")
        
        return results
    
    def _extract_lovart_code(self) -> Optional[str]:
        """从当前页面提取Lovart验证码"""
        try:
            # 查找Lovart邮件
            email_items = self.driver.find_elements(By.CSS_SELECTOR, "[class*='email-item'], [class*='mail-item']")
            
            for item in email_items:
                from_elem = item.find_element(By.CSS_SELECTOR, ".from, .sender")
                if from_elem and 'lovart' in from_elem.text.lower():
                    # 点击打开邮件
                    item.click()
                    time.sleep(1)
                    
                    # 获取邮件内容
                    try:
                        body = self.driver.find_element(By.CSS_SELECTOR, "[class*='email-body'], .mail-content")
                        text = body.text
                        
                        # 查找6位数字验证码
                        match = re.search(r'(\d{6})', text)
                        if match:
                            return match.group(1)
                    except:
                        pass
                    
                    # 尝试切换到iframe
                    try:
                        iframe = self.driver.find_element(By.TAG_NAME, "iframe")
                        self.driver.switch_to.frame(iframe)
                        text = self.driver.find_element(By.TAG_NAME, "body").text
                        
                        match = re.search(r'(\d{6})', text)
                        if match:
                            return match.group(1)
                    except:
                        pass
                    
                    # 返回
                    self.driver.switch_to.default_content()
                    time.sleep(0.5)
        except Exception as e:
            print(f"提取验证码失败: {e}")
        
        return None


def parse_accounts(accounts_str: str) -> List[Dict]:
    """解析账号字符串"""
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
    parser = argparse.ArgumentParser(description='Lovart验证码自动获取工具 (Selenium版本)')
    parser.add_argument('--import', dest='import_text', type=str, help='账号文本，每行一个账号')
    parser.add_argument('--file', '-f', type=str, help='账号文件路径')
    parser.add_argument('--get-code', type=str, help='获取指定邮箱的验证码')
    parser.add_argument('--get-all', action='store_true', help='获取所有账号的验证码')
    parser.add_argument('--headless', action='store_true', default=False, help='无头模式')
    parser.add_argument('--output', '-o', type=str, help='输出文件路径')
    parser.add_argument('--mode', '-m', choices=['append', 'overwrite'], default='append', help='导入模式')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Lovart验证码自动获取工具 (Selenium)")
    print("=" * 60)
    
    if not SELENIUM_AVAILABLE:
        print("错误: Selenium未安装")
        print("请运行: pip install selenium webdriver-manager")
        return
    
    # 创建获取器
    fetcher = LovartSeleniumFetcher()
    
    try:
        # 启动浏览器
        fetcher.start(headless=args.headless)
        
        # 处理导入
        if args.import_text:
            accounts = parse_accounts(args.import_text)
            import_text = accounts_to_text(accounts)
            fetcher.import_accounts(import_text, mode=args.mode)
        
        elif args.file:
            with open(args.file, 'r', encoding='utf-8') as f:
                accounts_text = f.read()
            accounts = parse_accounts(accounts_text)
            import_text = accounts_to_text(accounts)
            fetcher.import_accounts(import_text, mode=args.mode)
        
        # 获取单个验证码
        if args.get_code:
            print(f"\n获取 {args.get_code} 的验证码...")
            code = fetcher.get_lovart_code(args.get_code)
            print(f"验证码: {code}")
            
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump({args.get_code: code}, f, ensure_ascii=False, indent=2)
        
        # 获取所有验证码
        elif args.get_all:
            print("\n获取所有账号的验证码...")
            results = fetcher.get_all_codes()
            
            print("\n" + "=" * 60)
            print("结果:")
            print("=" * 60)
            for email, code in results.items():
                print(f"  {email}: {code}")
            
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