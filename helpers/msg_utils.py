# --- START OF FILE MERGE-BOT-master/helpers/msg_utils.py ---

import re
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
# --- MODIFIED START ---
from __init__ import LOGGER # Import LOGGER for error logging
# --- MODIFIED END ---


class MakeButtons:
    """
    Create buttons from list
    """

    def makebuttons(self, set1: list, set2: list, isUrl=False, isCallback=True,rows = 1):
        # --- MODIFIED START ---
        # Ensure lists are of the same length
        if len(set1) != len(set2):
             # Log error or raise exception? Let's log and return empty for now.
             LOGGER.error(f"Button text (len {len(set1)}) and data (len {len(set2)}) lists must have the same length!")
             return [] # Return empty list to avoid crashing caller
        if rows <= 0:
             LOGGER.warning(f"Invalid number of rows ({rows}) specified. Defaulting to 1.")
             rows = 1
        # --- MODIFIED END ---
        self._set1 = set1.copy()
        self._set2 = set2.copy()
        self._isUrl = isUrl
        self._isCallback = isCallback
        self.rows = rows
        return self._make()

    def _make(self):
        butt = []
        # --- MODIFIED START ---
        # Combine logic for clarity and ensure row handling is correct
        temp_set1 = self._set1.copy()
        temp_set2 = self._set2.copy()

        while temp_set1:
            buttons_in_row = []
            # Determine how many buttons to take for the current row
            # Ensure we don't try to take more buttons than available
            num_buttons = min(self.rows, len(temp_set1))

            for _ in range(num_buttons):
                # Check again inside loop just in case (shouldn't be needed with outer while)
                if not temp_set1: break

                text = temp_set1.pop(0)
                data = temp_set2.pop(0)

                # Basic validation
                if not isinstance(text, str) or not text:
                     LOGGER.warning(f"Invalid button text found: {text}. Skipping.")
                     continue
                if not isinstance(data, str) or not data:
                     LOGGER.warning(f"Invalid button data found for text '{text}': {data}. Skipping.")
                     continue


                if self._isUrl:
                    # Add basic URL validation?
                    if not data.startswith(('http://', 'https://', 'tg://')):
                         LOGGER.warning(f"Button data '{data}' for text '{text}' doesn't look like a valid URL. Adding anyway.")
                    buttons_in_row.append(InlineKeyboardButton(text=text, url=data))
                elif self._isCallback: # Use elif assuming it's either URL or Callback
                    # Callback data length check (Telegram limit is 64 bytes)
                    if len(data.encode('utf-8')) > 64:
                         LOGGER.warning(f"Callback data for text '{text}' exceeds 64 bytes: '{data[:30]}...'. May cause issues.")
                    buttons_in_row.append(InlineKeyboardButton(text=text, callback_data=data))
                # Add else block if other types are possible

            if buttons_in_row: # Add row only if it has buttons
                butt.append(buttons_in_row)

        return butt
        # --- MODIFIED END ---

# --- END OF FILE MERGE-BOT-master/helpers/msg_utils.py ---
