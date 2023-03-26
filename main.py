from io import BytesIO
import os
import random
import time
from pymongo import MongoClient
from datetime import datetime, timedelta
import requests
from telegram import (
    InputMediaPhoto,
    ReplyKeyboardRemove,
    Update,
    ParseMode,
)
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    ConversationHandler,
    CallbackQueryHandler,
)
from telegram_bot_calendar import DetailedTelegramCalendar, LSTEP
from telegram.error import BadRequest
from dotenv import load_dotenv
import logging
import json
from typing import List
from telegram.ext import messagequeue as mq
import telegramcalendar, utils, messages

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
    bot_username = context.bot.get_me().username
    help_text = "The rules:\n\n"
    help_text += "1. Post at least 3 images per week.\n"
    help_text += "2. Streak resets every Sunday.\n"
    help_text += f"Click me @{bot_username} and start me or else I'll not be able to send statistics personally to your DMs\n"
    help_text += "Use /stats to view your image submission statistics."
    context.bot.send_message(
        chat_id=update.effective_chat.id, text=help_text, parse_mode=ParseMode.HTML
    )


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
        send_typing(context.bot, update.effective_chat.id)
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="You haven't submitted any images yet.",
        )
        return

    # Get average submission rate
    total_images = user["total_images"]
    if total_images == 0:
        avg_rate = 0
    else:
        created_date = datetime.strptime(user["created_at"], "%Y-%m-%d %H:%M:%S.%f")
        days_since_created = (datetime.now() - created_date).days
        try:
            avg_rate = total_images / days_since_created
        except ZeroDivisionError:
            avg_rate = 0

    stats_text = f"<b>Your image submission statistics</b>:\n\n"
    stats_text += f"<b>Total images submitted</b>: {user['total_images']}\n"
    stats_text += f"<b>This week's streak</b>: {user['current_streak']} / 7\n"
    # stats_text += f"<b>Average submission rate</b>: {avg_rate:.2f} images/day\n\n"
    # stats_text += "<b>Leaderboard</b>:\n\n"

    # for i, (user_id, total_images) in enumerate(leaderboard[:10]):
    #     stats_text += f"{i+1}. {user_id}: {total_images}\n"

    context.bot.send_animation(
        chat_id=update.effective_user.id,
        animation=random.choice(gifs),
        caption=stats_text,
        parse_mode=ParseMode.HTML,
    )

    # Define the start and end dates for the week you want to retrieve images for
    start_of_week = datetime.now().date() - timedelta(days=datetime.now().weekday())
    end_of_week = start_of_week + timedelta(days=7)

    # Convert start_of_week and end_of_week to datetime.datetime objects
    start_of_week = datetime.combine(start_of_week, datetime.min.time())
    end_of_week = datetime.combine(end_of_week, datetime.max.time())

    # Find all images uploaded during the current week
    imagesSentByUser = images.find(
        {
            "user_id": user_id,
            "timestamp": {"$gte": start_of_week, "$lt": end_of_week},
        }
    )

    for image in imagesSentByUser:
        send_typing(context.bot, update.effective_chat.id)
        context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=image["image_url"],
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
    send_typing(context.bot, update.effective_chat.id)
    context.bot.send_message(
        chat_id=update.effective_chat.id, text=streakText, parse_mode=ParseMode.HTML
    )


def send_typing(bot, chat_id):
    bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.TYPING)
    time.sleep(2)  # simulate typing for 2 seconds


