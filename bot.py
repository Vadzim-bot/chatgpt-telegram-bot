import telebot
from openai import OpenAI
import psycopg2
from datetime import datetime, timedelta
import time
from config import *

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=OPENAI_KEY)

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

last_message_time = {}

def anti_spam(user_id):
    now = time.time()
    if user_id in last_message_time:
        if now - last_message_time[user_id] < 2:
            return False
    last_message_time[user_id] = now
    return True

@bot.message_handler(commands=['start'])
def start(m):
    cursor.execute(
        "INSERT INTO users(telegram_id) VALUES(%s) ON CONFLICT DO NOTHING",
        (m.from_user.id,))
    conn.commit()

    bot.send_message(
        m.chat.id,
        "🤖 Привет!\n\n"
        "10 сообщений бесплатно.\n"
        "Подписка — 7€/мес."
    )

@bot.message_handler(commands=['admin'])
def admin(m):
    if m.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE subscribed=TRUE")
    paid = cursor.fetchone()[0]

    bot.send_message(m.chat.id,
        f"👥 Пользователи: {users}\n💳 Подписок: {paid}")

@bot.message_handler(func=lambda m: True)
def chat(m):

    user_id = m.from_user.id

    if not anti_spam(user_id):
        return

    cursor.execute(
        "SELECT messages_count, subscribed FROM users WHERE telegram_id=%s",
        (user_id,))
    messages_count, subscribed = cursor.fetchone()

    if messages_count >= FREE_LIMIT and not subscribed:
        bot.send_message(m.chat.id,
            "❌ Лимит закончился.\nВведите /subscribe")
        return

    # последние 6 сообщений
    cursor.execute("""
        SELECT role, content FROM chat_history
        WHERE user_id=%s
        ORDER BY created_at DESC LIMIT 6
    """,(user_id,))
    history = cursor.fetchall()

    messages = [{"role":r,"content":c} for r,c in reversed(history)]
    messages.append({"role":"user","content":m.text})

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )

    answer = response.choices[0].message.content

    bot.send_message(m.chat.id, answer)

    cursor.execute(
        "INSERT INTO chat_history(user_id,role,content) VALUES(%s,%s,%s)",
        (user_id,"user",m.text))
    cursor.execute(
        "INSERT INTO chat_history(user_id,role,content) VALUES(%s,%s,%s)",
        (user_id,"assistant",answer))

    cursor.execute(
        "UPDATE users SET messages_count=messages_count+1 WHERE telegram_id=%s",
        (user_id,))
    conn.commit()

bot.infinity_polling()