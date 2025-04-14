from dotenv import load_dotenv

load_dotenv(
    "config.env",
    override=True,
)
import asyncio
import os
import shutil
import time
# --- MODIFIED START ---
import re
import aiohttp
import yt_dlp
# --- MODIFIED END ---

import psutil
import pyromod
from PIL import Image
from pyrogram import Client, filters,enums
from pyrogram.errors import (
    FloodWait,
    InputUserDeactivated,
    PeerIdInvalid,
    UserIsBlocked,
    MessageNotModified # Added
)
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    User,
)

from __init__ import (
    AUDIO_EXTENSIONS,
    BROADCAST_MSG,
    LOGGER,
    MERGE_MODE,
    SUBTITLE_EXTENSIONS,
    UPLOAD_AS_DOC,
    UPLOAD_TO_DRIVE,
    VIDEO_EXTENSIONS,
    bMaker,
    formatDB,
    gDict,
    queueDB,
    replyDB,
    # --- MODIFIED START ---
    get_aio_session,
    close_aio_session,
    # --- MODIFIED END ---
)
from config import Config
from helpers import database
# --- MODIFIED START ---
from helpers.utils import UserSettings, get_readable_file_size, get_readable_time, sanitize_filename, handle_duplicate_filename
from helpers.display_progress import Progress # Import Progress class
# --- MODIFIED END ---


botStartTime = time.time()
parent_id = Config.GDRIVE_FOLDER_ID


class MergeBot(Client):
    def start(self):
        super().start()
        try:
            # --- MODIFIED START ---
            # Initialize aiohttp session
            loop = asyncio.get_event_loop()
            loop.run_until_complete(get_aio_session())
            # --- MODIFIED END ---
            self.send_message(chat_id=int(Config.OWNER), text="<b>Bot Started!</b>")
        except Exception as err:
            LOGGER.error(f"Boot alert failed! Error: {err}. Please start bot in PM") # Log error
        return LOGGER.info("Bot Started!")

    def stop(self):
        # --- MODIFIED START ---
        # Close aiohttp session
        loop = asyncio.get_event_loop()
        loop.run_until_complete(close_aio_session())
        # --- MODIFIED END ---
        super().stop()
        return LOGGER.info("Bot Stopped")


mergeApp = MergeBot(
    name="merge-bot",
    api_hash=Config.API_HASH,
    api_id=Config.TELEGRAM_API,
    bot_token=Config.BOT_TOKEN,
    workers=300,
    plugins=dict(root="plugins"),
    app_version="5.0+yash-mergebot",
)


# --- MODIFIED START ---
# Ensure download directory exists using the config path
if not os.path.isdir(Config.DOWNLOAD_LOCATION):
    try:
        os.makedirs(Config.DOWNLOAD_LOCATION)
        LOGGER.info(f"Created download directory: {Config.DOWNLOAD_LOCATION}")
    except OSError as e:
        LOGGER.critical(f"Could not create download directory: {Config.DOWNLOAD_LOCATION}. Error: {e}")
        # Consider exiting if the directory is essential and cannot be created
# Ensure the old 'downloads' path also exists for compatibility if needed, though ideally migrate fully
if not os.path.isdir("downloads"):
     try:
         os.makedirs("downloads")
     except OSError as e:
         LOGGER.warning(f"Could not create legacy 'downloads' directory. Error: {e}")
# --- MODIFIED END ---


@mergeApp.on_message(filters.command(["log"]) & filters.user(Config.OWNER_USERNAME))
async def sendLogFile(c: Client, m: Message):
    # --- MODIFIED START ---
    log_file = "./mergebotlog.txt"
    if os.path.exists(log_file):
        await m.reply_document(document=log_file)
    else:
        await m.reply_text("Log file not found.")
    # --- MODIFIED END ---
    return


@mergeApp.on_message(filters.command(["login"]) & filters.private)
async def loginHandler(c: Client, m: Message):
    user = UserSettings(m.from_user.id, m.from_user.first_name)
    if user.banned:
        await m.reply_text(text=f"**Banned User Detected!**\n  🛡️ Unfortunately you can't use me\n\nContact: 🈲 @{Config.OWNER_USERNAME}", quote=True)
        return
    if user.user_id == int(Config.OWNER):
        user.allowed = True
        user.set() # Save owner's allowed status
    if user.allowed:
        await m.reply_text(text=f"**You are already allowed to use me!**\n  ⚡ Don't Spam", quote=True) # Modified message
    else:
        try:
            passwd = m.text.split(" ", 1)[1]
        except IndexError: # Check for IndexError specifically
            await m.reply_text("**Command:**\n  `/login <password>`\n\n**Usage:**\n  `password`: Get the password from owner",quote=True,parse_mode=enums.parse_mode.ParseMode.MARKDOWN)
            # --- MODIFIED START ---
            return # Added return
            # --- MODIFIED END ---
        passwd = passwd.strip()
        if passwd == Config.PASSWORD:
            user.allowed = True
            await m.reply_text(
                text=f"**Login passed ✅,**\n  ⚡ Now you can use me!!", quote=True
            )
        else:
            await m.reply_text(
                text=f"**Login failed ❌,**\n  🛡️ Unfortunately you can't use me\n\nContact: 🈲 @{Config.OWNER_USERNAME}",
                quote=True,
            )
    user.set() # Save changes (allowed status)
    del user # Clean up object
    return


@mergeApp.on_message(filters.command(["stats"]) & filters.private)
async def stats_handler(c: Client, m: Message):
    # --- MODIFIED START ---
    # Check if user is allowed (owner or logged in)
    user = UserSettings(m.from_user.id, m.from_user.first_name)
    if m.from_user.id != int(Config.OWNER) and not user.allowed:
        await m.reply_text("You are not authorized to use this command.", quote=True)
        return
    # --- MODIFIED END ---

    currentTime = get_readable_time(time.time() - botStartTime)
    try: # Add try-except for disk usage and network stats
        total, used, free = shutil.disk_usage(Config.DOWNLOAD_LOCATION) # Check download location disk
        total = get_readable_file_size(total)
        used = get_readable_file_size(used)
        free = get_readable_file_size(free)
        sent = get_readable_file_size(psutil.net_io_counters().bytes_sent)
        recv = get_readable_file_size(psutil.net_io_counters().bytes_recv)
        cpuUsage = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory().percent
        disk = psutil.disk_usage(Config.DOWNLOAD_LOCATION).percent # Check download location disk %
        stats = (
            f"<b>╭「 💠 BOT STATISTICS 」</b>\n"
            f"<b>│</b>\n"
            f"<b>├⏳ Bot Uptime : {currentTime}</b>\n"
            f"<b>├💾 Total Disk Space ({Config.DOWNLOAD_LOCATION}) : {total}</b>\n"
            f"<b>├📀 Used Space ({Config.DOWNLOAD_LOCATION}) : {used}</b>\n"
            f"<b>├💿 Free Space ({Config.DOWNLOAD_LOCATION}) : {free}</b>\n"
            f"<b>├🔺 Total Upload : {sent}</b>\n"
            f"<b>├🔻 Total Download : {recv}</b>\n"
            f"<b>├🖥 CPU : {cpuUsage}%</b>\n"
            f"<b>├⚙️ RAM : {memory}%</b>\n"
            f"<b>╰💿 DISK ({Config.DOWNLOAD_LOCATION}) : {disk}%</b>"
        )
        await m.reply_text(text=stats, quote=True)
    except Exception as e:
        LOGGER.error(f"Error getting stats: {e}")
        await m.reply_text(f"Failed to retrieve some stats. Error: {e}", quote=True)