def button_handler(update, context):
    query = update.callback_query
    if query.data == "yes":
        # Get the photo file ID from context
        photo_id = context.user_data.get("file_id")
        if photo_id:
            send_typing(context.bot, update.effective_chat.id)

            # # Define the progress bar message
            # progress_message = context.bot.send_message(
            #     chat_id=update.effective_chat.id,
            #     text="Uploading images... [                    ]",
            #     parse_mode=ParseMode.MARKDOWN,
            # )

            # # Simulate image upload
            # for i in range(1, 11):
            #     sleep_time = random.uniform(0, 0.000005)
            #     time.sleep(sleep_time)
            #     context.bot.edit_message_text(
            #         chat_id=update.effective_chat.id,
            #         message_id=progress_message.message_id,
            #         text=f"Uploading images... {i*10}%",
            #     )

            user_id = update.effective_user.id
            user = users.find_one({"user_id": user_id})
            now = datetime.now()

            user_data = {}

            # Update the user's statistics and check the streak
            if user is None:
                user_data = {
                    "user_id": user_id,
                    "username": update.effective_user.username
                    or update.effective_user.first_name,
                    "total_images": 1,
                    "current_streak": 1,
                    "longest_streak": 0,
                    "created_at": now.strftime("%Y-%m-%d %H:%M:%S.%f"),
                    "last_submission": datetime.strptime(
                        str(now), "%Y-%m-%d %H:%M:%S.%f"
                    ),
                }
                users.insert_one(user_data)
                message_text = (
                    f"{user_data['username']} submitted his 1st gym proof of the week"
                )
                send_typing(context.bot, update.effective_chat.id)
                # Send the message for the streak
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=message_text,
                )
            else:
                total_images = user["total_images"] + 1
                last_submission = datetime.strptime(
                    user["last_submission"], "%Y-%m-%d %H:%M:%S.%f"
                )

                message_text = ""

                streak = user["current_streak"]
                # if last_submission.date() < now.date():
                #     streak += 1
                # if streak <= 3:
                #     message_text = f"{user['username']} submitted his {streak}{'st' if streak>1 else 'nd' if streak>2 else 'rd'} gym proof of the week"
                # else:
                #     message_text = (
                #         f"{user['username']} submitted his {streak}th gym proof of the week"
                #     )
                # if streak > user.get("longest_streak", 0):
                #     users.update_one({"user_id": user_id}, {"$set": {"longest_streak": streak}})
                users.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "total_images": total_images,
                            "current_streak": streak,
                            "last_submission": datetime.strptime(
                                str(now), "%Y-%m-%d %H:%M:%S.%f"
                            ),
                        }
                    },
                )

            # Add the image to the database
            image_url = context.user_data.get("image_url")
            image_data = {
                "user_id": user_id,
                "image_url": image_url,
                "timestamp": datetime.strptime(str(now), "%Y-%m-%d %H:%M:%S.%f"),
            }
            images.insert_one(image_data)

            congrats_animations = [
                "https://media.giphy.com/media/xT8qBepJQzUjXpeWU8/giphy.gif",
                "https://media.giphy.com/media/jJQC2puVZpTMO4vUs0/giphy.gif",
                "https://media.giphy.com/media/3oz8xAFtqoOUUrsh7W/giphy.gif",
                "https://media.giphy.com/media/g9582DNuQppxC/giphy.gif",
                "https://media.giphy.com/media/fdyZ3qI0GVZC0/giphy.gif",
            ]

            # Check if the user has completed their weekly submission
            if user is not None and user["current_streak"] >= 3:
                send_typing(context.bot, update.effective_chat.id)
                context.bot.send_animation(
                    chat_id=update.effective_chat.id,
                    animation=random.choice(congrats_animations),
                    caption="Congratulations! You have completed your weekly image submission.",
                )
            elif (
                user is not None
                and now.weekday() == 6
                and (
                    user.get("last_submission") is not None
                    or user_data.get("last_submission") is not None
                )
            ):
                users.update_one(
                    {"user_id": user_id}, {"$set": {"current_streak": 0}}
                )  # Reset the streak
                send_typing(context.bot, update.effective_chat.id)
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Your weekly streak has been reset.",
                )

            # # Delete the progress bar message
            # context.bot.delete_message(
            #     chat_id=update.effective_chat.id,
            #     message_id=progress_message.message_id,
            # )

            # context.bot.send_message(
            #     chat_id=update.effective_chat.id,
            #     text="Your image has been added",
            # )

            # Send gym proof count
            current_streak = (
                user.get("current_streak", 0) or user_data["current_streak"]
            )
            if current_streak == 1:
                count_text = "1st"
            elif current_streak == 2:
                count_text = "2nd"
            elif current_streak == 3:
                count_text = "3rd"
            else:
                return  # Do not send anything if streak is less than 1 or more than 3

            message = f"{user.get('username')} submitted his {count_text} gym proof of the week."
            send_typing(context.bot, update.effective_chat.id)
            context.bot.send_message(chat_id=update.effective_chat.id, text=message)

            # Send leaderboard
            send_typing(context.bot, update.effective_chat.id)
            leaderboard = get_leaderboard(users)
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=leaderboard,
                parse_mode=ParseMode.HTML,
            )
            query.answer()
        else:
            # If photo ID not found in context, return
            query.answer(
                text="Photo not found. Please upload an image first.", show_alert=True
            )
    elif query.data == "no":
        query.answer()
        query.edit_message_text("Okay, let's stop here then.")
    else:
        # If callback data not recognized, do nothing
        (kind, _, _, _, _) = utils.separate_callback_data(query.data)
        if kind == messages.CALENDAR_CALLBACK:
            inline_calendar_handler(update, context)
        pass
    message_id = query.message.message_id
    context.bot.delete_message(chat_id=query.message.chat_id, message_id=message_id)


