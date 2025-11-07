import os
import asyncio
from typing import Optional, List, Dict

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

# ───────────── env ─────────────
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

def parse_ids(raw: str) -> List[int]:
    ids: List[int] = []
    for part in raw.split(","):
        p = part.strip()
        if not p:
            continue
        ids.append(int(p))
    return ids

recipients_raw = (os.getenv("RECIPIENT_IDS") or "").strip()
admin_raw = (os.getenv("ADMIN_ID") or "").strip()
RECIPIENT_IDS: List[int] = parse_ids(recipients_raw) if recipients_raw else (parse_ids(admin_raw) if admin_raw else [])

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not RECIPIENT_IDS:
    print("⚠️ WARNING: No recipients configured. Set RECIPIENT_IDS or ADMIN_ID in Railway Variables.")

# ───────── aiogram base ─────────
bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ─────────── i18n texts ─────────
TEXTS: Dict[str, Dict[str, str]] = {
    "ru": {
        "choose_lang": "Выберите язык / Choose language 🌐",
        "lang_ru": "Русский 🇷🇺",
        "lang_en": "English 🇬🇧",
        "hello": "👋 Здравствуйте! Давайте оставим заявку.\n\n1️⃣ Напишите ваше <b>имя</b>.",
        "ask_phone": "2️⃣ Оставьте <b>телефон</b>.\n\nМожно поделиться контактом кнопкой ниже 📱 или ввести вручную.",
        "share_contact": "📱 Поделиться контактом",
        "type_phone": "⌨️ Ввести номер вручную",
        "phone_bad": "❌ Не похоже на номер. Введите в международном формате, например +79991234567.",
        "ask_note": "3️⃣ Добавьте сообщение (по желанию) 💬.\nЕсли не нужно — отправьте «-».",
        "lead_sent": "✅ Спасибо! Ваша заявка отправлена.\nМы свяжемся с вами в ближайшее время.",
        "lead_card_title": "<b>Новая заявка</b> 📝",
        "name": "Имя",
        "phone": "Телефон",
        "message": "Сообщение",
        "from": "От",
        "start_again": "🔁 Начать заново: /start\n🌐 Сменить язык: /lang",
        "lang_set_ru": "Язык установлен: Русский 🇷🇺",
        "lang_set_en": "Language set: English 🇬🇧",
    },
    "en": {
        "choose_lang": "Выберите язык / Choose language 🌐",
        "lang_ru": "Русский 🇷🇺",
        "lang_en": "English 🇬🇧",
        "hello": "👋 Hello! Let’s leave a request.\n\n1️⃣ Please type your <b>name</b>.",
        "ask_phone": "2️⃣ Please share your <b>phone number</b>.\n\nYou can tap the button below 📱 or type it manually.",
        "share_contact": "📱 Share phone",
        "type_phone": "⌨️ Type phone manually",
        "phone_bad": "❌ This doesn’t look like a phone number. Use international format, e.g. +447911123456.",
        "ask_note": "3️⃣ Add a message (optional) 💬.\nSend “-” to skip.",
        "lead_sent": "✅ Thanks! Your request has been sent.\nWe will contact you shortly.",
        "lead_card_title": "<b>New Lead</b> 📝",
        "name": "Name",
        "phone": "Phone",
        "message": "Message",
        "from": "From",
        "start_again": "🔁 Start again: /start\n🌐 Change language: /lang",
        "lang_set_ru": "Язык установлен: Русский 🇷🇺",
        "lang_set_en": "Language set: English 🇬🇧",
    },
}

def t(lang: str, key: str) -> str:
    return TEXTS.get(lang, TEXTS["ru"]).get(key, key)

# ─────────── FSM ───────────
class Lead(StatesGroup):
    lang = State()
    name = State()
    phone = State()
    note = State()

# ───────── keyboards ─────────
def lang_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=TEXTS["ru"]["lang_ru"], callback_data="lang_ru"),
        InlineKeyboardButton(text=TEXTS["en"]["lang_en"], callback_data="lang_en"),
    ]])

