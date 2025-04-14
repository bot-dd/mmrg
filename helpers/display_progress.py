#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# (c) Shrimadhav U K | gautamajay52

import logging
import math
import os
import time
# --- MODIFIED START ---
import asyncio # Import asyncio
from pyrogram.errors import FloodWait, MessageNotModified # Added MessageNotModified
# --- MODIFIED END ---
from __init__ import (
    FINISHED_PROGRESS_STR,
    UN_FINISHED_PROGRESS_STR,
    EDIT_SLEEP_TIME_OUT,
    gDict,
    LOGGER,
)
from pyrogram import Client

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message


class Progress:
    def __init__(self, from_user, client, mess: Message):
        self._from_user = from_user
        self._client = client
        self._mess = mess
        self._cancelled = False
        # --- MODIFIED START ---
        self._last_update_time = 0 # Track last update time to throttle edits
        self._start_time = time.time() # Store start time internally
        # --- MODIFIED END ---

    @property
    def is_cancelled(self):
        chat_id = self._mess.chat.id
        mes_id = self._mess.id
        # --- MODIFIED START ---
        # Check gDict safely and update internal flag
        # This allows checking self._cancelled directly after checking the property
        if not self._cancelled and chat_id in gDict and mes_id in gDict[chat_id]:
            self._cancelled = True
            LOGGER.info(f"Cancellation requested for message {mes_id} in chat {chat_id}")
        # --- MODIFIED END ---
        return self._cancelled

    # --- MODIFIED START ---
    async def progress_for_pyrogram(self, current, total, ud_type, start, count="", filesize=None):
        """
        Updates the progress message.

        Parameters:
            current (int): Current bytes processed.
            total (int | None): Total bytes, or None if unknown.
            ud_type (str): Description of the operation (e.g., "Downloading", "Uploading").
            start (float): Timestamp when the operation started.
            count (str, optional): Additional text to append (e.g., file count). Defaults to "".
            filesize (str, optional): Pre-formatted total filesize string (e.g., "1.2 GiB"). Defaults to None.
        """
        # --- MODIFIED END ---
        now = time.time()
        # --- MODIFIED START ---
        # Throttle updates: Skip if not enough time has passed, unless it's the final update
        if not self.is_cancelled and current != total and (now - self._last_update_time) < EDIT_SLEEP_TIME_OUT :
            return # Skip update if too soon

        # Update last edit time only if an edit happens or would have happened
        self._last_update_time = now
        # --- MODIFIED END ---

        if self.is_cancelled:
            # --- MODIFIED START ---
            # Avoid re-editing if already cancelled
            if "Cancelled" not in self._mess.text:
                try:
                    await self._mess.edit(
                        f"⛔ **Cancelled** ⛔ \n\n `{ud_type}` ({humanbytes(total if total else 0)})"
                    )
                except MessageNotModified:
                     pass # Ignore if message already shows cancelled
                except FloodWait as fw:
                     LOGGER.warning(f"FloodWait while editing cancel message: {fw.x}s")
                     await asyncio.sleep(fw.x)
                except Exception as e:
                     LOGGER.error(f"Error editing cancel message: {e}")
            # Try to stop transmission - depends on pyrogram version/method
            # This might need adjustment based on how downloads/uploads are initiated
            # if hasattr(self._client, 'stop_transmission'):
            #      try:
            #          await self._client.stop_transmission()
            #          LOGGER.info(f"Stop transmission called for user {self._from_user}")
            #      except Exception as stop_err:
            #          LOGGER.error(f"Error calling stop_transmission: {stop_err}")
            # --- MODIFIED END ---
            return # Stop further processing

        chat_id = self._mess.chat.id
        mes_id = self._mess.id
        from_user = self._from_user
        # now = time.time() # Moved up
        diff = now - start
        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "⛔ Cancel ⛔",
                        callback_data=(
                            f"gUPcancel/{chat_id}/{mes_id}/{from_user}"
                        ).encode("UTF-8"),
                    )
                ]
            ]
        )

        # --- MODIFIED START ---
        # Calculate progress metrics safely
        if total is not None and total > 0:
            percentage = current * 100 / total
            progress_bar_fill = math.floor(percentage / 5) # 20 units total (100/5)
            progress_bar = "[{0}{1}] {2:.1f}%".format( # Display one decimal place
                "".join([FINISHED_PROGRESS_STR for _ in range(progress_bar_fill)]),
                "".join([UN_FINISHED_PROGRESS_STR for _ in range(20 - progress_bar_fill)]),
                percentage,
            )
            # Calculate speed and ETA only if diff > 0 to avoid division by zero
            if diff > 0:
                speed = current / diff
                if speed > 0 and current < total: # Estimate ETA only if speed is positive and not finished
                     time_to_completion_ms = ((total - current) / speed) * 1000
                     estimated_total_time = TimeFormatter(milliseconds=time_to_completion_ms)
                elif current == total:
                     estimated_total_time = "Done!"
                     speed = 0 # Speed is irrelevant when done
                else: # speed is 0 or negative, or diff is 0
                     estimated_total_time = "Inf."
                     speed = 0
            else: # diff is 0 (first update)
                speed = 0
                estimated_total_time = "Inf."
        else: # Handle cases where total size is 0 or None (e.g., streams)
             percentage = 0
             estimated_total_time = "N/A"
             progress_bar = "[{}] ???%".format( # Indicate unknown progress
                 ''.join([UN_FINISHED_PROGRESS_STR for _ in range(20)])
             )
             speed = current / diff if diff > 0 else 0 # Can still show current speed

        elapsed_time = TimeFormatter(milliseconds=round(diff * 1000))
        speed_str = f"{humanbytes(speed)}/s" if speed > 0 else "---"
        # Use provided filesize string if available, otherwise format total
        total_str = filesize if filesize else humanbytes(total if total else 0)
        current_str = humanbytes(current)

        progress_text = f"\n<code>{progress_bar}</code>\n"

        # Construct the message body
        tmp = (
            f"{progress_text}\n"
            f"**Processed:** `{current_str}` of `{total_str}`\n"
            f"**Speed:** `{speed_str}`\n"
            f"**Elapsed:** `{elapsed_time}` | **ETA:** `{estimated_total_time}`\n"
            f"{count}" # Append extra info like file count
        )
        # --- MODIFIED END ---

        try:
            # --- MODIFIED START ---
            # Edit the message with the new progress text and markup
            # Pyrogram handles MessageNotModified internally now, but explicit check can sometimes be useful
            new_content = f"{ud_type}\n{tmp}"
            # Get current content safely
            current_content = None
            if self._mess.text:
                current_content = self._mess.text
            elif self._mess.caption:
                current_content = self._mess.caption

            # Only edit if content has changed to potentially reduce API calls
            if current_content != new_content:
                if self._mess.caption:
                    await self._mess.edit_caption(caption=new_content, reply_markup=reply_markup)
                else:
                    await self._mess.edit_text(text=new_content, reply_markup=reply_markup)
            # --- MODIFIED END ---
        except MessageNotModified: # Catch specific exception
            pass # Ignore if message hasn't changed
        except FloodWait as fd:
            logger.warning(f"FloodWait: Sleeping for {fd.x} seconds during progress update.")
            await asyncio.sleep(fd.x) # Use asyncio.sleep
        except Exception as ou:
            logger.error(f"Error updating progress for user {from_user} on message {mes_id}: {ou}", exc_info=True)


