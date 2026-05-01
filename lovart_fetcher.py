"""
Lovart验证码获取工具
用于从 https://app.wyx66.com/ 网站自动获取邮箱中的Lovart验证码
"""

import requests
import json
import time
import re
from typing import Optional, List, Dict

class LovartCodeFetcher:
    def __init__(self, base_url: str = "https://app.wyx66.com"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json"
        })
    
    def refresh_emails(self, email_address: str, client_id: str, refresh_token: str, 
                      folder: str = "inbox", token_type: str = "imap") -> Dict:
        """
        刷新邮箱邮件
        
        Args:
            email_address: 邮箱地址
            client_id: Client ID
            refresh_token: 刷新令牌
            folder: 文件夹 (默认: inbox)
            token_type: 令牌类型 (默认: imap)
        
        Returns:
            API响应结果
        """
        url = f"{self.base_url}/api/emails/refresh"
        data = {
            "email_address": email_address,
            "client_id": client_id,
            "refresh_token": refresh_token,
            "folder": folder,
            "token_type": token_type
        }
        
        try:
            response = self.session.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"刷新邮件失败: {e}")
            return {"error": str(e)}
    
    def detect_permission(self, client_id: str, refresh_token: str) -> Dict:
        """
        检测账号权限类型
        
        Args:
            client_id: Client ID
            refresh_token: 刷新令牌
        
        Returns:
            权限检测结果
        """
        url = f"{self.base_url}/detect-permission"
        data = {
            "client_id": client_id,
            "refresh_token": refresh_token
        }
        
        try:
            response = self.session.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"检测权限失败: {e}")
            return {"error": str(e)}
    
    def get_lovart_code_from_emails(self, emails_data: Dict) -> Optional[str]:
        """
        从邮件数据中提取Lovart验证码
        
        Args:
            emails_data: 邮件数据
        
        Returns:
            Lovart验证码，如果没有找到则返回None
        """
        # 这个方法需要根据实际的API返回格式来实现
        # 目前需要先了解API返回的具体格式
        
        # 查找来自 lovart@lovart.ai 的邮件
        if "messages" in emails_data:
            for msg in emails_data["messages"]:
                if msg.get("from", "").lower() == "lovart@lovart.ai":
                    subject = msg.get("subject", "")
                    if "welcome to lovart" in subject.lower() or "verification" in subject.lower():
                        # 提取验证码
                        body = msg.get("body", "")
                        code_match = re.search(r'(\d{6})', body)
                        if code_match:
                            return code_match.group(1)
        
        return None


def main():
    """
    主函数 - 演示如何使用
    """
    fetcher = LovartCodeFetcher()
    
    # 示例账号数据 (需要替换为实际数据)
    # 格式: email_address, client_id, refresh_token
    accounts = [
        {
            "email": "example@hotmail.com",
            "client_id": "your_client_id",
            "refresh_token": "your_refresh_token"
        }
    ]
    
    print("=" * 50)
    print("Lovart验证码获取工具")
    print("=" * 50)
    
    for account in accounts:
        print(f"\n处理账号: {account['email']}")
        
        # 刷新邮件
        result = fetcher.refresh_emails(
            email_address=account["email"],
            client_id=account["client_id"],
            refresh_token=account["refresh_token"]
        )
        
        print(f"刷新结果: {result}")
        
        # 提取验证码
        code = fetcher.get_lovart_code_from_emails(result)
        if code:
            print(f"找到验证码: {code}")
        else:
            print("未找到Lovart验证码")


if __name__ == "__main__":
    main()