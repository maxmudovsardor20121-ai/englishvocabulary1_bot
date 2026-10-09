import asyncio
import io
import random
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from gtts import gTTS
from words import WORDS_DATABASE

BOT_TOKEN = "8808067954:AAHp1MlZoZJNjbxbYzu_bcktLxcdHNBDT3E"
ADMIN_ID = 8753030115  # O'zingizning Telegram ID'ingizni yozing

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            total_tests INTEGER DEFAULT 0,
            correct_answers INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

def db_add_user(user_id, full_name):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, full_name) VALUES (?, ?)", (user_id, full_name))
    cursor.execute("UPDATE users SET full_name = ? WHERE user_id = ?", (full_name, user_id))
    conn.commit()
    conn.close()

def db_update_stats(user_id, correct):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users 
        SET total_tests = total_tests + 1,
            correct_answers = correct_answers + ?
        WHERE user_id = ?
    """, (correct, user_id))
    conn.commit()
    conn.close()

def db_get_user_stats(user_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, total_tests, correct_answers FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def db_get_leaderboard():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, correct_answers FROM users ORDER BY correct_answers DESC LIMIT 10")
    rows = cursor.fetchall()
    conn.close()
    return rows

def db_get_all_users():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

class Registration(StatesGroup):
    waiting_for_name = State()
    main_menu = State()
    words_viewing = State()
    quiz_active = State()
    broadcast_waiting = State()

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Testlar")],
            [KeyboardButton(text="👤 Profil"), KeyboardButton(text="🏆 Reyting")],
            [KeyboardButton(text="🔊 Talaffuz")]
        ],
        resize_keyboard=True
    )

def get_levels_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="A1"), KeyboardButton(text="A2")],
            [KeyboardButton(text="B1"), KeyboardButton(text="B2")],
            [KeyboardButton(text="C1"), KeyboardButton(text="C2")],
            [KeyboardButton(text="⬅️ Asosiy menyu")]
        ],
        resize_keyboard=True
    )

def generate_audio(text):
    tts = gTTS(text=text, lang="en")
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return fp.read()

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("Salom! Iltimos, ism va familiyangizni kiriting:")
    await state.set_state(Registration.waiting_for_name)

@dp.message(Registration.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    user_name = message.text.strip()
    db_add_user(message.from_user.id, user_name)
    await state.update_data(full_name=user_name)
    await message.answer(f"Xush kelibsiz, {user_name}!", reply_markup=get_main_keyboard())
    await state.set_state(Registration.main_menu)

@dp.message(Registration.main_menu, F.text == "⬅️️ Asosiy menyu")
async def back_to_main_menu(message: types.Message, state: FSMContext):
    await message.answer("Asosiy menyu:", reply_markup=get_main_keyboard())

@dp.message(Registration.main_menu, F.text == "📚 Testlar")
async def choose_level_menu(message: types.Message):
    await message.answer("Darajani tanlang:", reply_markup=get_levels_keyboard())

@dp.message(Registration.main_menu, F.text == "👤 Profil")
async def show_profile(message: types.Message):
    stats = db_get_user_stats(message.from_user.id)
    if stats:
        name, tests, correct = stats
        text = f"👤 Ism: {name}\nTestlar: {tests}\nTo'g'ri javoblar: {correct}"
    else:
        text = "Profil topilmadi. /start bosing."
    await message.answer(text)

@dp.message(Registration.main_menu, F.text == "🏆 Reyting")
async def show_leaderboard(message: types.Message):
    leaders = db_get_leaderboard()
    if not leaders:
        await message.answer("Reyting bo'sh.")
        return
    text = "🏆 Top o'quvchilar:\n\n"
    for idx, (name, score) in enumerate(leaders, 1):
        text += f"{idx}. {name} — {score} ball\n"
    await message.answer(text)

@dp.message(Registration.main_menu, F.text == "🔊 Talaffuz")
async def audio_mode_info(message: types.Message):
    await message.answer("Inglizcha so'z yuboring, talaffuzini tashlab beraman!")

@dp.message(Registration.main_menu, F.text.in_(["A1", "A2", "B1", "B2", "C1", "C2"]))
async def process_level(message: types.Message, state: FSMContext):
    selected_level = message.text
    words_pool = WORDS_DATABASE.get(selected_level, [])
    chosen_words = random.sample(words_pool, min(len(words_pool), 20))
    await state.update_data(current_level=selected_level, current_words=chosen_words)

    words_text = f"📚 {selected_level} daraja so'zlari:\n\n"
    for idx, w in enumerate(chosen_words, 1):
        words_text += f"{idx}. {w['en']} — {w['ru']}\n"

    inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Testni boshlash", callback_data="start_quiz")],
            [InlineKeyboardButton(text="🔊 O'qib berish", callback_data="voice_words_list")],
            [InlineKeyboardButton(text="⬅️ Ortga", callback_data="back_to_levels")]
        ]
    )
    await message.answer(words_text, reply_markup=ReplyKeyboardRemove())
    await message.answer("Tanlang:", reply_markup=inline_kb)
    await state.set_state(Registration.words_viewing)

@dp.callback_query(Registration.words_viewing, F.data == "voice_words_list")
async def voice_list_handler(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    words = data.get("current_words", [])
    text_to_speak = ", ".join([w["en"] for w in words])
    audio_bytes = generate_audio(text_to_speak)
    voice_file = BufferedInputFile(audio_bytes, filename="words.mp3")
    await callback.message.answer_voice(voice_file)
    await callback.answer()

@dp.callback_query(Registration.words_viewing, F.data == "back_to_levels")
async def back_to_levels_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer("Darajani tanlang:", reply_markup=get_levels_keyboard())
    await state.set_state(Registration.main_menu)

@dp.callback_query(Registration.words_viewing, F.data == "start_quiz")
async def start_quiz_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    data = await state.get_data()
    words = data.get("current_words", [])
    await state.update_data(quiz_index=0, correct_count=0)
    await state.set_state(Registration.quiz_active)
    await send_next_quiz(callback.from_user.id, state, words, 0)

@dp.poll_answer(Registration.quiz_active)
async def handle_poll_answer(poll_answer: types.PollAnswer, state: FSMContext):
    data = await state.get_data()
    words = data.get("current_words", [])
    index = data.get("quiz_index", 0)
    correct_count = data.get("correct_count", 0)
    current_options = data.get("current_options", [])

    if poll_answer.option_ids and current_options:
        user_choice_id = poll_answer.option_ids[0]
        selected_text = current_options[user_choice_id]
        current_item = words[index]
        if selected_text == current_item["ru"]:
            correct_count += 1
            await state.update_data(correct_count=correct_count)

    await state.update_data(quiz_index=index + 1)
    await send_next_quiz(poll_answer.user.id, state, words, index + 1)

async def send_next_quiz(user_id, state, words, index):
    data = await state.get_data()
    if index >= len(words):
        correct = data.get("correct_count", 0)
        total = len(words)
        user_name = data.get("full_name", "O'quvchi")
        level = data.get("current_level", "A1")
        db_update_stats(user_id, correct)
        
        await bot.send_message(
            user_id,
            f"🎉 Test yakunlandi!\nIsm: {user_name}\nDaraja: {level}\nTo'g'ri: {correct} / {total}",
            reply_markup=get_main_keyboard()
        )
        try:
            await bot.send_message(ADMIN_ID, f"📥 Yangi natija:\nIsm: {user_name}\nDaraja: {level}\nNatija: {correct}/{total}")
        except Exception:
            pass
        await state.set_state(Registration.main_menu)
        return

    item = words[index]
    options = item["options"].copy()
    random.shuffle(options)
    correct_option_id = options.index(item["ru"])
    await state.update_data(current_options=options)

    await bot.send_poll(
        chat_id=user_id,
        question=f"[{index+1}/{len(words)}] '{item['en']}' tarjimasini toping:",
        options=options,
        type="quiz",
        correct_option_id=correct_option_id,
        is_anonymous=False
    )

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    users = db_get_all_users()
    await message.answer(f"Foydalanuvchilar soni: {len(users)}\n/broadcast - xabar yuborish")

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Xabar matnini kiriting:")
    await state.set_state(Registration.broadcast_waiting)

@dp.message(Registration.broadcast_waiting)
async def process_broadcast(message: types.Message, state: FSMContext):
    users = db_get_all_users()
    for uid in users:
        try:
            await bot.send_message(uid, message.text)
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await message.answer("Xabar yuborildi!")
    await state.set_state(Registration.main_menu)

@dp.message(Registration.main_menu)
async def auto_voice_handler(message: types.Message):
    text = message.text.strip()
    if text.isascii() and len(text) < 100:
        try:
            audio_bytes = generate_audio(text)
            voice_file = BufferedInputFile(audio_bytes, filename="voice.mp3")
            await message.answer_voice(voice_file)
        except Exception as e:
            await message.answer(f"Xatolik: {e}")
    else:
        await message.answer("Menyudan foydalaning:", reply_markup=get_main_keyboard())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
