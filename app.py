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
from aiogram.client.default import DefaultBotProperties  # ✅ для aiogram 3.7+
from dotenv import load_dotenv


# ─────────────────── env ───────────────────
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_ENV = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

ADMIN_ID: Optional[int]
if ADMIN_ID_ENV and ADMIN_ID_ENV.strip():
    try:
        ADMIN_ID = int(ADMIN_ID_ENV)
    except ValueError:
        raise RuntimeError("ADMIN_ID must be a number (Telegram ID)")
else:
    ADMIN_ID = None

# ───────────────── aiogram ────────────────
# ✅ так правильно для aiogram >= 3.7: parse_mode задаём через default
bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


# ───────────────── FSM ────────────────────
class Lead(StatesGroup):
    name = State()
    phone = State()
    note = State()


# ──────────────── keyboards ───────────────
def contact_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Поделиться контактом", request_contact=True)],
            [KeyboardButton(text="Ввести номер вручную")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


# ───────────────── utils ──────────────────
def normalize_phone(raw: str) -> Optional[str]:
    """Привести номер к виду +7… / +… и быстро отсеять мусор."""
    if not raw:
        return None
    digits = "".join(ch for ch in raw if ch.isdigit() or ch == "+")
    if not digits:
        return None
    # 8XXXXXXXXXX -> +7XXXXXXXXXX (частый случай РФ)
    if digits.startswith("8") and len(digits) >= 11:
        digits = "+7" + digits[1:]
    if not digits.startswith("+"):
        digits = "+" + digits
    # минимально полезная длина
    if sum(ch.isdigit() for ch in digits) < 7:
        return None
    return digits


# ──────────────── handlers ────────────────
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.set_state(Lead.name)
    await message.answer(
        "Здравствуйте! Давайте оставим заявку.\n\n"
        "1) Напишите ваше <b>имя</b>."
    )


@dp.message(Lead.name, F.text)
async def got_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(Lead.phone)
    await message.answer(
        "2) Оставьте <b>телефон</b>.\n\n"
        "Можно поделиться контактом кнопкой ниже или ввести вручную.",
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
        "3) Добавьте сообщение (по желанию). Если не нужно — отправьте «-».",
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
        "3) Добавьте сообщение (по желанию). Если не нужно — отправьте «-».",
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(Lead.note, F.text)
async def finalize(message: Message, state: FSMContext):
    note = message.text.strip()
    if note in {"-", "—", "нет", "не нужно"}:
        note = "-"

    data = await state.get_data()
    await state.clear()

    lead_card = (
        "<b>Новая заявка</b> 📝\n\n"
        f"Имя: {data.get('name')}\n"
        f"Телефон: {data.get('phone')}\n"
        f"Сообщение: {note or '-'}\n\n"
        f"От: @{message.from_user.username or message.from_user.id}"
    )

    if ADMIN_ID is not None:
        try:
            await bot.send_message(ADMIN_ID, lead_card)
        except Exception as e:
            # даже если не смогли отправить админу — покажем пользователю успех
            print("Не удалось отправить админу:", e)

    await message.answer("Спасибо! Ваша заявка отправлена. Мы свяжемся с вами в ближайшее время.")


# Фоллбек: если пользователь пишет что-то вне сценария — начать заново
@dp.message(F.text)
async def fallback(message: Message, state: FSMContext):
    if await state.get_state() is None:
        await start(message, state)


# ─────────────── entrypoint ───────────────
async def main():
    print("Bot started. Polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
