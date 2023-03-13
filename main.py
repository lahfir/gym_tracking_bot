import os
import random
import time
from pymongo import MongoClient
from datetime import datetime, timedelta
import requests
from telegram import Update, ParseMode
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    CallbackQueryHandler,
    Job,
)
from telegram.error import BadRequest
from dotenv import load_dotenv
import logging
import matplotlib.pyplot as plt
import seaborn as sns
import json

quotes = []

# Load quotes from JSON file
with open("quotes.json", "r") as f:
    quotes = json.load(f)

# Create a logger instance
logger = logging.getLogger(__name__)

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL)
db = client["image_bot"]
users = db["users"]
images = db["images"]

# Define the start command handler
def start(update: Update, context: CallbackContext) -> None:
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Hello, I'm your image bot! Please add me to a group to get started.",
    )


# Define the help command handler
def help(update: Update, context: CallbackContext) -> None:
    help_text = "The rules:\n\n"
    help_text += "1. Post only one image per day.\n"
    help_text += "2. Post at least 3 images per week.\n"
    help_text += "3. Streak resets every Sunday.\n"
    help_text += "4. Don't delete any of your previous images.\n\n"
    help_text += "Use /stats to view your image submission statistics."
    context.bot.send_message(chat_id=update.effective_chat.id, text=help_text)


# Define the stats command handler
# def stats(update: Update, context: CallbackContext) -> None:
#     gifs = [
#         "https://media.giphy.com/media/3o6ZsYzuLyRfSGX4f6/giphy.gif",
#         "https://media.giphy.com/media/xTiTnqZMwp5twnUKfS/giphy.gif",
#         "https://media.giphy.com/media/EzjCaYFnApVy8/giphy.gif",
#     ]

#     user_id = update.effective_user.id
#     user = users.find_one({"user_id": user_id})
#     if user is None:
#         context.bot.send_message(
#             chat_id=update.effective_chat.id,
#             text="You haven't submitted any images yet.",
#         )
#         return

#     stats_text = f"<b>Your image submission statistics</b>:\n\n"
#     stats_text += f"<b>Total images submitted</b>: {user['total_images']}\n"
#     stats_text += f"<b>This week's streak</b>: {user['current_streak']} / 7\n"
#     # stats_text += f"<b>Current streak</b>: {user['current_streak']} / 3"
#     context.bot.send_animation(
#         chat_id=update.effective_chat.id,
#         animation=random.choice(gifs),
#         caption=stats_text,
#         parse_mode=ParseMode.HTML,
#     )


def stats(update: Update, context: CallbackContext) -> None:
    gifs = [
        "https://media.giphy.com/media/3o6ZsYzuLyRfSGX4f6/giphy.gif",
        "https://media.giphy.com/media/xTiTnqZMwp5twnUKfS/giphy.gif",
        "https://media.giphy.com/media/EzjCaYFnApVy8/giphy.gif",
    ]

    user_id = update.effective_user.id
    user = users.find_one({"user_id": user_id})
    if user is None:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="You haven't submitted any images yet.",
        )
        return

    # Get longest streak
    longest_streak = 0
    streak_end_date = None
    streak_start_date = None
    for streak in user.get("streaks", []):
        streak_length = (
            streak.get("end_date", datetime.now()) - streak.get("start_date")
        ).days + 1
        if streak_length > longest_streak:
            longest_streak = streak_length
            streak_end_date = streak.get("end_date")
            streak_start_date = streak.get("start_date")
    longest_streak = max(longest_streak, user.get("current_streak", 0))

    # Get average submission rate
    total_images = user.get("total_images", 0)
    if total_images == 0:
        avg_rate = 0
    else:
        created_date = datetime.strptime(user["created_at"], "%Y-%m-%d %H:%M:%S.%f")
        days_since_created = (datetime.now() - created_date).days
        avg_rate = total_images / days_since_created

    # Get leaderboard
    leaderboard = []
    for user in users.find({}, {"user_id": 1, "total_images": 1}):
        leaderboard.append((user["user_id"], user["total_images"]))
    leaderboard.sort(key=lambda x: x[1], reverse=True)

    stats_text = f"<b>Your image submission statistics</b>:\n\n"
    stats_text += f"<b>Total images submitted</b>: {user['total_images']}\n"
    stats_text += f"<b>This week's streak</b>: {user.get('current_streak', 0)} / 7\n"
    stats_text += f"<b>Longest streak</b>: {longest_streak} days ({streak_start_date.date()} - {streak_end_date.date()})\n"
    stats_text += f"<b>Average submission rate</b>: {avg_rate:.2f} images/day\n\n"
    stats_text += "<b>Leaderboard</b>:\n"
    for i, (user_id, total_images) in enumerate(leaderboard[:10]):
        stats_text += f"{i+1}. {user_id}: {total_images}\n"
    context.bot.send_animation(
        chat_id=update.effective_chat.id,
        animation=random.choice(gifs),
        caption=stats_text,
        parse_mode=ParseMode.HTML,
    )


