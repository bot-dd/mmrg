# --- START OF FILE MERGE-BOT-master/helpers/rclone_upload.py ---

import os
import re
import subprocess
import time
import asyncio
import json
import traceback
from pyrogram.client import Client
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.types import CallbackQuery, Message
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from helpers import database
# --- MODIFIED START ---
from __init__ import LOGGER, FINISHED_PROGRESS_STR, UN_FINISHED_PROGRESS_STR # Import progress bar chars
from helpers.utils import get_readable_file_size, TimeFormatter # Import formatting utils
from config import Config # Import Config
# --- MODIFIED END ---


class Status:
    # Shared List
    Tasks = []

    def __init__(self):
        self._task_id = len(self.Tasks) + 1

    def refresh_info(self):
        raise NotImplementedError

    def update_message(self):
        raise NotImplementedError

    def is_active(self):
        raise NotImplementedError

    def set_inactive(self):
        raise NotImplementedError


class RCUploadTask(Status):
    def __init__(self, task):
        super().__init__()
        self.Tasks.append(self)
        self._dl_task = task
        self._active = True
        self._upmsg = ""
        self._prev_cont = ""
        self._message = None
        self._error = ""
        self._omess = None
        self.cancel = False
        # --- MODIFIED START ---
        self._start_time = time.time() # Track start time
        # --- MODIFIED END ---

    async def set_original_message(self, omess):
        self._omess = omess

    async def get_original_message(self):
        return self._omess

    async def get_sender_id(self):
        # --- MODIFIED START ---
        # Use from_user.id for callbackquery origin message
        if isinstance(self._omess, CallbackQuery):
            return self._omess.from_user.id
        elif isinstance(self._omess, Message):
             # Fallback for potential direct message usage (though current flow uses CB)
             return self._omess.from_user.id if self._omess.from_user else None
        return None
        # --- MODIFIED END ---

    async def set_message(self, message):
        self._message = message

    async def refresh_info(self, msg):
        # The rclone is process dependent so cant be updated here.
        self._upmsg = msg

    async def create_message(self):
        """Creates the progress message string from rclone output."""
        # --- MODIFIED START ---
        # Enhanced parsing and formatting for consistency
        mat = re.search(
            r"Transferred:\s+(?P<current>[\d.]+\s*[KMGTPEZY]?i?B)\s+/\s+(?P<total>[\d.]+\s*[KMGTPEZY]?i?B),\s+(?P<percentage>[\d.]+)%,\s+(?P<speed>[\d.]+\s*[KMGTPEZY]?i?B/s),\s+ETA\s+(?P<eta>[\dhms]+)",
            self._upmsg
        )
        if mat:
            data = mat.groupdict()
            percentage = float(data.get('percentage', 0))
            prg = self.progress_bar(percentage) # Use percentage directly
            eta_str = data.get('eta', 'N/A')
            # Try converting hms eta to a more standard format if possible
            # eta_seconds = 0
            # parts = re.findall(r'(\d+)([hms])', eta_str)
            # for val, unit in parts:
            #     val = int(val)
            #     if unit == 'h': eta_seconds += val * 3600
            #     elif unit == 'm': eta_seconds += val * 60
            #     elif unit == 's': eta_seconds += val
            # eta_formatted = TimeFormatter(eta_seconds * 1000) if eta_seconds > 0 else eta_str

            elapsed_time = TimeFormatter(round((time.time() - self._start_time) * 1000))

            progress = (
                f"**Uploading to Rclone Drive...**\n\n"
                f"**File:** `{os.path.basename(await self.get_original_message().text if await self.get_original_message() else 'Unknown')}`\n" # Show filename if possible
                f"<code>{prg}</code>\n\n"
                f"**Progress:** `{percentage:.1f}%`\n"
                f"**Transferred:** `{data.get('current','?')}` of `{data.get('total','?')}`\n"
                f"**Speed:** `{data.get('speed','?')}`\n"
                f"**Elapsed:** `{elapsed_time}` | **ETA:** `{eta_str}`\n\n" # Use rclone's ETA directly for now
                f"**Engine:** `RClone`"
            )
            return progress
        else:
             # Fallback if regex fails
             return f"**Uploading to Rclone Drive...**\n`{self._upmsg}`\n\n**Engine:** `RClone`"
        # --- MODIFIED END ---

    def progress_bar(self, percentage):
        """Returns a text progress bar (20 units)."""
        # --- MODIFIED START ---
        # Use imported progress bar characters
        try:
            percentage = float(percentage)
            if not 0 <= percentage <= 100:
                percentage = 0
        except (ValueError, TypeError):
            percentage = 0

        filled_units = round(percentage / 5) # 100 / 5 = 20 units
        unfilled_units = 20 - filled_units

        return f"[{FINISHED_PROGRESS_STR * filled_units}{UN_FINISHED_PROGRESS_STR * unfilled_units}]"
        # --- MODIFIED END ---

    async def update_message(self):
        if not self._message: return # Check if message exists

        progress = await self.create_message()
        if not self._prev_cont == progress:
            self._prev_cont = progress
            try:
                await self._message.edit(
                    progress,
                    reply_markup=InlineKeyboardMarkup(
                        # --- MODIFIED START ---
                        # Ensure cancel callback data is unique or identifiable if needed
                        # Using 'rc_cancel_{task_id}' might be better if multiple rclone tasks run
                        [[InlineKeyboardButton("⛔ Cancel Upload ⛔", callback_data=f"rc_cancel_{self._task_id}")]]
                        # --- MODIFIED END ---
                    ),
                )
            except MessageNotModified:
                pass # Ignore if message hasn't changed
            except FloodWait as e:
                LOGGER.warning(f"Rclone Progress FloodWait: Sleeping for {e.x}s")
                await asyncio.sleep(e.x)
            except Exception as e:
                LOGGER.error(f"Error updating Rclone progress message: {e}", exc_info=True)

    async def is_active(self):
        return self._active

    async def set_inactive(self, error=None):
        self._active = False
        if error is not None:
            self._error = error
        LOGGER.info(f"Rclone Task {self._task_id} set to inactive.")


