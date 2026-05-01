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
import sys
import shutil
import json
from typing import Optional, List, Dict
from datetime import datetime

# 跨平台字体设置
if sys.platform == "darwin":
    UI_FONT = "PingFang SC"
    UI_FONT_BOLD = ("PingFang SC", "bold")
    MONO_FONT = "SF Mono"
elif sys.platform == "win32":
    UI_FONT = "微软雅黑"
    UI_FONT_BOLD = ("微软雅黑", "bold")
    MONO_FONT = "Consolas"
else:
    UI_FONT = "sans-serif"
    UI_FONT_BOLD = ("sans-serif", "bold")
    MONO_FONT = "monospace"

# 尝试导入Selenium
SELENIUM_MISSING = []
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    SELENIUM_MISSING.append("selenium")

if SELENIUM_AVAILABLE:
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        WEBDRIVER_MANAGER_AVAILABLE = True
    except ImportError:
        WEBDRIVER_MANAGER_AVAILABLE = False
        SELENIUM_MISSING.append("webdriver-manager")
else:
    WEBDRIVER_MANAGER_AVAILABLE = False

# 尝试导入剪贴板
try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False


class LovartGUIFetcher:
    """GUI版本的Lovart验证码获取器"""
    
    def __init__(self, log_func=None):
        self.driver = None
        self.wait = None
        self.running = False
        self.log_func = log_func
        self._lock = threading.Lock()
        self._headless = False
        # 使用绝对路径确保持久化目录稳定
        self.user_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "chrome_profile"))
        if not os.path.exists(self.user_data_dir):
            os.makedirs(self.user_data_dir)

        # 设置调试图片目录
        self.debug_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "debug_logs"))
        if not os.path.exists(self.debug_dir):
            os.makedirs(self.debug_dir)

    def log(self, message: str):
        """记录日志"""
        if self.log_func:
            self.log_func(message)
        print(f"[Fetcher] {message}")

    def _cleanup_lock(self):
        """清理浏览器锁定文件并尝试结束残留进程"""
        lock_files = [
            os.path.join(self.user_data_dir, "SingletonLock"),
            os.path.join(self.user_data_dir, "Default", "SingletonLock"),
        ]
        
        # 尝试通过命令行结束可能占用该目录的 Chrome 进程
        try:
            # 仅在 Windows 下尝试执行
            if os.name == 'nt':
                # 寻找并结束所有 chromedriver 和相关的 chrome 进程
                os.system('taskkill /f /im chromedriver.exe /t >nul 2>&1')
                # 注意：这里不直接杀掉所有 chrome.exe，以免影响用户正常的浏览器
                # 但如果启动持续失败，可能需要手动关闭所有 Chrome
        except:
            pass

        for f in lock_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                    self.log(f"已清理残留的锁定文件: {os.path.basename(f)}")
                except Exception as e:
                    self.log(f"警告: 无法清理锁定文件，可能仍被占用: {e}")

    def _is_session_alive(self) -> bool:
        """检查浏览器会话是否仍然有效"""
        if not self.driver:
            return False
        try:
            self.driver.execute_script("return true;")
            return True
        except:
            return False

    def start(self, headless: bool = False):
        """启动浏览器"""
        if not SELENIUM_AVAILABLE:
            raise Exception("Selenium未安装，请运行: pip install selenium")
        if not WEBDRIVER_MANAGER_AVAILABLE:
            raise Exception("webdriver-manager未安装，请运行: pip install webdriver-manager")

        self._headless = headless
        self.log(f"正在配置浏览器 (模式: {'静默' if headless else '显式'})...")
        self._cleanup_lock()
        
        options = Options()
        if headless:
            options.add_argument('--headless=new')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
        else:
            options.add_argument('--start-maximized')
        
        # 确保持久化配置目录
        options.add_argument(f'--user-data-dir={self.user_data_dir}')
        options.add_argument('--profile-directory=Default')
        
        # 核心稳定性参数
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--remote-allow-origins=*')
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--no-first-run')
        options.add_argument('--no-default-browser-check')
        
        # 移除实验性参数，有时会导致崩溃
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        try:
            self.log("正在启动 Chrome (如果长时间没反应，请关闭所有已打开的 Chrome 浏览器)...")
            service = Service(ChromeDriverManager().install())
            # 设置启动超时
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
            err_str = str(e)
            if "session not created" in err_str or "crashed" in err_str:
                self.log("启动崩溃！检测到可能的环境冲突。")
                self.log(">>> 解决方案：请保存好您的工作，手动关闭所有已打开的 Chrome 浏览器窗口，然后重试。")
            raise Exception(f"浏览器启动失败: {err_str}")
            
        self.driver.set_page_load_timeout(60)
        self.driver.set_script_timeout(60)
        
        self.log("正在打开目标网页...")
        try:
            self.driver.get("https://app.wyx66.com/")
            self.log("网页已打开，正在初始化...")
        except:
            self.log("网页打开缓慢，正在继续...")
        
        self.wait = WebDriverWait(self.driver, 60)
        time.sleep(3)
        self._main_window_handle = self.driver.current_window_handle
        self.log("浏览器已就绪")
        return self

    def get_imported_accounts(self) -> List[str]:
        """获取所有已经导入的邮箱账号"""
        accounts = []
        try:
            self._ensure_main_page()
            self.log("正在解析页面账号列表...")
            
            # 获取所有账号行
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            self.log(f"找到 {len(rows)} 行数据")
            
            for i, row in enumerate(rows):
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if not cells:
                        continue
                        
                    # 打印整行文本用于调试
                    row_text = row.text.strip()
                    
                    # 尝试从单元格中寻找邮箱
                    email = ""
                    for cell in cells:
                        cell_text = cell.text.strip()
                        if "@" in cell_text:
                            # 进一步过滤，确保是类似邮箱的格式
                            if "." in cell_text and len(cell_text) > 5:
                                email = cell_text
                                break
                    
                    if email:
                        accounts.append(email)
                        # self.log(f"解析到账号: {email}") # 可选：开启详细日志
                    else:
                        # 如果单元格没找到，尝试从行文本中通过正则提取
                        match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', row_text)
                        if match:
                            email = match.group(0)
                            accounts.append(email)
                            
                except Exception as e:
                    self.log(f"解析第 {i+1} 行失败: {e}")
            
        except Exception as e:
            self.log(f"获取账号失败: {e}")
            
        return accounts
    
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
            self._ensure_main_page()
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

    def get_code_by_keyword(self, keyword: str, email: Optional[str] = None) -> Optional[str]:
        """根据关键字查找最新的验证码

        Args:
            keyword: 要查找的关键字 (如 'lovart', 'Trae')
            email: 可选，指定只在某个邮箱账号中查找

        Returns:
            最新的验证码
        """
        try:
            self._ensure_main_page()

            # 如果指定了邮箱，先找到该邮箱并点击查看
            if email:
                self.log(f"正在定位邮箱: {email}")
                rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                target_row = None
                for row in rows:
                    if email.lower() in row.text.lower():
                        target_row = row
                        break
                
                if not target_row:
                    self.log(f"未找到邮箱: {email}")
                    return None
                
                # 点击查看按钮
                self._click_view_button(target_row)
                time.sleep(3)
            
            self.log(f"正在查找包含关键字 '{keyword}' 的最新邮件...")
            
            # 查找所有邮件项，找到包含关键字的
            code = self._extract_code_by_keyword(keyword)
            
            if code:
                self.log(f"成功找到验证码: {code} (关键字: {keyword})")
                return code
            else:
                self.log(f"未找到包含关键字 '{keyword}' 的验证码邮件")
                
        except Exception as e:
            self.log(f"根据关键字查找验证码失败: {e}")
            
        return None

    def _click_view_button(self, row_element):
        """点击行的查看按钮"""
        try:
            view_btn = None
            cells = row_element.find_elements(By.TAG_NAME, "td")
            if cells:
                for cell in cells:
                    try:
                        btns = cell.find_elements(By.TAG_NAME, "button")
                        for b in btns:
                            if "查看" in b.text or "view" in b.text.lower():
                                view_btn = b
                                break
                        if not view_btn and btns:
                            view_btn = btns[0]
                        if view_btn:
                            break
                    except:
                        pass
            
            if not view_btn:
                try:
                    view_btn = row_element.find_element(By.XPATH, ".//button[contains(text(), '查看')]")
                except:
                    pass
            
            if view_btn:
                self.driver.execute_script("arguments[0].scrollIntoView();", view_btn)
                self.driver.execute_script("arguments[0].click();", view_btn)
        except Exception as e:
            self.log(f"点击查看按钮失败: {e}")

    def _extract_code_by_keyword(self, keyword: str) -> Optional[str]:
        """使用收件箱搜索框按关键字找到最新邮件并提取验证码"""
        try:
            time.sleep(2)

            # 1. 尝试使用搜索框搜索关键词
            search_input = None
            for selector in [
                "input[placeholder*='搜索']",
                "input[placeholder*='search']",
                "input[placeholder*='Search']",
                "input[type='search']",
                "input[class*='search']",
            ]:
                try:
                    search_input = self.driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except:
                    continue

            if search_input:
                self.log(f"找到搜索框，输入关键词: {keyword}")
                search_input.clear()
                search_input.send_keys(keyword)
                time.sleep(2)

            # 2. 找到邮件列表中第一封（最新）包含关键词的邮件并点击
            email_items = self.driver.find_elements(
                By.CSS_SELECTOR,
                "div[class*='cursor-pointer'], div[class*='email-item'], div[class*='mail-item'], li[class*='mail'], tr[class*='mail']"
            )

            for item in email_items:
                try:
                    if keyword.lower() in item.text.lower():
                        self.driver.execute_script("arguments[0].scrollIntoView();", item)
                        self.driver.execute_script("arguments[0].click();", item)
                        self.log("已点击最新匹配邮件")
                        time.sleep(3)
                        break
                except:
                    continue

            # 3. 从当前页面（邮件详情）提取6位验证码
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            code_match = re.search(r'\b(\d{6})\b', body_text)
            if code_match:
                return code_match.group(1)

            # 4. 兜底：从页面源码提取
            page_source = self.driver.page_source
            code_match = re.search(r'>(\d{6})<', page_source)
            if code_match:
                return code_match.group(1)

        except Exception as e:
            self.log(f"提取验证码失败: {e}")

        return None

    def _ensure_main_page(self):
        """确保当前在主账号列表页"""
        if not self._is_session_alive():
            raise Exception("浏览器会话已失效，请重新启动浏览器")

        # 保存主窗口句柄，防止操作过程中打开了新标签页
        try:
            current_handles = self.driver.window_handles
            if hasattr(self, '_main_window_handle') and self._main_window_handle in current_handles:
                if self.driver.current_window_handle != self._main_window_handle:
                    self.driver.switch_to.window(self._main_window_handle)
            else:
                self._main_window_handle = self.driver.current_window_handle
        except:
            pass

        # 始终强制导航回主页，确保关闭所有弹窗/模态框，恢复干净的表格视图
        try:
            self.driver.get("https://app.wyx66.com/")
        except Exception as e:
            raise Exception(f"无法导航到目标网页（浏览器会话可能已失效）: {e}")

        time.sleep(3)

        # 等待表格行加载
        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
            )
        except:
            self.log("等待表格加载超时，继续尝试...")

    def get_account_by_row(self, row_index: int) -> Optional[str]:
        """根据行号获取邮箱账号 (从1开始)"""
        try:
            self._ensure_main_page()

            # 获取所有账号行
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            if row_index < 1 or row_index > len(rows):
                self.log(f"行号错误: 输入 {row_index}, 实际共有 {len(rows)} 行")
                return None
            
            target_row = rows[row_index - 1]
            cells = target_row.find_elements(By.TAG_NAME, "td")
            
            email = ""
            # 尝试从单元格中寻找邮箱
            for cell in cells:
                cell_text = cell.text.strip()
                if "@" in cell_text and "." in cell_text and len(cell_text) > 5:
                    email = cell_text
                    break
            
            if not email:
                # 正则兜底
                match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', target_row.text)
                if match:
                    email = match.group(0)
            
            if email:
                self.log(f"成功获取第 {row_index} 行账号: {email}")
                return email
            else:
                self.log(f"第 {row_index} 行未发现有效邮箱地址")
                
        except Exception as e:
            self.log(f"根据行号获取账号失败: {e}")
            
        return None

    def save_screenshot(self, name: str):
        """保存诊断截图到 debug 文件夹"""
        try:
            if self.driver:
                filename = f"debug_{name}_{int(time.time())}.png"
                filepath = os.path.join(self.debug_dir, filename)
                self.driver.save_screenshot(filepath)
                print(f"诊断截图已保存: {filepath}")
        except Exception as e:
            print(f"保存截图失败: {e}")

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
            self._ensure_main_page()
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
        self._driver_lock = threading.Lock()

        # macOS 按钮颜色兼容: 使用 ttk + clam 主题
        if sys.platform == "darwin":
            self._btn_styles = ttk.Style()
            self._btn_styles.theme_use('clam')
            self._btn_style_count = 0

        self.setup_ui()

    def _colored_btn(self, parent, text, command, font, bg, fg="white", active_bg=None, **kwargs):
        """创建跨平台彩色按钮。macOS 用 ttk+clam 主题, Windows 用原生 tk.Button"""
        if active_bg is None:
            active_bg = bg
        kwargs.pop('pady', None)

        if sys.platform == "darwin":
            self._btn_style_count += 1
            name = f"Btn{self._btn_style_count}.TButton"
            self._btn_styles.configure(name, background=bg, foreground=fg,
                                       font=font, borderwidth=0, relief='flat')
            self._btn_styles.map(name,
                background=[('active', active_bg), ('pressed', active_bg)],
                foreground=[('active', fg)])
            btn = ttk.Button(parent, text=text, style=name, command=command)
            if 'width' in kwargs:
                btn.configure(width=kwargs['width'])
            return btn
        else:
            return tk.Button(parent, text=text, command=command, font=font,
                             bg=bg, fg=fg, activebackground=active_bg, **kwargs)

    def setup_ui(self):
        """设置UI"""
        # 标题
        title_label = tk.Label(self.root, text="Lovart验证码自动获取工具",
                             font=(UI_FONT, 20, "bold"))
        title_label.pack(pady=15)

        # 账号输入框
        input_frame = tk.Frame(self.root)
        input_frame.pack(pady=10, padx=30, fill=tk.X)

        tk.Label(input_frame, text="账号信息 (格式: email----password----client_id----refresh_token):",
                font=(UI_FONT, 11)).pack(anchor=tk.W)

        self.account_entry = tk.Entry(input_frame, font=(MONO_FONT, 11), width=70)
        self.account_entry.pack(pady=5, fill=tk.X)

        # 快捷输入按钮
        quick_frame = tk.Frame(self.root)
        quick_frame.pack(pady=5)

        # 浏览器模式开关
        self.headless_var = tk.BooleanVar(value=True) # 默认开启静默模式
        self.headless_check = tk.Checkbutton(quick_frame, text="静默运行浏览器 (不显示窗口)",
                                           variable=self.headless_var, font=(UI_FONT, 10))
        self.headless_check.pack(side=tk.LEFT, padx=10)

        tk.Label(quick_frame, text="快捷输入:", font=(UI_FONT, 10)).pack(side=tk.LEFT, padx=(20, 5))

        quick_btn = tk.Button(quick_frame, text="粘贴示例账号", command=self.paste_sample,
                             font=(UI_FONT, 9), width=15)
        quick_btn.pack(side=tk.LEFT, padx=5)

        # 按钮区域
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=15)

        self.import_btn = self._colored_btn(button_frame, "自动导入", self.import_account,
                                           (UI_FONT, 12), "#4CAF50", active_bg="#45a049",
                                           width=12, pady=8)
        self.import_btn.pack(side=tk.LEFT, padx=5)

        self.manual_btn = self._colored_btn(button_frame, "手动模式", self.manual_mode,
                                           (UI_FONT, 12), "#9C27B0", active_bg="#7B1FA2",
                                           width=12, pady=8)
        self.manual_btn.pack(side=tk.LEFT, padx=5)

        self.get_code_btn = self._colored_btn(button_frame, "获取验证码", self.get_code,
                                             (UI_FONT, 12), "#2196F3", active_bg="#1976D2",
                                             width=10, pady=8)
        self.get_code_btn.pack(side=tk.LEFT, padx=5)

        self.get_accounts_btn = self._colored_btn(button_frame, "获取已导入账号", self.get_imported_accounts,
                                                 (UI_FONT, 12), "#607D8B", active_bg="#455A64",
                                                 width=14, pady=8)
        self.get_accounts_btn.pack(side=tk.LEFT, padx=5)

        self.get_all_btn = self._colored_btn(button_frame, "获取全部", self.get_all_codes,
                                            (UI_FONT, 12), "#FF9800", active_bg="#F57C00",
                                            width=10, pady=8)
        self.get_all_btn.pack(side=tk.LEFT, padx=5)

        # 行号查询区域
        row_query_frame = tk.Frame(self.root, bg="#f5f5f5")
        row_query_frame.pack(fill=tk.X, pady=5, padx=30)

        tk.Label(row_query_frame, text="输入行号查询:", font=(UI_FONT, 10), bg="#f5f5f5").pack(side=tk.LEFT, padx=(10, 5))
        self.row_entry = tk.Entry(row_query_frame, font=(UI_FONT, 10), width=8)
        self.row_entry.pack(side=tk.LEFT, padx=5)
        self.row_entry.insert(0, "1") # 默认第1行

        self.get_row_btn = self._colored_btn(row_query_frame, "按行号获取账号", self.get_account_by_row_action,
                                            (UI_FONT, 10), "#673AB7", active_bg="#512DA8")
        self.get_row_btn.pack(side=tk.LEFT, padx=10)

        # 关键字查询区域
        keyword_query_frame = tk.Frame(self.root, bg="#f5f5f5")
        keyword_query_frame.pack(fill=tk.X, pady=5, padx=30)

        tk.Label(keyword_query_frame, text="关键字查询验证码:", font=(UI_FONT, 10), bg="#f5f5f5").pack(side=tk.LEFT, padx=(10, 5))
        self.keyword_entry = tk.Entry(keyword_query_frame, font=(UI_FONT, 10), width=15)
        self.keyword_entry.pack(side=tk.LEFT, padx=5)
        self.keyword_entry.insert(0, "lovart") # 默认关键字

        self.get_keyword_btn = self._colored_btn(keyword_query_frame, "根据关键字查找", self.get_code_by_keyword_action,
                                                (UI_FONT, 10), "#009688", active_bg="#00796B")
        self.get_keyword_btn.pack(side=tk.LEFT, padx=10)

        # 状态显示
        status_frame = tk.Frame(self.root)
        status_frame.pack(pady=5, padx=30, fill=tk.BOTH, expand=True)

        tk.Label(status_frame, text="运行日志:", font=(UI_FONT, 11)).pack(anchor=tk.W)

        self.status_text = scrolledtext.ScrolledText(status_frame, height=10, font=(MONO_FONT, 10))
        self.status_text.pack(pady=5, fill=tk.BOTH, expand=True)

        # 验证码显示
        result_frame = tk.Frame(self.root)
        result_frame.pack(pady=10, padx=30, fill=tk.X)

        tk.Label(result_frame, text="最新验证码:", font=(UI_FONT, 12)).pack(anchor=tk.W)

        self.code_entry = tk.Entry(result_frame, font=(MONO_FONT, 24, "bold"), justify=tk.CENTER)
        self.code_entry.pack(pady=8, fill=tk.X)

        # 复制按钮
        copy_frame = tk.Frame(self.root)
        copy_frame.pack(pady=5)

        copy_btn = self._colored_btn(copy_frame, "复制到剪贴板", self.copy_code,
                                    (UI_FONT, 12), "#673AB7", active_bg="#512DA8",
                                    width=18, pady=5)
        copy_btn.pack()
        
        # 底部信息
        footer_label = tk.Label(self.root, text="手动模式: 打开浏览器后您可以手动导入或登录\n获取验证码: 只输入邮箱(如 test@outlook.com) 即可在已导入列表中查找", 
                              font=(UI_FONT, 9), fg="gray", justify=tk.LEFT)
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

    def _ensure_driver_ready(self) -> LovartGUIFetcher:
        """确保浏览器驱动就绪，会话失效时自动重启"""
        with self._driver_lock:
            if not self.fetcher or not self.fetcher.driver:
                self.log("正在启动浏览器...")
                self.fetcher = LovartGUIFetcher(log_func=self.log)
                self.fetcher.start(headless=self.headless_var.get())
            elif not self.fetcher._is_session_alive():
                self.log("检测到浏览器会话已失效，正在重新启动...")
                was_headless = self.fetcher._headless
                self.fetcher.close()
                time.sleep(1)
                self.fetcher = LovartGUIFetcher(log_func=self.log)
                self.fetcher.start(headless=was_headless)
        return self.fetcher
    
    def import_account(self):
        """导入账号"""
        account_text = self.account_entry.get().strip()
        
        if not account_text or "----" not in account_text:
            messagebox.showwarning("警告", "自动导入需要完整的账号信息格式 (email----password----...)")
            return
        
        # 禁用按钮
        self.set_buttons_state(False)
        
        # 后台线程执行
        def run():
            try:
                self._ensure_driver_ready()

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
        is_full_info = '----' in account_text
        email = account_text.split('----')[0].strip() if is_full_info else account_text
        
        # 禁用按钮
        self.set_buttons_state(False)
        self.log(f"正在准备获取 {email} 的验证码...")
        
        def run():
            try:
                self._ensure_driver_ready()

                # 如果提供了完整信息，则尝试自动导入
                if is_full_info:
                    self.log("检测到完整账号信息，正在自动导入...")
                    self.fetcher.import_account(account_text)
                
                # 获取验证码
                self.log(f"正在查找邮箱: {email}")
                code = self.fetcher.get_lovart_code(email)
                
                if code:
                    self.code_entry.delete(0, tk.END)
                    self.code_entry.insert(0, code)
                    self.log(f"成功找到验证码: {code}")
                    
                    # 自动复制
                    self.copy_to_clipboard(code)
                    self.log("验证码已复制到剪贴板!")
                else:
                    self.log("未找到验证码，请确保账号有相关邮件")
                    messagebox.showwarning("警告", "未找到验证码")
            
            except Exception as e:
                self.log(f"错误: {e}")
                messagebox.showerror("错误", str(e))
            
            finally:
                self.set_buttons_state(True)
        
        threading.Thread(target=run, daemon=True).start()
    
    def get_imported_accounts(self):
        """获取所有已经导入的邮箱账号"""
        self.set_buttons_state(False)
        self.log("开始获取已导入账号任务...")
        
        def run():
            try:
                self._ensure_driver_ready()

                accounts = self.fetcher.get_imported_accounts()
                
                if accounts:
                    self.log(f"成功获取 {len(accounts)} 个已导入账号:")
                    for i, email in enumerate(accounts):
                        self.log(f"  {i+1}. {email}")
                    # 自动复制所有账号到剪贴板
                    all_accounts = "\n".join(accounts)
                    self.copy_to_clipboard(all_accounts)
                    self.log("账号已复制到剪贴板!")
                    # 同时填充第一个账号到输入框（需要在主线程操作UI）
                    self.root.after(0, lambda: self.account_entry.delete(0, tk.END))
                    self.root.after(0, lambda: self.account_entry.insert(0, accounts[0]))
                    self.log("第一个账号已填充到上方输入框")
                    self.root.after(0, lambda: messagebox.showinfo("成功", f"成功获取 {len(accounts)} 个已导入账号\n\n(已自动复制到剪贴板)"))
                else:
                    self.log("未找到任何已导入账号")
                    self.root.after(0, lambda: messagebox.showwarning("提醒", "未找到任何已导入账号，请先导入"))
            except Exception as e:
                self.log(f"获取账号列表失败: {str(e)}")
                self.root.after(0, lambda: messagebox.showerror("错误", f"获取失败: {str(e)}"))
            finally:
                self.root.after(0, lambda: self.set_buttons_state(True))
        
        threading.Thread(target=run, daemon=True).start()

    def get_account_by_row_action(self):
        """按行号获取账号的操作"""
        row_str = self.row_entry.get().strip()
        if not row_str or not row_str.isdigit():
            messagebox.showwarning("警告", "请输入有效的数字行号")
            return
            
        row_index = int(row_str)
        self.set_buttons_state(False)
        self.log(f"正在查询第 {row_index} 行的账号...")
        
        def run():
            try:
                self._ensure_driver_ready()

                email = self.fetcher.get_account_by_row(row_index)
                
                if email:
                    self.log(f"第 {row_index} 行账号为: {email}")
                    self.account_entry.delete(0, tk.END)
                    self.account_entry.insert(0, email)
                    self.log("账号已填充到上方输入框")
                    self.copy_to_clipboard(email)
                    self.log("账号已复制到剪贴板!")
                    self.root.after(0, lambda: messagebox.showinfo("成功", f"成功获取第 {row_index} 行账号:\n{email}\n\n(已自动复制到剪贴板)"))
                else:
                    self.log(f"未能获取到第 {row_index} 行账号")
                    self.root.after(0, lambda: messagebox.showwarning("失败", f"未能获取到第 {row_index} 行账号，请检查行号是否正确"))
            except Exception as e:
                self.log(f"按行号查询失败: {str(e)}")
            finally:
                self.root.after(0, lambda: self.set_buttons_state(True))
        
        threading.Thread(target=run, daemon=True).start()

    def get_code_by_keyword_action(self):
        """根据关键字获取验证码的操作"""
        keyword = self.keyword_entry.get().strip()
        if not keyword:
            messagebox.showwarning("警告", "请输入要查找的关键字 (如 'lovart', 'Trae')")
            return
            
        self.set_buttons_state(False)
        self.log(f"正在根据关键字 '{keyword}' 查找最新验证码...")
        
        def run():
            try:
                self._ensure_driver_ready()

                # 检查是否在账号输入框中指定了邮箱
                account_text = self.account_entry.get().strip()
                email = None
                if account_text and "@" in account_text:
                    email = account_text.split('----')[0].strip()
                
                code = self.fetcher.get_code_by_keyword(keyword, email)
                
                if code:
                    self.code_entry.delete(0, tk.END)
                    self.code_entry.insert(0, code)
                    self.log(f"成功找到验证码: {code}")
                    
                    # 自动复制
                    self.copy_to_clipboard(code)
                    self.log("验证码已复制到剪贴板!")
                    self.root.after(0, lambda: messagebox.showinfo("成功", f"成功找到验证码:\n{code}\n\n(已自动复制到剪贴板)"))
                else:
                    self.log(f"未找到包含关键字 '{keyword}' 的验证码")
                    self.root.after(0, lambda: messagebox.showwarning("失败", f"未找到包含关键字 '{keyword}' 的验证码邮件"))
            except Exception as e:
                self.log(f"根据关键字查询失败: {str(e)}")
            finally:
                self.root.after(0, lambda: self.set_buttons_state(True))
        
        threading.Thread(target=run, daemon=True).start()

    def get_all_codes(self):
        """获取所有账号的验证码"""
        self.set_buttons_state(False)
        self.log("正在准备批量获取验证码...")
        
        def run():
            try:
                self._ensure_driver_ready()

                self.log("正在批量处理所有账号...")
                codes = self.fetcher.get_all_lovart_codes()
                
                if codes:
                    self.log(f"批量获取完成，共 {len(codes)} 个结果")
                    for email, code in codes.items():
                        self.log(f"  [{email}] -> {code if code else '未找到'}")
                    self.root.after(0, lambda: messagebox.showinfo("成功", f"批量获取完成，共 {len(codes)} 个结果"))
                else:
                    self.log("未找到任何结果")
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
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
        except:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
    
    def manual_mode(self):
        """手动操作模式"""
        if self.fetcher and self.fetcher.driver:
            self.log("正在切换模式，请稍候...")
            self.fetcher.close()
            
        self.set_buttons_state(False)
        
        def run():
            try:
                self.fetcher = LovartGUIFetcher(log_func=self.log)
                self.fetcher.start(headless=False)
                self.log("显式浏览器已启动，请在其中手动操作")
            except Exception as e:
                self.log(f"启动失败: {str(e)}")
            finally:
                self.root.after(0, lambda: self.set_buttons_state(True))
        
        threading.Thread(target=run, daemon=True).start()

    def set_buttons_state(self, enabled: bool):
        """设置按钮状态"""
        state = tk.NORMAL if enabled else tk.DISABLED
        self.import_btn.config(state=state)
        self.manual_btn.config(state=state)
        self.get_code_btn.config(state=state)
        self.get_accounts_btn.config(state=state)
        self.get_all_btn.config(state=state)
        if hasattr(self, 'get_row_btn'):
            self.get_row_btn.config(state=state)
        if hasattr(self, 'get_keyword_btn'):
            self.get_keyword_btn.config(state=state)
        self.root.update()


def main():
    """主函数"""
    root = tk.Tk()
    app = LovartGUIApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()