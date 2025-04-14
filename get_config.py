# --- START OF FILE MERGE-BOT-master/get_config.py ---

from requests import get as rget
from __init__ import LOGGER
import os
import subprocess
from dotenv import load_dotenv

CONFIG_FILE_URL = os.environ.get('CONFIG_FILE_URL')
try:
    # --- MODIFIED START ---
    # Check if URL is provided and seems valid before attempting download
    if CONFIG_FILE_URL and CONFIG_FILE_URL.startswith('http'):
        LOGGER.info(f"Attempting to download config file from: {CONFIG_FILE_URL}")
    # --- MODIFIED END ---
        try:
            res = rget(CONFIG_FILE_URL)
            if res.status_code == 200:
                with open('config.env', 'wb+') as f:
                    f.write(res.content)
                # --- MODIFIED START ---
                LOGGER.info("Successfully downloaded config.env.")
                # --- MODIFIED END ---
            else:
                LOGGER.error(f"Failed to download config.env: Status Code {res.status_code}")
        except Exception as e:
            LOGGER.error(f"Error downloading config.env from {CONFIG_FILE_URL}: {e}")
    # --- MODIFIED START ---
    # Log if URL is not provided but don't raise TypeError explicitly
    elif not CONFIG_FILE_URL:
         LOGGER.info("CONFIG_FILE_URL not set. Skipping download.")
    else:
         LOGGER.warning(f"CONFIG_FILE_URL ('{CONFIG_FILE_URL}') does not look like a valid URL. Skipping download.")
    # --- MODIFIED END ---
except Exception as e:
    # --- MODIFIED START ---
    # Log unexpected errors during the config download check process
    LOGGER.error(f"Unexpected error during config file URL processing: {e}")
    # --- MODIFIED END ---
    pass

# --- MODIFIED START ---
# Load .env file if it exists, regardless of download attempt
if os.path.exists("config.env"):
    LOGGER.info("Loading environment variables from config.env")
    load_dotenv(
        "config.env",
        override=True,
    )
else:
    LOGGER.info("config.env file not found. Relying on system environment variables.")
# --- MODIFIED END ---

# tired of redeploying :(
UPSTREAM_REPO = os.environ.get('UPSTREAM_REPO')
UPSTREAM_BRANCH = os.environ.get('UPSTREAM_BRANCH')
try:
    if not UPSTREAM_REPO: # Check if empty or None
       raise TypeError("UPSTREAM_REPO not set or empty.")
except TypeError as e:
    # --- MODIFIED START ---
    LOGGER.info(f"{e} Skipping automatic update.")
    # --- MODIFIED END ---
    UPSTREAM_REPO = None # Ensure it's None if not valid

# --- MODIFIED START ---
# Set default branch if not provided
if UPSTREAM_REPO and not UPSTREAM_BRANCH:
    UPSTREAM_BRANCH = 'master'
    LOGGER.info("UPSTREAM_BRANCH not set, defaulting to 'master'.")
# --- MODIFIED END ---

if UPSTREAM_REPO is not None:
    if os.path.exists('.git'):
        # --- MODIFIED START ---
        LOGGER.info("Removing existing .git directory.")
        # Use shutil for potentially more robust removal
        try:
            shutil.rmtree('.git')
        except OSError as e:
            LOGGER.error(f"Failed to remove existing .git directory: {e}")
            UPSTREAM_REPO = None # Abort update if .git can't be removed
        # --- MODIFIED END ---

    # --- MODIFIED START ---
    # Proceed only if UPSTREAM_REPO is still considered valid
    if UPSTREAM_REPO:
        LOGGER.info(f"Attempting to update repository from {UPSTREAM_REPO} branch {UPSTREAM_BRANCH}")
        # Improved git commands for robustness and clarity
        commands = [
            "git init -q",
            "git config --global user.email 'mergebot@example.com'", # Use a generic email
            "git config --global user.name 'MergeBot Updater'",     # Use a generic name
            "git add .",
            "git commit -m 'Update before fetching upstream' -q --allow-empty", # Allow empty commit
            f"git remote add origin {UPSTREAM_REPO}",
            "git fetch origin -q",
            f"git reset --hard origin/{UPSTREAM_BRANCH} -q"
        ]
        command_str = " && ".join(commands)
        update = subprocess.run(command_str, shell=True, capture_output=True, text=True)
        # --- MODIFIED END ---

        if update.returncode == 0:
            LOGGER.info(f'Successfully updated with latest commit from {UPSTREAM_REPO}/{UPSTREAM_BRANCH}')
        else:
            # --- MODIFIED START ---
            # Log stderr and stdout for better debugging
            LOGGER.warning(f'Something went wrong while updating from {UPSTREAM_REPO}/{UPSTREAM_BRANCH}.')
            LOGGER.warning(f'Return Code: {update.returncode}')
            if update.stdout:
                 LOGGER.warning(f'stdout:\n{update.stdout}')
            if update.stderr:
                 LOGGER.warning(f'stderr:\n{update.stderr}')
            LOGGER.warning('Please check your UPSTREAM_REPO and UPSTREAM_BRANCH variables.')
            # --- MODIFIED END ---
# --- END OF FILE MERGE-BOT-master/get_config.py ---
