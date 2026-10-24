"""
Evora Recruitment Bot - Telegram screening bot for Twitter VA applicants.

Setup:
    pip install "python-telegram-bot>=21.0"
    export BOT_TOKEN="123456:ABC..."        # from @BotFather
    export ADMIN_CHAT_ID="123456789"        # your own Telegram user id (ask @userinfobot)
    python evora_recruitment_bot.py

Windows (PowerShell):
    $env:BOT_TOKEN="123456:ABC..."
    $env:ADMIN_CHAT_ID="123456789"
    python evora_recruitment_bot.py
"""

import json
import logging
import os
from datetime import datetime, timezone

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
BOT_NAME = "Evora Recruitment Bot"
JOB_NAME = "Twitter VA Opportunity"

# --------------------------------------------------------------------------
# QUESTIONS - edit this list to change the form.
#
# type "text"    : free text answer
# type "number"  : numeric answer, optionally bounded (lo/hi) and with a
#                  minimum ("min") below which the applicant is rejected
# type "choice"  : buttons; "must_be" = only this answer qualifies
# "reject_label" : line shown in the rejection message
# --------------------------------------------------------------------------
QUESTIONS = [
    {
        "key": "name",
        "label": "Name",
        "text": "👤 What is your *full name*?",
        "type": "text",
    },
    {
        "key": "country",
        "label": "Country",
        "text": "🌍 Which *country* do you live in?",
        "type": "text",
    },
    {
        "key": "age",
        "label": "Age",
        "text": "🎂 How *old* are you?",
        "type": "number",
        "lo": 1,
        "hi": 99,
        "min": 18,
        "reject_label": "Age minimum 18",
    },
    {
        "key": "hours",
        "label": "Hours per day",
        "text": "⏱ How many *hours per day* can you work?",
        "type": "number",
        "lo": 0,
        "hi": 24,
        "min": 5,
        "reject_label": "Work time minimum 5 hours/day",
    },
    {
        "key": "internet",
        "label": "Internet (1-10)",
        "text": "📶 Rate your *internet connection* from 1 to 10.",
        "type": "number",
        "lo": 1,
        "hi": 10,
        "min": 3,
        "reject_label": "Internet connection minimum 3/10",
    },
    {
        "key": "english",
        "label": "English (1-10)",
        "text": "🗣 Rate your *English level* from 1 to 10.",
        "type": "number",
        "lo": 1,
        "hi": 10,
        "min": 5,
        "reject_label": "English level minimum 5/10",
    },
    {
        "key": "device",
        "label": "Device",
        "text": "📱 Can you work on *phone*, *PC*, or *both*?",
        "type": "choice",
        "options": ["Phone", "PC", "Both"],
    },
    {
        "key": "twitter_exp",
        "label": "Twitter/X experience",
        "text": "🐦 Do you have experience managing *Twitter/X accounts*?",
        "type": "choice",
        "options": ["Yes", "A little", "No"],
    },
    {
        "key": "other_job",
        "label": "Other job",
        "text": "💼 Do you have another job or studies at the same time?",
        "type": "choice",
        "options": ["Yes", "No"],
    },
    {
        "key": "timezone",
        "label": "Timezone / availability",
        "text": "🕒 What is your *timezone* and which hours are you available?",
        "type": "text",
    },
    {
        "key": "about",
        "label": "About",
        "text": "✍️ Describe yourself in a few words.",
        "type": "text",
    },
]

REJECTION_TEMPLATE = (
    "❌ *APPLICATION NOT QUALIFIED*\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    f"Thank you for your interest in our {JOB_NAME}.\n\n"
    "Unfortunately, your application doesn't meet our minimum requirements:\n\n"
    "❌ {reason}\n\n"
    "We encourage you to apply again once you meet our criteria.\n\n"
    "Good luck! 💪\n\n"
    f"- {BOT_NAME}"
)

DISCORD_LINK = "https://discord.gg/t5MU8bb7D"

ACCEPTED_TEXT = (
    "✅ *Congratulations, you passed the first step!*\n\n"
    "Your application has been submitted. 🙏\n\n"
    "👉 Join our Discord to continue:\n"
    f"{DISCORD_LINK}\n\n"
    "📅 *Recruiting calls*\n"
    "Every day, Africa/Lagos time:\n"
    "• 09:00\n"
    "• 11:00\n"
    "• 19:00\n"
    "• 21:00\n"
    "• 23:00\n\n"
    "You get a reminder in the #reminders channel on Discord before each call."
)