async def rclone_driver(userMess: Message, cb: CallbackQuery, merged_video_path):
    """Initiates the Rclone upload process."""
    # --- MODIFIED START ---
    # Use Config.DOWNLOAD_LOCATION for user data path
    user_data_dir = os.path.join(Config.DOWNLOAD_LOCATION, "userdata", str(cb.from_user.id))
    conf_path = os.path.join(user_data_dir, "rclone.conf")

    if not os.path.exists(conf_path):
        LOGGER.error(f"Rclone config file not found for user {cb.from_user.id} at {conf_path}")
        await cb.message.edit("❌ Rclone config file not found. Please send your `rclone.conf` file first.")
        return None # Indicate failure

    # Ensure merged video file exists
    if not os.path.exists(merged_video_path):
         LOGGER.error(f"Merged video file not found for Rclone upload: {merged_video_path}")
         await cb.message.edit("❌ Internal Error: Merged video file missing.")
         return None
    # --- MODIFIED END ---

    dl_task = None # This seems unused, maybe related to a download task?
    ul_task = RCUploadTask(dl_task) # Create a status tracking task

    # --- MODIFIED START ---
    # Read Drive Name more safely
    drive_name = None
    try:
        with open(conf_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("[") and line.endswith("]"):
                    drive_name = line[1:-1]
                    break # Found the first remote name
        if not drive_name:
             raise ValueError("No remote name found in rclone.conf")
    except Exception as e:
        LOGGER.error(f"Failed to read Rclone remote name from {conf_path}: {e}")
        await cb.message.edit("❌ Error reading Rclone config file. Ensure it contains a remote name like `[MyDrive]`.")
        return None

    # Use GDRIVE_FOLDER_ID from config, default to root
    base_dir = Config.GDRIVE_FOLDER_ID if Config.GDRIVE_FOLDER_ID != "root" else "/"
    if base_dir != "/" and not base_dir.endswith('/'): # Ensure trailing slash if not root
        base_dir += '/'
    # --- MODIFIED END ---

    edtime = 5 # Edit interval for progress update (seconds)

    try:
        # Pass callback query (cb) instead of userMess for context, and the task object
        upload_result = await rclone_upload(
            merged_video_path=merged_video_path,
            cb=cb, # Pass callback query
            mess_to_edit=cb.message, # Pass the message to edit for progress
            drive_name=drive_name,
            base_dir=base_dir,
            edit_interval=edtime,
            conf_path=conf_path,
            task=ul_task,
        )
        return upload_result # Return the task object (contains status)
    except Exception as er:
        await ul_task.set_inactive(error=str(er))
        LOGGER.error(f"Error during Rclone upload process: {er}", exc_info=True)
        try: # Try to inform the user
            await cb.message.edit(f"❌ Rclone upload failed!\nError: `{er}`")
        except Exception: pass
        return None # Indicate failure
    # --- MODIFIED END ---


async def rclone_upload(
    merged_video_path: str,
    cb: CallbackQuery, # Changed from userMess
    mess_to_edit: Message, # Changed from mess
    drive_name: str, # Changed capitalization
    base_dir: str, # Changed capitalization
    edit_interval: int, # Changed name
    conf_path: str,
    task: RCUploadTask,
):
    """Performs the Rclone upload and updates progress."""
    # --- MODIFIED START ---
    # Set original message context for the task (used for cancel button user check)
    await task.set_original_message(cb) # Use callback query here

    # Prepare cancel callback data using task ID for uniqueness
    cancel_callback_data = f"rc_cancel_{task._task_id}"

    # Send initial status message
    msg: Message = await mess_to_edit.edit( # Edit the existing message
        "** Rclone Upload Initializing...**",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⛔ Cancel Upload ⛔", callback_data=cancel_callback_data)]]
        ),
    )
    await task.set_message(msg) # Store the message object in the task for updates

    # Construct rclone command
    # Use --drive-chunk-size 64M or 128M for potentially better GDrive performance
    # Use --transfers 4 (or more/less depending on server resources)
    rclone_copy_cmd = [
        "rclone", "copy",
        f"--config={conf_path}",
        str(merged_video_path), # Source path
        f"{drive_name}:{base_dir}", # Destination remote:path
        "--drive-chunk-size", "64M", # Adjust as needed
        "--transfers", "4",         # Adjust as needed
        # "-f", "- *.!qB", # Filter flag seems misplaced, usually used with sync/copy --filter
        "--buffer-size", "32M",      # Adjust buffer size
        "-P", # Progress flag
    ]
    LOGGER.info(f"Executing Rclone command: {' '.join(rclone_copy_cmd)}")
    # --- MODIFIED END ---

    # --- MODIFIED START ---
    # Run rclone and display progress
    rclone_process = await asyncio.create_subprocess_exec(
        *rclone_copy_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE # Capture stderr as well
    )
    await task.set_message(msg) # Ensure task has the message object

    rclone_success = await rclone_process_display(
        process=rclone_process,
        edit_interval=edit_interval,
        task=task, # Pass the task object
    )

    stdout, stderr = await rclone_process.communicate() # Get final output
    rclone_stderr = stderr.decode().strip()

    if not rclone_success or rclone_process.returncode != 0:
        error_msg = f"Rclone upload failed (Return Code: {rclone_process.returncode})."
        if not rclone_success and task.cancel: # Check if cancelled via callback
             error_msg = "Rclone upload cancelled by user."
        LOGGER.error(error_msg)
        if rclone_stderr:
            LOGGER.error(f"Rclone stderr:\n{rclone_stderr}")
            error_msg += f"\n```\n{rclone_stderr.splitlines()[-3:]}\n```" # Show last few lines

        await task.set_inactive(error=error_msg)
        try: # Try to edit the message with the error
            await msg.edit(f"❌ {error_msg}")
        except Exception as edit_err:
            LOGGER.error(f"Failed to edit Rclone error message: {edit_err}")
        return task # Return the task object with error status

    # --- Upload Complete ---
    LOGGER.info(f"Rclone upload successful for {os.path.basename(merged_video_path)}")
    await msg.edit("✅ Rclone upload complete! Fetching shareable link...") # Update status

    # Get GDrive link
    file_id, file_name = await getGdriveLink(
        driveName=drive_name,
        baseDir=base_dir,
        entName=os.path.basename(merged_video_path),
        conf_path=conf_path,
        isdir=False,
    )

    if file_id:
        file_link = f"https://drive.google.com/file/d/{file_id}/view"
        final_text = (
            f"✅ **Upload Successful!**\n\n"
            f"**File:** `{file_name}`\n"
            f"**Destination:** `{drive_name}:{base_dir}`"
        )
        button = [[InlineKeyboardButton("☁️ View on Drive ☁️", url=file_link)]]
        LOGGER.info(f"Uploaded File ID: {file_id}, Link: {file_link}")
        await msg.edit(final_text, reply_markup=InlineKeyboardMarkup(button), disable_web_page_preview=True)
    else:
        LOGGER.error("Rclone upload finished, but failed to retrieve GDrive file ID/link.")
        await msg.edit(
             f"✅ **Upload Successful!**\n\n"
             f"**File:** `{os.path.basename(merged_video_path)}`\n"
             f"**Destination:** `{drive_name}:{base_dir}`\n\n"
             f"⚠️ Could not automatically retrieve the shareable link."
        )

    await task.set_inactive() # Mark task as finished
    return task # Return the completed task object
    # --- MODIFIED END ---


