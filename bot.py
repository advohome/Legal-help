import os
import requests
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup, Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackContext

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

def start(update: Update, context: CallbackContext):
    keyboard = ReplyKeyboardMarkup(CATEGORIES, one_time_keyboard=True, resize_keyboard=True)
    update.message.reply_text("Выберите тип документа:", reply_markup=keyboard)
    return DOC_TYPE

def choose_type(update: Update, context: CallbackContext):
    choice = update.message.text
    if choice not in doc_names:
        update.message.reply_text("Выберите из списка.")
        return DOC_TYPE
    context.user_data['doc_type'] = choice
    update.message.reply_text("Ваше ФИО:")
    return MY_NAME

def get_my_name(update: Update, context: CallbackContext):
    context.user_data['my_name'] = update.message.text
    update.message.reply_text("Кому адресован документ?")
    return OPPONENT

def get_opponent(update: Update, context: CallbackContext):
    context.user_data['opponent'] = update.message.text
    update.message.reply_text("Опишите ситуацию:")
    return SITUATION

def get_situation(update: Update, context: CallbackContext):
    context.user_data['situation'] = update.message.text
    update.message.reply_text("Составляю документ...")

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
        update.message.reply_text(doc[:4000])
        update.message.reply_text("✅ Готово. /start — ещё раз.")
    except Exception as e:
        update.message.reply_text(f"Ошибка: {e}")

    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("Отменено. /start")
    return ConversationHandler.END

# Создаём Updater (старый API, совместим с версией 20.x)
updater = Updater(token=BOT_TOKEN, use_context=True)
dp = updater.dispatcher

dp.add_handler(ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        DOC_TYPE: [MessageHandler(Filters.text & ~Filters.command, choose_type)],
        MY_NAME: [MessageHandler(Filters.text & ~Filters.command, get_my_name)],
        OPPONENT: [MessageHandler(Filters.text & ~Filters.command, get_opponent)],
        SITUATION: [MessageHandler(Filters.text & ~Filters.command, get_situation)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
))

# Webhook для Render
@app_flask.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), updater.bot)
    updater.dispatcher.process_update(update)
    return 'OK'

@app_flask.route('/')
def home():
    return 'Bot running'

if __name__ == "__main__":
    if RENDER_URL:
        bot = Bot(token=BOT_TOKEN)
        bot.set_webhook(url=f"{RENDER_URL}/webhook")
    port = int(os.environ.get("PORT", 5000))
    app_flask.run(host="0.0.0.0", port=port)
