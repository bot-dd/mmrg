# --- START OF FILE MERGE-BOT-master/helpers/database.py ---

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from pyrogram.types import CallbackQuery
from config import Config
# --- MODIFIED START ---
from __init__ import LOGGER, MERGE_MODE
import time # Import time
import asyncio # Import asyncio
# --- MODIFIED END ---


# --- MODIFIED START ---
# Use a single Database class instance for connection pooling
class MongoDB:
    def __init__(self):
        self.client = None
        self.db = None
        try:
            # Ensure DATABASE_URL is loaded
            if not Config.DATABASE_URL:
                LOGGER.critical("DATABASE_URL is not set in the environment/config file!")
                raise ValueError("DATABASE_URL is required.")

            self.client = MongoClient(Config.DATABASE_URL, serverSelectionTimeoutMS=5000) # Add timeout
            # The ismaster command is cheap and does not require auth.
            self.client.admin.command('ismaster')
            self.db = self.client.get_database("MergeBot") # Use get_database for flexibility
            LOGGER.info("Successfully connected to MongoDB.")
        except Exception as e:
            LOGGER.critical(f"Failed to connect to MongoDB: {e}", exc_info=True)
            # Handle connection failure gracefully if needed
            self.client = None
            self.db = None

    def get_db(self):
        # Check connection before returning db object
        if self.client and self.db:
            try:
                 # Ping before returning to ensure connection is alive
                 self.client.admin.command('ping')
                 return self.db
            except Exception as e:
                 LOGGER.error(f"MongoDB connection lost: {e}. Attempting to reconnect...")
                 # Attempt to reconnect (optional, depends on desired behavior)
                 try:
                     self.client = MongoClient(Config.DATABASE_URL, serverSelectionTimeoutMS=5000)
                     self.client.admin.command('ismaster')
                     self.db = self.client.get_database("MergeBot")
                     LOGGER.info("Successfully reconnected to MongoDB.")
                     return self.db
                 except Exception as recon_e:
                     LOGGER.critical(f"Failed to reconnect to MongoDB: {recon_e}")
                     self.client = None
                     self.db = None
                     return None
        else:
             LOGGER.error("Database connection not available.")
             return None


# Instantiate the database connection
db_connection = MongoDB()

# Old Database class kept for compatibility but ideally refactor calls to use db_connection.get_db()
# This class definition itself doesn't seem used elsewhere in the provided code,
# but we keep it as requested. Calls like Database.mergebot.users will fail if db_connection is None.
class Database:
     client = MongoClient(Config.DATABASE_URL) if Config.DATABASE_URL else None
     mergebot = client.MergeBot if client else None

# --- MODIFIED END ---


async def addUser(uid, fname, lname):
    # --- MODIFIED START ---
    db = db_connection.get_db()
    if not db:
        LOGGER.error("Database connection not available in addUser.")
        return
    # --- MODIFIED END ---
    try:
        userDetails = {
            # "_id": uid, # _id is the primary key, no need to set it explicitly in $set
            "name": f"{fname} {lname if lname else ''}".strip(), # Handle None lname
            # --- MODIFIED START ---
            # Add timestamp for last seen/updated
            "last_seen": time.time()
            # --- MODIFIED END ---
        }
        # --- MODIFIED START ---
        # Use update_one with upsert=True to add or update user details
        # Set default settings only on insert ($setOnInsert)
        default_settings = {
            "user_settings": {
                "merge_mode": 1,
                "edit_metadata": False,
            },
            "isAllowed": False, # Default to not allowed unless owner or password used
            "isBanned": False,
            "thumbnail": None,
            "first_seen": time.time()
        }
        # Owner should be allowed by default on first insert
        if uid == int(Config.OWNER):
            default_settings["isAllowed"] = True

        result = db.users.update_one(
            {"_id": uid},
            {
                "$set": userDetails, # Update name and last_seen always
                "$setOnInsert": default_settings # Add defaults only if user doesn't exist
            },
            upsert=True
        )
        if result.upserted_id:
            LOGGER.info(f"New user added: id={uid}, Name={userDetails['name']}")
        elif result.modified_count > 0:
            LOGGER.info(f"User updated: id={uid}, Name={userDetails['name']}")
        # --- MODIFIED END ---
    except DuplicateKeyError:
        # This block should ideally not be reached with upsert=True, but kept for safety
        LOGGER.warning(f"Duplicate key error during upsert for id={uid}, should not happen.")
    except Exception as e: # Catch other potential errors
        LOGGER.error(f"Error in addUser for {uid}: {e}", exc_info=True)


