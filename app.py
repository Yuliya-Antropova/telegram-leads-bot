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
    CallbackQuery,
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
        "choose_lang": "🌐 Выберите язык / Choose language",
        "lang_ru": "Русский 🇷🇺",
        "lang_en": "English 🇬🇧",

        # Шаги без нумерации
        "step1": "👋 Привет! На связи помощник Nigma Interiors Design.\nДавайте оставим заявку на проект.\n\nКак вас зовут?",
        "step2": "Где вам удобнее общаться?",
        "method_tg": "✈️ Telegram",
        "method_wa": "🟢 WhatsApp",
        "method_call": "📞 Звонок",
        "step3": "✍️ Напишите ваш номер телефона или нажмите кнопку ниже «Поделиться контактом».",
        "share_contact": "📱 Поделиться контактом",
        "type_phone": "⌨️ Ввести номер вручную",
        "phone_bad": "❌ Не похоже на номер. Введите в международном формате, например +79991234567.",
        "step4": "📝 Если хотите, напишите подробности. А если нет — отправьте любой символ.",
        "step5": "🤝 Приятно познакомиться! Скоро мы свяжемся с вами указанным вами способом.",

        "lead_card_title": "<b>Новая заявка</b> 📝",
        "name": "Имя",
        "method": "Способ связи",
        "phone": "Телефон",
        "message": "Сообщение",
        "from": "От",
        "start_again": "🔁 Начать заново: /start\n🌐 Сменить язык: /lang",
    },
    "en": {
        "choose_lang": "🌐 Выберите язык / Choose language",
        "lang_ru": "Русский 🇷🇺",
        "lang_en": "English 🇬🇧",

        "step1": "👋 Hi! This is the Nigma Interiors Design assistant.\nLet’s leave a project request.\n\nWhat’s your name?",
        "step2": "Where is it more convenient to communicate?",
        "method_tg": "✈️ Telegram",
        "method_wa": "🟢 WhatsApp",
        "method_call": "📞 Phone call",
        "step3": "✍️ Type your phone number or tap the button below to share your contact.",
        "share_contact": "📱 Share contact",
        "type_phone": "⌨️ Type phone manually",
        "phone_bad": "❌ This doesn’t look like a phone number. Use international format, e.g. +447911123456.",
        "step4": "📝 If you wish, add details. If not — send any character.",
        "step5": "🤝 Nice to meet you! We’ll contact you soon via the method you selected.",

        "lead_card_title": "<b>New Lead</b> 📝",
        "name": "Name",
        "method": "Contact method",
        "phone": "Phone",
        "message": "Message",
        "from": "From",
        "start_again": "🔁 Start again: /start\n🌐 Change language: /lang",
    },
}

def t(lang: str, key: str) -> str:
    return TEXTS.get(lang, TEXTS["ru"]).get(key, key)

# ─────────── FSM ───────────
class Lead(StatesGroup):
    lang = State()
    name = State()
    method = State()
    phone = State()
    note = State()

# ───────── keyboards ─────────
def lang_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=TEXTS["ru"]["lang_ru"], callback_data="lang_ru"),
        InlineKeyboardButton(text=TEXTS["en"]["lang_en"], callback_data="lang_en"),
    ]])

def method_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "method_tg"), callback_data="method_tg"),
        InlineKeyboardButton(text=t(lang, "method_wa"), callback_data="method_wa"),
        InlineKeyboardButton(text=t(lang, "method_call"), callback_data="method_call"),
    ]])

def phone_kb(lang: str) -> ReplyKeyboardMarkup:
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
    await m.answer("🌐 Выберите язык / Choose language", reply_markup=lang_kb())

@dp.message(Command("lang"))
async def cmd_lang(m: Message, state: FSMContext):
    await state.set_state(Lead.lang)
    await m.answer("🌐 Выберите язык / Choose language", reply_markup=lang_kb())

@dp.callback_query(Lead.lang, F.data.in_({"lang_ru", "lang_en"}))
async def set_lang(cb: CallbackQuery, state: FSMContext):
    lang = "ru" if cb.data == "lang_ru" else "en"
    await state.update_data(lang=lang)
    await state.set_state(Lead.name)
    await cb.message.answer(t(lang, "step1"))
    await cb.answer()

@dp.message(Lead.lang)
async def lang_fallback(m: Message, state: FSMContext):
    await state.update_data(lang="ru")
    await state.set_state(Lead.name)
    await m.answer(t("ru", "step1"))

@dp.message(Lead.name, F.text)
async def got_name(m: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await state.update_data(name=m.text.strip())
    await state.set_state(Lead.method)
    # ✅ одна отправка: текст + inline-кнопки способа связи
    await m.answer(t(lang, "step2"), reply_markup=method_kb(lang))

@dp.callback_query(Lead.method, F.data.in_({"method_tg", "method_wa", "method_call"}))
async def set_method_cb(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    mapping = {
        "method_tg": t(lang, "method_tg"),
        "method_wa": t(lang, "method_wa"),
        "method_call": t(lang, "method_call"),
    }
    await state.update_data(method=mapping[cb.data])
    await state.set_state(Lead.phone)
    await cb.message.answer(t(lang, "step3"), reply_markup=phone_kb(lang))
    await cb.answer()

@dp.message(Lead.method, F.text)
async def set_method_text(m: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    text = m.text.lower()
    if any(x in text for x in ["telegram", "телеграм", "tg"]):
        method = t(lang, "method_tg")
    elif any(x in text for x in ["whatsapp", "ватсап", "вотсап", "вацап"]):
        method = t(lang, "method_wa")
    elif any(x in text for x in ["звонок", "call", "phone call"]):
        method = t(lang, "method_call")
    else:
        method = t(lang, "method_tg")  # дефолт
    await state.update_data(method=method)
    await state.set_state(Lead.phone)
    await m.answer(t(lang, "step3"), reply_markup=phone_kb(lang))

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
    await m.answer(t(lang, "step4"), reply_markup=ReplyKeyboardRemove())

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
    await m.answer(t(lang, "step4"), reply_markup=ReplyKeyboardRemove())

@dp.message(Lead.note, F.text)
async def finalize(m: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    note = m.text.strip()

    lead_card = (
        f"{t(lang, 'lead_card_title')}\n\n"
        f"{t(lang, 'name')}: {data.get('name')}\n"
        f"{t(lang, 'method')}: {data.get('method')}\n"
        f"{t(lang, 'phone')}: {data.get('phone')}\n"
        f"{t(lang, 'message')}: {note}\n\n"
        f"{t(lang, 'from')}: @{m.from_user.username or m.from_user.id}"
    )

    await send_to_recipients(lead_card)
    await m.answer(t(lang, "step5") + "\n\n" + t(lang, "start_again"))
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
