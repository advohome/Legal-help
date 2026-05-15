import os
import requests
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, filters, ContextTypes, CallbackContext

# Токены
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

# Flask
app_flask = Flask(__name__)

# Состояния
DOC_TYPE, MY_NAME, OPPONENT, DATE, SITUATION, PRICE, GOAL = range(7)

CATEGORIES = [
    ["Претензия (возврат товара)", "Исковое заявление"],
    ["Ответ на претензию", "Жалоба в Роспотребнадзор"],
    ["Ходатайство в суд", "Возражение на приказ"],
    ["Взыскание неустойки", "Трудовой спор"]
]

doc_names = {
    "Претензия (возврат товара)": "претензию",
    "Исковое заявление": "исковое заявление в суд",
    "Ответ на претензию": "ответ на претензию",
    "Жалоба в Роспотребнадзор": "жалобу в Роспотребнадзор",
    "Ходатайство в суд": "ходатайство в суд",
    "Возражение на приказ": "возражение на судебный приказ",
    "Взыскание неустойки": "заявление о взыскании неустойки",
    "Трудовой спор": "заявление по трудовому спору"
}

async def start(update: Update, context: CallbackContext):
    keyboard = ReplyKeyboardMarkup(CATEGORIES, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "⚖️ Конструктор юридических документов\n\nВыберите тип документа:",
        reply_markup=keyboard
    )
    return DOC_TYPE

async def choose_type(update: Update, context: CallbackContext):
    choice = update.message.text
    if choice not in doc_names:
        await update.message.reply_text("Пожалуйста, выберите категорию из списка.")
        return DOC_TYPE
    context.user_data['doc_type'] = choice
    await update.message.reply_text("Введите ваше ФИО (или название организации):")
    return MY_NAME

async def get_my_name(update: Update, context: CallbackContext):
    context.user_data['my_name'] = update.message.text
    await update.message.reply_text("Кому адресован документ?")
    return OPPONENT

async def get_opponent(update: Update, context: CallbackContext):
    context.user_data['opponent'] = update.message.text
    await update.message.reply_text("Дата события (ДД.ММ.ГГГГ):")
    return DATE

async def get_date(update: Update, context: CallbackContext):
    context.user_data['date'] = update.message.text
    await update.message.reply_text("Опишите ситуацию:")
    return SITUATION

async def get_situation(update: Update, context: CallbackContext):
    context.user_data['situation'] = update.message.text
    await update.message.reply_text("Сумма требований (или «нет»):")
    return PRICE

async def get_price(update: Update, context: CallbackContext):
    context.user_data['price'] = update.message.text
    await update.message.reply_text("Чего хотите добиться?")
    return GOAL

async def get_goal(update: Update, context: CallbackContext):
    context.user_data['goal'] = update.message.text
    await update.message.reply_text("Составляем документ...")

    data = context.user_data
    full_context = f"""Составь {doc_names[data['doc_type']]} на основе данных:

=== ДАННЫЕ ===
- ФИО: {data['my_name']}
- Адресат: {data['opponent']}
- Дата: {data['date']}
- Ситуация: {data['situation']}
- Сумма: {data['price']}
- Цель: {data['goal']}

Используй ТОЛЬКО статьи: ЗоЗПП 18-29, ГК 309-310-330-395-1064, ГПК 35-57-131-132-166-167, КоАП 14.8, ТК 142-236-392.
Начинай сразу с текста документа. Если данных мало — добавь раздел «РИСКИ»."""

    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {DEEPSEEK_KEY}"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "Ты — юридический конструктор документов. Официально-деловой стиль. Начинай сразу с заголовка."},
                    {"role": "user", "content": full_context}
                ],
                "temperature": 0.3,
                "max_tokens": 3000
            }
        )

        if response.status_code != 200:
            raise Exception(f"Ошибка API: {response.status_code}")

        result = response.json()
        document = result["choices"][0]["message"]["content"]

        if len(document) > 4000:
            for i in range(0, len(document), 4000):
                await update.message.reply_text(document[i:i+4000])
        else:
            await update.message.reply_text(document)

        await update.message.reply_text("✅ Готово. /start — составить ещё один.")

    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")

    return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext):
    await update.message.reply_text("Отменено. /start — начать заново.")
    return ConversationHandler.END

async def help_cmd(update: Update, context: CallbackContext):
    await update.message.reply_text("/start — составить документ\n/cancel — отменить")

# Создаём приложение Telegram
telegram_app = Application.builder().token(BOT_TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        DOC_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_type)],
        MY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_my_name)],
        OPPONENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_opponent)],
        DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
        SITUATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_situation)],
        PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_price)],
        GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_goal)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

telegram_app.add_handler(conv_handler)
telegram_app.add_handler(CommandHandler("help", help_cmd))

# Webhook
@app_flask.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        telegram_app.update_queue.put_nowait(update)
    return 'OK'

@app_flask.route('/')
def home():
    return "Bot is running"

# Запуск
if __name__ == "__main__":
    if RENDER_URL:
        # Устанавливаем webhook на Render
        bot = Bot(token=BOT_TOKEN)
        bot.set_webhook(url=f"{RENDER_URL}/webhook")
        print(f"Webhook set to {RENDER_URL}/webhook")
    port = int(os.environ.get("PORT", 5000))
    app_flask.run(host="0.0.0.0", port=port)
