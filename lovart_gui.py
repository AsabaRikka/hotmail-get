"""
Lovart验证码自动获取工具 - 图形界面版本 v2.0
功能：
1. 输入账号信息并导入到 https://app.wyx66.com/
2. 自动查找最新的Lovart验证码
3. 复制验证码到剪贴板

依赖安装:
    pip install selenium webdriver-manager pyperclip

运行:
    python lovart_gui.py
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import re
import os
import shutil
import json
from typing import Optional, List, Dict
from datetime import datetime

# 尝试导入Selenium
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# 尝试导入剪贴板
try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False


class LovartGUIFetcher:
    """GUI版本的Lovart验证码获取器"""
    
    def __init__(self):
        self.driver = None
        self.wait = None
        self.running = False
        # 设置持久化数据目录
        self.user_data_dir = os.path.join(os.getcwd(), "chrome_profile")
        if not os.path.exists(self.user_data_dir):
            os.makedirs(self.user_data_dir)
    
    def start(self, headless: bool = False):
        """启动浏览器"""
        if not SELENIUM_AVAILABLE:
            raise Exception("Selenium未安装")
        
        options = Options()
        if headless:
            options.add_argument('--headless')
        
        # 使用持久化配置目录
        options.add_argument(f'--user-data-dir={self.user_data_dir}')
        options.add_argument('--profile-directory=Default')
        
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1280,720')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--start-maximized')
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
            
        self.driver.set_page_load_timeout(60)
        self.driver.set_script_timeout(60)
        self.driver.get("https://app.wyx66.com/")
        
        self.wait = WebDriverWait(self.driver, 60)
        time.sleep(5)
        return self
    
    def close(self):
        """关闭浏览器"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
    
    def import_account(self, account_text: str, mode: str = "append") -> bool:
        """
        导入单个账号
        
        Args:
            account_text: 账号文本，格式: email----password----client_id----refresh_token
            mode: "append" 或 "overwrite"
        
        Returns:
            是否成功
        """
        try:
            # 点击导入邮箱按钮
            wait = WebDriverWait(self.driver, 20)
            
            # 尝试多种选择器定位“导入邮箱”按钮
            selectors = [
                "//button[contains(text(), '导入邮箱')]",
                "//button[contains(., '导入邮箱')]",
                "//span[contains(text(), '导入邮箱')]/parent::button",
                "//div[contains(text(), '导入邮箱')]/parent::button",
                "//button[contains(text(), '导入')]",
                "//button[contains(text(), 'Import')]"
            ]
            
            import_btn = None
            last_err = None
            
            for selector in selectors:
                try:
                    import_btn = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    if import_btn:
                        break
                except Exception as e:
                    last_err = e
                    continue
            
            if not import_btn:
                # 记录页面源码以便分析
                print(f"无法找到导入按钮。页面部分源码: {self.driver.page_source[:500]}")
                raise Exception(f"找不到'导入邮箱'按钮，请检查页面是否加载正常。详情: {last_err}")
                
            import_btn.click()
            time.sleep(1.5)
            
            # 解析账号
            parts = account_text.split('----')
            if len(parts) < 4:
                parts = account_text.split('\t')
            
            if len(parts) >= 4:
                import_text = f"{parts[0].strip()}\t{parts[1].strip()}\t{parts[2].strip()}\t{parts[3].strip()}"
            else:
                import_text = account_text
            
            # 输入账号文本
            textarea = wait.until(EC.presence_of_element_located((By.TAG_NAME, "textarea")))
            textarea.clear()
            textarea.send_keys(import_text)
            
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
                    confirm_btn = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    if confirm_btn:
                        break
                except:
                    continue
            
            if not confirm_btn:
                raise Exception(f"找不到'{button_text}'按钮")
                
            confirm_btn.click()
            
            # 等待导入完成
            time.sleep(3)
            return True
            
        except Exception as e:
            print(f"导入失败: {e}")
            return False
    
    def get_lovart_code(self, email: str) -> Optional[str]:
        """
        获取指定邮箱的Lovart验证码
        """
        try:
            # 等待页面加载
            time.sleep(3)
            
            # 记录当前页面状态
            self.save_screenshot("before_search")
            
            # 查找账号行
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            print(f"找到 {len(rows)} 行账号数据")
            
            for i, row in enumerate(rows):
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if not cells: continue
                    
                    row_text = row.text.lower()
                    print(f"第 {i+1} 行文本: {row_text}")
                    
                    # 更加宽松的匹配：只要这一行包含邮箱即可
                    if email.lower() in row_text:
                        print(f"匹配到邮箱: {email}，正在尝试点击查看...")
                        
                        # 尝试多种方式点击查看按钮
                        view_btn = None
                        
                        # 1. 尝试在最后一列找按钮
                        last_cell = cells[-1]
                        try:
                            btns = last_cell.find_elements(By.TAG_NAME, "button")
                            for b in btns:
                                if "查看" in b.text or "view" in b.text.lower():
                                    view_btn = b
                                    break
                            if not view_btn and btns:
                                view_btn = btns[0] # 如果没找到文字，取第一个按钮
                        except:
                            pass
                            
                        # 2. 尝试在整行找包含“查看”的按钮
                        if not view_btn:
                            try:
                                view_btn = row.find_element(By.XPATH, ".//button[contains(text(), '查看')]")
                            except:
                                try:
                                    view_btn = row.find_element(By.XPATH, ".//button[contains(., '查看')]")
                                except:
                                    pass
                        
                        if view_btn:
                            self.driver.execute_script("arguments[0].scrollIntoView();", view_btn)
                            time.sleep(0.5)
                            # 使用 JS 点击以防被遮挡
                            self.driver.execute_script("arguments[0].click();", view_btn)
                            print("已通过脚本点击查看按钮")
                        else:
                            print("未找到查看按钮，尝试直接点击该行")
                            self.driver.execute_script("arguments[0].click();", row)
                            
                        time.sleep(5) # 增加等待邮件列表加载的时间
                        self.save_screenshot("after_click_view")
                        
                        # 查找Lovart邮件
                        code = self._extract_lovart_code()
                        return code
                except Exception as e:
                    print(f"处理第 {i+1} 行时出错: {e}")
            
            print(f"在 {len(rows)} 行中未找到邮箱: {email}")
            
        except Exception as e:
            print(f"获取验证码失败: {e}")
            self.save_screenshot("error_get_code")
        
        return None

    def save_screenshot(self, name: str):
        """保存诊断截图"""
        try:
            if self.driver:
                filename = f"debug_{name}_{int(time.time())}.png"
                self.driver.save_screenshot(filename)
                print(f"诊断截图已保存: {filename}")
        except:
            pass

    def _extract_lovart_code(self) -> Optional[str]:
        """从当前页面提取Lovart验证码"""
        try:
            # 等待邮件列表加载
            time.sleep(5)
            self.save_screenshot("email_list_view")
            
            # 1. 检查是否有 iframe (有些邮件列表可能在 iframe 里)
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            for i, iframe in enumerate(iframes):
                try:
                    self.driver.switch_to.frame(iframe)
                    content = self.driver.page_source.lower()
                    if 'lovart' in content:
                        print(f"在 iframe {i} 中发现 'lovart'")
                        # 在 iframe 中寻找验证码
                        code_match = re.search(r'(\d{6})', content)
                        if code_match:
                            code = code_match.group(1)
                            self.driver.switch_to.default_content()
                            return code
                    self.driver.switch_to.default_content()
                except:
                    self.driver.switch_to.default_content()
                    continue

            # 2. 在主文档中寻找邮件项
            email_selectors = [
                "div[class*='cursor-pointer']",
                "div[class*='flex'][class*='items-center']",
                ".ant-table-row", # 如果是 Ant Design 表格
                "tr", 
                "li"
            ]
            
            email_items = []
            for selector in email_selectors:
                try:
                    items = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    # 寻找包含 lovart 的项
                    for item in items:
                        if 'lovart' in item.text.lower():
                            email_items.append(item)
                    if email_items:
                        print(f"使用选择器 {selector} 找到 {len(email_items)} 个 Lovart 邮件项")
                        break
                except:
                    continue
            
            if not email_items:
                # 最后的绝招：搜索全页文本
                print("未找到明确的邮件项，尝试搜索全页文本...")
                page_text = self.driver.page_source
                # 寻找 lovart 关键字附近的 6 位数字
                # 这里的正则可以根据实际情况微调
                matches = re.findall(r'lovart.*?(\d{6})', page_text, re.IGNORECASE | re.DOTALL)
                if matches:
                    print(f"通过全页搜索找到验证码: {matches[0]}")
                    return matches[0]
                
                # 如果没找到，尝试直接找页面上所有的 6 位数字，取第一个
                all_codes = re.findall(r'\b(\d{6})\b', self.driver.find_element(By.TAG_NAME, "body").text)
                if all_codes:
                    print(f"在页面上找到 6 位数字: {all_codes[0]}")
                    return all_codes[0]
            
            for i, item in enumerate(email_items[:3]): # 只检查前3封相关的
                try:
                    print(f"正在尝试打开第 {i+1} 封 Lovart 邮件...")
                    self.driver.execute_script("arguments[0].scrollIntoView();", item)
                    self.driver.execute_script("arguments[0].click();", item)
                    time.sleep(3)
                    self.save_screenshot(f"email_detail_{i}")
                    
                    # 在打开的详情中找验证码
                    detail_content = self.driver.page_source
                    # 匹配 <div>123456</div> 或类似格式
                    code_match = re.search(r'>(\d{6})<', detail_content)
                    if not code_match:
                        # 匹配 123456
                        code_match = re.search(r'\b(\d{6})\b', self.driver.find_element(By.TAG_NAME, "body").text)
                    
                    if code_match:
                        code = code_match.group(1) if isinstance(code_match.group(0), str) else code_match.group(1)
                        # 如果是 000000 这种可能是占位符，继续找
                        if code != "000000":
                            print(f"从详情中成功提取验证码: {code}")
                            return code
                except:
                    continue
                    
        except Exception as e:
            print(f"提取验证码出错: {e}")
            self.save_screenshot("extract_error")
        
        return None
    
    def get_all_lovart_codes(self) -> Dict[str, Optional[str]]:
        """获取所有账号的验证码"""
        results = {}
        
        try:
            # 等待页面加载
            time.sleep(2)
            
            # 获取所有账号行
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            
            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 2:
                        email = cells[1].text
                        
                        # 点击查看按钮
                        view_buttons = cells[-1].find_elements(By.XPATH, ".//button[contains(text(), '查看')]")
                        for btn in view_buttons:
                            if btn.is_displayed():
                                btn.click()
                                break
                        time.sleep(2)
                        
                        # 查找Lovart邮件
                        code = self._extract_lovart_code()
                        results[email] = code
                        
                        # 关闭对话框
                        try:
                            self.driver.switch_to.default_content()
                            close_buttons = self.driver.find_elements(By.XPATH, "//button[contains(@aria-label, 'Close')]")
                            for btn in close_buttons:
                                if btn.is_displayed():
                                    btn.click()
                                    break
                        except:
                            pass
                        time.sleep(0.5)
                        
                except Exception as e:
                    print(f"处理失败: {e}")
        
        except Exception as e:
            print(f"获取验证码失败: {e}")
        
        return results


