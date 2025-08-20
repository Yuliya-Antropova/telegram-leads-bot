import os
import asyncio
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
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not ADMIN_ID:
    print("WARNING: ADMIN_ID is not set. Bot will run, but leads won't be forwarded.")
else:
    ADMIN_ID = int(ADMIN_ID)

bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# ---- FSM ----
class Lead(StatesGroup):
    name = State()
    phone = State()
    note = State()

# ---- Keyboards ----
def contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Поделиться контактом", request_contact=True)],
            [KeyboardButton(text="Ввести номер вручную")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# ---- Utils ----
def normalize_phone(raw: str) -> str | None:
    if not raw:
        return None
    # оставить цифры и +
    digits = ''.join(ch for ch in raw if ch.isdigit() or ch == '+')
    if not digits:
        return None
    # привести 8XXXXXXXXXX -> +7XXXXXXXXXX (для РФ)
    if digits.startswith('8') and len(digits) >= 11:
        digits = '+7' + digits[1:]
    if not digits.startswith('+'):
        digits = '+' + digits
    # минимальная длина
    if len(''.join(ch for ch in digits if ch.isdigit())) < 7:
        return None
    return digits

# ---- Handlers ----
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.set_state(Lead.name)
    await message.answer(
        "Здравствуйте! Давайте оставим заявку.\n\n"
        "1) Напишите ваше <b>имя</b>.",
    )

@dp.message(Lead.name, F.text)
async def got_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(Lead.phone)
    await message.answer(
        "2) Оставьте <b>телефон</b>.\n\n"
        "Можно поделиться контактом кнопкой ниже или ввести вручную.",
        reply_markup=contact_keyboard()
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
    await state.update_data(note=note)

    data = await state.get_data()
    await state.clear()

    lead_card = (
        "<b>Новая заявка</b> 📝\n\n"
        f"Имя: {data.get('name')}\n"
        f"Телефон: {data.get('phone')}\n"
        f"Сообщение: {data.get('note') or '-'}\n\n"
        f"От: @{message.from_user.username or message.from_user.id}"
    )

    # Отправляем админу, если указан
    if isinstance(ADMIN_ID, int):
        try:
            await bot.send_message(ADMIN_ID, lead_card)
        except Exception as e:
            print("Не удалось отправить админу:", e)

    await message.answer("Спасибо! Ваша заявка отправлена. Мы свяжемся с вами в ближайшее время.")

# Фоллбек: если пользователь начал писать заново
@dp.message(F.text)
async def fallback(message: Message, state: FSMContext):
    s = await state.get_state()
    if s is None:
        await start(message, state)

async def main():
    print("Bot started. Polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
