import asyncio
import aiohttp
import aiofiles
import os
import random
from datetime import datetime

# نفس الإعدادات من bot.py
CHECKER_API_URL = 'http://108.165.12.183:8081/'
SITES_FILE = 'sites.txt'
PROXY_FILE = 'proxy.txt'

async def test_proxy(proxy):
    """اختبار بروكسي واحد"""
    test_card = "5154623245618097|03|2032|156"
    test_site = "https://cleetusm.myshopify.com"
    try:
        params = {'cc': test_card, 'url': test_site, 'proxy': proxy}
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(CHECKER_API_URL, params=params) as resp:
                raw = await resp.json(content_type=None)
        response = raw.get('Response', '').lower()
        if 'proxy dead' in response or 'invalid proxy' in response:
            return False
        return True
    except:
        return False

async def test_site(site, proxy):
    """اختبار موقع واحد"""
    test_card = "5154623245618097|03|2032|156"
    try:
        params = {'cc': test_card, 'url': site, 'proxy': proxy}
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(CHECKER_API_URL, params=params) as resp:
                raw = await resp.json(content_type=None)
        response = raw.get('Response', '').lower()
        if 'timeout' in response or 'error' in response or 'cloudflare' in response:
            return False
        return True
    except:
        return False

async def clean_dead_proxies():
    """تنظيف البروكسيات الميتة"""
    print(f"[{datetime.now()}] 🧹 بدء تنظيف البروكسيات...")
    
    if not os.path.exists(PROXY_FILE):
        return
    
    async with aiofiles.open(PROXY_FILE, 'r') as f:
        proxies = [p.strip() for p in await f.readlines() if p.strip()]
    
    if not proxies:
        return
    
    alive = []
    dead = []
    
    for proxy in proxies:
        if await test_proxy(proxy):
            alive.append(proxy)
        else:
            dead.append(proxy)
        print(f"  {proxy[:50]}... {'✅' if proxy in alive else '❌'}")
    
    async with aiofiles.open(PROXY_FILE, 'w') as f:
        for proxy in alive:
            await f.write(f"{proxy}\n")
    
    print(f"[{datetime.now()}] ✅ تم: {len(alive)} شغال, {len(dead)} ميت (تم حذفهم)")
    return len(alive), len(dead)

async def clean_dead_sites():
    """تنظيف المواقع الميتة"""
    print(f"[{datetime.now()}] 🧹 بدء تنظيف المواقع...")
    
    if not os.path.exists(SITES_FILE):
        return
    
    # جلب بروكسي شغال للاختبار
    proxies = []
    if os.path.exists(PROXY_FILE):
        async with aiofiles.open(PROXY_FILE, 'r') as f:
            proxies = [p.strip() for p in await f.readlines() if p.strip()]
    
    if not proxies:
        print("⚠️ لا يوجد بروكسيات شغالة لإختبار المواقع")
        return
    
    async with aiofiles.open(SITES_FILE, 'r') as f:
        sites = [s.strip() for s in await f.readlines() if s.strip()]
    
    if not sites:
        return
    
    alive = []
    dead = []
    
    for site in sites:
        proxy = random.choice(proxies)
        if await test_site(site, proxy):
            alive.append(site)
        else:
            dead.append(site)
        print(f"  {site}... {'✅' if site in alive else '❌'}")
    
    async with aiofiles.open(SITES_FILE, 'w') as f:
        for site in alive:
            await f.write(f"{site}\n")
    
    print(f"[{datetime.now()}] ✅ تم: {len(alive)} شغال, {len(dead)} ميت (تم حذفهم)")
    return len(alive), len(dead)

async def add_free_proxies():
    """إضافة بروكسيات مجانية من API خارجي"""
    print(f"[{datetime.now()}] 🔄 جلب بروكسيات جديدة...")
    
    # مصادر بروكسيات مجانية
    proxy_sources = [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
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
                        if proxy and ':' in proxy:
                            new_proxies.append(proxy)
        except:
            pass
    
    # تحميل البروكسيات الموجودة
    existing = []
    if os.path.exists(PROXY_FILE):
        async with aiofiles.open(PROXY_FILE, 'r') as f:
            existing = [p.strip() for p in await f.readlines() if p.strip()]
    
    # إضافة البروكسيات الجديدة
    added = 0
    async with aiofiles.open(PROXY_FILE, 'a') as f:
        for proxy in new_proxies[:50]:  # حد أقصى 50 جديد
            if proxy not in existing:
                await f.write(f"{proxy}\n")
                added += 1
    
    print(f"[{datetime.now()}] ✅ تم إضافة {added} بروكسي جديد")
    return added

async def run_full_cleanup():
    """تنظيف كامل"""
    print("=" * 50)
    print(f"🚀 بدء الصيانة التلقائية - {datetime.now()}")
    print("=" * 50)
    
    # 1. تنظيف البروكسيات الميتة
    await clean_dead_proxies()
    
    # 2. تنظيف المواقع الميتة
    await clean_dead_sites()
    
    print("=" * 50)
    print(f"🏁 انتهت الصيانة - {datetime.now()}")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(run_full_cleanup())