@mergeApp.on_message(
    filters.command(["broadcast"])
    & filters.private
    & filters.user(Config.OWNER_USERNAME)
)
async def broadcast_handler(c: Client, m: Message):
    msg = m.reply_to_message
    if not msg: # Check if msg exists
        await m.reply_text("Please reply to a message to broadcast.")
        return

    user_cursor = await database.broadcast() # Get the cursor
    if not user_cursor:
        await m.reply_text("Could not retrieve user list from database.")
        return

    total_users = await c.db.users.count_documents({}) # Use await and the client's db connection
    if total_users == 0:
        await m.reply_text("No users found in the database.")
        return

    status = await m.reply_text(text=BROADCAST_MSG.format(str(total_users), "0"), quote=True)
    success = 0
    failed = 0
    start_time = time.time()

    async for user_doc in user_cursor: # Iterate directly over the cursor
        uid = user_doc["_id"]
        user_name = user_doc.get('name', f'ID:{uid}') # Use .get for safety

        if uid == int(Config.OWNER): # Skip owner
             continue

        try:
            await msg.copy(chat_id=uid)
            success += 1
            LOGGER.info(f"Message sent to {user_name}")
        except FloodWait as e:
            await asyncio.sleep(e.x) # Use e.x directly
            # Retry sending after sleep
            try:
                await msg.copy(chat_id=uid)
                success += 1
                LOGGER.info(f"Message sent to {user_name} after FloodWait")
            except Exception as retry_err:
                 LOGGER.warning(f"Retry failed for {user_name}: {retry_err}")
                 failed += 1
                 # Consider deleting user if retry fails too
                 # await database.deleteUser(uid)
        except InputUserDeactivated:
            await database.deleteUser(uid)
            LOGGER.info(f"{user_name} : deactivated\n")
            failed += 1
        except UserIsBlocked:
            await database.deleteUser(uid)
            LOGGER.info(f"{user_name} : blocked the bot\n")
            failed += 1
        except PeerIdInvalid:
            await database.deleteUser(uid)
            LOGGER.info(f"{user_name} : user id invalid\n")
            failed += 1
        except Exception as err:
            LOGGER.warning(f"Broadcast error for {user_name}: {err}\n")
            failed += 1
            # Optionally delete user on generic error too, or investigate further
            # await database.deleteUser(uid)

        # Update status message periodically or after each attempt
        if (success + failed) % 20 == 0 or (success + failed) == total_users: # Update every 20 users or at the end
             try:
                 current_time_elapsed = get_readable_time(time.time() - start_time)
                 new_text = BROADCAST_MSG.format(total_users, success) + f"\n**Failed: {failed}**\nElapsed: {current_time_elapsed}"
                 if status.text != new_text:
                      await status.edit_text(text=new_text)
             except MessageNotModified:
                 pass
             except FloodWait as fw:
                 await asyncio.sleep(fw.x)
             except Exception as status_err:
                 LOGGER.error(f"Failed to update broadcast status: {status_err}")

        await asyncio.sleep(0.5) # Reduced sleep time further

    end_time = time.time()
    total_time = get_readable_time(end_time - start_time)
    final_text = (
        f"**📢 Broadcast Complete!**\n\n"
        f"Total Users: {total_users}\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {failed}\n"
        f"🕒 Duration: {total_time}"
    )
    try:
        if status.text != final_text:
            await status.edit_text(text=final_text)
    except MessageNotModified:
        pass
    except Exception as final_status_err:
        LOGGER.error(f"Failed to edit final broadcast status: {final_status_err}")


@mergeApp.on_message(filters.command(["start"]) & filters.private)
async def start_handler(c: Client, m: Message):
    user = UserSettings(m.from_user.id, m.from_user.first_name)
    # --- MODIFIED START ---
    await database.addUser(
        uid=m.from_user.id,
        fname=m.from_user.first_name,
        lname=m.from_user.last_name
    ) # Add or update user on start
    # --- MODIFIED END ---

    if m.from_user.id != int(Config.OWNER):
        if user.allowed is False:
            res = await m.reply_text(
                text=f"Hi **{m.from_user.first_name}**\n\n 🛡️ Unfortunately you can't use me\n\n**Contact: 🈲 @{Config.OWNER_USERNAME}** ",
                quote=True,
            )
            return
    else:
        # Ensure owner is always allowed and settings are saved
        if not user.allowed:
            user.allowed = True
            user.set()
            LOGGER.info(f"Owner ({m.from_user.id}) detected and set as allowed.")

    res = await m.reply_text(
        text=f"Hi **{m.from_user.first_name}**\n\n ⚡ I am a file/video merger bot\n\n"
             f"Send /help for instructions.\nSend /settings to configure modes.\n"
             f"Send /dl <url> to download videos.\n\n"
             f"**Owner: 🈲 @{Config.OWNER_USERNAME}** ",
        quote=True,
    )
    del user


