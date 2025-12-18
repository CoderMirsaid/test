import logging
import asyncio
import aiosqlite
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Sozlamalar
API_TOKEN = "8213997249:AAGsX8EUFQYyW4zOTyRLL7NTbKZWv-UTsW0"
ADMIN_ID = 7763131749
DB_PATH = "kino_kanal.db"
MAIN_MOVIE_CHANNEL = "@UzMovies_OrgBot_Baza_1_2222"
PROMO_CHANNEL = "@UzMoviesOrg"
REQUIRED_CHANNELS = ["@UzMoviesOrg"]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# States for FSM
class MovieUpload(StatesGroup):
    waiting_video = State()
    waiting_name = State()
    waiting_language = State()
    waiting_genre = State()
    waiting_code = State()
    waiting_promo = State()

# Database initialization
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                language TEXT,
                genre TEXT,
                code TEXT UNIQUE,
                movie_message_id INTEGER,
                promo_message_id INTEGER,
                views INTEGER DEFAULT 0,
                added_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS movie_views (
                user_id INTEGER,
                movie_code TEXT,
                PRIMARY KEY (user_id, movie_code)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id INTEGER PRIMARY KEY,
                movies_viewed INTEGER DEFAULT 0,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_movie_views (
                user_id INTEGER,
                movie_code TEXT,
                viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, movie_code)
            )
        """)
        await db.commit()

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# Klaviaturalar
def main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="🎬 Kino qidirish"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="⚠️ Bot haqida"), KeyboardButton(text="📞 Aloqa")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="➕ Kino yuklash"), KeyboardButton(text="📋 Kinolar ro'yxati")],
        [KeyboardButton(text="📊 Admin statistika"), KeyboardButton(text="👥 Foydalanuvchilar")],
        [KeyboardButton(text="🔙 Orqaga")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def cancel_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(text="❌ Bekor qilish")]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

async def check_subscription(user_id: int) -> tuple[bool, list]:
    """Foydalanuvchining barcha majburiy kanallarga obuna bo'lganligini tekshirish"""
    not_subscribed = []
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ['left', 'kicked']:
                not_subscribed.append(channel)
        except Exception as e:
            logging.error(f"Error checking subscription for {channel}: {e}")
            not_subscribed.append(channel)
    
    return len(not_subscribed) == 0, not_subscribed

def subscription_keyboard(channels: list) -> InlineKeyboardMarkup:
    """Obuna bo'lish uchun tugmalar"""
    buttons = []
    for channel in channels:
        buttons.append([InlineKeyboardButton(text=f"📢 {channel}", url=f"https://t.me/{channel[1:]}")])
    buttons.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_subscription")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Start komandasi
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    # User stats qo'shish
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO user_stats(user_id) VALUES (?)", (user_id,))
        await db.commit()
    
    if is_admin(user_id):
        await message.answer(
            "👨‍💼 Xush kelibsiz Mirsaid siz bashqaruv paneliga kirdingiz nima yordam kerak!",
            reply_markup=admin_menu_keyboard()
        )
    else:
        # Obunani tekshirish
        is_subscribed, not_subscribed = await check_subscription(user_id)
        if not is_subscribed:
            await message.answer(
                "❗️Iltimos botdan foydalanish uchun asosiy kanalimizga obuna bo'ling:\n\n",
                reply_markup=subscription_keyboard(not_subscribed)
            )
        else:
            await message.answer(
                "🎬 Assalomu alaykum!\n\n"
                "📧 Kino kodini yuboring yoki quyidagi tugmalardan foydalaning:",
                reply_markup=main_menu_keyboard()
            )

# Obunani tekshirish callback
@dp.callback_query(F.data == "check_subscription")
async def check_sub_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    is_subscribed, not_subscribed = await check_subscription(user_id)
    
    if is_subscribed:
        await callback.message.delete()
        await callback.message.answer(
            "✅ Obuna tasdiqlandi! Endi botdan foydalanishingiz mumkin.\n\n"
            "📧 Kino kodini yuboring:",
            reply_markup=main_menu_keyboard()
        )
    else:
        await callback.answer(
            "❌ Siz hali barcha kanallarga obuna bo'lmadingiz!",
            show_alert=True
        )

