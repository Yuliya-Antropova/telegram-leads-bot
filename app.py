import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from dotenv import load_dotenv

# Загружаем токен и ID из переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not ADMIN_ID:
    print("WARNING: ADMIN_ID is not set. Бот будет работать, но заявки не будут пересылаться.")
else:
    ADMIN_ID = int(ADMIN_ID)

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# Клавиатура с кнопкой "Поделиться контактом"
def contact_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Поделиться контактом", request_contact=True)],
            [KeyboardButton(text="Ввести номер вручную")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

WELCOME = (
    "Здравствуйте! Давайте оставим заявку.\n\n"
    "1) Введите ваше имя"
)

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(WELCOME)

# Шаг 1: Имя
@dp.message(F.text)
async def step_name(message: Message, state=None):
    if not hasattr(message.chat, "temp_data"):
        message.chat.temp_data = {}
    if "name" not in message.chat.temp_data:
        message.chat.temp_data["name"] = message.text.strip()
        await message.answer("Теперь оставьте телефон:", reply_markup=contact_keyboard())
        return

    # Если это телефон или текст после имени
    if "phone" not in message.chat.temp_data:
        phone = message.text.strip()
        if len(phone) < 5:
            await message.answer("Не похоже на номер. Попробуйте ещё раз или нажмите «Поделиться контактом».")
            return
        message.chat.temp_data["phone"] = phone
        await message.answer("Добавьте сообщение (по желанию):", reply_markup=None)
        return

    # Сообщение (опционально)
    if "note" not in message.chat.temp_data:
        message.chat.temp_data["note"] = message.text.strip()
        data = message.chat.temp_data

        # Формируем карточку
        lead = (
            "Новая заявка 📝\n\n"
            f"Имя: {data.get('name')}\n"
            f"Телефон: {data.get('phone')}\n"
            f"Сообщение: {data.get('note') or '-'}\n\n"
            f"От: @{message.from_user.username or message.from_user.id}"
        )

        if isinstance(ADMIN_ID, int):
            try:
                await bot.send_message(ADMIN_ID, lead)
            except Exception as e:
                print("Ошибка отправки админу:", e)

        await message.answer("Спасибо! Ваша заявка отправлена 🙌")
        message.chat.temp_data = {}  # очищаем
        return

# Если пользователь отправил контакт
@dp.message(F.contact)
async def handle_contact(message: Message):
    if not hasattr(message.chat, "temp_data"):
        message.chat.temp_data = {}
    message.chat.temp_data["phone"] = message.contact.phone_number
    await message.answer("Добавьте сообщение (по желанию):", reply_markup=None)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