async def broadcast():
    # --- MODIFIED START ---
    db = db_connection.get_db()
    if not db:
        LOGGER.error("Database connection not available in broadcast.")
        return None # Return None or empty list/cursor on error
    # Find users who are not banned and potentially filter inactive ones later
    # Return the cursor directly for efficient iteration in the calling function
    return db.users.find({"isBanned": {"$ne": True}}) # Find users who are not banned
    # --- MODIFIED END ---


async def allowUser(uid, fname, lname):
    # --- MODIFIED START ---
    # This function seems deprecated by the UserSettings class and login logic,
    # but we'll update it to modify the 'isAllowed' field directly.
    db = db_connection.get_db()
    if not db:
        LOGGER.error("Database connection not available in allowUser.")
        return
    # --- MODIFIED END ---
    try:
        # --- MODIFIED START ---
        # Update the 'isAllowed' field in the user's document
        result = db.users.update_one(
            {"_id": uid},
            {"$set": {"isAllowed": True, "last_updated": time.time()}}
        )
        if result.matched_count > 0:
            LOGGER.info(f"User {uid} explicitly allowed.")
        else:
            # If user doesn't exist, add them and set allowed
            LOGGER.warning(f"User {uid} not found in allowUser. Adding and allowing.")
            await addUser(uid, fname, lname) # Add the user first with defaults
            db.users.update_one( # Then set allowed
                {"_id": uid},
                {"$set": {"isAllowed": True, "last_updated": time.time()}}
            )
        # --- MODIFIED END ---
    except Exception as e:
        LOGGER.error(f"Error allowing user {uid}: {e}", exc_info=True)


async def allowedUser(uid):
     # --- MODIFIED START ---
     # This function is also likely deprecated by UserSettings, check UserSettings.allowed instead
     db = db_connection.get_db()
     if not db:
         LOGGER.error("Database connection not available in allowedUser check.")
         return False
     user_settings = getUserMergeSettings(uid) # Reuse existing function
     return user_settings.get("isAllowed", False) if user_settings else False
     # --- MODIFIED END ---


async def saveThumb(uid, fid):
    # --- MODIFIED START ---
    # This should update the 'thumbnail' field in the user's settings document
    db = db_connection.get_db()
    if not db:
        LOGGER.error("Database connection not available in saveThumb.")
        return
    try:
        result = db.users.update_one(
            {"_id": uid},
            {"$set": {"thumbnail": fid, "last_updated": time.time()}}
        )
        if result.matched_count == 0:
             LOGGER.warning(f"User {uid} not found when trying to save thumbnail. Thumbnail not saved.")
        else:
             LOGGER.info(f"Thumbnail updated for user {uid}.")
    except Exception as e:
        LOGGER.error(f"Error saving thumbnail for user {uid}: {e}", exc_info=True)
    # --- MODIFIED END ---


async def delThumb(uid):
    # --- MODIFIED START ---
    # Set the 'thumbnail' field to None in the user's settings document
    db = db_connection.get_db()
    if not db:
        LOGGER.error("Database connection not available in delThumb.")
        return False
    try:
        result = db.users.update_one(
            {"_id": uid},
            {"$set": {"thumbnail": None, "last_updated": time.time()}}
        )
        if result.matched_count > 0:
            LOGGER.info(f"Thumbnail deleted for user {uid}.")
            return True
        else:
            LOGGER.warning(f"User {uid} not found when trying to delete thumbnail.")
            return False # Return False if user not found
    except Exception as e:
        LOGGER.error(f"Error deleting thumbnail for user {uid}: {e}", exc_info=True)
        return False
    # --- MODIFIED END ---


async def getThumb(uid):
    # --- MODIFIED START ---
    # Get the 'thumbnail' field from the user's settings document
    user_settings = getUserMergeSettings(uid) # Reuse existing function
    return user_settings.get("thumbnail") if user_settings else None
    # --- MODIFIED END ---