async def rclone_process_display(
    process: asyncio.subprocess.Process, # Changed type hint
    edit_interval: int, # Changed name
    task: RCUploadTask, # Pass task instead of messages
):
    """Reads rclone progress from stdout and updates the message via the task."""
    # --- MODIFIED START ---
    blank_lines = 0
    max_blank_lines = 10 # Stop reading if too many consecutive blank lines (process might be stuck)
    last_update_call = 0

    while process.returncode is None: # Loop while process is running
        try:
            # Read line with timeout to prevent blocking indefinitely
            line = await asyncio.wait_for(process.stdout.readline(), timeout=edit_interval * 2)
            if not line: # End of stream or process exited
                 break
            data = line.decode().strip()
        except asyncio.TimeoutError:
            # Timeout waiting for line, check if process is still alive
            if process.returncode is not None: break # Process finished
            continue # Continue waiting if process alive

        if data:
            blank_lines = 0 # Reset blank line counter
            # Check if the line contains progress info
            if "Transferred:" in data and "%" in data and "ETA" in data:
                now = time.time()
                # Throttle message edits
                if now - last_update_call >= edit_interval:
                    await task.refresh_info(data)
                    await task.update_message()
                    last_update_call = now
                    # Check for cancellation request from callback
                    if task.cancel:
                         LOGGER.info(f"Rclone process cancellation detected for task {task._task_id}.")
                         try:
                             process.terminate() # Send SIGTERM
                             await asyncio.wait_for(process.wait(), timeout=5) # Wait a bit for termination
                         except asyncio.TimeoutError:
                             LOGGER.warning(f"Rclone process {process.pid} did not terminate gracefully, sending SIGKILL.")
                             process.kill() # Force kill if terminate fails
                         except ProcessLookupError:
                              LOGGER.warning("Rclone process already terminated.")
                         except Exception as term_err:
                              LOGGER.error(f"Error terminating rclone process: {term_err}")
                         return False # Indicate cancellation
        else:
            blank_lines += 1
            if blank_lines >= max_blank_lines:
                LOGGER.warning(f"Rclone process stdout inactive for {max_blank_lines} reads. Assuming process stuck or finished.")
                break # Exit loop if stdout seems inactive

        await asyncio.sleep(0.1) # Small sleep to yield control

    # Final check on process return code after loop exits
    if process.returncode is None:
         # If loop exited due to inactivity but process still running, something is wrong
         LOGGER.warning(f"Exited rclone display loop, but process {process.pid} still running. Terminating.")
         try: process.terminate()
         except ProcessLookupError: pass
         return False # Indicate potential failure

    return process.returncode == 0 # Return True if exit code is 0 (success)
    # --- MODIFIED END ---


