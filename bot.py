import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ========== НАСТРОЙКИ ==========
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8703171624:AAEitrWlaMkZBfNp7SxHc-yId3PjzX1yhbI")
ADMIN_ID = 325845619

    DECORS = {
    "ec1007": {"name": "EC1007 Дуб Паркетный", "file": "EC1007.jpg"},
    "ec1012": {"name": "EC1012 Дуб Метик", "file": "EC1012.jpg"},
    "ec1055": {"name": "EC1055 Дуб Бардолино", "file": "EC1055.jpg"},
    "ec1056": {"name": "EC1056 Дуб Бардолино 2", "file": "EC1056.jpg"},
}

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

user_sessions = {}
pending_requests = {}

# ========== КЛИЕНТ ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Отправьте фото комнаты, затем выберите декор ламината.")

async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    photo = await update.message.photo[-1].get_file()
    room_path = f"temp_room_{user_id}.jpg"
    await photo.download_to_drive(room_path)
    user_sessions[user_id] = {"room": room_path}

    keyboard = [[InlineKeyboardButton(v["name"], callback_data=k)] for k, v in DECORS.items()]
    await update.message.reply_text("✅ Фото получено. Выберите декор:", reply_markup=InlineKeyboardMarkup(keyboard))

async def select_decor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    client_id = update.effective_user.id

    if client_id not in user_sessions:
        await query.edit_message_text("❌ Сессия истекла. Отправьте фото заново.")
        return

    decor = DECORS[query.data]
    room_path = user_sessions[client_id]["room"]

    await query.edit_message_text(f"⏳ Вы выбрали: {decor['name']}. Ожидайте, менеджер готовит визуализацию...")

    # Отправляем админу фото комнаты
    with open(room_path, "rb") as f:
        msg_room = await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=f,
            caption=f"🆕 Заявка от клиента ID: {client_id}\nДекор: {decor['name']}\n\nОтправьте сюда готовый результат — я перешлю клиенту."
        )

    # Отправляем админу образец + промпт на русском
    prompt = (
        f'Заменить напольное покрытие в комнате на ламинат, который выглядит точно как образец '
        f'{decor["name"]}. Сохранить всю мебель, освещение, стены и общую композицию комнаты без изменений. '
        f'Все должно быть максимально реалистично, сохранить перспективу и ракурс камеры.'
    )
    with open(decor["file"], "rb") as f:
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=f,
            caption=f"📌 Образец: {decor['name']}\n\n📋 Промпт для Gemini (скопируйте):\n\n{prompt}"
        )

    pending_requests[msg_room.message_id] = {
        "client_id": client_id,
        "decor_name": decor["name"]
    }

# ========== АДМИН ==========

async def admin_result_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if update.message.reply_to_message and update.message.reply_to_message.message_id in pending_requests:
        req = pending_requests.pop(update.message.reply_to_message.message_id)
    else:
        if not pending_requests:
            await update.message.reply_text("❌ Нет активных заявок.")
            return
        last_id = list(pending_requests.keys())[-1]
        req = pending_requests.pop(last_id)

    client_id = req["client_id"]
    decor_name = req["decor_name"]

    await context.bot.send_photo(
        chat_id=client_id,
        photo=update.message.photo[-1].file_id,
        caption=f"✅ Готово! Вот визуализация с декором: {decor_name}\n\nХочешь заменить декор? Выбери другой"
    )
    await update.message.reply_text("✅ Результат отправлен клиенту!")

# ========== ЗАПУСК ==========

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO & (~filters.User(ADMIN_ID)), receive_photo))
    app.add_handler(CallbackQueryHandler(select_decor))
    app.add_handler(MessageHandler(filters.PHOTO & filters.User(ADMIN_ID), admin_result_photo))

    print("🤖 Бот запущен! Нажмите Ctrl+C для остановки.")
    app.run_polling()

if __name__ == "__main__":
    main()