def contact_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "share_contact"), request_contact=True)],
            [KeyboardButton(text=t(lang, "type_phone"))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# ───────── utils ─────────
def normalize_phone(raw: str) -> Optional[str]:
    if not raw:
        return None
    digits = "".join(ch for ch in raw if ch.isdigit() or ch == "+")
    if not digits:
        return None
    if digits.startswith("8") and len(digits) >= 11:
        digits = "+7" + digits[1:]
    if not digits.startswith("+"):
        digits = "+" + digits
    if sum(ch.isdigit() for ch in digits) < 7:
        return None
    return digits

async def send_to_recipients(text: str):
    for chat_id in RECIPIENT_IDS:
        try:
            await bot.send_message(chat_id, text)
        except Exception as e:
            print(f"Send to {chat_id} failed: {e}")

# ───────── handlers ─────────
@dp.message(CommandStart())
async def cmd_start(m: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Lead.lang)
    await m.answer(t("ru", "choose_lang"))
    await m.answer(t("en", "choose_lang"), reply_markup=lang_kb())

@dp.message(Command("lang"))
async def cmd_lang(m: Message, state: FSMContext):
    await state.set_state(Lead.lang)
    await m.answer(t("ru", "choose_lang"))
    await m.answer(t("en", "choose_lang"), reply_markup=lang_kb())

@dp.callback_query(Lead.lang, F.data.in_({"lang_ru", "lang_en"}))
async def set_lang(cb, state: FSMContext):
    lang = "ru" if cb.data == "lang_ru" else "en"
    await state.update_data(lang=lang)
    await state.set_state(Lead.name)
    await cb.message.answer(t(lang, "hello"))
    await cb.answer(t(lang, "lang_set_ru") if lang == "ru" else t(lang, "lang_set_en"))

@dp.message(Lead.lang)
async def lang_fallback(m: Message, state: FSMContext):
    await state.update_data(lang="ru")
    await state.set_state(Lead.name)
    await m.answer(t("ru", "hello"))

@dp.message(Lead.name, F.text)
async def got_name(m: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await state.update_data(name=m.text.strip())
    await state.set_state(Lead.phone)
    await m.answer(t(lang, "ask_phone"), reply_markup=contact_kb(lang))

@dp.message(Lead.phone, F.contact)
async def got_contact(m: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    phone = normalize_phone(m.contact.phone_number)
    if not phone:
        await m.answer(t(lang, "phone_bad"))
        return
    await state.update_data(phone=phone)
    await state.set_state(Lead.note)
    await m.answer(t(lang, "ask_note"), reply_markup=ReplyKeyboardRemove())

@dp.message(Lead.phone, F.text)
async def got_phone_text(m: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    phone = normalize_phone(m.text.strip())
    if not phone:
        await m.answer(t(lang, "phone_bad"))
        return
    await state.update_data(phone=phone)
    await state.set_state(Lead.note)
    await m.answer(t(lang, "ask_note"), reply_markup=ReplyKeyboardRemove())

@dp.message(Lead.note, F.text)
async def finalize(m: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    note = m.text.strip()
    if note in {"-", "—", "нет", "не нужно"}:
        note = "-"

    lead_card = (
        f"{t(lang, 'lead_card_title')}\n\n"
        f"{t(lang, 'name')}: {data.get('name')}\n"
        f"{t(lang, 'phone')}: {data.get('phone')}\n"
        f"{t(lang, 'message')}: {note or '-'}\n\n"
        f"{t(lang, 'from')}: @{m.from_user.username or m.from_user.id}"
    )

    await send_to_recipients(lead_card)
    await m.answer(t(lang, "lead_sent") + "\n\n" + t(lang, "start_again"))
    await state.clear()

@dp.message(F.text)
async def fallback(m: Message, state: FSMContext):
    if await state.get_state() is None:
        await cmd_start(m, state)

# ───────── entrypoint ─────────
async def main():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print("Webhook deleted (if existed).")
    except Exception as e:
        print("delete_webhook error:", e)

    print("Bot started. Polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
