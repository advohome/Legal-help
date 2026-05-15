import os
import requests
import threading
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, filters, ContextTypes

# Токены из переменных окружения Render
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY")

# Flask-заглушка, чтобы Render видел открытый порт
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Бот работает"

@app_flask.route('/health')
def health():
    return "OK"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app_flask.run(host="0.0.0.0", port=port)

# Состояния разговора
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = ReplyKeyboardMarkup(CATEGORIES, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "⚖️ Конструктор юридических документов\n\nВыберите тип документа:",
        reply_markup=keyboard
    )
    return DOC_TYPE

async def choose_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice not in doc_names:
        await update.message.reply_text("Пожалуйста, выберите категорию из списка.")
        return DOC_TYPE
    context.user_data['doc_type'] = choice
    await update.message.reply_text("Введите ваше ФИО (или название организации):")
    return MY_NAME

async def get_my_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['my_name'] = update.message.text
    await update.message.reply_text("Кому адресован документ? (магазин, организация, суд):")
    return OPPONENT

async def get_opponent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['opponent'] = update.message.text
    await update.message.reply_text("Дата события (в формате ДД.ММ.ГГГГ):")
    return DATE

async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['date'] = update.message.text
    await update.message.reply_text("Опишите ситуацию (подробно, что произошло):")
    return SITUATION

async def get_situation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['situation'] = update.message.text
    await update.message.reply_text("Сумма требований (если есть, напишите число или «нет»):")
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['price'] = update.message.text
    await update.message.reply_text("Чего хотите добиться? (кратко: вернуть деньги, отменить приказ и т.д.):")
    return GOAL

async def get_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['goal'] = update.message.text
    await update.message.reply_text("Составляем документ... Это займёт несколько секунд.")

    data = context.user_data
    full_context = f"""Составь {doc_names[data['doc_type']]} на основе данных:

=== ДАННЫЕ ===
- ФИО: {data['my_name']}
- Адресат: {data['opponent']}
- Дата: {data['date']}
- Ситуация: {data['situation']}
- Сумма: {data['price']}
- Цель: {data['goal']}

Используй ТОЛЬКО статьи: ЗоЗПП 18-29, ГК 309-310-330-395-1064, ГПК 35-57-131-132-166-167, КоАП 14.8, ТК 142-236-392, Пленум ВС №17.
Начинай сразу с текста документа, без вступлений. Если данных мало — добавь раздел «РИСКИ»."""

    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {DEEPSEEK_KEY}"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "Ты — юридический конструктор документов для граждан РФ. Составляешь документы на основе фактов. Строго официально-деловой стиль. Начинай сразу с заголовка документа."},
                    {"role": "user", "content": full_context}
                ],
                "temperature": 0.3,
                "max_tokens": 3000
            }
        )

        if response.status_code != 200:
            raise Exception(f"Ошибка: {response.status_code}")

        result = response.json()
        document = result["choices"][0]["message"]["content"]

        if len(document) > 4000:
            for i in range(0, len(document), 4000):
                await update.message.reply_text(document[i:i+4000])
        else:
            await update.message.reply_text(document)

        await update.message.reply_text("✅ Документ готов. Хотите составить ещё один? Нажмите /start")

    except Exception as e:
        await update.message.reply_text(f"Ошибка при составлении документа: {str(e)}\nПопробуйте позже или нажмите /start.")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено. Нажмите /start чтобы начать заново.")
    return ConversationHandler.END

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Этот бот помогает составить юридические документы.\n\n"
        "Команды:\n"
        "/start — начать составление документа\n"
        "/help — эта справка\n"
        "/cancel — отменить текущий процесс"
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()

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

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", help_cmd))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    # Flask в отдельном потоке, бот в основном
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    main()