def leaderboard(update: Update, context: CallbackContext) -> None:
    streaks = []
    for user in users.find():
        streaks.append(
            {
                "username": user.get("username"),
                "current_streak": user.get("current_streak"),
            }
        )
    sorted_streaks = sorted(streaks, key=lambda x: x["current_streak"], reverse=True)
    streakText = f"<b>LEADERBOARD</b>\n\n"
    for i in range(0, len(sorted_streaks)):
        if sorted_streaks[i]["current_streak"] >= 3:
            streakText += f"{i+1}. {sorted_streaks[i]['username']} - {sorted_streaks[i]['current_streak']}/7 ✅\n"
        elif sorted_streaks[i]["current_streak"] >= 5:
            streakText += f"{i+1}. {sorted_streaks[i]['username']} - {sorted_streaks[i]['current_streak']}/7 🔥\n"
        else:
            streakText += f"{i+1}. {sorted_streaks[i]['username']} - {sorted_streaks[i]['current_streak']}/7\n"
    context.bot.send_message(
        chat_id=update.effective_chat.id, text=streakText, parse_mode=ParseMode.HTML
    )


# Define the image message handler
def image(update: Update, context: CallbackContext) -> None:

    # Define the progress bar message
    progress_message = context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Uploading images... [                    ]",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Simulate image upload
    for i in range(1, 11):
        sleep_time = random.uniform(0, 0.0005)
        time.sleep(sleep_time)
        context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=progress_message.message_id,
            text=f"Uploading images... <b>{i*10}%</b>",
            parse_mode=ParseMode.HTML,
        )

    # Check if the message has an image
    if not update.message.photo:
        context.bot.send_message(
            chat_id=update.effective_chat.id, text="Please submit only images."
        )
        return

    user_id = update.effective_user.id
    user = users.find_one({"user_id": user_id})
    now = datetime.now()

    # Check if the user has submitted an image today
    if user is not None and user.get("last_submission") is not None:
        last_submission = datetime.strptime(
            user["last_submission"], "%Y-%m-%d %H:%M:%S.%f"
        )
        # if last_submission.date() == now.date():
        #     context.bot.send_message(
        #         chat_id=update.effective_chat.id,
        #         text="You have already submitted an image today.",
        #     )
        #     return

    # Add the image to the database
    file_id = update.message.photo[-1].file_id
    image_url = context.bot.get_file(file_id).file_path
    image_data = {
        "user_id": user_id,
        "image_url": image_url,
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S.%f"),
    }
    images.insert_one(image_data)

    # Update the user's statistics
    if user is None:
        user_data = {
            "user_id": user_id,
            "username": update.effective_user.username
            or update.effective_user.first_name,
            "total_images": 1,
            "current_streak": 1,
            "longest_streak": 0,  # Add this line
            "last_submission": now.strftime("%Y-%m-%d %H:%M:%S.%f"),
        }
        users.insert_one(user_data)
    else:
        total_images = user["total_images"] + 1
        if (
            user.get("last_submission") is None
            or last_submission.date() < (now - timedelta(days=1)).date()
        ):
            current_streak = user["current_streak"] + 1
            if current_streak > user.get("longest_streak", 0):  # Add this block
                longest_streak = current_streak
            else:
                longest_streak = user.get("longest_streak", 0)
            if current_streak > 3:
                context.bot.send_animation(
                    chat_id=update.effective_chat.id,
                    animation="https://tenor.com/bkLRs.gif",
                    text="You're a warrior 🚀",
                )
        else:
            current_streak = user["current_streak"]
            longest_streak = user.get("longest_streak", 0)
        users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "total_images": total_images,
                    "current_streak": current_streak,
                    "longest_streak": longest_streak,  # Add this line
                    "last_submission": now.strftime("%Y-%m-%d %H:%M:%S.%f"),
                }
            },
        )

    # Check if the user has completed their weekly submission
    if user is not None and user["current_streak"] >= 3:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Congratulations! You have completed your weekly image submission.",
        )
    elif (
        user is not None
        and now.weekday() == 6
        and user.get("last_submission") is not None
    ):
        users.update_one(
            {"user_id": user_id}, {"$set": {"current_streak": 0}}
        )  # Reset the streak
        context.bot.send_message(
            chat_id=update.effective_chat.id, text="Your weekly streak has been reset."
        )

    # Delete the progress bar message
    context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=progress_message.message_id,
    )

    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Your image has been added",
    )


def reset_streaks(context: CallbackContext) -> None:
    users.update_many({}, {"$set": {"current_streak": 0}})