# Define the image message handler
def image(update: Update, context: CallbackContext) -> None:
    # Check if the message has an image
    if not update.message.photo:
        context.bot.send_message(
            chat_id=update.effective_chat.id, text="Please submit only images."
        )
        return

    # Get the photo file ID
    file_id = update.message.photo[-1].file_id
    image_url = context.bot.get_file(file_id).file_path

    # Ask the user if the photo is gym proof
    keyboard = [
        [
            InlineKeyboardButton("Yes", callback_data="yes"),
            InlineKeyboardButton("No", callback_data="no"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    sent_message = update.message.reply_text(
        "Is this gym proof?", reply_markup=reply_markup
    )

    # Store the photo file ID in context for later use
    context.user_data["sent_message_id"] = sent_message.message_id
    context.user_data["file_id"] = file_id
    context.user_data["image_url"] = image_url


def get_leaderboard(users) -> str:
    """Get the leaderboard of users sorted by their current streak."""
    streaks = []
    for user in users.find():
        streaks.append(
            {
                "username": user.get("username"),
                "current_streak": user.get("current_streak", 0),
                "longest_streak": user.get("longest_streak", 0),
            }
        )

    # Sort the streaks by current streak, then by longest streak
    sorted_streaks = sorted(
        streaks, key=lambda x: (-x["current_streak"], -x["longest_streak"])
    )

    # Generate the leaderboard message
    message = "<b>Leaderboard:</b>\n"
    for i, user_streak in enumerate(sorted_streaks):
        message += f"{i+1}. {user_streak['username']} - {user_streak['current_streak']} (Longest streak: {user_streak['longest_streak']})\n"

    return message


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
    send_typing(context.bot, update.effective_chat.id)
    new_user = update.message.new_chat_members[0]
    try:
        # help_text = f"Welcome <b>{new_user.username}</b>,\n"
        bot_username = context.bot.get_me().username
        help_text = "The rules:\n\n"
        help_text += "1. Post at least 3 images per week.\n"
        help_text += "2. Streak resets every Sunday.\n"
        help_text += f"Click me @{bot_username} and start me or else I'll not be able to send statistics personally to your DMs\n"
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
        send_typing(context.bot, update.effective_chat.id)
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
    send_typing(context.bot, update.effective_chat.id)
    context.bot.send_animation(
        chat_id=group_chat_id,
        animation=gif,
        caption=welcome_message,
        parse_mode=ParseMode.HTML,
    )


# Define maximum number of images to send in one message
MAX_IMAGES_PER_MESSAGE = 10


def inline_calendar_handler(update, context):
    selected, date = telegramcalendar.process_calendar_selection(update, context)
    if selected:
        context.bot.send_message(
            chat_id=update.callback_query.from_user.id,
            text=str(date.strftime("%d/%m/%Y")),
            reply_markup=ReplyKeyboardRemove(),
        )


def get_user_images_in_date_range(
    user_id: int, start_date: datetime, end_date: datetime
) -> List[str]:
    """
    Retrieve all images posted by the user within the specified date range.
    :param user_id: Telegram user ID
    :param start_date: Start date of the range
    :param end_date: End date of the range
    :return: List of image URLs
    """
    start_date = datetime.strptime(start_date, "%d/%m/%Y").date()
    end_date = datetime.strptime(end_date, "%d/%m/%Y").date()
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    print(start_datetime, end_datetime)

    cursor = images.find(
        {
            "user_id": user_id,
            "timestamp": {"$gte": start_datetime, "$lte": end_datetime},
        }
    )
    uploaded = []
    for doc in cursor:
        uploaded.append(doc["image_url"])
    return uploaded


def get_user_date_ranges(user_id: int) -> List[str]:
    """
    Retrieve all the date ranges in which the user has posted images.
    :param user_id: Telegram user ID
    :return: List of date range strings
    """
    date_ranges = []
    cursor = images.find({"user_id": user_id})
    for doc in cursor:
        doc_date = datetime.strptime(doc["timestamp"], "%Y-%m-%d %H:%M:%S.%f").date()
        date_range = (
            f"{doc_date.strftime('%Y-%m-%d')} - {doc_date.strftime('%Y-%m-%d')}"
        )
        if date_range not in date_ranges:
            date_ranges.append(date_range)
    return date_ranges


def get_date_range_from_callback_data(callback_data: str) -> tuple:
    """
    Extract the start and end dates from the callback data.
    :param callback_data: Callback data sent by the user
    :return: Tuple containing the start and end dates as datetime objects
    """
    date_range = callback_data.split(" - ")
    start_date = datetime.strptime(date_range[0], "%Y-%m-%d")
    end_date = (
        datetime.strptime(date_range[1], "%Y-%m-%d")
        + timedelta(days=1)
        - timedelta(microseconds=1)
    )
    return start_date, end_date


# def send_images(
#     update: Update, context: CallbackContext, image_urls: List[str]
# ) -> None:
#     """
#     Send the images to the user in batches.
#     :param update: Telegram update object
#     :param context: Telegram context object
#     :param image_urls: List of image URLs to send
#     :return: None
#     """
#     message_queue = mq.MessageQueue()
#     message_queue.set_scheduled_queue(context.bot, context.job_queue)
#     for i in range(0, len(image_urls), MAX_IMAGES_PER_MESSAGE):
#         batch = image_urls[i : i + MAX_IMAGES_PER_MESSAGE]
#         context.bot.send_media_group(
#             update.effective_chat.id,
#             [InputMediaPhoto(media=image_url) for image_url in batch],
#         )
#     context.job_queue.run_once(message_queue.stop, 5)


def get_user_weekly_images_in_range(user_id, start_date, end_date):
    """
    Retrieve all images posted by the user within the specified date range.
    :param user_id: Telegram user ID
    :param start_date: Start date of the range
    :param end_date: End date of the range
    :return: List of image URLs
    """

    start_date = datetime.strptime(start_date, "%d/%m/%Y").date()
    end_date = datetime.strptime(end_date, "%d/%m/%Y").date()
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    cursor = images.find(
        {
            "user_id": user_id,
            "timestamp": {"$gte": start_datetime, "$lte": end_datetime},
        }
    )
    uploaded = []
    for doc in cursor:
        uploaded.append(doc["image_url"])
    return uploaded


def send_images(update: Update, context: CallbackContext) -> int:
    """
    Get the list of images and send them to the user.
    :param update: Update object from Telegram
    :param context: CallbackContext object from Telegram
    :return: Integer representing the next state in the conversation flow
    """
    user_id = update.message.from_user.id
    start_date = context.user_data["start_date"]
    end_date = context.user_data["end_date"]
    user_images = get_user_weekly_images_in_range(user_id, start_date, end_date)
    if not user_images:
        update.message.reply_text(
            "You haven't uploaded any images for this date range."
        )
        return ConversationHandler.END
    photo_list = []
    context.bot.send_chat_action(
        chat_id=user_id, action=telegram.ChatAction.UPLOAD_PHOTO
    )
    time.sleep(2)  # simulate typing for 2 seconds
    for image_url in user_images:
        response = requests.get(image_url)
        photo = BytesIO(response.content)
        photo_list.append(InputMediaPhoto(photo))
    context.bot.send_media_group(chat_id=user_id, media=photo_list)
    # End conversation
    context.user_data.pop("state", None)
    context.user_data.pop("start_date", None)
    context.user_data.pop("end_date", None)
    return ConversationHandler.END


GET_DATE_RANGE_START = 1
GET_DATE_RANGE_END = 2


def select_date_range_start(update: Update, context: CallbackContext) -> int:
    """
    Start the conversation to select the date range.
    :param update:" = Update object from Telegram
    :param context: CallbackContext object from Telegram
    :return: Integer representing the next state in the conversation flow
    """
    user_id = update.message.from_user.id
    context.bot.send_message(
        chat_id=user_id,
        text="Please select a start date for the image range:",
        reply_markup=ReplyKeyboardRemove(),
    )
    # Set state to GET_DATE_RANGE_START
    context.user_data["state"] = GET_DATE_RANGE_START
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="CALENDAR",
        reply_markup=telegramcalendar.create_calendar(),
    )
    return GET_DATE_RANGE_START


def select_date_range_end(update: Update, context: CallbackContext) -> int:
    """
    Get the end date for the selected date range.
    :param update: Update object from Telegram
    :param context: CallbackContext object from Telegram
    :return: Integer representing the next state in the conversation flow
    """
    context.user_data["start_date"] = update.message.text

    start_date = datetime.strptime(update.message.text, "%d/%m/%Y").date()
    start_datetime = datetime.combine(start_date, datetime.min.time())
    print(start_datetime)

    user_id = update.message.from_user.id
    context.user_data["state"] = GET_DATE_RANGE_END
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="CALENDAR",
        reply_markup=telegramcalendar.create_calendar(),
    )
    return GET_DATE_RANGE_END


def validate_date_range(update, context):
    """Validate the selected date range."""
    user_id = update.message.from_user.id
    start_date = context.user_data["start_date"]
    context.user_data["end_date"] = update.message.text
    end_date = context.user_data["end_date"]
    # Do validation here
    context.bot.send_message(
        chat_id=user_id,
        text=f"Selected date range: {start_date} - {end_date}",
        reply_markup=ReplyKeyboardRemove(),
    )

    if start_date > end_date:
        context.bot.send_message(
            chat_id=user_id,
            text="The start date must be before the end date. Please try again.",
        )
        return select_date_range_start(update, context)

    images = get_user_images_in_date_range(user_id, start_date, end_date)
    if images:
        send_images(update, context)
        return ConversationHandler.END
    else:
        context.bot.send_message(
            chat_id=user_id,
            text="No images found for the selected date range. Please try again.",
        )
        return select_date_range_start(update, context)


def cancel(update: Update, context: CallbackContext) -> int:
    """
    Cancel the current operation and return to the main menu.
    """
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text(
        "Operation canceled. Type /help to see the list of available commands.",
        reply_markup=ReplyKeyboardRemove(),
    )
    context.user_data.clear()
    return ConversationHandler.END


conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler(
            "sent_images", select_date_range_start, filters=Filters.chat_type.private
        )
    ],
    states={
        GET_DATE_RANGE_START: [
            MessageHandler(
                Filters.text & ~(Filters.command | Filters.regex("^Done$")),
                select_date_range_end,
            )
        ],
        GET_DATE_RANGE_END: [
            MessageHandler(
                Filters.text & ~(Filters.command | Filters.regex("^Done$")),
                validate_date_range,
            )
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)


def main() -> None:
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Add handlers for commands
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help))
    dispatcher.add_handler(CommandHandler("stats", stats))
    dispatcher.add_handler(CommandHandler("leaderboard", leaderboard))
    dispatcher.add_handler(CallbackQueryHandler(button_handler))
    dispatcher.add_handler(
        MessageHandler(Filters.status_update.new_chat_members, welcome_new_user)
    )
    # Add handler for image messages
    dispatcher.add_handler(MessageHandler(Filters.photo, image))
    dispatcher.add_handler(conv_handler)

    # Start polling for updates
    updater.start_polling(timeout=123)

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

    updater.job_queue.run_repeating(
        leaderboard,
        interval=60 * 60 * 5,  # Run every 5 hours
        first=0,  # Start immediately
    )

    updater.job_queue.run_repeating(send_quote, interval=10, first=0)

    # Log errors
    updater.dispatcher.add_error_handler(error)

    # Run the bot
    updater.idle()


if __name__ == "__main__":
    main()