def humanbytes(size):
    """Converts bytes to a human-readable format (KiB, MiB, etc.)."""
    # https://stackoverflow.com/a/49361727/4723940
    # 2**10 = 1024
    # --- MODIFIED START ---
    if size is None or size < 0: # Handle None and negative sizes
        return "0 B"
    if size == 0: return "0 B"
    # --- MODIFIED END ---
    power = 2**10
    n = 0
    Dic_powerN = {0: "B", 1: "KiB", 2: "MiB", 3: "GiB", 4: "TiB"} # Use KiB, MiB etc.
    while size >= power and n < len(Dic_powerN) - 1: # Check n boundary
        size /= power
        n += 1
    # --- MODIFIED START ---
    # Format to 2 decimal places if KiB or greater, otherwise show as integer B
    if n > 0:
        return f"{size:.2f} {Dic_powerN[n]}"
    else:
        return f"{int(size)} {Dic_powerN[n]}" # Show bytes as integer
    # --- MODIFIED END ---


def TimeFormatter(milliseconds: int) -> str:
    """Formats milliseconds into a human-readable string (Xd, Xh, Xm, Xs)."""
    # --- MODIFIED START ---
    if milliseconds is None or milliseconds < 0:
        return "N/A" # Handle invalid input
    if milliseconds == 0:
        return "0s"
    # --- MODIFIED END ---
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = (
        ((str(days) + "d, ") if days else "")
        + ((str(hours) + "h, ") if hours else "")
        + ((str(minutes) + "m, ") if minutes else "")
        + ((str(seconds) + "s, ") if seconds else "")
        # + ((str(milliseconds) + "ms, ") if milliseconds else "") # Milliseconds often too noisy
    )
    # --- MODIFIED START ---
    # Return "0s" if empty, otherwise remove trailing ", "
    return tmp[:-2] if tmp else "0s"
    # --- MODIFIED END ---
# --- END OF FILE MERGE-BOT-master/helpers/display_progress.py ---