@mergeApp.on_message(
    (filters.document | filters.video | filters.audio) & filters.private
)
async def files_handler(c: Client, m: Message):
    user_id = m.from_user.id
    user = UserSettings(user_id, m.from_user.first_name)

    # --- MODIFIED START ---
    # Combined owner check and allowed check
    if m.from_user.id != int(Config.OWNER) and not user.allowed:
        await m.reply_text(
            text=f"Hi **{m.from_user.first_name}**\n\n 🛡️ Unfortunately you can't use me\n\n**Contact: 🈲 @{Config.OWNER_USERNAME}** ",
            quote=True,
        )
        return
    if user.banned: # Added ban check here too
        await m.reply_text(text=f"**Banned User Detected!**\n Contact: 🈲 @{Config.OWNER_USERNAME}", quote=True)
        return
    # --- MODIFIED END ---

    if user.merge_mode == 4: # extract_mode
        await m.reply_text("Bot is in **Extract Mode**. Send /extract replying to a media file to extract streams, or change mode in /settings.", quote=True)
        return

    # --- MODIFIED START ---
    # Use Config.DOWNLOAD_LOCATION and user-specific directory
    user_download_dir = os.path.join(Config.DOWNLOAD_LOCATION, str(user_id))
    input_ = os.path.join(user_download_dir, "input.txt") # Path for concat list file
    if not os.path.isdir(user_download_dir):
        try:
            os.makedirs(user_download_dir)
        except OSError as e:
            LOGGER.error(f"Failed to create download directory {user_download_dir}: {e}")
            await m.reply_text("Error creating user directory. Cannot proceed.")
            return
    # --- MODIFIED END ---

    if os.path.exists(input_):
        await m.reply_text("Sorry Bro,\nAlready One process in Progress!\nDon't Spam.")
        return

    media = m.video or m.document or m.audio
    if media is None: # Check if media is found
        # This case should ideally not happen with the message filters, but check anyway
        LOGGER.warning(f"No media found in message {m.id} from user {user_id}")
        await m.reply_text("Media not found in message.")
        return

    # --- MODIFIED START ---
    # Handle missing file_name robustly
    file_name = getattr(media, 'file_name', None)
    mime_type = getattr(media, 'mime_type', 'application/octet-stream')
    if file_name:
        # Sanitize the original filename
        file_name = sanitize_filename(file_name)
        try:
            currentFileNameExt = file_name.rsplit(sep=".", maxsplit=1)[-1].lower()
        except IndexError:
             # No extension found, try guessing from mime type
             currentFileNameExt = mime_type.split('/')[-1].lower()
             file_name = f"{file_name}.{currentFileNameExt}" # Append guessed ext
             LOGGER.warning(f"No extension in filename '{media.file_name}', guessed '{currentFileNameExt}' from mime '{mime_type}'. New name: {file_name}")
    else:
        # Guess filename and extension if original name is missing
        currentFileNameExt = mime_type.split('/')[-1].lower()
        file_name = f"telegram_media_{int(time.time())}.{currentFileNameExt}"
        LOGGER.warning(f"Original file name missing. Using generated name: {file_name}")
    # --- MODIFIED END ---

    if currentFileNameExt == "conf": # Use == for string comparison
        # --- MODIFIED START ---
        # Ensure the message being replied to is the config file itself
        if m.document and m.document.file_name and m.document.file_name.lower().endswith(".conf"):
            await m.reply_text(
                text="**💾 RClone config file found, Do you want to save it?**",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton("✅ Yes", callback_data=f"rclone_save"),
                            InlineKeyboardButton("❌ No", callback_data="rclone_discard"),
                        ]
                    ]
                ),
                quote=True,
            )
        else:
             await m.reply_text("Received a file with '.conf' extension, but it doesn't seem to be an RClone config sent as a document.")
        # --- MODIFIED END ---
        return

    # Initialize queueDB if needed, including metadata dict
    if queueDB.get(user_id) is None:
        queueDB[user_id] = {"videos": [], "subtitles": [], "audios": [], "metadata": {}}

    # ==================
    # === Merge Mode 1: Video + Video ===
    # ==================
    if user.merge_mode == 1:
        # Check format consistency
        if queueDB[user_id]["videos"]: # If queue is not empty
            first_file_ext = formatDB.get(user_id)
            if first_file_ext and currentFileNameExt != first_file_ext:
                await m.reply_text(
                    f"First you sent a **{first_file_ext.upper()}** file, please send only that type of file for merging.",
                    quote=True,
                )
                return
        else: # First file being added
            formatDB[user_id] = currentFileNameExt

        # Check if it's a valid video extension
        if currentFileNameExt not in VIDEO_EXTENSIONS:
            await m.reply_text(
                f"This file format (**{currentFileNameExt.upper()}**) is not allowed for video merging.\nPlease send only MP4, MKV, or WEBM.",
                quote=True,
            )
            return

        # Check queue length limit
        if len(queueDB[user_id]["videos"]) >= 10:
            markup = await makeButtons(c, m, queueDB) # Show current queue
            await m.reply_text(
                "You have already added the maximum of 10 videos. Press **Merge Now**.",
                reply_markup=InlineKeyboardMarkup(markup) if markup else None,
                quote=True
            )
            return

        editable = await m.reply_text("Processing...", quote=True)

        # Add video to queue
        queueDB[user_id]["videos"].append(m.id)
        # Ensure subtitle list matches video list length (add None for this new video)
        while len(queueDB[user_id]["subtitles"]) < len(queueDB[user_id]["videos"]):
             queueDB[user_id]["subtitles"].append(None)

        # Update status message
        current_queue_len = len(queueDB[user_id]["videos"])
        if current_queue_len == 1:
            MessageText = "**Send me more videos** (up to 10 total) to merge them into a single file."
            buttons = bMaker.makebuttons(["Cancel"], ["cancel"])
        else:
            MessageText = f"Okay, **{current_queue_len}/10** videos added.\nSend more videos or press **Merge Now**."
            buttons = await makeButtons(c, m, queueDB) # This now includes Merge/Cancel

        # Delete previous status message if it exists
        if replyDB.get(user_id):
            try:
                await c.delete_messages(chat_id=m.chat.id, message_ids=replyDB[user_id])
            except Exception as e:
                LOGGER.warning(f"Could not delete previous status message {replyDB[user_id]}: {e}")
            replyDB.pop(user_id, None)

        # Send new status message
        reply_ = await editable.edit(
            text=MessageText,
            reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
        )
        replyDB[user_id] = reply_.id

    # ==================
    # === Merge Mode 2: Video + Audio ===
    # ==================
    elif user.merge_mode == 2:
        editable = await m.reply_text("Processing...", quote=True)

        # If no video added yet, this must be the video
        if not queueDB[user_id]["videos"]:
            if currentFileNameExt not in VIDEO_EXTENSIONS:
                await editable.edit("Please send the **Video file first** for Mode 2 (Video+Audio).")
                return
            queueDB[user_id]["videos"].append(m.id)
            MessageText = "✅ Video added.\nNow, send all the **Audio files** you want to add to this video."
            buttons = bMaker.makebuttons(["Cancel"], ["cancel"])
            reply_ = await editable.edit(text=MessageText, reply_markup=InlineKeyboardMarkup(buttons))
            replyDB[user_id] = reply_.id
            return

        # If video exists, check if this is a valid audio file
        elif currentFileNameExt in AUDIO_EXTENSIONS:
            queueDB[user_id]["audios"].append(m.id)
            MessageText = f"Okay, **{len(queueDB[user_id]['audios'])}** audio track(s) added.\nSend more audios or press **Merge Now**."
            buttons = await makeButtons(c, m, queueDB)

            # Delete previous status message
            if replyDB.get(user_id):
                try:
                    await c.delete_messages(chat_id=m.chat.id, message_ids=replyDB[user_id])
                except Exception as e:
                    LOGGER.warning(f"Could not delete previous status message {replyDB[user_id]}: {e}")
                replyDB.pop(user_id, None)

            reply_ = await editable.edit(
                text=MessageText,
                reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
            )
            replyDB[user_id] = reply_.id
            return

        # If video exists but file is not audio
        else:
            await editable.edit(f"This file type (**{currentFileNameExt.upper()}**) is not a valid AUDIO.\nPlease send only audio files (e.g., MP3, M4A, AAC) after the initial video.")
            return

    # ==================
    # === Merge Mode 3: Video + Subtitle ===
    # ==================
    elif user.merge_mode == 3:
        editable = await m.reply_text("Processing...", quote=True)

        # If no video added yet, this must be the video
        if not queueDB[user_id]["videos"]:
            if currentFileNameExt not in VIDEO_EXTENSIONS:
                await editable.edit("Please send the **Video file first** for Mode 3 (Video+Subtitle).")
                return
            queueDB[user_id]["videos"].append(m.id)
            MessageText = "✅ Video added.\nNow, send all the **Subtitle files** (SRT, ASS) you want to add."
            buttons = bMaker.makebuttons(["Cancel"], ["cancel"])
            reply_ = await editable.edit(text=MessageText, reply_markup=InlineKeyboardMarkup(buttons))
            replyDB[user_id] = reply_.id
            return

        # If video exists, check if this is a valid subtitle file
        elif currentFileNameExt in SUBTITLE_EXTENSIONS:
            queueDB[user_id]["subtitles"].append(m.id)
            # Count valid subs added so far
            valid_subs = len([s for s in queueDB[user_id]["subtitles"] if s is not None])
            MessageText = f"Okay, **{valid_subs}** subtitle track(s) added.\nSend more subtitles or press **Merge Now**."
            buttons = await makeButtons(c, m, queueDB)

            # Delete previous status message
            if replyDB.get(user_id):
                try:
                    await c.delete_messages(chat_id=m.chat.id, message_ids=replyDB[user_id])
                except Exception as e:
                    LOGGER.warning(f"Could not delete previous status message {replyDB[user_id]}: {e}")
                replyDB.pop(user_id, None)

            reply_ = await editable.edit(
                text=MessageText,
                reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
            )
            replyDB[user_id] = reply_.id
            return

        # If video exists but file is not subtitle
        else:
            await editable.edit(f"This file type (**{currentFileNameExt.upper()}**) is not a valid SUBTITLE.\nPlease send only subtitle files (e.g., SRT, ASS) after the initial video.")
            return


@mergeApp.on_message(filters.photo & filters.private)
async def photo_handler(c: Client, m: Message):
    user = UserSettings(m.chat.id, m.from_user.first_name)
    # --- MODIFIED START ---
    # Combined owner check and allowed check
    if m.from_user.id != int(Config.OWNER) and not user.allowed:
        await m.reply_text(
            text=f"Hi **{m.from_user.first_name}**\n\n 🛡️ Unfortunately you can't use me\n\n**Contact: 🈲 @{Config.OWNER_USERNAME}** ",
            quote=True,
        )
        del user
        return
    if user.banned: # Added ban check
        await m.reply_text(text=f"**Banned User Detected!**\n Contact: 🈲 @{Config.OWNER_USERNAME}", quote=True)
        del user
        return
    # --- MODIFIED END ---

    thumbnail = m.photo.file_id
    msg = await m.reply_text("Saving Thumbnail. . . .", quote=True)
    user.thumbnail = thumbnail
    user.set()
    # await database.saveThumb(m.from_user.id, thumbnail) # This is handled by user.set() now

    # --- MODIFIED START ---
    # Use Config.DOWNLOAD_LOCATION and user-specific directory
    user_download_dir = os.path.join(Config.DOWNLOAD_LOCATION, str(m.from_user.id))
    if not os.path.isdir(user_download_dir):
        try:
            os.makedirs(user_download_dir)
        except OSError as e:
            LOGGER.error(f"Failed to create directory {user_download_dir} for thumbnail: {e}")
            await msg.edit_text("❌ Error saving thumbnail: Could not create directory.")
            del user
            return
    LOCATION = os.path.join(user_download_dir, f"{m.from_user.id}_thumb.jpg")
    # --- MODIFIED END ---

    try: # Add try-except for download
        await c.download_media(message=m, file_name=LOCATION)
        await msg.edit_text(text="✅ Custom Thumbnail Saved!")
    except Exception as e:
        LOGGER.error(f"Failed to download/save thumbnail for user {m.from_user.id}: {e}")
        await msg.edit_text(text="❌ Error saving thumbnail.")

    del user


@mergeApp.on_message(filters.command(["extract"]) & filters.private)
async def media_extracter(c: Client, m: Message):
    user = UserSettings(uid=m.from_user.id, name=m.from_user.first_name)

    # --- MODIFIED START ---
    # Combined owner check and allowed check
    if m.from_user.id != int(Config.OWNER) and not user.allowed:
        await m.reply_text("You are not allowed to use this command.", quote=True)
        return
    if user.banned: # Added ban check
        await m.reply_text(text=f"**Banned User Detected!**\n Contact: 🈲 @{Config.OWNER_USERNAME}", quote=True)
        return

    # Check if mode is set to Extract
    if user.merge_mode != 4:
         await m.reply(
             text="Change settings and set mode to **Extract**\nthen use /extract command by replying to a media file."
         )
         return
    # --- MODIFIED END ---

    if m.reply_to_message is None:
        await m.reply(text="Reply /extract to a video or document file")
        return

    rmess = m.reply_to_message
    if rmess.video or rmess.document:
        media = rmess.video or rmess.document
        mid=rmess.id
        # --- MODIFIED START ---
        # Handle case where file_name might be None
        file_name = getattr(media, 'file_name', None)
        if file_name is None:
            file_name = f"media_{mid}" # Fallback name
            LOGGER.warning(f"File name not found for media {mid} in extract command, using fallback.")
        # --- MODIFIED END ---

        markup = bMaker.makebuttons(
            set1=["Audio", "Subtitle", "All", "Cancel"], # Added "All"
            set2=[f"extract_audio_{mid}", f"extract_subtitle_{mid}", f"extract_all_{mid}", 'cancel'], # Added "extract_all"
            isCallback=True,
            rows=2,
        )
        await m.reply(
            text="Choose from below what you want to extract?",
            quote=True,
            reply_markup=InlineKeyboardMarkup(markup),
        )
    else:
        await m.reply("Please reply to a video or document file containing streams.")