async def getGdriveLink(driveName, baseDir, entName: str, conf_path: str, isdir=True):
    """Gets the Google Drive file ID and name for a given entity."""
    # --- MODIFIED START ---
    # Validate inputs
    if not driveName or not baseDir or not entName or not conf_path:
         LOGGER.error("getGdriveLink: Missing required arguments.")
         return None, None
    if not os.path.exists(conf_path):
         LOGGER.error(f"getGdriveLink: Rclone config not found at {conf_path}")
         return None, None

    LOGGER.info(f"Getting GDrive ID for: {driveName}:{baseDir}{entName}")
    # Escape special characters in the entity name for the filter flag
    # Simple escaping for common cases, might need more robust solution
    escapedEntName = entName.replace('[', '\\[').replace(']', '\\]').replace('*', '\\*').replace('?', '\\?')

    # Use rclone lsjson with filtering for efficiency
    # Filter directly for the entity name at the specified path
    target_path = os.path.join(baseDir, entName).replace("\\", "/") # Ensure forward slashes
    get_id_cmd = [
        "rclone", "lsjson",
        f"--config={conf_path}",
        f"{driveName}:{baseDir}", # List the base directory
        "--files-only", # Consider adding --dirs-only if isdir=True? Currently ignored.
        "--filter", f'+ /{escapedEntName}', # Include only the specific file/dir name within the baseDir
        "--filter", "- *", # Exclude everything else
        # Alternative using full path filter (might be slower if baseDir is huge)
        # f"{driveName}:{target_path}",
        # "--no-traverse", # Avoid traversing subdirs if possible
    ]
    # --- MODIFIED END ---

    LOGGER.debug(f"Executing GDrive link command: {' '.join(get_id_cmd)}")
    process = await asyncio.create_subprocess_exec(
        *get_id_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE # Capture stderr
    )

    stdout, stderr = await process.communicate()
    stdout_str = stdout.decode().strip()
    stderr_str = stderr.decode().strip()

    if process.returncode != 0:
        LOGGER.error(f"Rclone lsjson failed (Code: {process.returncode}) for {entName}")
        LOGGER.error(f"Rclone stderr:\n{stderr_str}")
        return None, None # Return None, None on error

    try:
        # rclone lsjson returns a list of objects
        data = json.loads(stdout_str)
        if data and isinstance(data, list):
            # Find the exact match (lsjson with filter might still return parent dirs sometimes)
            for item in data:
                 # Check name and ensure it's directly within the target dir (or is the target dir)
                 item_path = item.get("Path")
                 if item_path == entName: # Check if the Path matches the entity name directly
                     file_id = item.get("ID")
                     name = item.get("Name")
                     if file_id and name:
                          LOGGER.info(f"Found GDrive ID: {file_id} for Name: {name}")
                          return file_id, name
                     else:
                          LOGGER.warning(f"Found matching entity '{entName}' but missing ID or Name in lsjson output: {item}")
            # If no exact match found in the list
            LOGGER.warning(f"Rclone lsjson returned data, but exact match for '{entName}' not found in base dir '{baseDir}'. Output: {stdout_str}")
            return None, None
        else:
            LOGGER.warning(f"Rclone lsjson did not return a valid list for {entName}. Output: {stdout_str}")
            return None, None
    except json.JSONDecodeError:
        LOGGER.error(f"Failed to decode rclone lsjson output: {stdout_str}")
        return None, None
    except Exception as e:
        LOGGER.error(f"Error processing rclone lsjson output for {entName}: {e}", exc_info=True)
        return None, None
# --- END OF FILE MERGE-BOT-master/helpers/rclone_upload.py ---
