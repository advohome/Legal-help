import os
import requests
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

app_flask = Flask(__name__)

DOC_TYPE, MY_NAME, OPPONENT, SITUATION = range(4)

CATEGORIES = [
    ["Претензия", "Исковое заявление"],
    ["Ответ на претензию", "Жалоба в Роспотребнадзор"]
]

doc_names = {
    "Претензия": "претензию",
    "Исковое заявление": "исковое заявление",
    "Ответ на претензию": "ответ на претензию",
    "Жалоба в Роспотребнадзор": "жалобу в Роспотребнадзор"
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = ReplyKeyboardMarkup(CATEGORIES, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Выберите тип документа:", reply_markup=keyboard)
    return DOC_TYPE

async def choose_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice not in doc_names:
        await update.message.reply_text("Выберите из списка.")
        return DOC_TYPE
    context.user_data['doc_type'] = choice
    await update.message.reply_text("Ваше ФИО:")
    return MY_NAME

async def get_my_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['my_name'] = update.message.text
    await update.message.reply_text("Кому адресован документ?")
    return OPPONENT

async def get_opponent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['opponent'] = update.message.text
    await update.message.reply_text("Опишите ситуацию:")
    return SITUATION

async def get_situation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['situation'] = update.message.text
    await update.message.reply_text("Составляю документ...")

    data = context.user_data
    prompt = f"Составь {doc_names[data['doc_type']]}.\nФИО: {data['my_name']}\nКому: {data['opponent']}\nСитуация: {data['situation']}\n\nНачинай сразу с текста документа."

    try:
        r = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "Ты — конструктор документов. Официально-деловой стиль."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 2000
            }
        )
        doc = r.json()["choices"][0]["message"]["content"]
        await update.message.reply_text(doc[:4000])
        await update.message.reply_text("✅ Готово. /start — ещё раз.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено. /start")
    return ConversationHandler.END

# Приложение Telegram
telegram_app = Application.builder().token(BOT_TOKEN).build()

telegram_app.add_handler(ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        DOC_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_type)],
        MY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_my_name)],
        OPPONENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_opponent)],
        SITUATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_situation)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
))

# Webhook — принимает сообщения от Telegram
@app_flask.route('/webhook', methods=['POST'])
async def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    await telegram_app.process_update(update)
    return 'OK'

@app_flask.route('/')
def home():
    return 'Bot running'

# Запуск
if __name__ == "__main__":
    if RENDER_URL:
        bot = Bot(token=BOT_TOKEN)
        bot.set_webhook(url=f"{RENDER_URL}/webhook")
    port = int(os.environ.get("PORT", 5000))
    app_flask.run(host="0.0.0.0", port=port)