@mergeApp.on_message(filters.command(["help"]) & filters.private)
async def help_msg(c: Client, m: Message):
    # --- MODIFIED START ---
    # Check if user is allowed
    user = UserSettings(m.from_user.id, m.from_user.first_name)
    if m.from_user.id != int(Config.OWNER) and not user.allowed:
         await m.reply_text(f"Hi **{m.from_user.first_name}**\n\n 🛡️ Please /login first.", quote=True)
         return
    # --- MODIFIED END ---
    await m.reply_text(
        text="""**Follow These Steps for Merging:**

1) Use /settings to choose your merge mode (Video+Video, Video+Audio, Video+Subtitle).
2) Send the video(s), audio(s), or subtitle(s) according to the selected mode.
3) Send /savethumb replying to a photo to set a custom thumbnail (optional).
4) Once all files are sent, press the **Merge Now** button.
5) Choose upload destination (Telegram or Drive - requires Rclone setup).
6) Choose upload format (Video or File).
7) Choose whether to rename the output file.
8) If **Edit Metadata** is enabled in /settings, you'll be prompted for Title, Description, Tags.

**Other Commands:**
/dl <url> - Download video from URL.
/extract - Reply to a media file to extract audio/subtitles (set mode to Extract in /settings).
/showthumbnail - View your saved thumbnail.
/deletethumbnail - Remove your saved thumbnail.
/settings - Configure merge mode and metadata editing.
/about - Information about the bot.
/log - (Owner) Get bot logs.
/stats - (Owner/Allowed) View bot statistics.
/broadcast - (Owner) Send message to all users.
/ban <user_id> - (Owner) Ban a user.
/unban <user_id> - (Owner) Unban a user.
/login <password> - Access the bot if password protected.""",
        quote=True,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Close 🔐", callback_data="close")]]
        ),
    )


@mergeApp.on_message(filters.command(["about"]) & filters.private)
async def about_handler(c: Client, m: Message):
    # --- MODIFIED START ---
    # Check if user is allowed
    user = UserSettings(m.from_user.id, m.from_user.first_name)
    if m.from_user.id != int(Config.OWNER) and not user.allowed:
         await m.reply_text(f"Hi **{m.from_user.first_name}**\n\n 🛡️ Please /login first.", quote=True)
         return
    # --- MODIFIED END ---
    await m.reply_text(
        text="""
**ᴡʜᴀᴛ's ɴᴇᴡ:**
👨‍💻 ʙᴀɴ/ᴜɴʙᴀɴ ᴜsᴇʀs
👨‍💻 ᴇxᴛʀᴀᴄᴛ ᴀʟʟ ᴀᴜᴅɪᴏs ᴀɴᴅ sᴜʙᴛɪᴛʟᴇs ғʀᴏᴍ ᴛᴇʟᴇɢʀᴀᴍ ᴍᴇᴅɪᴀ
👨‍💻 ᴍᴇʀɢᴇ ᴠɪᴅᴇᴏ + ᴀᴜᴅɪᴏ
👨‍💻 ᴍᴇʀɢᴇ ᴠɪᴅᴇᴏ + sᴜʙᴛɪᴛʟᴇs
👨‍💻 ᴜᴘʟᴏᴀᴅ ᴛᴏ ᴅʀɪᴠᴇ ᴜsɪɴɢ ʏᴏᴜʀ ᴏᴡɴ ʀᴄʟᴏɴᴇ ᴄᴏɴғɪɢ
👨‍💻 ᴍᴇʀɢᴇᴅ ᴠɪᴅᴇᴏ ᴘʀᴇsᴇʀᴠᴇs ᴀʟʟ sᴛʀᴇᴀᴍs ᴏғ ᴛʜᴇ ғɪʀsᴛ ᴠɪᴅᴇᴏ ʏᴏᴜ sᴇɴᴅ (ɪ.ᴇ ᴀʟʟ ᴀᴜᴅɪᴏᴛʀᴀᴄᴋs/sᴜʙᴛɪᴛʟᴇs)
👨‍💻 **ɴᴇᴡ:** ᴅɪʀᴇᴄᴛ ᴠɪᴅᴇᴏ ᴅᴏᴡɴʟᴏᴀᴅ ғʀᴏᴍ ᴜʀʟs (ᴜsɪɴɢ /dl)
👨‍💻 **ɴᴇᴡ:** sᴍᴀʀᴛ ғɪʟᴇ ɴᴀᴍɪɴɢ (ᴘʀᴇsᴇʀᴠᴇs ᴛɪᴛʟᴇ, ʜᴀɴᴅʟᴇs sᴘᴇᴄɪᴀʟ ᴄʜᴀʀs & ᴅᴜᴘʟɪᴄᴀᴛᴇs)
👨‍💻 **ɴᴇᴡ:** ᴇᴅɪᴛ ᴍᴇᴛᴀᴅᴀᴛᴀ (ᴛɪᴛʟᴇ, ᴅᴇsᴄʀɪᴘᴛɪᴏɴ, ᴛᴀɢs) ᴀғᴛᴇʀ ᴍᴇʀɢɪɴɢ (ᴠɪᴀ /settings)
➖➖➖➖➖➖➖➖➖➖➖➖➖
**ғᴇᴀᴛᴜʀᴇs**
🔰 ᴍᴇʀɢᴇ ᴜᴘᴛᴏ 𝟷𝟶 ᴠɪᴅᴇᴏ ɪɴ ᴏɴᴇ
🔰 ᴜᴘʟᴏᴀᴅ ᴀs ᴅᴏᴄᴜᴍᴇɴᴛs/ᴠɪᴅᴇᴏ
🔰 ᴄᴜsᴛᴏᴍs ᴛʜᴜᴍʙɴᴀɪʟ sᴜᴘᴘᴏʀᴛ
🔰 ᴜsᴇʀs ᴄᴀɴ ʟᴏɢɪɴ ᴛᴏ ʙᴏᴛ ᴜsɪɴɢ ᴘᴀssᴡᴏʀᴅ
🔰 ᴏᴡɴᴇʀ ᴄᴀɴ ʙʀᴏᴀᴅᴄᴀsᴛ ᴍᴇssᴀɢᴇ ᴛᴏ ᴀʟʟ ᴜsᴇʀs
		""",
        quote=True,
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("👨‍💻Developer👨‍💻", url="https://t.me/yashoswalyo")],
                [
                    InlineKeyboardButton(
                        "🏘Source Code🏘", url="https://github.com/yashoswalyo/MERGE-BOT"
                    ),
                    InlineKeyboardButton(
                        "🤔Deployed By🤔", url=f"https://t.me/{Config.OWNER_USERNAME}"
                    ),
                ],
                [InlineKeyboardButton("Close 🔐", callback_data="close")],
            ]
        ),
    )


@mergeApp.on_message(
    filters.command(["savethumb", "setthumb", "savethumbnail"]) & filters.private
)
async def save_thumbnail(c: Client, m: Message):
    # --- MODIFIED START ---
    # Check if user is allowed
    user = UserSettings(m.from_user.id, m.from_user.first_name)
    if m.from_user.id != int(Config.OWNER) and not user.allowed:
         await m.reply_text(f"Hi **{m.from_user.first_name}**\n\n 🛡️ Please /login first.", quote=True)
         return
    if user.banned: # Added ban check
        await m.reply_text(text=f"**Banned User Detected!**\n Contact: 🈲 @{Config.OWNER_USERNAME}", quote=True)
        return
    # --- MODIFIED END ---

    if m.reply_to_message:
        if m.reply_to_message.photo:
            await photo_handler(c, m.reply_to_message) # Call the existing handler
        else:
            await m.reply(text="Please reply to a valid photo message.", quote=True)
    else:
        await m.reply(text="Please reply to a photo message to save it as thumbnail.", quote=True)
    return