async def deleteUser(uid):
    # --- MODIFIED START ---
    db = db_connection.get_db()
    if not db:
        LOGGER.error("Database connection not available in deleteUser.")
        return
    try:
        # Delete the entire user document from the 'users' collection
        result = db.users.delete_one({"_id": uid})
        if result.deleted_count > 0:
            LOGGER.info(f"Deleted user {uid} from database.")
        else:
            LOGGER.warning(f"Attempted to delete user {uid}, but they were not found.")
        # Also clear any runtime cache for the user
        MERGE_MODE.pop(uid, None)
        # Optionally clear other caches like queueDB, formatDB if needed upon deletion
        from __init__ import queueDB, formatDB, replyDB, UPLOAD_AS_DOC, UPLOAD_TO_DRIVE
        queueDB.pop(uid, None)
        formatDB.pop(uid, None)
        replyDB.pop(uid, None)
        UPLOAD_AS_DOC.pop(f"{uid}", None)
        UPLOAD_TO_DRIVE.pop(f"{uid}", None)
        LOGGER.info(f"Cleared runtime cache for deleted user {uid}.")
    except Exception as e:
        LOGGER.error(f"Error deleting user {uid}: {e}", exc_info=True)
    # --- MODIFIED END ---


async def addUserRcloneConfig(cb: CallbackQuery, fileId):
    # --- MODIFIED START ---
    db = db_connection.get_db()
    if not db:
        LOGGER.error("Database connection not available in addUserRcloneConfig.")
        try: # Try to edit the message even if DB fails
             await cb.message.edit("❌ Database Error! Cannot save RClone config.")
        except Exception: pass
        return
    # --- MODIFIED END ---
    try:
        await cb.message.edit("💾 Adding RClone config to DB...")
        uid = cb.from_user.id
        # --- MODIFIED START ---
        # Use update_one with upsert=True in a separate 'rcloneData' collection
        result = db.rcloneData.update_one(
            {"_id": uid},
            {"$set": {"rcloneFileId": fileId, "last_updated": time.time()}},
            upsert=True
        )
        if result.upserted_id:
            LOGGER.info(f"Rclone config added for user {uid}")
        elif result.modified_count > 0:
            LOGGER.info(f"Rclone config updated for user {uid}")
        # --- MODIFIED END ---
    except DuplicateKeyError: # Should not happen with upsert
        LOGGER.warning(f"Duplicate key error during Rclone upsert for user {uid}, should not happen.")
        # Attempt replace_one as fallback (though upsert should handle this)
        try:
             db.rcloneData.replace_one({"_id": uid}, {"rcloneFileId": fileId, "last_updated": time.time()})
             LOGGER.info(f"Rclone config replaced for user {uid} after duplicate error.")
        except Exception as replace_err:
             LOGGER.error(f"Error replacing Rclone config for {uid} after duplicate error: {replace_err}")
             await cb.message.edit("❌ Error updating Rclone config!")
             return
    except Exception as err:
        LOGGER.error(f"Error saving Rclone config for {cb.from_user.id}: {err}", exc_info=True)
        await cb.message.edit("❌ Error saving Rclone config!")
        return # Return early on error

    await cb.message.edit("✅ Rclone config saved successfully.")
    await asyncio.sleep(3) # Give user time to read
    try:
        await cb.message.delete() # Clean up message
    except Exception as del_err:
        LOGGER.warning(f"Could not delete Rclone confirmation message: {del_err}")


async def getUserRcloneConfig(uid):
    # --- MODIFIED START ---
    db = db_connection.get_db()
    if not db:
        LOGGER.error("Database connection not available in getUserRcloneConfig.")
        return None
    # --- MODIFIED END ---
    try:
        # --- MODIFIED START ---
        # Find from 'rcloneData' collection
        res = db.rcloneData.find_one({"_id": uid})
        return res.get("rcloneFileId") if res else None # Return fileId or None
        # --- MODIFIED END ---
    except Exception as err:
        # --- MODIFIED START ---
        LOGGER.error(f"Error retrieving Rclone config for {uid}: {err}", exc_info=True)
        # --- MODIFIED END ---
        return None