class LovartGUIApp:
    """图形界面应用程序"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Lovart验证码获取工具")
        self.root.geometry("750x600")
        self.root.resizable(False, False)
        
        self.fetcher = None
        self.running = False
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        # 标题
        title_label = tk.Label(self.root, text="Lovart验证码自动获取工具", 
                             font=("微软雅黑", 20, "bold"))
        title_label.pack(pady=15)
        
        # 账号输入框
        input_frame = tk.Frame(self.root)
        input_frame.pack(pady=10, padx=30, fill=tk.X)
        
        tk.Label(input_frame, text="账号信息 (格式: email----password----client_id----refresh_token):", 
                font=("微软雅黑", 11)).pack(anchor=tk.W)
        
        self.account_entry = tk.Entry(input_frame, font=("Consolas", 11), width=70)
        self.account_entry.pack(pady=5, fill=tk.X)
        
        # 快捷输入按钮
        quick_frame = tk.Frame(self.root)
        quick_frame.pack(pady=5)
        
        tk.Label(quick_frame, text="快捷输入:", font=("微软雅黑", 10)).pack(side=tk.LEFT)
        
        quick_btn = tk.Button(quick_frame, text="粘贴示例账号", command=self.paste_sample,
                             font=("微软雅黑", 9), width=15)
        quick_btn.pack(side=tk.LEFT, padx=5)
        
        # 按钮区域
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=15)
        
        self.import_btn = tk.Button(button_frame, text="自动导入", command=self.import_account,
                                   font=("微软雅黑", 12), width=12, bg="#4CAF50", fg="white",
                                   activebackground="#45a049", pady=8)
        self.import_btn.pack(side=tk.LEFT, padx=5)

        self.manual_btn = tk.Button(button_frame, text="手动模式", command=self.manual_mode,
                                   font=("微软雅黑", 12), width=12, bg="#9C27B0", fg="white",
                                   activebackground="#7B1FA2", pady=8)
        self.manual_btn.pack(side=tk.LEFT, padx=5)
        
        self.get_code_btn = tk.Button(button_frame, text="获取验证码", command=self.get_code,
                                     font=("微软雅黑", 12), width=12, bg="#2196F3", fg="white",
                                     activebackground="#1976D2", pady=8)
        self.get_code_btn.pack(side=tk.LEFT, padx=5)
        
        self.get_all_btn = tk.Button(button_frame, text="获取全部", command=self.get_all_codes,
                                    font=("微软雅黑", 12), width=14, bg="#FF9800", fg="white",
                                    activebackground="#F57C00", pady=8)
        self.get_all_btn.pack(side=tk.LEFT, padx=5)
        
        # 状态显示
        status_frame = tk.Frame(self.root)
        status_frame.pack(pady=5, padx=30, fill=tk.BOTH, expand=True)
        
        tk.Label(status_frame, text="运行日志:", font=("微软雅黑", 11)).pack(anchor=tk.W)
        
        self.status_text = scrolledtext.ScrolledText(status_frame, height=10, font=("Consolas", 10))
        self.status_text.pack(pady=5, fill=tk.BOTH, expand=True)
        
        # 验证码显示
        result_frame = tk.Frame(self.root)
        result_frame.pack(pady=10, padx=30, fill=tk.X)
        
        tk.Label(result_frame, text="最新验证码:", font=("微软雅黑", 12)).pack(anchor=tk.W)
        
        self.code_entry = tk.Entry(result_frame, font=("Consolas", 24, "bold"), justify=tk.CENTER)
        self.code_entry.pack(pady=8, fill=tk.X)
        
        # 复制按钮
        copy_frame = tk.Frame(self.root)
        copy_frame.pack(pady=5)
        
        copy_btn = tk.Button(copy_frame, text="复制到剪贴板", command=self.copy_code,
                            font=("微软雅黑", 12), width=18, bg="#673AB7", fg="white",
                            activebackground="#512DA8", pady=5)
        copy_btn.pack()
        
        # 底部信息
        footer_label = tk.Label(self.root, text="手动模式: 打开浏览器后您可以手动导入或登录\n获取验证码: 只输入邮箱(如 test@outlook.com) 即可在已导入列表中查找", 
                              font=("微软雅黑", 9), fg="gray", justify=tk.LEFT)
        footer_label.pack(pady=8)
    
    def paste_sample(self):
        """粘贴示例账号"""
        sample = "qijvl33265942@hotmail.com----lanju62153177----9e5f94bc-e8a4-4e73-b8be-63364c29d753----M.C529_SN1.0.U.-CvnnC36GYVuUnZOQ5l7EZc*j!qc5AoK4*8IrgKB6bxvoY65XsTubyGZFM0JuyVv8KdoIYaEbKsm1ylUNfVjFUA4mCyr!lGEJiFVIUghmt2HY!DyFtqvOU6vZPojviWwNkLTxZEFjXSFXErXDhS8ESLVtROVk5lSOXRy4yFipoW72HIhtgLjDiZYrpUF9ko8JV0248mLUV8DA0yqmGgg6vibl!T3Pa3a!nTcb2QOUmDfIQ8VWanP8hwOLWwNXEqHpxZ*m5Zh60F9ImdV*Zpy6gatNctOx1OrTJ1AlFYeWCW0bUOYJ6n4yQXHbJN1XdHXAINg8GF*C0VZLB5foMZsSBRFLTR*8oYGcaGLM*MBL71Mg9pdARCpYwkhB3uSDVbnRrVA8H2qUsIdZm2quN!bRY6wyyTfQU3zJz*3utp6gANHS7DOnJcYZpbb222W*FedUlg$$"
        self.account_entry.delete(0, tk.END)
        self.account_entry.insert(0, sample)
    
    def log(self, message: str):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.see(tk.END)
    
    def import_account(self):
        """导入账号"""
        account_text = self.account_entry.get().strip()
        
        if not account_text or "----" not in account_text:
            messagebox.showwarning("警告", "自动导入需要完整的账号信息格式 (email----password----...)")
            return
        
        # 禁用按钮
        self.set_buttons_state(False)
        self.log("正在准备自动导入...")
        
        # 后台线程执行
        def run():
            try:
                self.log("正在启动Chrome浏览器...")
                self.fetcher = LovartGUIFetcher()
                self.fetcher.start(headless=False)
                self.log("浏览器已启动，等待页面加载...")
                time.sleep(3)
                
                self.log("正在导入账号...")
                if self.fetcher.import_account(account_text):
                    self.log("账号导入成功!")
                    self.root.after(0, lambda: messagebox.showinfo("成功", "账号导入成功!"))
                else:
                    self.log("账号导入失败!")
                    self.root.after(0, lambda: messagebox.showerror("错误", "账号导入失败!"))
            
            except Exception as e:
                error_msg = str(e)
                self.log(f"错误: {error_msg}")
                self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
            
            finally:
                self.root.after(0, lambda: self.set_buttons_state(True))
        
        threading.Thread(target=run, daemon=True).start()
    
    def get_code(self):
        """获取验证码"""
        account_text = self.account_entry.get().strip()
        
        if not account_text:
            messagebox.showwarning("警告", "请先输入邮箱账号或完整的账号信息")
            return
        
        # 提取邮箱
        email = account_text.split('----')[0].strip() if '----' in account_text else account_text
        
        # 禁用按钮
        self.set_buttons_state(False)
        self.log(f"正在查找 {email} 的验证码...")
        
        def run():
            try:
                if not self.fetcher or not self.fetcher.driver:
                    self.fetcher = LovartGUIFetcher()
                    self.fetcher.start(headless=False)
                    self.log("浏览器已启动")
                    
                    # 如果提供了完整信息，则尝试自动导入
                    if '----' in account_text:
                        self.log("检测到完整账号信息，正在自动导入...")
                        self.fetcher.import_account(account_text)
                    else:
                        self.log("未检测到完整信息，假设账号已手动导入")
                
                # 获取验证码
                code = self.fetcher.get_lovart_code(email)
                
                if code:
                    self.code_entry.delete(0, tk.END)
                    self.code_entry.insert(0, code)
                    self.log(f"找到验证码: {code}")
                    
                    # 自动复制
                    self.copy_to_clipboard(code)
                    self.log("验证码已复制到剪贴板!")
                else:
                    self.log("未找到验证码，请确保账号有Lovart邮件")
                    messagebox.showwarning("警告", "未找到验证码")
            
            except Exception as e:
                self.log(f"错误: {e}")
                messagebox.showerror("错误", str(e))
            
            finally:
                self.set_buttons_state(True)
        
        threading.Thread(target=run, daemon=True).start()
    
    def get_all_codes(self):
        """获取所有账号的验证码"""
        self.set_buttons_state(False)
        self.log("正在准备批量获取...")
        
        def run():
            try:
                if not self.fetcher or not self.fetcher.driver:
                    self.fetcher = LovartGUIFetcher()
                    self.fetcher.start(headless=False)
                    self.log("浏览器已启动")
                
                self.log("正在从页面读取邮箱列表...")
                # 这里假设用户已经导入了账号
                # 调用 fetcher 的方法获取所有验证码
                codes = self.fetcher.get_all_lovart_codes()
                
                if codes:
                    self.log(f"成功获取 {len(codes)} 个验证码")
                    # 在日志中显示
                    for email, code in codes.items():
                        self.log(f"[{email}] -> {code}")
                    self.root.after(0, lambda: messagebox.showinfo("成功", f"批量获取完成，共 {len(codes)} 个"))
                else:
                    self.log("未找到任何验证码，请确保账号已登录并有邮件")
            except Exception as e:
                self.log(f"批量获取失败: {str(e)}")
            finally:
                self.root.after(0, lambda: self.set_buttons_state(True))
        
        threading.Thread(target=run, daemon=True).start()
    
    def copy_code(self):
        """复制验证码"""
        code = self.code_entry.get().strip()
        if code:
            self.copy_to_clipboard(code)
            self.log("验证码已复制到剪贴板!")
            messagebox.showinfo("成功", "验证码已复制到剪贴板!")
        else:
            messagebox.showwarning("警告", "没有可复制的验证码")
    
    def copy_to_clipboard(self, text: str):
        """复制到剪贴板"""
        try:
            if CLIPBOARD_AVAILABLE:
                pyperclip.copy(text)
            else:
                # 备用方法
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
        except:
            # 备用方法
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
    
    def manual_mode(self):
        """手动操作模式"""
        self.set_buttons_state(False)
        self.log("启动手动模式...")
        
        def run():
            try:
                if not self.fetcher or not self.fetcher.driver:
                    self.fetcher = LovartGUIFetcher()
                    self.fetcher.start(headless=False)
                    self.log("浏览器已启动，请在浏览器中手动导入或登录")
                else:
                    self.log("浏览器已在运行中")
                    self.fetcher.driver.maximize_window()
                
                self.log("提示：手动导入完成后，直接点击'获取验证码'即可")
            except Exception as e:
                self.log(f"启动失败: {str(e)}")
            finally:
                self.root.after(0, lambda: self.set_buttons_state(True))
        
        threading.Thread(target=run, daemon=True).start()

    def set_buttons_state(self, enabled: bool):
        """设置按钮状态"""
        state = tk.NORMAL if enabled else tk.DISABLED
        self.import_btn.config(state=state)
        self.get_code_btn.config(state=state)
        self.get_all_btn.config(state=state)


def main():
    """主函数"""
    root = tk.Tk()
    app = LovartGUIApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()