@mergeApp.on_message(filters.command(["showthumbnail"]) & filters.private)
async def show_thumbnail(c: Client, m: Message):
    # --- MODIFIED START ---
    # Check if user is allowed
    user = UserSettings(m.from_user.id, m.from_user.first_name)
    if m.from_user.id != int(Config.OWNER) and not user.allowed:
         await m.reply_text(f"Hi **{m.from_user.first_name}**\n\n 🛡️ Please /login first.", quote=True)
         return
    if user.banned: # Added ban check
        await m.reply_text(text=f"**Banned User Detected!**\n Contact: 🈲 @{Config.OWNER_USERNAME}", quote=True)
        return
    # --- MODIFIED END ---
    try:
        # user = UserSettings(m.from_user.id, m.from_user.first_name) # Already got user settings
        thumb_id = user.thumbnail
        # --- MODIFIED START ---
        # Use Config.DOWNLOAD_LOCATION and user-specific directory
        user_download_dir = os.path.join(Config.DOWNLOAD_LOCATION, str(m.from_user.id))
        LOCATION = os.path.join(user_download_dir, f"{m.from_user.id}_thumb.jpg")
        # --- MODIFIED END ---

        if thumb_id is None:
             await m.reply_text(text="❌ Custom thumbnail not set.", quote=True)
        elif os.path.exists(LOCATION):
            await m.reply_photo(
                photo=LOCATION, caption="🖼️ Your currently saved custom thumbnail", quote=True
            )
        else:
            # If file doesn't exist locally, try downloading it from file_id
            await m.reply_text("⏳ Thumbnail found in settings, attempting to download...", quote=True)
            try:
                await c.download_media(message=str(thumb_id), file_name=LOCATION)
                await m.reply_photo(
                    photo=LOCATION, caption="🖼️ Your currently saved custom thumbnail", quote=True
                )
            except Exception as dl_err:
                LOGGER.error(f"Failed to download saved thumb ({thumb_id}) for user {m.from_user.id}: {dl_err}")
                await m.reply_text(text="❌ Custom thumbnail found in settings, but failed to download it.", quote=True)
                # Optionally clear the invalid thumb_id from settings
                # user.thumbnail = None
                # user.set()
        del user
    except Exception as err:
        LOGGER.error(f"Show thumbnail error for user {m.from_user.id}: {err}") # Log the actual error
        await m.reply_text(text="❌ An error occurred while trying to show the thumbnail.", quote=True)


@mergeApp.on_message(filters.command(["deletethumbnail"]) & filters.private)
async def delete_thumbnail(c: Client, m: Message):
    # --- MODIFIED START ---
    # Check if user is allowed
    user = UserSettings(m.from_user.id, m.from_user.first_name)
    if m.from_user.id != int(Config.OWNER) and not user.allowed:
         await m.reply_text(f"Hi **{m.from_user.first_name}**\n\n 🛡️ Please /login first.", quote=True)
         return
    if user.banned: # Added ban check
        await m.reply_text(text=f"**Banned User Detected!**\n Contact: 🈲 @{Config.OWNER_USERNAME}", quote=True)
        return
    # --- MODIFIED END ---
    try:
        # user = UserSettings(m.from_user.id, m.from_user.first_name) # Already got user settings
        if user.thumbnail is None:
             await m.reply_text("❌ You don't have a custom thumbnail set.", quote=True)
             return

        user.thumbnail = None
        user.set() # Update database

        # --- MODIFIED START ---
        # Use Config.DOWNLOAD_LOCATION and user-specific directory
        user_download_dir = os.path.join(Config.DOWNLOAD_LOCATION, str(m.from_user.id))
        location = os.path.join(user_download_dir, f"{m.from_user.id}_thumb.jpg")
        if os.path.exists(location): # Check existence before removing
            try:
                os.remove(location)
            except OSError as e:
                 LOGGER.error(f"Error removing thumbnail file {location}: {e}")
        # --- MODIFIED END ---

        await m.reply_text("✅ Custom thumbnail deleted successfully.", quote=True)
        del user
    except Exception as err:
        LOGGER.error(f"Delete thumbnail error for user {m.from_user.id}: {err}") # Log the error
        await m.reply_text(text="❌ An error occurred while deleting the thumbnail.", quote=True)

@mergeApp.on_message(filters.command(["ban","unban"]) & filters.private)
async def ban_user(c:Client,m:Message):
    # --- MODIFIED START ---
    # Ensure owner is allowed to use the bot regardless of DB status
    if m.from_user.id != int(Config.OWNER):
        await m.reply_text("You are not authorized to use this command.", quote=True)
        return

    command_parts = m.text.split(' ', 2) # Split max 2 times
    incoming = command_parts[0].lower() # Use lower case for command check
    # --- MODIFIED END ---

    if incoming == '/ban':
        # --- MODIFIED START --- removed redundant owner check ---
        try:
            abuser_id = int(command_parts[1]) # Use command_parts
            # --- MODIFIED END ---
            if abuser_id == int(Config.OWNER):
                await m.reply_text("I can't ban you master,\nPlease don't abandon me. ",quote=True)
            else:
                try:
                    user_obj: User = await c.get_users(abuser_id)
                    udata  = UserSettings(uid=abuser_id,name=user_obj.first_name)
                    udata.banned=True
                    udata.allowed=False # Ensure banned users are not allowed
                    udata.set()
                    await m.reply_text(f"Pooof, {user_obj.mention} (`{abuser_id}`) has been **BANNED**",quote=True) # Use mention
                    acknowledgement = f"""
Dear {user_obj.first_name},
Your account has been **banned** by the administrator.

While the account is banned, you will not be able to use this bot (merging, extracting, downloading, etc.).

Contact @{Config.OWNER_USERNAME} if you believe this is a mistake."""
                    try:
                        await c.send_message(
                            chat_id=abuser_id,
                            text=acknowledgement
                        )
                    except (UserIsBlocked, InputUserDeactivated, PeerIdInvalid):
                        await m.reply_text("Acknowledgement not sent (User blocked bot, is deactivated, or ID invalid).", quote=True)
                    except Exception as e:
                        await m.reply_text(f"An error occured while sending acknowledgement\n\n`{e}`",quote=True)
                        LOGGER.error(f"Error sending ban acknowledgement to {abuser_id}: {e}")
                except ValueError:
                    await m.reply_text(f"Invalid User ID: {command_parts[1]}", quote=True)
                except Exception as e:
                    # --- MODIFIED START ---
                    await m.reply_text(f"Could not ban user `{command_parts[1]}`. Error: {e}", quote=True)
                    # --- MODIFIED END ---
                    LOGGER.error(f"Error banning user {command_parts[1]}: {e}")
        except IndexError: # Catch specific errors
            await m.reply_text("**Command:**\n  `/ban <user_id>`\n\n**Usage:**\n  `user_id`: Numerical User ID of the user",quote=True,parse_mode=enums.parse_mode.ParseMode.MARKDOWN)
        # --- MODIFIED START --- removed redundant else block ---
        return

    elif incoming == '/unban':
        # --- MODIFIED START --- removed redundant owner check ---
        try:
            abuser_id = int(command_parts[1]) # Use command_parts
            # --- MODIFIED END ---
            if abuser_id == int(Config.OWNER):
                await m.reply_text("Master, you cannot be banned in the first place!",quote=True) # Adjusted message
            else:
                try:
                    user_obj: User = await c.get_users(abuser_id)
                    udata  = UserSettings(uid=abuser_id,name=user_obj.first_name)
                    if not udata.banned:
                         await m.reply_text(f"{user_obj.mention} (`{abuser_id}`) is not currently banned.", quote=True)
                         return

                    udata.banned=False
                    # --- MODIFIED START ---
                    # Decide if unbanning should automatically allow, or if they need to login again
                    # Let's keep them disallowed, they need to /login again if required.
                    # udata.allowed=True
                    # --- MODIFIED END ---
                    udata.set()
                    await m.reply_text(f"Pooof, {user_obj.mention} (`{abuser_id}`) has been **UN_BANNED**",quote=True) # Use mention
                    release_notice = f"""
Good news {user_obj.first_name}, the ban has been lifted on your account. You should be able to use the bot again now (you might need to /login if a password is set)."""
                    try:
                        await c.send_message(
                            chat_id=abuser_id,
                            text=release_notice
                        )
                    except (UserIsBlocked, InputUserDeactivated, PeerIdInvalid):
                         await m.reply_text("Release notice not sent (User blocked bot, is deactivated, or ID invalid).", quote=True)
                    except Exception as e:
                        await m.reply_text(f"An error occured while sending release notice\n\n`{e}`",quote=True)
                        LOGGER.error(f"Error sending unban notice to {abuser_id}: {e}")
                except ValueError:
                     await m.reply_text(f"Invalid User ID: {command_parts[1]}", quote=True)
                except Exception as e:
                    # --- MODIFIED START ---
                    await m.reply_text(f"Could not unban user `{command_parts[1]}`. Error: {e}", quote=True)
                     # --- MODIFIED END ---
                    LOGGER.error(f"Error unbanning user {command_parts[1]}: {e}")
        except IndexError: # Catch specific errors
            await m.reply_text("**Command:**\n  `/unban <user_id>`\n\n**Usage:**\n  `user_id`: Numerical User ID of the user",quote=True,parse_mode=enums.parse_mode.ParseMode.MARKDOWN)
        # --- MODIFIED START --- removed redundant else block ---
        return