def getUserMergeSettings(uid: int):
    # --- MODIFIED START ---
    db = db_connection.get_db()
    if not db:
        LOGGER.error("Database connection not available in getUserMergeSettings.")
        return None
    # --- MODIFIED END ---
    try:
        # --- MODIFIED START ---
        # Fetch from the main users collection
        res_cur = db.users.find_one({"_id": uid})
        # --- MODIFIED END ---
        return res_cur # Returns the entire user document or None
    except Exception as e:
        LOGGER.error(f"Error getting user settings for {uid}: {e}", exc_info=True) # Log error with uid
        return None


def setUserMergeSettings(uid: int, name: str, mode, edit_metadata, banned, allowed, thumbnail):
    # --- MODIFIED START ---
    db = db_connection.get_db()
    if not db:
        LOGGER.error("Database connection not available in setUserMergeSettings.")
        return
    # --- MODIFIED END ---
    modes = Config.MODES
    mode_index = mode - 1 # Convert mode number (1-4) to index (0-3)
    if not (0 <= mode_index < len(modes)):
        LOGGER.error(f"Invalid mode '{mode}' provided for user {uid}. Defaulting to mode 1.")
        mode = 1 # Default to mode 1 if invalid
        mode_index = 0

    if uid:
        try:
            # --- MODIFIED START ---
            # Define the document structure clearly
            user_settings_doc = {
                "name": name, # Update name
                "user_settings": {
                    "merge_mode": mode,
                    "edit_metadata": bool(edit_metadata), # Ensure boolean
                },
                "isAllowed": bool(allowed), # Ensure boolean
                "isBanned": bool(banned),   # Ensure boolean
                "thumbnail": thumbnail, # Can be None or file_id string
                "last_updated": time.time() # Add last updated timestamp
            }
            # Use update_one with upsert=True in the main users collection
            # Set defaults only on insert
            default_settings = {
                "user_settings": {
                    "merge_mode": 1,
                    "edit_metadata": False,
                },
                "isAllowed": False,
                "isBanned": False,
                "thumbnail": None,
                "first_seen": time.time()
            }
            # Owner should be allowed by default on first insert
            if uid == int(Config.OWNER):
                 default_settings["isAllowed"] = True
                 user_settings_doc["isAllowed"] = True # Ensure owner stays allowed on update

            result = db.users.update_one(
                {"_id": uid},
                {"$set": user_settings_doc, "$setOnInsert": default_settings},
                upsert=True
            )

            if result.upserted_id:
                 LOGGER.info(f"User {uid} inserted with settings: Mode={modes[mode_index]}, EditMeta={edit_metadata}, Allowed={user_settings_doc['isAllowed']}, Banned={banned}")
            elif result.modified_count > 0:
                 LOGGER.info(f"User {uid} settings updated: Mode={modes[mode_index]}, EditMeta={edit_metadata}, Allowed={allowed}, Banned={banned}")
            # --- MODIFIED END ---

        except Exception as e: # Catch specific exceptions if possible
            # --- MODIFIED START ---
            LOGGER.error(f"Failed to set user settings for {uid}: {e}", exc_info=True)
            # --- MODIFIED END ---
            return # Return early on error

        # Update runtime cache
        MERGE_MODE[uid] = mode
    # --- MODIFIED START --- Removed redundant mode==2/3 blocks ---
    # --- MODIFIED END ---
    # LOGGER.info(MERGE_MODE) # Logging this dict frequently might be noisy


def enableMetadataToggle(uid: int, value: bool):
    # --- MODIFIED START ---
    # This function seems unused, the logic is handled in UserSettings.set() / setUserMergeSettings()
    # LOGGER.warning("enableMetadataToggle function called but is likely deprecated.")
    pass
    # --- MODIFIED END ---


def disableMetadataToggle(uid: int, value: bool):
     # --- MODIFIED START ---
    # This function seems unused, the logic is handled in UserSettings.set() / setUserMergeSettings()
    # LOGGER.warning("disableMetadataToggle function called but is likely deprecated.")
    pass
    # --- MODIFIED END ---
# --- END OF FILE MERGE-BOT-master/helpers/database.py ---
