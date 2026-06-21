"""
One Way Import — Telegram lead-intake bot.

A client runs /start, answers four short questions (source country, car/budget,
age, contact), and the bot:
  1) confirms to the client and links the turnkey calculator for a precise quote;
  2) forwards a clean, structured lead to the sales team chat.

Stack: python-telegram-bot v21 (async, ConversationHandler).
Config via environment variables (no secrets in code):
  BOT_TOKEN        — token from @BotFather
  MANAGER_CHAT_ID  — chat/channel id where leads are posted
  CALC_URL         — public link to the turnkey calculator
"""

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters,
)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("oneway-bot")

BOT_TOKEN = os.environ["BOT_TOKEN"]
MANAGER_CHAT_ID = os.environ.get("MANAGER_CHAT_ID")          # e.g. -1001234567890
CALC_URL = os.environ.get("CALC_URL", "https://example.github.io/auto-calculator/")

# Conversation states
COUNTRY, BUDGET, AGE, CONTACT = range(4)

COUNTRIES = {
    "kr": "🇰🇷 Корея",
    "cn": "🇨🇳 Китай",
    "eu": "🇪🇺 Европа",
    "na": "Ещё не определился",
}
AGES = {
    "new": "До 3 лет",
    "mid": "3–5 лет",
    "old": "Старше 5 лет",
    "any": "Не важно",
}


def kb(options: dict) -> InlineKeyboardMarkup:
    """Build a one-button-per-row inline keyboard from {callback: label}."""
    return InlineKeyboardMarkup([[InlineKeyboardButton(v, callback_data=k)]
                                 for k, v in options.items()])


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data.clear()
    await update.message.reply_text(
        "Привет! Подберём авто под ключ из Кореи, Китая или Европы.\n"
        "Четыре коротких вопроса — и менеджер свяжется с расчётом.\n\n"
        "Откуда смотрим машину?",
        reply_markup=kb(COUNTRIES),
    )
    return COUNTRY


async def country(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    ctx.user_data["country"] = COUNTRIES[q.data]
    await q.edit_message_text(f"Страна: {COUNTRIES[q.data]}")
    await q.message.reply_text(
        "Какую машину хочешь? Напиши модель или бюджет — "
        "например «BMW X5» или «до 8 млн ₽»."
    )
    return BUDGET


async def budget(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["budget"] = update.message.text.strip()
    await update.message.reply_text("Какой возраст авто интересует?",
                                    reply_markup=kb(AGES))
    return AGE


async def age(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    ctx.user_data["age"] = AGES[q.data]
    await q.edit_message_text(f"Возраст: {AGES[q.data]}")
    await q.message.reply_text(
        "Последнее: как тебя зовут и куда удобнее ответить?\n"
        "Телефон не обязателен — твой телеграм у меня уже есть."
    )
    return CONTACT


async def contact(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["contact"] = update.message.text.strip()
    user = update.effective_user
    d = ctx.user_data

    # 1) confirm to the client + hand off to the precise calculator
    await update.message.reply_text(
        f"Готово, {d['contact'].split()[0]}! Заявку передал менеджеру — "
        "свяжемся в течение рабочего дня.\n\n"
        f"Прикинуть точную цену под ключ можно прямо сейчас: {CALC_URL}"
    )

    # 2) push a structured lead to the sales team
    handle = f"@{user.username}" if user.username else f"id {user.id}"
    lead = (
        "🚗 *Новая заявка — One Way Import*\n"
        f"• Контакт: {d['contact']} ({handle})\n"
        f"• Страна: {d['country']}\n"
        f"• Запрос: {d['budget']}\n"
        f"• Возраст: {d['age']}"
    )
    if MANAGER_CHAT_ID:
        try:
            await ctx.bot.send_message(MANAGER_CHAT_ID, lead, parse_mode="Markdown")
        except Exception as e:                       # don't lose the client over a config issue
            log.error("Failed to deliver lead: %s", e)
    else:
        log.warning("MANAGER_CHAT_ID not set — lead only logged:\n%s", lead)

    return ConversationHandler.END


async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Ок, отменил. Напиши /start, когда будешь готов.")
    return ConversationHandler.END


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            COUNTRY: [CallbackQueryHandler(country)],
            BUDGET:  [MessageHandler(filters.TEXT & ~filters.COMMAND, budget)],
            AGE:     [CallbackQueryHandler(age)],
            CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, contact)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    log.info("Bot is up.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()