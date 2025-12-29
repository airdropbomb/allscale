import requests
import time
import re
import random
import string
import os
import json
import hashlib

REFERRAL_CODE = "dW_cD9ZELyYRY3yyhK2se3zhFtB-_CwogtCedcQm762kXfI1SyXhqOSocSY9qhOCMN2buA==" # Change it with yours.

class AllScale:
    def __init__(self):
        self.mail_tm_base = "https://api.mail.tm"
        self.allscale_base = "https://app.allscale.io"
        self.proxies = self.load_proxies()
        self.current_proxy_index = 0
        self.allscale_headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
            'origin': self.allscale_base,
            'referer': f'{self.allscale_base}/pay/register?code={REFERRAL_CODE}',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36'
        }
    
    def load_proxies(self):
        try:
            if os.path.exists('proxy.txt'):
                with open('proxy.txt', 'r') as f:
                    proxies = [line.strip() for line in f if line.strip()]
                if proxies:
                    print(f"✅ Loaded {len(proxies)} proxies from proxy.txt")
                    return proxies
        except Exception as e:
            print(f"⚠️  Error loading proxies: {e}")
        return []
    
    def get_next_proxy(self):
        if not self.proxies:
            return None
        
        proxy = self.proxies[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        
        if not proxy.startswith('http'):
            if proxy.count(':') >= 3:
                parts = proxy.split(':')
                proxy = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
            else:
                proxy = f"http://{proxy}"
        
        return {
            'http': proxy,
            'https': proxy
        }
        
    def generate_username(self):
        consonants = 'bcdfghjklmnpqrstvwxyz'
        vowels = 'aeiou'
        length = random.randint(8, 12)
        
        username = ''
        for i in range(length):
            if i % 2 == 0:
                username += random.choice(consonants)
            else:
                username += random.choice(vowels)
        
        return username.capitalize()
        
    def generate_secret_key(self, timestamp: str):
        secret_key = hashlib.sha256(
            f"vT*IUEGgyL{timestamp}".encode()
        ).hexdigest()
        return secret_key
    
    def get_mail_domain(self):
        try:
            proxies = self.get_next_proxy()
            response = requests.get(
                f"{self.mail_tm_base}/domains",
                proxies=proxies,
                timeout=30
            )
            response.raise_for_status()
            domains = response.json()['hydra:member']
            return domains[0]['domain'] if domains else None
        except Exception as e:
            print(f"❌ Error getting domain: {e}")
            return None
    
    def create_temp_email(self, username: str, domain: str):
        try:
            email = f"{username.lower()}@{domain}"
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            
            proxies = self.get_next_proxy()
            response = requests.post(
                f"{self.mail_tm_base}/accounts",
                json={
                    "address": email,
                    "password": password
                },
                proxies=proxies,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            return {
                "email": data['address'],
                "password": password,
                "id": data['id']
            }
        except Exception as e:
            print(f"❌ Error creating email: {e}")
            return None
    
    def get_auth_token(self, email: str, password: str):
        try:
            proxies = self.get_next_proxy()
            response = requests.post(
                f"{self.mail_tm_base}/token",
                json={
                    "address": email,
                    "password": password
                },
                proxies=proxies,
                timeout=30
            )
            response.raise_for_status()
            return response.json()['token']
        except Exception as e:
            print(f"❌ Error getting token: {e}")
            return None
    
    def extract_otp_code(self, content: str):
        if not content:
            return None

        match = re.search(r'\b(\d{6})\b', content)
        if match:
            return match.group(1)

        return None
    
    def wait_for_verification_email(self, token: str, max_attempts: int = 30):
        print("⏳ Wait for email verification...")
        
        for attempt in range(max_attempts):
            try:
                proxies = self.get_next_proxy()
                response = requests.get(
                    f"{self.mail_tm_base}/messages",
                    headers={"Authorization": f"Bearer {token}"},
                    proxies=proxies,
                    timeout=30
                )
                
                if response.ok:
                    messages = response.json()['hydra:member']
                    
                    for msg in messages:
                        if msg['from']['address'] == 'no-reply@mail.turnkey.com':
                            msg_response = requests.get(
                                f"{self.mail_tm_base}/messages/{msg['id']}",
                                headers={"Authorization": f"Bearer {token}"},
                                proxies=proxies,
                                timeout=30
                            )
                            
                            if msg_response.ok:
                                msg_data = msg_response.json()
                                html_content = msg_data.get('html', [msg_data.get('text', [''])])[0]

                                otp_code = self.extract_otp_code(html_content)
                                if otp_code:
                                    return otp_code
                
                time.sleep(3)
                print(f"   Attempt {attempt + 1}/{max_attempts}...")
                
            except Exception as e:
                print(f"❌ Error checking inbox: {e}")
                time.sleep(3)
        
        return None
    
    def send_email_otp(self, email: str):
        try:
            data = json.dumps({
                "email": email,
                "check_user_existence": False
            })

            headers = self.allscale_headers.copy()

            timestmap = str(int(time.time()))
            secret_key = self.generate_secret_key(timestmap)

            headers["Content-Length"] = str(len(data))
            headers["Content-Type"] = "application/json"
            headers["Secret-Key"] = secret_key
            headers["Timestamp"] = timestmap
            
            proxies = self.get_next_proxy()
            response = requests.post(
                f"{self.allscale_base}/api/public/turnkey/send_email_otp",
                data=data,
                headers=headers,
                proxies=proxies,
                timeout=30
            )
            
            data = response.json()
            
            if response.ok and data.get('code') == 0:
                return {"success": True, "data": data}
            else:
                return {"success": False, "error": data}
        except Exception as e:
            return {"success": False, "error": str(e)}
        
    def email_otp_auth(self, email: str, otp_id: str, otp_code: str):
        try:
            data = json.dumps({
                "email": email,
                "otp_id": otp_id,
                "otp_code": otp_code,
                "referer_id": REFERRAL_CODE
            })

            headers = self.allscale_headers.copy()

            timestmap = str(int(time.time()))
            secret_key = self.generate_secret_key(timestmap)

            headers["Content-Length"] = str(len(data))
            headers["Content-Type"] = "application/json"
            headers["Secret-Key"] = secret_key
            headers["Timestamp"] = timestmap
            
            proxies = self.get_next_proxy()
            response = requests.post(
                f"{self.allscale_base}/api/public/turnkey/email_otp_auth",
                data=data,
                headers=headers,
                proxies=proxies,
                timeout=30
            )
            
            data = response.json()
            
            if response.ok and data.get('code') == 0:
                return {"success": True, "data": data}
            else:
                return {"success": False, "error": data}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def create_account(self):
        print("\n" + "="*60)
        
        username = self.generate_username()
        print(f"👤 Username: {username}")
        
        domain = self.get_mail_domain()
        if not domain:
            return {"success": False, "error": "Failed to get mail domain"}
        
        email_data = self.create_temp_email(username, domain)
        if not email_data:
            return {"success": False, "error": "Failed to create email"}
        
        email = email_data['email']
        print(f"📧 Email   : {email}")
        
        mail_token = self.get_auth_token(email, email_data['password'])
        if not mail_token:
            return {"success": False, "error": "Failed to get mail token"}
        
        print("📝 Request OTP...")
        send_result = self.send_email_otp(email)
        
        if not send_result['success']:
            print(f"❌ Request OTP failed: {send_result.get('error', 'Unknown error')}")
            return send_result
        
        otp_id = send_result['data']['data']

        print(f"✅ Request OTP successful!")
        print(f"   OTP ID: {otp_id}")
        
        otp_code = self.wait_for_verification_email(mail_token)
        
        if not otp_code:
            print("❌ OTP Code not received")
            return {"success": False, "error": "Verification email timeout"}
        
        print(f"🔑 OTP Code: {otp_code}")
        
        print("✉️  Verifying OTP...")
        auth_result = self.email_otp_auth(email, otp_id, otp_code)
        
        if not auth_result['success']:
            print(f"❌ OTP verification failed: {auth_result.get('error', 'Unknown error')}")
            return auth_result
        
        print(f"✅ OTP verified successfully")
        print(f"✅ Done!")
        
        return {
            "success": True,
            "username": username,
            "email": email,
            "verified": True
        }
    
    def run(self, total_accounts: int = 1, delay_between: int = 5):
        print(f"🎯 Referral Code: {REFERRAL_CODE}")
        print(f"🔢 Total Accounts: {total_accounts}")
        print(f"⏱️  Delay Between: {delay_between}s")
        
        success_count = 0
        failed_count = 0
        
        for i in range(total_accounts):
            print(f"\n🚀 Creating account {i + 1}/{total_accounts}...")
            
            result = self.create_account()
            
            if result['success']:
                success_count += 1
                print(f"✅ Account {i + 1} created successfully!")
            else:
                failed_count += 1
                print(f"❌ Account {i + 1} failed: {result.get('error', 'Unknown error')}")
            
            if i < total_accounts - 1:
                print(f"\n⏳ Waiting {delay_between} seconds before next account...")
                time.sleep(delay_between)
        
        print("\n" + "="*60)
        print(f"""
╔══════════════════════════════════════════════════════════╗
║                    SUMMARY                               ║
╠══════════════════════════════════════════════════════════╣
║  ✅ Success: {success_count:<2}                                        ║
║  ❌ Failed:  {failed_count:<2}                                        ║
║  📊 Total:   {total_accounts:<2}                                        ║
╚══════════════════════════════════════════════════════════╝
        """)


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════╗
║          AUTO REFERRAL AllScale Pay - VONSSY              ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    try:
        TOTAL_ACCOUNTS = int(input("🔢 Number of accounts you want to create: ").strip())
        if TOTAL_ACCOUNTS < 1:
            print("❌ Minimum number of accounts is 1!")
            exit(1)
    except ValueError:
        print("❌ Enter a valid number!")
        exit(1)
    
    DELAY_BETWEEN = 5
    
    bot = AllScale()

    bot.run(total_accounts=TOTAL_ACCOUNTS, delay_between=DELAY_BETWEEN)
