from flask import Flask, request
import stripe
import psycopg2
from datetime import datetime, timedelta
from config import *

app = Flask(__name__)

stripe.api_key = STRIPE_API_KEY
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

@app.route("/")
def home():
    return "BOT RUNNING"

@app.route("/webhook", methods=["POST"])
def webhook():

    payload = request.data
    sig = request.headers.get("Stripe-Signature")

    event = stripe.Webhook.construct_event(
        payload, sig, STRIPE_WEBHOOK_SECRET)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        telegram_id = int(session["client_reference_id"])

        cursor.execute(
            "UPDATE users SET subscribed=TRUE WHERE telegram_id=%s",
            (telegram_id,))
        conn.commit()

    # очистка старых сообщений (30 дней)
    cursor.execute(
        "DELETE FROM chat_history WHERE created_at < NOW() - INTERVAL '30 days'")
    conn.commit()

    return "",200