# --- MODIFIED START ---
# Helper function for yt-dlp progress hook
def ytdl_progress_hook(d, bot: Client, pyrogram_progress: Progress, message: Message, start_time):
    """Updates Pyrogram progress message based on yt-dlp progress."""
    if d['status'] == 'downloading':
        total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
        downloaded_bytes = d.get('downloaded_bytes')
        # Ensure values are valid numbers before proceeding
        if isinstance(total_bytes, (int, float)) and isinstance(downloaded_bytes, (int, float)):
            # Use pyrogram progress function within the event loop
            try:
                # Schedule the coroutine to run in the bot's event loop
                asyncio.run_coroutine_threadsafe(
                    pyrogram_progress.progress_for_pyrogram(
                        current=downloaded_bytes,
                        total=total_bytes,
                        ud_type=f"Downloading video...",
                        start=start_time,
                        filesize=get_readable_file_size(total_bytes) # Add readable total size
                    ),
                    bot.loop # Pass the bot's event loop
                )
            except Exception as e:
                 # Log errors without stopping the download if the hook fails
                 LOGGER.warning(f"Error scheduling/running progress hook: {e}")
        # else:
        #      LOGGER.debug(f"Skipping progress update due to invalid byte values: total={total_bytes}, downloaded={downloaded_bytes}")

    elif d['status'] == 'finished':
        LOGGER.info(f"yt-dlp download finished: {d.get('filename')}")
        # Optionally, send a final 100% progress update
        total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
        if isinstance(total_bytes, (int, float)) and total_bytes > 0:
             try:
                 asyncio.run_coroutine_threadsafe(
                     pyrogram_progress.progress_for_pyrogram(
                         current=total_bytes,
                         total=total_bytes,
                         ud_type=f"Download complete.",
                         start=start_time,
                         filesize=get_readable_file_size(total_bytes)
                     ),
                     bot.loop
                 )
             except Exception as e:
                 LOGGER.warning(f"Error scheduling/running final progress hook: {e}")

    elif d['status'] == 'error':
        LOGGER.error(f"yt-dlp error during download: {d.get('filename')}, Error: {d.get('error', 'Unknown error')}")


