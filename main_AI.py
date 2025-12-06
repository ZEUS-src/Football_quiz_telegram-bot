import pandas as pd
import re
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
import asyncio
from putergenai import PuterClient
import os
from dotenv import load_dotenv
load_dotenv()
# -------------------
# --- CONFIG ---
# -------------------

BOT_TOKEN = os.getenv('BOT_TOKEN')
USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')

bot = AsyncTeleBot(BOT_TOKEN)

# User session data
user_data = {}

# -------------------
# --- PUTER CLIENT ---
# -------------------
puter_client = PuterClient()
puter_logged_in = False

async def get_question(question_type="Hard", language="ar"):
    global puter_logged_in, puter_client

    if not puter_logged_in:
        await puter_client.login(USERNAME, PASSWORD)
        puter_logged_in = True

    result = await puter_client.ai_chat(
        prompt=(
            "Give me random question about football(soocer) and answer in the following format:\n"
            "Question: <question>\n"
            "Answer: ||<answer>||\n"
            f"The question should be of {question_type} difficulty and in {language} language."
        ),
        options={"model": "gpt-4o", "stream": False}
    )

    return result["response"]["result"]["message"]["content"]

# -------------------
# --- HELPERS ---
# -------------------
def escape_md(text):
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)

def escape_md_keep_pipes(text):
    text = text.replace("||", "%%PIPE%%")
    text = escape_md(text)
    return text.replace("%%PIPE%%", "||")

async def send_difficulty(chat_id):
    prev_msg_id = user_data[chat_id].get("difficulty_message_id")
    if prev_msg_id:
        try:
            await bot.delete_message(chat_id, prev_msg_id)
        except:
            pass

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Easy", callback_data="easy"),
        InlineKeyboardButton("Hard", callback_data="hard")
    )
    markup.add(
        InlineKeyboardButton("Reset Chat", callback_data="reset_chat")
    )

    lang = user_data[chat_id]["language"]
    text = "Choose difficulty:" if lang == "en" else "اختر مستوى الصعوبة:"

    msg = await bot.send_message(
        chat_id,
        escape_md(text),
        reply_markup=markup,
        parse_mode='MarkdownV2'
    )

    user_data[chat_id]["difficulty_message_id"] = msg.message_id
    user_data[chat_id]["all_messages"].append(msg.message_id)

# -------------------
# --- BOT HANDLERS ---
# -------------------
@bot.message_handler(commands=['start'])
async def start(message):
    chat_id = message.chat.id

    # Remove any keyboard to prevent typing
    await bot.send_message(chat_id, "Keyboard removed. Use the buttons below only.",
                           reply_markup=ReplyKeyboardRemove())

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("English", callback_data="lang_en"),
        InlineKeyboardButton("Arabic", callback_data="lang_ar")
    )

    msg = await bot.send_message(
        chat_id,
        "Choose your language / اختر لغتك:",
        reply_markup=markup
    )

    user_data[chat_id] = {
        "language": None,
        "difficulty_message_id": None,
        "all_messages": [msg.message_id]
    }

@bot.callback_query_handler(func=lambda c: True)
async def handle_callback(call):
    chat_id = call.message.chat.id

    if chat_id not in user_data:
        await bot.answer_callback_query(call.id, "Please send /start first.", show_alert=True)
        return

    # Language selection
    if call.data.startswith("lang_"):
        lang = call.data.split("_")[1]
        user_data[chat_id]["language"] = lang

        await bot.answer_callback_query(call.id)
        await send_difficulty(chat_id)
        return

    # Reset chat
    if call.data == "reset_chat":
        for msg_id in user_data[chat_id].get("all_messages", []):
            try:
                await bot.delete_message(chat_id, msg_id)
            except:
                pass

        user_data.pop(chat_id)

        await bot.answer_callback_query(call.id)
        await bot.send_message(chat_id, "Chat reset. Send /start to begin again.",
                               reply_markup=ReplyKeyboardRemove())
        return

    # Difficulty selection
    if call.data in ["easy", "hard"]:
        lang = user_data[chat_id]["language"]

        question = await get_question(
            question_type=call.data,
            language=lang
        )

        question_md = escape_md_keep_pipes(question)

        msg = await bot.send_message(
            chat_id,
            question_md,
            parse_mode='MarkdownV2'
        )

        user_data[chat_id]["all_messages"].append(msg.message_id)

        await send_difficulty(chat_id)
        await bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: True)
async def block_typing(message):
    chat_id = message.chat.id

    # Delete any manual message
    try:
        await bot.delete_message(chat_id, message.message_id)
    except:
        pass

    await bot.send_message(
        chat_id,
        "⚠️ Use the buttons only!",
        reply_to_message_id=message.message_id
    )

# -------------------
# --- RUN BOT ---
# -------------------
print("Bot is running...")
asyncio.run(bot.polling(non_stop=True))