# Kino yuklash jarayoni (Admin)
@dp.message(F.text == "➕ Kino yuklash")
async def start_movie_upload(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        "📹 Kino videosini yuboring:",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(MovieUpload.waiting_video)

@dp.message(MovieUpload.waiting_video, F.video)
async def process_video(message: types.Message, state: FSMContext):
    # Videoni asosiy kanalga yuklash
    try:
        sent_message = await bot.copy_message(
            chat_id=MAIN_MOVIE_CHANNEL,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )
        
        await state.update_data(movie_message_id=sent_message.message_id)
        await message.answer("✅ Video yuklandi!\n\n📝 Kino nomini kiriting:")
        await state.set_state(MovieUpload.waiting_name)
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}\n\nIltimos, qaytadan urinib ko'ring.")
        await state.clear()

@dp.message(MovieUpload.waiting_name, F.text)
async def process_name(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await message.answer("❌ Bekor qilindi", reply_markup=admin_menu_keyboard())
        await state.clear()
        return
    
    await state.update_data(name=message.text)
    await message.answer("🌐 Kino tilini kiriting (masalan: O'zbek, Rus, Ingliz):")
    await state.set_state(MovieUpload.waiting_language)

@dp.message(MovieUpload.waiting_language, F.text)
async def process_language(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await message.answer("❌ Bekor qilindi", reply_markup=admin_menu_keyboard())
        await state.clear()
        return
    
    await state.update_data(language=message.text)
    await message.answer("🎭 Kino janrini kiriting (masalan: Jangari, Drama, Komediya):")
    await state.set_state(MovieUpload.waiting_genre)

@dp.message(MovieUpload.waiting_genre, F.text)
async def process_genre(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await message.answer("❌ Bekor qilindi", reply_markup=admin_menu_keyboard())
        await state.clear()
        return
    
    await state.update_data(genre=message.text)
    await message.answer("📧 Kino kodini kiriting (4 ta raqam, masalan: 1234):")
    await state.set_state(MovieUpload.waiting_code)

@dp.message(MovieUpload.waiting_code, F.text)
async def process_code(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await message.answer("❌ Bekor qilindi", reply_markup=admin_menu_keyboard())
        await state.clear()
        return
    
    code = message.text.strip()
    
    # Kod tekshirish
    if not code.isdigit() or len(code) != 4:
        await message.answer("❌ Kod faqat 4 ta raqamdan iborat bo'lishi kerak!\n\nQaytadan kiriting:")
        return
    
    # Kod bazada borligini tekshirish
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT code FROM movies WHERE code=?", (code,))
        existing = await cursor.fetchone()
    
    if existing:
        await message.answer("❌ Bu kod allaqachon ishlatilgan!\n\nBoshqa kod kiriting:")
        return
    
    await state.update_data(code=code)
    
    await message.answer(
        f"✅ Kino kodi: <b>{code}</b>\n\n"
        "🎥 Endi qisqa promo videoni yuboring (15-60 sekund):",
        parse_mode="HTML"
    )
    await state.set_state(MovieUpload.waiting_promo)

@dp.message(MovieUpload.waiting_promo, F.video)
async def process_promo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    try:
        promo_text = (
            f"🎬 <b>{data['name']}</b>\n\n"
            f"🌐 Til: {data['language']}\n"
            f"🎭 Janr: {data['genre']}\n"
            f"📧 Kod: <b>{data['code']}</b>\n\n"
            f"👇 Kino ko'rish uchun:"
        )
        
        # Inline tugma
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎬 Kinoni ko'rish", url=f"https://t.me/{bot._me.username}?start={data['code']}")]
        ])
        
        sent_promo = await bot.send_video(
            chat_id=PROMO_CHANNEL,
            video=message.video.file_id,
            caption=promo_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        # Ma'lumotlarni bazaga saqlash
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO movies (name, language, genre, code, movie_message_id, promo_message_id, added_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (data['name'], data['language'], data['genre'], data['code'], 
                 data['movie_message_id'], sent_promo.message_id, message.from_user.id)
            )
            await db.commit()
        
        await message.answer(
            f"✅ Kino muvaffaqiyatli yuklandi!\n\n"
            f"🎬 Nomi: {data['name']}\n"
            f"🌐 Til: {data['language']}\n"
            f"🎭 Janr: {data['genre']}\n"
            f"📧 Kod: <b>{data['code']}</b>",
            reply_markup=admin_menu_keyboard(),
            parse_mode="HTML"
        )
        await state.clear()
        
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")
        await state.clear()

# Kino qidirish (foydalanuvchi)
@dp.message(F.text)
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    text = message.text
    
    # Admin menyulari
    if is_admin(user_id):
        if text == "🔙 Orqaga":
            await message.answer("Bosh menyu", reply_markup=main_menu_keyboard())
            return
        elif text == "📋 Kinolar ro'yxati":
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute("SELECT name, code, views FROM movies ORDER BY id DESC LIMIT 10")
                movies = await cursor.fetchall()
            
            if movies:
                text = "📋 So'nggi 10 ta kino:\n\n"
                for m in movies:
                    text += f"🎬 {m[0]}\n🔢 Kod: {m[1]} | 👁 {m[2]} ta ko'rilgan\n\n"
                await message.answer(text)
            else:
                await message.answer("Hozircha kinolar yo'q")
            return
    
    # Oddiy foydalanuvchilar uchun
    if text in ["🎬 Kino qidirish", "📊 Statistika", "⚠️ Bot haqida", "📞 Aloqa"]:
        if text == "📊 Statistika":
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute("SELECT COUNT(*) FROM movies")
                movie_count = (await cursor.fetchone())[0]
                cursor = await db.execute("SELECT movies_viewed FROM user_stats WHERE user_id=?", (user_id,))
                user_views = await cursor.fetchone()
                views = user_views[0] if user_views else 0
            
            await message.answer(
                f"📊 Statistika:\n\n"
                f"🎬 Jami kinolar: {movie_count}\n"
                f"📤 Yuklangan: {views}"
            )
        elif text == "🎬 Kino qidirish":
            await message.answer("🔢 Kino kodini kiriting:")
        elif text == "⚠️ Bot haqida":
            await message.answer(
                "🤖 Kino Bot\n"
                "Bu bot orqali siz kinolarni kod yordamida topishingiz mumkin.\n\n"
                f"📢 Kino kodlarini olish uchun kanal: {PROMO_CHANNEL}"
            )
        elif text == "📞 Aloqa":
            await message.answer("📞 Aloqa uchun: @CoderMirsaid")
        return
    
    # Kino kodi tekshirish
    if text.isdigit() and len(text) == 4:
        # Obunani tekshirish
        is_subscribed, not_subscribed = await check_subscription(user_id)
        if not is_subscribed:
            await message.answer(
                "❗️ Kino ko'rish uchun asosiy kanalimizga obuna bo'ling:",
                reply_markup=subscription_keyboard(not_subscribed)
            )
            return
        
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT name, language, genre, code, movie_message_id, views FROM movies WHERE code=?",
                (text,)
            )
            movie = await cursor.fetchone()
        
        if movie:
            # Ko'rishlar sonini oshirish
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE movies SET views = views + 1 WHERE code=?", (text,))
                await db.execute("UPDATE user_stats SET movies_viewed = movies_viewed + 1 WHERE user_id=?", (user_id,))
                await db.commit()
            
            loading_msg = await message.answer("⏳ Kino yuklanmoqda...")
            
            try:
                # Kino ma'lumotlari
                caption = (
                    f"🎬 <b>{movie[0]}</b>\n\n"
                    f"<b>🌐 Til: {movie[1]}</b>\n"
                    f"<b>🎭 Janr: {movie[2]}</b>\n"
                    f"<b>📧 Kodi: </b>{movie[3]}\n"
                    f"<b>📤 Yuklangan:</b> {movie[5] + 1}\n\n"
                    f"<b>🤖 Botimiz:</b> @UzMoviesOrgBot\n"
                    f"<b>📢 Kanalimiz:</b> @UzMoviesOrg"
                )
                
                # Videoni forward qilish
                await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=MAIN_MOVIE_CHANNEL,
                    message_id=movie[4],
                    caption=caption,
                    parse_mode="HTML"
                )
                
                await bot.delete_message(chat_id=user_id, message_id=loading_msg.message_id)
            except Exception as e:
                await message.answer(f"❌ Xatolik: {e}")
        else:
            await message.answer("❌ Bunday kino topilmadi. Kodni tekshiring!")

async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())