# Direct Download Command (/dl)
@mergeApp.on_message(filters.command(["dl"]) & filters.private)
async def download_handler(c: Client, m: Message):
    user = UserSettings(m.from_user.id, m.from_user.first_name)
    # Combined checks
    if m.from_user.id != int(Config.OWNER) and not user.allowed:
        await m.reply_text(f"Hi **{m.from_user.first_name}**\n\n 🛡️ Unfortunately you can't use me\n\n**Contact: 🈲 @{Config.OWNER_USERNAME}** ", quote=True)
        return
    if user.banned:
        await m.reply_text(text=f"**Banned User Detected!**\n Contact: 🈲 @{Config.OWNER_USERNAME}", quote=True)
        return

    if len(m.command) < 2:
        await m.reply_text("Please provide a video URL after the command.\nUsage: `/dl <video_url>`")
        return

    url = m.command[1].strip()
    # Basic URL validation
    if not re.match(r'https?://\S+', url):
        await m.reply_text("Invalid URL provided. Please enter a valid HTTP/HTTPS URL.")
        return

    editable = await m.reply_text("🔄 Processing URL...", quote=True)
    user_download_dir = os.path.join(Config.DOWNLOAD_LOCATION, str(m.from_user.id))
    if not os.path.isdir(user_download_dir):
        try:
            os.makedirs(user_download_dir)
        except OSError as e:
            LOGGER.error(f"Failed to create download dir {user_download_dir} for /dl: {e}")
            await editable.edit_text("❌ Internal error: Could not create download directory.")
            return

    start_time = time.time()
    prog = Progress(m.from_user.id, c, editable)
    downloaded_path = None
    final_download_path = None # Initialize to prevent UnboundLocalError

    # --- yt-dlp Download ---
    try:
        LOGGER.info(f"Attempting download with yt-dlp for URL: {url}")
        ydl_opts = {
            'format': 'bestvideo[ext=mp4][filesize<=2000M]+bestaudio[ext=m4a]/best[ext=mp4][filesize<=2000M]/bestvideo[filesize<=2000M]+bestaudio/best[filesize<=2000M]', # Prefer mp4, limit size for TG free tier
            'outtmpl': os.path.join(user_download_dir, '%(title)s [%(id)s].%(ext)s'), # Include ID for uniqueness
            'noplaylist': True,
            'progress_hooks': [lambda d: ytdl_progress_hook(d, c, prog, editable, start_time)],
            'nocheckcertificate': True,
            'quiet': True,
            'no_warnings': True,
            'postprocessors': [{ # Embed metadata if possible
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }],
            'merge_output_format': 'mp4', # Merge to mp4 if separate streams downloaded
            # Add User-Agent if needed
            # 'http_headers': {'User-Agent': 'Mozilla/5.0 ...'}
        }
        # --- MODIFIED START ---
        # Handle potential premium upload size limit
        if Config.IS_PREMIUM:
             ydl_opts['format'] = ydl_opts['format'].replace('2000M', '4000M') # Increase limit for premium
        # --- MODIFIED END ---


        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # Run extract_info in a separate thread to avoid blocking asyncio loop
                info_dict = await asyncio.to_thread(ydl.extract_info, url, download=False)

                original_title = info_dict.get('title', 'video')
                video_id = info_dict.get('id', str(int(time.time()))) # Use timestamp as fallback id
                ext = info_dict.get('ext', 'mp4')
                filesize = info_dict.get('filesize') or info_dict.get('filesize_approx')

                # Check filesize before downloading (optional, extract_info might already do this based on format selection)
                if filesize:
                    limit = 4000 * 1024 * 1024 if Config.IS_PREMIUM else 2000 * 1024 * 1024
                    if filesize > limit:
                        await editable.edit_text(f"❌ Video is too large ({get_readable_file_size(filesize)}). Limit is {get_readable_file_size(limit)}.")
                        return

                # Smart Naming
                safe_title = sanitize_filename(original_title)
                temp_filename = f"{safe_title} [{video_id}].{ext}"
                download_path_template = os.path.join(user_download_dir, temp_filename)

                # yt-dlp's outtmpl handles duplicates if we don't interfere, but let's keep our handler just in case
                # final_download_path = handle_duplicate_filename(download_path_template)
                # Use the path yt-dlp intends to use directly
                final_download_path = ydl.prepare_filename(info_dict)

                # Ensure the final path is within the user's directory (security check)
                if not final_download_path.startswith(user_download_dir):
                     LOGGER.error(f"Security Alert: yt-dlp prepared filename outside user directory: {final_download_path}")
                     await editable.edit_text("❌ Security error during filename preparation.")
                     return

                await editable.edit_text(f"📥 Starting download: `{os.path.basename(final_download_path)}`")
                # Run download in a separate thread
                await asyncio.to_thread(ydl.download, [url])

                # Check if the file actually exists after download attempt
                if os.path.exists(final_download_path):
                    downloaded_path = final_download_path
                    LOGGER.info(f"yt-dlp download successful: {downloaded_path}")
                else:
                    # This might happen if yt-dlp errors out but doesn't raise DownloadError
                    LOGGER.warning(f"yt-dlp finished for {url}, but output file '{final_download_path}' not found.")
                    # Attempt fallback without explicit error message yet
                    await editable.edit_text(f"⚠️ yt-dlp finished, but file not found. Trying fallback...")
                    await asyncio.sleep(2)


            except yt_dlp.utils.DownloadError as ytdl_err:
                error_msg = str(ytdl_err)
                LOGGER.warning(f"yt-dlp failed for {url}: {error_msg}")
                # Provide more specific feedback if possible
                if "Unsupported URL" in error_msg:
                     await editable.edit_text(f"❌ Unsupported URL: {url}")
                     return
                elif "Video unavailable" in error_msg:
                     await editable.edit_text(f"❌ Video unavailable.")
                     return
                elif "Private video" in error_msg:
                    await editable.edit_text(f"❌ This is a private video.")
                    return
                elif "login" in error_msg.lower():
                     await editable.edit_text(f"❌ This video may require login.")
                     return
                # Generic fallback message
                await editable.edit_text(f"⚠️ yt-dlp failed. Trying fallback download...\n`{error_msg[:150]}`")
                await asyncio.sleep(2)
            except Exception as e:
                LOGGER.error(f"Unexpected yt-dlp error for {url}: {e}", exc_info=True)
                await editable.edit_text(f"❌ Unexpected error during yt-dlp processing: {type(e).__name__}")
                return

    except Exception as e:
         LOGGER.error(f"Error setting up yt-dlp for {url}: {e}", exc_info=True)
         await editable.edit_text(f"❌ Error initializing downloader: {type(e).__name__}")
         return


    # --- aiohttp Fallback Download ---
    if not downloaded_path:
        try:
            LOGGER.info(f"Attempting fallback download with aiohttp for URL: {url}")
            session = await get_aio_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=None), allow_redirects=True) as response: # Allow redirects
                response.raise_for_status() # Raise HTTP errors
                total_size = int(response.headers.get('content-length', 0))

                # Determine filename (more robustly)
                content_disposition = response.headers.get('content-disposition')
                original_filename = None
                if content_disposition:
                    filenames = re.findall('filename="?(.+)"?', content_disposition)
                    if filenames:
                        original_filename = filenames[0]

                if not original_filename:
                     # Use URL path component as fallback
                     original_filename = os.path.basename(response.url.path) or f"download_{int(time.time())}"

                safe_filename_base = sanitize_filename(os.path.splitext(original_filename)[0])

                # Guess extension from Content-Type or URL
                content_type = response.headers.get('content-type')
                guessed_ext = '.mp4' # Default
                if content_type and '/' in content_type:
                    mime_map = {'video/mp4': '.mp4', 'video/webm': '.webm', 'video/quicktime': '.mov', 'video/x-matroska': '.mkv', 'application/octet-stream': ''}
                    mime_main = content_type.split(';')[0].strip()
                    guessed_ext = mime_map.get(mime_main, '') # Get extension or empty string

                if not guessed_ext and '.' in original_filename: # Fallback to URL extension
                     guessed_ext = os.path.splitext(original_filename)[1]

                if not guessed_ext: guessed_ext = '.mp4' # Final fallback

                temp_filename = f"{safe_filename_base}{guessed_ext}"
                download_path_template = os.path.join(user_download_dir, temp_filename)
                final_download_path = handle_duplicate_filename(download_path_template)

                await editable.edit_text(f"📥 Starting fallback download: `{os.path.basename(final_download_path)}`")
                downloaded_bytes = 0
                start_time_aio = time.time() # Reset start time for aiohttp progress
                last_update_time = 0

                with open(final_download_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024): # Read in 1MB chunks
                        if not chunk: # Handle empty chunks if the connection breaks
                            break
                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        # Throttle progress updates
                        current_time = time.time()
                        if current_time - last_update_time > 2: # Update every 2 seconds
                            await prog.progress_for_pyrogram(
                                current=downloaded_bytes,
                                total=total_size,
                                ud_type=f"Downloading (fallback)...",
                                start=start_time_aio,
                                filesize=get_readable_file_size(total_size) if total_size else "Unknown size"
                            )
                            last_update_time = current_time

                # Final progress update
                await prog.progress_for_pyrogram(
                    current=downloaded_bytes,
                    total=total_size if total_size else downloaded_bytes, # Use downloaded if total unknown
                    ud_type=f"Download complete (fallback).",
                    start=start_time_aio,
                    filesize=get_readable_file_size(total_size) if total_size else get_readable_file_size(downloaded_bytes)
                )

                if os.path.exists(final_download_path) and downloaded_bytes > 0:
                     downloaded_path = final_download_path
                     LOGGER.info(f"aiohttp download successful: {downloaded_path}")
                else:
                     LOGGER.error(f"aiohttp download finished for {url}, but file is missing or empty: {final_download_path}")
                     await editable.edit_text("❌ Fallback download failed (file missing or empty).")
                     if os.path.exists(final_download_path): os.remove(final_download_path) # Clean up


        except aiohttp.ClientResponseError as http_err:
             LOGGER.error(f"aiohttp download failed for {url}: HTTP {http_err.status} {http_err.message}")
             await editable.edit_text(f"❌ Download Failed (HTTP {http_err.status}).\nBoth yt-dlp and fallback failed.")
             if 'final_download_path' in locals() and os.path.exists(final_download_path): os.remove(final_download_path)
             return
        except aiohttp.ClientError as aio_err:
            LOGGER.error(f"aiohttp download failed for {url}: {aio_err}")
            await editable.edit_text(f"❌ Download Failed.\nBoth yt-dlp and fallback failed.\nError: `{aio_err}`")
            if 'final_download_path' in locals() and os.path.exists(final_download_path): os.remove(final_download_path)
            return
        except Exception as e:
            LOGGER.error(f"Unexpected aiohttp error for {url}: {e}", exc_info=True)
            await editable.edit_text(f"❌ Unexpected error during fallback download: {type(e).__name__}")
            if 'final_download_path' in locals() and os.path.exists(final_download_path): os.remove(final_download_path)
            return

    # --- Uploading ---
    if downloaded_path and os.path.exists(downloaded_path):
        await editable.edit_text("⬆️ Uploading video...")
        final_name = os.path.basename(downloaded_path)
        file_size = os.path.getsize(downloaded_path)

        # Check size limit again before upload
        limit = 4000 * 1024 * 1024 if Config.IS_PREMIUM else 2000 * 1024 * 1024
        if file_size > limit:
             await editable.edit_text(f"❌ Downloaded file is too large ({get_readable_file_size(file_size)}) for Telegram upload. Limit: {get_readable_file_size(limit)}.")
             if os.path.exists(downloaded_path): os.remove(downloaded_path)
             return

        upload_client = userBot if Config.USER_SESSION_STRING and userBot else c # Use userbot if available
        log_chat_id = int(LOGCHANNEL) if LOGCHANNEL else None

        try:
            upload_prog = Progress(m.from_user.id, upload_client, editable)
            c_time = time.time()
            # Attempt to get duration and dimensions for video upload
            duration, width, height, video_thumbnail = 0, 0, 0, None
            try:
                 metadata = extractMetadata(createParser(downloaded_path))
                 if metadata:
                      duration = metadata.get("duration").seconds if metadata.has("duration") else 0
                      width = metadata.get("width") if metadata.has("width") else 0
                      height = metadata.get("height") if metadata.has("height") else 0
                 if duration > 0:
                      thumb_path = await take_screen_shot(downloaded_path, user_download_dir, duration / 2)
                      if thumb_path and os.path.exists(thumb_path):
                           video_thumbnail = thumb_path
            except Exception as meta_err:
                 LOGGER.warning(f"Could not extract metadata/thumbnail for downloaded file {final_name}: {meta_err}")

            caption = f"`{final_name}`\n\nDownloaded from: `{url[:50]}{'...' if len(url)>50 else ''}`"

            if duration > 0 and width > 0 and height > 0 and video_thumbnail:
                 # Send as video if possible
                 sent_message = await upload_client.send_video(
                     chat_id=m.chat.id,
                     video=downloaded_path,
                     caption=caption,
                     duration=duration,
                     width=width,
                     height=height,
                     thumb=video_thumbnail,
                     progress=upload_prog.progress_for_pyrogram,
                     progress_args=(f"Uploading: `{final_name}`", c_time)
                 )
            else:
                 # Send as document otherwise
                 sent_message = await upload_client.send_document(
                     chat_id=m.chat.id,
                     document=downloaded_path,
                     caption=caption,
                     thumb=video_thumbnail, # Can still add thumb to doc
                     force_document=True,
                     progress=upload_prog.progress_for_pyrogram,
                     progress_args=(f"Uploading: `{final_name}`", c_time)
                 )

            await editable.delete() # Clean up progress message

            # Log to channel if configured
            if log_chat_id and sent_message:
                 log_caption = f"`{final_name}`\nDownloaded by: {m.from_user.mention} (`{m.from_user.id}`)\nFrom: `{url}`"
                 try:
                      await sent_message.copy(log_chat_id, caption=log_caption)
                 except Exception as log_err:
                      LOGGER.error(f"Failed to copy downloaded file to log channel {log_chat_id}: {log_err}")

        except Exception as upload_err:
            LOGGER.error(f"Failed to upload downloaded file {downloaded_path}: {upload_err}", exc_info=True)
            await editable.edit_text(f"❌ Failed to upload the downloaded file.\nError: `{upload_err}`")
        finally:
             # Clean up downloaded file and thumbnail
             if os.path.exists(downloaded_path):
                 os.remove(downloaded_path)
             if 'video_thumbnail' in locals() and video_thumbnail and os.path.exists(video_thumbnail):
                  os.remove(video_thumbnail)
    else:
        # This case should be handled by the download error messages, but as a final fallback:
        if not await editable.get_edit_state(): # Check if message was already edited to an error
             await editable.edit_text("❌ Download failed. No file to upload.")

    return