ASKING = 0
APPLICATIONS_FILE = "applications.jsonl"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
log = logging.getLogger("evora-bot")


def keyboard_for(question):
    if question["type"] == "choice":
        return ReplyKeyboardMarkup(
            [question["options"]], one_time_keyboard=True, resize_keyboard=True
        )
    return ReplyKeyboardRemove()


async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    idx = context.user_data["idx"]
    q = QUESTIONS[idx]
    progress = f"_({idx + 1}/{len(QUESTIONS)})_\n"
    await update.message.reply_text(
        progress + q["text"], parse_mode="Markdown", reply_markup=keyboard_for(q)
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    context.user_data["idx"] = 0
    context.user_data["answers"] = {}
    await update.message.reply_text(
        f"📋 *{JOB_NAME} - Application*\n\n"
        "This form is only for applicants aged *18 or older*.\n"
        "Type /cancel at any time to quit.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    await ask(update, context)
    return ASKING


async def reject(update: Update, context: ContextTypes.DEFAULT_TYPE, reason: str) -> int:
    await update.message.reply_text(
        REJECTION_TEMPLATE.format(reason=reason),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    user = update.effective_user
    log.info("Rejected %s (%s): %s", user.id, user.username, reason)
    context.user_data.clear()
    return ConversationHandler.END


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    idx = context.user_data.get("idx")
    if idx is None:
        await update.message.reply_text("Type /start to begin your application.")
        return ConversationHandler.END

    q = QUESTIONS[idx]
    raw = (update.message.text or "").strip()

    # ---- validation + instant rejection -------------------------------
    if q["type"] == "number":
        try:
            value = float(raw.replace(",", "."))
        except ValueError:
            await update.message.reply_text("Please answer with a number.")
            return ASKING
        if not (q["lo"] <= value <= q["hi"]):
            await update.message.reply_text(
                f"Please enter a number between {q['lo']} and {q['hi']}."
            )
            return ASKING
        value = int(value) if value.is_integer() else value
        context.user_data["answers"][q["key"]] = value
        if "min" in q and value < q["min"]:
            return await reject(update, context, q["reject_label"])

    elif q["type"] == "choice":
        match = next((o for o in q["options"] if o.lower() == raw.lower()), None)
        if match is None:
            await update.message.reply_text(
                "Please choose one of the buttons: " + " / ".join(q["options"])
            )
            return ASKING
        context.user_data["answers"][q["key"]] = match
        if "must_be" in q and match != q["must_be"]:
            return await reject(update, context, q["reject_label"])

    else:  # text
        if len(raw) < 2:
            await update.message.reply_text("Please write a bit more.")
            return ASKING
        context.user_data["answers"][q["key"]] = raw[:500]

    # ---- next question or finish --------------------------------------
    context.user_data["idx"] += 1
    if context.user_data["idx"] < len(QUESTIONS):
        await ask(update, context)
        return ASKING

    return await finish(update, context)


async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    answers = context.user_data["answers"]
    handle = f"@{user.username}" if user.username else "(no username)"

    await update.message.reply_text(
        ACCEPTED_TEXT, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove()
    )

    # Save to file
    record = {
        "date": datetime.now(timezone.utc).isoformat(),
        "telegram_id": user.id,
        "telegram_username": user.username,
        "answers": answers,
    }
    with open(APPLICATIONS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # Notify admin (plain text to avoid Markdown parsing issues with user input)
    if ADMIN_CHAT_ID:
        lines = ["🆕 NEW QUALIFIED APPLICATION", ""]
        for q in QUESTIONS:
            lines.append(f"{q['label']}: {answers.get(q['key'], '-')}")
        lines.append("")
        lines.append(f"Telegram: {handle} (id {user.id})")
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text="\n".join(lines))

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Application cancelled. Type /start to begin again.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("Set the BOT_TOKEN environment variable first.")

    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={ASKING: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer)]},
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )
    app.add_handler(conv)
    log.info("%s is running...", BOT_NAME)
    app.run_polling()


if __name__ == "__main__":
    main()
