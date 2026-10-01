import aiohttp
import asyncio
import re
import json
import random
import os
from urllib.parse import quote
from colorama import Fore, Style, init
import telebot
import threading

init(autoreset=True)

# التوكن الخاص بالبوت
BOT_TOKEN = '8685441179:AAH4-3zfVXcJSdiT3XNBXPtRmRrgDb6-Imk'
bot = telebot.TeleBot(BOT_TOKEN)

# الآيدي الخاص بك للحماية التامة
ADMIN_USER_ID = 8727595342

# ملف حفظ الصيدات لعدم تكرارها نهائياً
DB_FILE = 'saved_channels.json'

# قاموس لتتبع عمليات البحث الجارية لكل شات
active_searches = {}

def load_saved_ids():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_new_id(cid):
    saved = load_saved_ids()
    saved.add(cid)
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(saved), f, ensure_ascii=False)
    except:
        pass

# ------------------------------------
# الحروف وقائمة البادئات الذكية الواسعة
# ------------------------------------
arabic_letters = (
    "اأإآءئؤبپتثجچحخدذرزسشصضطظعغفقكگلمنهوي"
    "ةى"
)

prefixes = [
    "", "ا", "أ", "إ", "آ", "ال", "اب", "ام", "ان",
    "با", "بي", "بو", "ت", "ث", "ج", "ح", "خ",
    "د", "ذ", "ر", "ز", "س", "ش", "ص", "ض",
    "ط", "ظ", "ع", "غ", "ف", "في", "ق", "ك",
    "ل", "لا", "لي", "م", "مي", "مو", "ن", "هـ",
    "و", "وا", "وي", "ي", "يا"
]

# ------------------------------------
# محرك البحث السحابي المتقدم
# ------------------------------------
async def search_youtube_channels(session, query):
    try:
        encoded = quote(query)
        url = f'https://www.youtube.com/results?search_query={encoded}&sp=EgIQAg%253D%253D'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept-Language': 'ar,en'
        }
        async with session.get(url, headers=headers) as r:
            if r.status != 200:
                return []
            text = await r.text()

            pattern = re.compile(
                r'"channelId"\s*:\s*"(?P<id>[^"]+)"[^\}]*?"title"\s*:\s*\{([^\}]*?)\}',
                re.DOTALL | re.IGNORECASE
            )
            matches = pattern.finditer(text)

            results = []
            for m in matches:
                cid = m.group('id')
                title_block = m.group(2)

                tmatch = re.search(r'"simpleText"\s*:\s*"([^"]+)"', title_block)
                if tmatch:
                    title = tmatch.group(1)
                else:
                    rmatch = re.search(r'"text"\s*:\s*"([^"]+)"', title_block)
                    title = rmatch.group(1) if rmatch else None

                if title:
                    results.append((title.strip(), cid))
            return results
    except:
        return []

# ------------------------------------
# محرك الصيد الذكي مع التحكم بالإيقاف
# ------------------------------------
async def run_search(target_query, chat_id):
    already_saved_ids = load_saved_ids()
    session_found_ids = set()
    sent_words_in_session = set()
    session_caught_list = []

    search_state = {"running": True, "caught": session_caught_list}
    active_searches[chat_id] = search_state

    print(Fore.CYAN + f'🚀 بدء الصيد لنهاية الكلمة: "{target_query}"' + Style.RESET_ALL)

    conn = aiohttp.TCPConnector(limit=150, limit_per_host=150, ssl=False)
    async with aiohttp.ClientSession(connector=conn) as session:
        combinations = [(letter, p) for letter in arabic_letters for p in prefixes]
        random.shuffle(combinations)

        async def process_query(letter, prefix):
            if not search_state["running"]:
                return

            query = letter + prefix + target_query
            channels = await search_youtube_channels(session, query)

            for title, cid in channels:
                if not search_state["running"]:
                    break
                if cid in already_saved_ids or cid in session_found_ids:
                    continue

                words = title.split()
                matched_word = None
                
                for w in words:
                    clean_w = re.sub(r'[^\w\s]', '', w)
                    if clean_w.lower().endswith(target_query.lower()) and clean_w.lower() != target_query.lower():
                        matched_word = w
                        break

                if matched_word:
                    if matched_word in sent_words_in_session:
                        continue

                    sent_words_in_session.add(matched_word)
                    session_found_ids.add(cid)
                    save_new_id(cid)
                    
                    formatted_msg = f"{matched_word}/قنات"
                    session_caught_list.append(formatted_msg)

                    print(Fore.GREEN + f'⚡ صيد دقيق: {formatted_msg}' + Style.RESET_ALL)
                    
                    try:
                        bot.send_message(chat_id, formatted_msg)
                    except:
                        pass
                    
                    break

        for l, p in combinations:
            if not search_state["running"]:
                break
            await process_query(l, p)

        if chat_id in active_searches:
            del active_searches[chat_id]

        print(Fore.CYAN + "📤 إرسال القائمة النهائية للنتائج..." + Style.RESET_ALL)
        try:
            if session_caught_list:
                final_text = "مفردات كاسرهم:\n\n"
                for item in session_caught_list:
                    final_text += f"`{item}`\n"
                bot.send_message(chat_id, final_text, parse_mode="Markdown")
            else:
                bot.send_message(chat_id, f"⚠️ لم يتم صيد أي نتائج جديدة للكلمة ({target_query}).")
        except Exception as e:
            print(f"Error sending final list: {e}")

def start_async_loop(target_query, chat_id):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_search(target_query, chat_id))

# ------------------------------------
# استقبال الرسائل والأوامر (مع قفل الحماية الصارم)
# ------------------------------------
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text.strip() if message.text else ""

    # قفل الحماية: تجاهل أي شخص غيرك
    if user_id != ADMIN_USER_ID:
        return

    if not text:
        return

    # الترحيب المطلوب
    if text == '/start':
        bot.reply_to(message, "هلا والله انت الأن بحمايت كاسرهم")
        return

    # إذا طلب المستخدم إيقاف البحث
    if text in ["وقف", "/stop", "ايقاف"]:
        if chat_id in active_searches:
            active_searches[chat_id]["running"] = False
            bot.reply_to(message, "طيب")
        else:
            bot.reply_to(message, "⚠️ لا توجد عملية بحث جارية حالياً لكي أوقفها.")
        return

    if chat_id in active_searches:
        active_searches[chat_id]["running"] = False

    bot.reply_to(message, "لا تخاف والكفو وياك 🫡🔥")
    
    t = threading.Thread(target=start_async_loop, args=(text, chat_id))
    t.start()

# ------------------------------------
# تشغيل البوت محلياً
# ------------------------------------
if __name__ == '__main__':
    os.system('cls' if os.name == 'nt' else 'clear')
    print(Fore.GREEN + "🤖 [البوت الكفو] يعمل الآن بأمان تام ومحمي خصيصاً لك..." + Style.RESET_ALL)
    bot.infinity_polling()
              
