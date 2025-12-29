import requests
import time
import re
import random
import string
import os
import json
import hashlib

# --- သင့်ရဲ့ Referral Code ကို ဒီမှာ ထည့်ပါ ---
REFERRAL_CODE = "dW_cD9ZELyYRY3yyhK2se3zhFtB-_CwogtCedcQm762kXfI1SyXhqOSocSY9qhOCMN2buA==" 

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
            print(f"⚠️ Proxy file error: {e}")
        return []
    
    def get_next_proxy(self):
        if not self.proxies: return None
        proxy = self.proxies[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        if not proxy.startswith('http'):
            if proxy.count(':') >= 3:
                parts = proxy.split(':')
                proxy = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
            else:
                proxy = f"http://{proxy}"
        return {'http': proxy, 'https': proxy}
        
    def generate_username(self):
        consonants, vowels = 'bcdfghjklmnpqrstvwxyz', 'aeiou'
        length = random.randint(8, 12)
        return ''.join(random.choice(consonants if i % 2 == 0 else vowels) for i in range(length)).capitalize()
        
    def generate_secret_key(self, timestamp: str):
        return hashlib.sha256(f"vT*IUEGgyL{timestamp}".encode()).hexdigest()
    
    def get_mail_domain(self):
        try:
            res = requests.get(f"{self.mail_tm_base}/domains", proxies=self.get_next_proxy(), timeout=30)
            return res.json()['hydra:member'][0]['domain']
        except: return None
    
    def create_temp_email(self, username: str, domain: str):
        try:
            email = f"{username.lower()}@{domain}"
            pwd = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            res = requests.post(f"{self.mail_tm_base}/accounts", json={"address": email, "password": pwd}, proxies=self.get_next_proxy(), timeout=30)
            data = res.json()
            return {"email": data['address'], "password": pwd, "id": data['id']}
        except: return None
    
    def get_auth_token(self, email: str, password: str):
        try:
            res = requests.post(f"{self.mail_tm_base}/token", json={"address": email, "password": password}, proxies=self.get_next_proxy(), timeout=30)
            return res.json()['token']
        except: return None
    
    def extract_otp_code(self, content: str):
        match = re.search(r'\b(\d{6})\b', content)
        return match.group(1) if match else None
    
    def wait_for_verification_email(self, token: str, max_attempts: int = 30):
        print("⏳ Waiting for OTP email...")
        for _ in range(max_attempts):
            try:
                proxies = self.get_next_proxy()
                res = requests.get(f"{self.mail_tm_base}/messages", headers={"Authorization": f"Bearer {token}"}, proxies=proxies, timeout=30)
                if res.ok:
                    messages = res.json()['hydra:member']
                    for msg in messages:
                        if 'turnkey' in msg['from']['address']:
                            msg_res = requests.get(f"{self.mail_tm_base}/messages/{msg['id']}", headers={"Authorization": f"Bearer {token}"}, proxies=proxies, timeout=30)
                            if msg_res.ok:
                                otp = self.extract_otp_code(msg_res.json().get('html', [''])[0])
                                if otp: return otp
                time.sleep(3)
            except: time.sleep(3)
        return None
    
    def email_otp_auth(self, email: str, otp_id: str, otp_code: str):
        # --- အရေးကြီးသော Retry System (Pending Error အတွက်) ---
        for i in range(6): # စုစုပေါင်း ၆ ကြိမ်အထိ စမ်းမည်
            try:
                data = json.dumps({"email": email, "otp_id": otp_id, "otp_code": otp_code, "referer_id": REFERRAL_CODE})
                ts = str(int(time.time()))
                headers = self.allscale_headers.copy()
                headers.update({"Content-Type": "application/json", "Secret-Key": self.generate_secret_key(ts), "Timestamp": ts})
                
                res = requests.post(f"{self.allscale_base}/api/public/turnkey/email_otp_auth", data=data, headers=headers, proxies=self.get_next_proxy(), timeout=30)
                res_data = res.json()
                
                if res.ok and res_data.get('code') == 0:
                    return {"success": True, "data": res_data}
                
                # Server က မအားသေးရင် (Pending) ၁၀ စက္ကန့် စောင့်ပြီး ထပ်စမ်းမယ်
                if "ACTIVITY_STATUS_PENDING" in str(res_data):
                    print(f"⚠️ System is still processing (Attempt {i+1}/6). Waiting 10s...")
                    time.sleep(10)
                else:
                    return {"success": False, "error": res_data}
            except Exception as e:
                time.sleep(5)
        return {"success": False, "error": "Timeout after multiple retries"}

    def run(self, total: int):
        success = 0
        for i in range(total):
            print(f"\n🚀 Creating Account {i+1}/{total}")
            username = self.generate_username()
            domain = self.get_mail_domain()
            if not domain: continue
            
            email_info = self.create_temp_email(username, domain)
            if not email_info: 
                print("❌ Email creation failed (Rate Limit?). Waiting 60s...")
                time.sleep(60)
                continue
                
            token = self.get_auth_token(email_info['email'], email_info['password'])
            
            # Send OTP Request
            ts = str(int(time.time()))
            headers = self.allscale_headers.copy()
            headers.update({"Content-Type": "application/json", "Secret-Key": self.generate_secret_key(ts), "Timestamp": ts})
            otp_req = requests.post(f"{self.allscale_base}/api/public/turnkey/send_email_otp", 
                                  json={"email": email_info['email'], "check_user_existence": False}, 
                                  headers=headers, proxies=self.get_next_proxy())
            
            if not otp_req.ok:
                print("❌ OTP Request Failed")
                continue
                
            otp_id = otp_req.json().get('data')
            otp_code = self.wait_for_verification_email(token)
            
            if otp_code:
                print(f"🔑 OTP Code: {otp_code}")
                print("⏳ Waiting 15s for Server stability...")
                time.sleep(15) # Verify မလုပ်ခင် အရင်ဆုံး ၁၅ စက္ကန့် စောင့်မယ်
                
                result = self.email_otp_auth(email_info['email'], otp_id, otp_code)
                if result.get('success'):
                    success += 1
                    print("✅ Account Success!")
                else:
                    print(f"❌ Failed: {result.get('error')}")
            
            # Rate Limit မဖြစ်အောင် အကောင့်တစ်ခုပြီးတိုင်း ၆၀ စက္ကန့် စောင့်မယ်
            if i < total - 1:
                print("⏳ Cooling down for 60s to avoid IP Block...")
                time.sleep(60)
        
        print(f"\n✨ Done! Total Success: {success}/{total}")

if __name__ == "__main__":
    try:
        num = int(input("🔢 How many accounts?: "))
        AllScale().run(num)
    except KeyboardInterrupt: exit()