def warn_users(context: CallbackContext) -> None:
    now = datetime.now()
    users_to_warn = users.find(
        {
            "$expr": {"$lt": ["$current_streak", 3]},
            "last_warned": {"$lt": now - timedelta(days=7)},
        }
    )
    for user in users_to_warn:
        try:
            context.bot.send_message(
                chat_id=user["chat_id"],
                text="You have not submitted 3 images this week. Please submit more images to avoid being warned again 😭",
            )
            users.update_one(
                {"user_id": user["user_id"]}, {"$set": {"last_warned": now}}
            )
        except BadRequest as e:
            print(f"Failed to send warning message to user {user['user_id']}: {str(e)}")


# Define the error handler function
def error(update: Update, context: CallbackContext) -> None:
    """Log the error and send a message to the user."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


QUOTES = [
    "Believe you can and you're halfway there. -Theodore Roosevelt",
    "It does not matter how slowly you go as long as you do not stop. -Confucius",
    "Start where you are. Use what you have. Do what you can. -Arthur Ashe",
    "Believe in yourself and all that you are. Know that there is something inside you that is greater than any obstacle. -Christian D. Larson",
    "Don't watch the clock; do what it does. Keep going. -Sam Levenson",
]


def send_quote(context: CallbackContext) -> None:
    random_quote = random.choice(quotes)
    quote = f"<b>{random_quote.text}</b> - {random_quote.author}"
    context.bot.send_message(
        chat_id=context.job.context.chat_id, text=quote, parse_mode=ParseMode.HTML
    )


def welcome_new_user(update: Update, context: CallbackContext) -> None:
    new_user = update.message.new_chat_members[0]
    try:
        # help_text = f"Welcome <b>{new_user.username}</b>,\n"
        help_text = "The rules:\n\n"
        help_text += "1. Post only one image per day.\n"
        help_text += "2. Post at least 3 images per week.\n"
        help_text += "3. Streak resets every Sunday.\n"
        help_text += "4. Don't delete any of your previous images.\n\n"
        help_text += "Use /stats to view your image submission statistics."
        # Send a welcome message with a random gif
        gifs = [
            "https://media.giphy.com/media/l0MYGb1LuZ3n7dRnO/giphy.gif",
            "https://media.giphy.com/media/Ae7SI3LoPYj8Q/giphy.gif",
            "https://media.giphy.com/media/ypqHf6pQ5kQEg/giphy.gif",
            "https://media.giphy.com/media/5L57f5fI3f2716NaJ3/giphy.gif",
            "https://media.giphy.com/media/LpDmTYtmOJLXxkMB3H/giphy.gif",
            "https://media.giphy.com/media/Yknm7GgtMRkRaP5UMi/giphy.gif",
        ]
        gif = random.choice(gifs)
        context.bot.send_animation(
            chat_id=new_user.id,
            animation=gif,
            caption=help_text,
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        print(e)

    prompts = [
        "Don't worry, we won't judge you for being addicted to taking pictures...we are too! 😂📷👌",
        "Glad to see you made it to the party! Join in on the fun and let's share some incredible images together! 🎉📷🌅",
        "where the images are as beautiful as the sunrise and as rare as a unicorn sighting! 🦄📸🌅",
        "You have just entered the image-sharing zone, where all your wildest photo-sharing dreams come true! 😜📷🌅",
        "where our images are hotter than a jalapeno eating a habanero on a sunny day in Mexico! 😎🌶️🔥",
    ]

    group_chat_id = update.effective_chat.id
    new_member_mention = (
        f"@{new_user.username}" if new_user.username else new_user.first_name
    )
    welcome_message = f"Welcome <b>{new_member_mention}</b> to the group! {random.choice(prompts)},\n\n {help_text}"
    context.bot.send_animation(
        chat_id=group_chat_id,
        animation=gif,
        caption=welcome_message,
        parse_mode=ParseMode.HTML,
    )


def main() -> None:
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Add handlers for commands
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help))
    dispatcher.add_handler(CommandHandler("stats", stats))
    dispatcher.add_handler(CommandHandler("groupstats", leaderboard))
    dispatcher.add_handler(
        MessageHandler(Filters.status_update.new_chat_members, welcome_new_user)
    )

    # Add handler for image messages
    dispatcher.add_handler(MessageHandler(Filters.photo, image))

    # Start polling for updates
    updater.start_polling()

    # Schedule job to reset streaks every Sunday at midnight
    updater.job_queue.run_daily(
        reset_streaks,
        time=datetime.time(hour=0, minute=0, second=0),
        days=(6,),
        context=dispatcher,
    )

    # Schedule job to warn users who haven't submitted 3 images by Saturday at midnight
    updater.job_queue.run_daily(
        warn_users,
        time=datetime.time(hour=0, minute=0, second=0),
        days=(5,),
        context=dispatcher,
    )

    updater.job_queue.run_repeating(send_quote, interval=10, first=0)

    # Log errors
    updater.dispatcher.add_error_handler(error)

    # Run the bot
    updater.idle()


if __name__ == "__main__":
    main()
