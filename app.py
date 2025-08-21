import os
import asyncio
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

# ───────── env ─────────
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# 📌 Фиксированный chat_id группы
GROUP_CHAT_ID = -4716856992

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

# ─────── aiogram ───────
bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ─────── FSM ───────
class Lead(StatesGroup):
    name = State()
    contact_method = State()
    phone = State()
    note = State()

def contact_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться контактом", request_contact=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def method_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📞 Звонок")],
            [KeyboardButton(text="💬 Telegram")],
            [KeyboardButton(text="🟢 WhatsApp")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

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

# ─────── handlers ───────
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.set_state(Lead.name)
    await message.answer(
        "👋 Привет! На связи помощник команды <b>Nigma Interior</b>.\n\n"
        "Чтобы мы связались с Вами, напишите, как Вас зовут?"
    )

@dp.message(Lead.name, F.text)
async def got_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(Lead.contact_method)
    await message.answer(
        "📌 Уточните, как удобнее связаться?",
        reply_markup=method_kb()
    )

@dp.message(Lead.contact_method, F.text)
async def got_method(message: Message, state: FSMContext):
    await state.update_data(contact_method=message.text.strip())
    await state.set_state(Lead.phone)
    await message.answer(
        "✍️ Напишите Ваш номер телефона или нажмите кнопку ниже «Поделиться контактом».",
        reply_markup=contact_kb()
    )

@dp.message(Lead.phone, F.contact)
async def got_contact(message: Message, state: FSMContext):
    phone = normalize_phone(message.contact.phone_number)
    if not phone:
        await message.answer("Не смог распознать номер. Введите его вручную в формате +7999…")
        return
    await state.update_data(phone=phone)
    await state.set_state(Lead.note)
    await message.answer(
        "📝 Если хотите, напишите подробности. А если нет — отправьте любой символ.",
        reply_markup=ReplyKeyboardRemove()
    )

@dp.message(Lead.phone, F.text)
async def got_phone_text(message: Message, state: FSMContext):
    phone = normalize_phone(message.text.strip())
    if not phone:
        await message.answer("Не похоже на номер. Введите в международном формате, например +79991234567.")
        return
    await state.update_data(phone=phone)
    await state.set_state(Lead.note)
    await message.answer(
        "📝 Если хотите, напишите подробности. А если нет — отправьте любой символ.",
        reply_markup=ReplyKeyboardRemove()
    )

@dp.message(Lead.note, F.text)
async def finalize(message: Message, state: FSMContext):
    note = message.text.strip()
    if not note or note in {"-", "—"}:
        note = "-"

    data = await state.get_data()
    await state.clear()

    lead_card = (
        "<b>Новая заявка</b> 📝\n\n"
        f"Имя: {data.get('name')}\n"
        f"Способ связи: {data.get('contact_method')}\n"
        f"Телефон: {data.get('phone')}\n"
        f"Сообщение: {note}\n\n"
        f"От: @{message.from_user.username or message.from_user.id}"
    )

    try:
        await bot.send_message(GROUP_CHAT_ID, lead_card)
    except Exception as e:
        print("Не удалось отправить в группу:", e)

    await message.answer("🤝 Приятно познакомиться! Скоро мы свяжемся с вами указанным Вами способом.")

@dp.message(F.text)
async def fallback(message: Message, state: FSMContext):
    if await state.get_state() is None:
        await start(message, state)

# ───── entrypoint ─────
async def main():
    print("Bot started. Polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