# --- MODIFIED END ---


async def showQueue(c: Client, cb: CallbackQuery):
    try:
        markup = await makeButtons(c, cb.message, queueDB)
        if not markup: # Handle case where makeButtons returns empty
             await cb.message.edit("Your queue is empty. Send files to merge.")
             return

        await cb.message.edit(
            text="Okay,\nNow Send Me Next Video or Press **Merge Now** Button!",
            reply_markup=InlineKeyboardMarkup(markup),
        )
    except ValueError: # This might occur if queueDB structure is unexpected
        LOGGER.error(f"ValueError in showQueue for user {cb.from_user.id}. Queue: {queueDB.get(cb.from_user.id)}")
        await cb.message.edit("An error occurred displaying the queue (ValueError). Please /cancel and try again.")
    except MessageNotModified:
        pass # Ignore if the message content is already correct
    except Exception as e: # Catch other potential errors
        LOGGER.error(f"Error in showQueue for user {cb.from_user.id}: {e}", exc_info=True)
        await cb.message.edit("An error occurred while displaying the queue.")
    return


async def delete_all(root):
    try:
        # --- MODIFIED START ---
        # Ensure root exists before trying to remove
        if os.path.exists(root) and os.path.isdir(root): # Also check if it's a directory
             shutil.rmtree(root)
             LOGGER.info(f"Deleted directory: {root}")
        elif os.path.exists(root):
             LOGGER.warning(f"Path exists but is not a directory, cannot delete with rmtree: {root}")
        # else:
        #      LOGGER.info(f"Directory not found, no need to delete: {root}")
        # --- MODIFIED END ---
    except Exception as e:
        LOGGER.error(f"Error deleting directory {root}: {e}")


async def makeButtons(bot: Client, m: Message, db: dict):
    markup = []
    # --- MODIFIED START ---
    # Use message.chat.id consistently as the key
    chat_id = m.chat.id
    user = UserSettings(chat_id, getattr(m.chat, 'first_name', 'User')) # Use chat.first_name as fallback
    user_queue = db.get(chat_id)
    # --- MODIFIED END ---

    # Handle case where user queue might not exist yet
    if not user_queue:
        # LOGGER.warning(f"No queue found for user {chat_id} in makeButtons")
        # Return only cancel if queue is truly empty or doesn't exist
        return [[InlineKeyboardButton("💥 Clear Files", callback_data="cancel")]]

    # --- MODIFIED START ---
    # Simplify logic and improve safety
    video_ids = user_queue.get("videos", [])
    audio_ids = user_queue.get("audios", [])
    subtitle_ids = user_queue.get("subtitles", []) # This might contain None values

    # Get all relevant message objects efficiently
    all_ids_to_fetch = video_ids + audio_ids + [sub_id for sub_id in subtitle_ids if sub_id is not None]
    if not all_ids_to_fetch: # If no valid IDs, only show cancel
         return [[InlineKeyboardButton("💥 Clear Files", callback_data="cancel")]]

    try:
         messages = await bot.get_messages(chat_id=chat_id, message_ids=all_ids_to_fetch)
         message_dict = {msg.id: msg for msg in messages} # Create a dict for quick lookup
    except Exception as e:
         LOGGER.error(f"Failed to get messages for makeButtons (User: {chat_id}, IDs: {all_ids_to_fetch}): {e}")
         return [[InlineKeyboardButton("⚠️ Error Loading Queue", callback_data="cancel")]] # Indicate error

    # Build buttons based on mode
    button_rows = []
    if user.merge_mode == 1: # Video + Video
        for vid_id in video_ids:
             msg = message_dict.get(vid_id)
             if msg:
                 media = msg.video or msg.document
                 fname = getattr(media, 'file_name', f"Video ID: {vid_id}")
                 button_rows.append([InlineKeyboardButton(f"📹 {fname}", callback_data=f"showFileName_{vid_id}")])
             else:
                 LOGGER.warning(f"Message {vid_id} not found for user {chat_id} queue.")

    elif user.merge_mode == 2: # Video + Audio
        # Show video first
        if video_ids:
             msg = message_dict.get(video_ids[0])
             if msg:
                 media = msg.video or msg.document
                 fname = getattr(media, 'file_name', f"Video ID: {video_ids[0]}")
                 button_rows.append([InlineKeyboardButton(f"📹 {fname}", callback_data=f"tryotherbutton")]) # Video not removable in this mode?
        # Show added audios
        for aud_id in audio_ids:
             msg = message_dict.get(aud_id)
             if msg:
                 media = msg.audio or msg.document
                 fname = getattr(media, 'file_name', f"Audio ID: {aud_id}")
                 # Make audio removable? Add callback like "removeAudio_{aud_id}"
                 button_rows.append([InlineKeyboardButton(f"🎵 {fname}", callback_data=f"tryotherbutton")])

    elif user.merge_mode == 3: # Video + Subtitle
        # Show video first
        if video_ids:
             msg = message_dict.get(video_ids[0])
             if msg:
                 media = msg.video or msg.document
                 fname = getattr(media, 'file_name', f"Video ID: {video_ids[0]}")
                 button_rows.append([InlineKeyboardButton(f"📹 {fname}", callback_data=f"tryotherbutton")]) # Video not removable?
        # Show added subtitles
        valid_sub_ids = [sub_id for sub_id in subtitle_ids if sub_id is not None]
        for sub_id in valid_sub_ids:
             msg = message_dict.get(sub_id)
             if msg:
                 media = msg.document # Subtitles are documents
                 fname = getattr(media, 'file_name', f"Subtitle ID: {sub_id}")
                 # Make subs removable? Add callback like "removeMode3Sub_{sub_id}"
                 button_rows.append([InlineKeyboardButton(f"📜 {fname}", callback_data=f"tryotherbutton")])

    # Append Merge and Clear buttons if there's anything actionable
    if video_ids: # Allow merging/cancelling as long as the base video is present
         button_rows.append([InlineKeyboardButton("🔗 Merge Now", callback_data="merge")])
         button_rows.append([InlineKeyboardButton("💥 Clear Files", callback_data="cancel")])

    return button_rows
    # --- MODIFIED END ---


LOGCHANNEL = Config.LOGCHANNEL
try:
    if not Config.USER_SESSION_STRING: # Check if string is empty or None
        raise ValueError("USER_SESSION_STRING is not set.")
    LOGGER.info("Attempting to start USER Session...")
    userBot = Client(
        name="merge-bot-user",
        session_string=Config.USER_SESSION_STRING,
        no_updates=True, # Keep no_updates=True if only used for uploads
        # --- MODIFIED START ---
        api_id=Config.TELEGRAM_API, # Explicitly provide api_id and hash
        api_hash=Config.API_HASH,
        # --- MODIFIED END ---
    )
    # Test the session connection during initialization
    with userBot:
        user = userBot.get_me()
        LOGGER.info(f"User session started successfully as {user.first_name} (Premium: {user.is_premium})")
        Config.IS_PREMIUM = user.is_premium
        # Send boot message only if premium and LOGCHANNEL is set
        if user.is_premium and LOGCHANNEL:
             try:
                 userBot.send_message(
                     chat_id=int(LOGCHANNEL),
                     text="✅ Bot booted with **Premium Account** for uploads up to 4GB.\n\nThanks for using <a href='https://github.com/yashoswalyo/merge-bot'>this repo</a>",
                     disable_web_page_preview=True,
                 )
             except Exception as log_err:
                 LOGGER.error(f"Failed to send premium boot message to LOGCHANNEL ({LOGCHANNEL}): {log_err}")
        elif not user.is_premium:
             LOGGER.warning("User session is active but account is not Premium. Upload limit remains 2GB.")


except (ValueError, KeyError) as e: # Catch missing session string error
    userBot = None
    Config.IS_PREMIUM = False
    LOGGER.warning(f"No User Session String provided ({e}), Default Bot session will be used for uploads (2GB limit).")
except Exception as err: # Catch other potential errors during userBot init
    userBot = None
    Config.IS_PREMIUM = False
    LOGGER.error(f"Failed to initialize User session: {err}", exc_info=True)
    LOGGER.warning("Default Bot session will be used for uploads (2GB limit).")


if __name__ == "__main__":
    # The userBot initialization logic is now above
    mergeApp.run()
