# --- START OF FILE MERGE-BOT-master/helpers/ffmpeg_helper.py ---

import asyncio
import subprocess
import shutil
import os
import time
import ffmpeg
from pyrogram.types import CallbackQuery
from config import Config
from pyrogram.types import Message
from __init__ import LOGGER
from helpers.utils import get_path_size, sanitize_filename # Added sanitize_filename

# --- MODIFIED START ---
import json # Needed for metadata processing
# --- MODIFIED END ---


async def MergeVideo(input_file: str, user_id: int, message: Message, format_: str):
    """
    This is for Merging Videos Together!
    :param `input_file`: input.txt file's location.
    :param `user_id`: Pass user_id as integer.
    :param `message`: Pass Editable Message for Showing FFmpeg Progress.
    :param `format_`: Pass File Extension.
    :return: This will return Merged Video File Path or None on failure.
    """
    # --- MODIFIED START ---
    # Use Config.DOWNLOAD_LOCATION and ensure user directory exists
    user_download_dir = os.path.join(Config.DOWNLOAD_LOCATION, str(user_id))
    if not os.path.isdir(user_download_dir):
         try: os.makedirs(user_download_dir)
         except OSError as e:
             LOGGER.error(f"Failed to create directory {user_download_dir} in MergeVideo: {e}")
             await message.edit("❌ Internal Error: Could not create working directory.")
             return None
    # Sanitize format_ just in case
    format_ = sanitize_filename(format_)
    output_vid = os.path.join(user_download_dir, f"[@yashoswalyo]_merged.{format_.lower()}")
    # --- MODIFIED END ---

    # --- MODIFIED START ---
    # Ensure input file exists
    if not os.path.exists(input_file):
        LOGGER.error(f"Input file list not found: {input_file}")
        await message.edit("❌ Internal Error: Input file list not found.")
        return None
    # Build command carefully
    file_generator_command = [
        "ffmpeg",
        "-hide_banner", # Hide banner for cleaner logs
        "-f", "concat",
        "-safe", "0",
        "-i", input_file,
        "-map", "0", # Map all streams from the concatenated input
        "-c", "copy", # Copy all streams
        # "-metadata", "handler_name=MergeBot", # Optional: Add a handler name
        output_vid,
    ]
    # --- MODIFIED END ---
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            *file_generator_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await message.edit("⏳ Merging videos... Please wait.") # More informative message
        stdout, stderr = await process.communicate()
        e_response = stderr.decode().strip()
        t_response = stdout.decode().strip()

        # --- MODIFIED START ---
        # Check return code and log appropriately
        if process.returncode == 0:
            LOGGER.info(f"FFmpeg MergeVideo successful for user {user_id}.")
            # Minimal stdout logging unless debug needed: LOGGER.debug(f"FFmpeg MergeVideo Output:\n{t_response}")
            if os.path.exists(output_vid): # Double-check existence
                return output_vid
            else:
                LOGGER.error(f"FFmpeg MergeVideo finished successfully, but output file missing: {output_vid}")
                await message.edit("❌ Merge Error: Output file not found after successful merge.")
                return None
        else:
            LOGGER.error(f"FFmpeg MergeVideo failed for user {user_id}. Return Code: {process.returncode}")
            LOGGER.error(f"FFmpeg stderr:\n{e_response}")
            error_summary = e_response.splitlines()[-3:] # Get last few lines of error
            await message.edit(f"❌ Merge Failed!\n```\n{'\n'.join(error_summary)}\n```")
            # Clean up failed output file
            if os.path.exists(output_vid):
                try: os.remove(output_vid)
                except OSError: pass
            return None
        # --- MODIFIED END ---

    except NotImplementedError:
        LOGGER.error("FFmpeg execution failed: NotImplementedError. Ensure bot runs on Linux/Unix.")
        await message.edit(
            text="Unable to Execute FFmpeg Command! Got `NotImplementedError` ...\n\nPlease run bot in a Linux/Unix Environment."
        )
        return None
    except Exception as e:
        LOGGER.error(f"Unexpected error during MergeVideo for user {user_id}: {e}", exc_info=True)
        await message.edit(f"❌ Unexpected Merge Error: {type(e).__name__}")
        # Clean up failed output file
        if process and process.returncode != 0 and os.path.exists(output_vid):
             try: os.remove(output_vid)
             except OSError: pass
        return None


async def MergeSub(filePath: str, subPath: str, user_id):
    """
    DEPRECATED? Use MergeSubNew for multi-sub support.
    This is for Merging Video + Single Subtitle Together.

    Parameters:
    - `filePath`: Path to Video file.
    - `subPath`: Path to subtitile file.
    - `user_id`: To get parent directory.

    returns: Merged Video File Path or None on failure.
    """
    LOGGER.warning("MergeSub function called (likely deprecated). Use MergeSubNew.")
    # --- MODIFIED START ---
    # Use Config.DOWNLOAD_LOCATION and ensure user directory exists
    user_download_dir = os.path.join(Config.DOWNLOAD_LOCATION, str(user_id))
    if not os.path.isdir(user_download_dir):
        try: os.makedirs(user_download_dir)
        except OSError as e:
            LOGGER.error(f"Failed to create directory {user_download_dir} in MergeSub: {e}")
            return None
    # Create a temporary output path
    output_path = os.path.join(user_download_dir, f"[MergeSub]_{os.path.basename(filePath)}")
    # --- MODIFIED END ---

    # --- MODIFIED START ---
    # Check input file existence
    if not os.path.exists(filePath):
        LOGGER.error(f"MergeSub Error: Video file not found: {filePath}")
        return None
    if not os.path.exists(subPath):
        LOGGER.error(f"MergeSub Error: Subtitle file not found: {subPath}")
        return None
    # --- MODIFIED END ---

    LOGGER.info("Generating single subtitle mux command")
    muxcmd = []
    muxcmd.append("ffmpeg")
    muxcmd.append("-hide_banner")
    muxcmd.append("-i")
    muxcmd.append(filePath)
    muxcmd.append("-i")
    muxcmd.append(subPath)
    muxcmd.append("-map")
    muxcmd.append("0:v:?") # Map video streams from input 0 (video)
    muxcmd.append("-map")
    muxcmd.append("0:a:?") # Map audio streams from input 0 (video)
    muxcmd.append("-map")
    muxcmd.append("0:s:?") # Map existing subtitle streams from input 0 (video)
    muxcmd.append("-map")
    muxcmd.append("1:s:0?") # Map first subtitle stream from input 1 (subtitle file), optional

    try: # Add try-except for probe
        videoData = ffmpeg.probe(filename=filePath)
        videoStreamsData = videoData.get("streams", []) # Use .get with default
    except ffmpeg.Error as probe_error:
        LOGGER.error(f"Failed to probe video file {filePath} in MergeSub: {probe_error}")
        return None # Cannot proceed without probing

    existingSubTrackCount = 0
    for i in range(len(videoStreamsData)):
        if videoStreamsData[i].get("codec_type") == "subtitle": # Use .get
            existingSubTrackCount += 1

    # Add metadata for the *new* subtitle track being added
    muxcmd.append(f"-metadata:s:s:{existingSubTrackCount}") # Index is 0-based count of *existing* subs
    subTitle = f"Track {existingSubTrackCount+1} - tg@yashoswalyo" # Title for the newly added track
    muxcmd.append(f"title={subTitle}")

    muxcmd.append("-c:v")
    muxcmd.append("copy")
    muxcmd.append("-c:a")
    muxcmd.append("copy")
    muxcmd.append("-c:s")
    muxcmd.append("copy") # Try to copy subtitle codec first

    # --- MODIFIED START ---
    # Use output_path variable
    muxcmd.append(output_path)
    # --- MODIFIED END ---

    LOGGER.info("Muxing single subtitle...")
    # --- MODIFIED START ---
    # Use subprocess.run for better error handling
    process = subprocess.run(muxcmd, capture_output=True, text=True)
    if process.returncode != 0:
         # Try forcing SRT as fallback if copy failed
         if "Subtitle encoding" in process.stderr or "unable to find suitable output format" in process.stderr:
             LOGGER.warning("Subtitle copy failed, retrying with -c:s srt")
             muxcmd[-3] = "srt" # Change subtitle codec
             process_srt = subprocess.run(muxcmd, capture_output=True, text=True)
             if process_srt.returncode != 0:
                 LOGGER.error(f"FFmpeg MergeSub Error (even with SRT):\n{process_srt.stderr}")
                 if os.path.exists(output_path): os.remove(output_path)
                 return None
             else:
                 LOGGER.info(f"FFmpeg MergeSub Output (with SRT):\n{process_srt.stdout}")
                 # Proceed to move
         else:
             LOGGER.error(f"FFmpeg MergeSub Error:\n{process.stderr}")
             if os.path.exists(output_path): os.remove(output_path)
             return None
    else:
        LOGGER.info(f"FFmpeg MergeSub Output:\n{process.stdout}")
    # --- MODIFIED END ---

    # --- MODIFIED START ---
    # Replace original file with the muxed one
    try:
        shutil.move(output_path, filePath)
        LOGGER.info(f"Successfully muxed subtitle into: {filePath}")
        return filePath # Return the original path which now contains the muxed sub
    except Exception as move_err:
        LOGGER.error(f"Failed to move muxed file {output_path} to {filePath}: {move_err}")
        # If move fails, the muxed file is still at output_path
        # Decide whether to return output_path or None. Returning None might be safer.
        return None
    # --- MODIFIED END ---


def MergeSubNew(filePath: str, subPath: str, user_id, file_list):
    """
    This method is for Merging Video + Subtitle(s) Together.

    Parameters:
    - `filePath`: Path to Video file (seems redundant if file_list[0] is video).
    - `subPath`: Path to subtitle file (seems redundant if file_list[1:] are subs).
    - `user_id`: To get parent directory.
    - `file_list`: List of all input files (Expected: [video_path, sub1_path, sub2_path, ...])

    returns: Merged Video File Path or None on failure.
    """
    LOGGER.info("Generating multi-subtitle mux command")
    # --- MODIFIED START ---
    # Use Config.DOWNLOAD_LOCATION and ensure user directory exists
    user_download_dir = os.path.join(Config.DOWNLOAD_LOCATION, str(user_id))
    if not os.path.isdir(user_download_dir):
        try: os.makedirs(user_download_dir)
        except OSError as e:
            LOGGER.error(f"Failed to create directory {user_download_dir} in MergeSubNew: {e}")
            return None
    # Create a temporary output path
    output_path = os.path.join(user_download_dir, f"[MergeSubNew]_{os.path.basename(file_list[0]) if file_list else 'output.mkv'}")

    # Validate file_list
    if not file_list or len(file_list) < 2:
        LOGGER.error("MergeSubNew requires at least one video and one subtitle in file_list.")
        return None

    videoPath = file_list[0]
    subtitlePaths = file_list[1:]

    # Check input file existence
    if not os.path.exists(videoPath):
        LOGGER.error(f"MergeSubNew Error: Video file not found: {videoPath}")
        return None
    for subP in subtitlePaths:
        if not os.path.exists(subP):
            LOGGER.error(f"MergeSubNew Error: Subtitle file not found: {subP}")
            # Optionally remove the missing sub from the list and continue, or fail here.
            return None # Fail if any subtitle is missing
    # --- MODIFIED END ---

    muxcmd = []
    muxcmd.append("ffmpeg")
    muxcmd.append("-hide_banner")

    try: # Add try-except for probe
        videoData = ffmpeg.probe(filename=videoPath)
        videoStreamsData = videoData.get("streams", [])
    except ffmpeg.Error as probe_error:
         LOGGER.error(f"Failed to probe video file {videoPath} in MergeSubNew: {probe_error}")
         return None

    existingSubTrackCount = 0
    for stream in videoStreamsData:
        if stream.get("codec_type") == "subtitle":
            existingSubTrackCount += 1

    # --- MODIFIED START ---
    # Add video input first
    muxcmd.extend(["-i", videoPath])
    # Add all subtitle inputs
    for subP in subtitlePaths:
        muxcmd.extend(["-i", subP])
    # --- MODIFIED END ---

    # --- MODIFIED START ---
    # Map streams: copy all from video, then add new subs
    muxcmd.extend(["-map", "0:v:?"]) # Map video from input 0
    muxcmd.extend(["-map", "0:a:?"]) # Map audio from input 0
    muxcmd.extend(["-map", "0:s:?"]) # Map existing subs from input 0

    # Map new subtitle streams from subsequent inputs
    for i, subP in enumerate(subtitlePaths):
        input_index = i + 1 # Subtitle inputs start from index 1 in ffmpeg command
        muxcmd.extend(["-map", f"{input_index}:s:0?"]) # Map first subtitle stream from this input, optional
        # Add metadata for this new subtitle track
        new_sub_index = existingSubTrackCount + i
        muxcmd.extend([f"-metadata:s:s:{new_sub_index}", f"title=Track {new_sub_index+1} ({os.path.basename(subP)}) - tg@yashoswalyo"])
    # --- MODIFIED END ---

    # --- MODIFIED START ---
    # Copy codecs
    muxcmd.extend(["-c", "copy"]) # Copy all streams (video, audio, subtitle)
    # --- MODIFIED END ---

    # --- MODIFIED START ---
    # Use output_path variable
    muxcmd.append(output_path)
    # --- MODIFIED END ---
    LOGGER.info("Multi-sub muxing command: " + " ".join(muxcmd))

    # --- MODIFIED START ---
    # Use subprocess.run and handle potential codec issues
    process = subprocess.run(muxcmd, capture_output=True, text=True)
    if process.returncode != 0:
        # Try forcing common subtitle codecs if copy failed
        if "Subtitle encoding" in process.stderr or "unable to find suitable output format" in process.stderr:
             LOGGER.warning("Subtitle copy failed, retrying with common subtitle codecs (e.g., mov_text, srt)")
             # Find the '-c copy' and replace it
             try:
                 copy_index = muxcmd.index("-c") + 1
                 muxcmd[copy_index] = "mov_text" # Try mov_text first (common for mp4/mkv)
                 muxcmd.insert(copy_index+1, "-c:s") # Add specific subtitle codec
                 muxcmd.insert(copy_index+2, "srt") # Try srt as well
             except ValueError:
                 LOGGER.error("Could not find '-c copy' to replace for subtitle fallback.")
                 if os.path.exists(output_path): os.remove(output_path)
                 return None

             process_fallback = subprocess.run(muxcmd, capture_output=True, text=True)
             if process_fallback.returncode != 0:
                 LOGGER.error(f"FFmpeg MergeSubNew Error (even with fallback codecs):\n{process_fallback.stderr}")
                 if os.path.exists(output_path): os.remove(output_path)
                 return None
             else:
                 LOGGER.info(f"FFmpeg MergeSubNew Output (with fallback codecs):\n{process_fallback.stdout}")
                 return output_path
        else:
            LOGGER.error(f"FFmpeg MergeSubNew Error:\n{process.stderr}")
            if os.path.exists(output_path): os.remove(output_path)
            return None
    else:
        LOGGER.info(f"FFmpeg MergeSubNew Output:\n{process.stdout}")
        return output_path
    # --- MODIFIED END ---


def MergeAudio(videoPath: str, files_list: list, user_id):
    """
    Merges additional audio tracks into a video file.

    Parameters:
    - `videoPath`: Redundant if files_list[0] is the video.
    - `files_list`: List containing video path first, then audio paths.
                    Example: [video.mkv, audio1.m4a, audio2.mp3]
    - `user_id`: User ID for directory structure.

    Returns: Path to the muxed video file or None on failure.
    """
    LOGGER.info("Generating Multi-Audio Mux Command")
    # --- MODIFIED START ---
    # Use Config.DOWNLOAD_LOCATION and ensure user directory exists
    user_download_dir = os.path.join(Config.DOWNLOAD_LOCATION, str(user_id))
    if not os.path.isdir(user_download_dir):
        try: os.makedirs(user_download_dir)
        except OSError as e:
            LOGGER.error(f"Failed to create directory {user_download_dir} in MergeAudio: {e}")
            return None
    # Create a temporary output path
    output_path = os.path.join(user_download_dir, f"[MergeAudio]_{os.path.basename(files_list[0]) if files_list else 'output.mkv'}")

    # Validate file_list
    if not files_list or len(files_list) < 2:
        LOGGER.error("MergeAudio requires at least one video and one audio file in file_list.")
        return None

    videoPath = files_list[0] # Assume first file is video
    audioPaths = files_list[1:]

    # Check input file existence
    if not os.path.exists(videoPath):
        LOGGER.error(f"MergeAudio Error: Video file not found: {videoPath}")
        return None
    for audP in audioPaths:
        if not os.path.exists(audP):
            LOGGER.error(f"MergeAudio Error: Audio file not found: {audP}")
            return None # Fail if any audio is missing
    # --- MODIFIED END ---

    muxcmd = []
    muxcmd.append("ffmpeg")
    muxcmd.append("-hide_banner")

    try: # Add try-except for probe
        videoData = ffmpeg.probe(filename=videoPath)
        videoStreamsData = videoData.get("streams", [])
    except ffmpeg.Error as probe_error:
         LOGGER.error(f"Failed to probe video file {videoPath} in MergeAudio: {probe_error}")
         return None

    # --- MODIFIED START ---
    # Add video input first
    muxcmd.extend(["-i", videoPath])
    # Add all audio inputs
    for audP in audioPaths:
        muxcmd.extend(["-i", audP])
    # --- MODIFIED END ---

    # --- MODIFIED START ---
    # Map streams: copy all from video, add new audio, manage dispositions
    muxcmd.extend(["-map", "0:v:?"]) # Map video from input 0
    muxcmd.extend(["-map", "0:s:?"]) # Map subtitles from input 0

    # Map existing audio streams from video and clear disposition
    existingAudioTrackCount = 0
    for stream in videoStreamsData:
        if stream.get("codec_type") == "audio":
            stream_index = stream.get("index")
            if stream_index is not None:
                 muxcmd.extend(["-map", f"0:{stream_index}"]) # Map the existing audio stream
                 muxcmd.extend([f"-disposition:a:{existingAudioTrackCount}", "0"]) # Clear disposition
                 existingAudioTrackCount += 1

    firstNewAudioIndex = existingAudioTrackCount # Index for ffmpeg metadata/disposition

    # Map new audio streams from subsequent inputs
    for i, audP in enumerate(audioPaths):
        input_index = i + 1 # Audio inputs start from index 1 in ffmpeg command
        muxcmd.extend(["-map", f"{input_index}:a:0?"]) # Map first audio stream from this input, optional
        # Add metadata for this new audio track
        new_audio_index = firstNewAudioIndex + i
        muxcmd.extend([f"-metadata:s:a:{new_audio_index}", f"title=Track {new_audio_index+1} ({os.path.basename(audP)}) - tg@yashoswalyo"])

    # Set the first *new* audio track as default if new tracks were added
    if audioPaths:
        muxcmd.extend([f"-disposition:a:{firstNewAudioIndex}", "default"])
    # --- MODIFIED END ---

    # --- MODIFIED START ---
    # Copy codecs
    muxcmd.extend(["-c", "copy"]) # Copy all streams (video, audio, subtitle)
    # --- MODIFIED END ---

    # --- MODIFIED START ---
    # Use output_path variable
    muxcmd.append(output_path)
    # --- MODIFIED END ---

    LOGGER.info("Multi-audio mux command: " + " ".join(muxcmd))
    # --- MODIFIED START ---
    # Use subprocess.run
    process = subprocess.run(muxcmd, capture_output=True, text=True)
    if process.returncode != 0:
        LOGGER.error(f"FFmpeg MergeAudio Error:\n{process.stderr}")
        if os.path.exists(output_path): os.remove(output_path)
        return None
    else:
        LOGGER.info(f"FFmpeg MergeAudio Output:\n{process.stdout}")
        return output_path
    # --- MODIFIED END ---


async def cult_small_video(video_file, output_directory, start_time, end_time, format_):
    """Cuts a small video segment."""
    # https://stackoverflow.com/a/13891070/4723940
    # --- MODIFIED START ---
    # Validate inputs
    if not os.path.exists(video_file):
        LOGGER.error(f"cult_small_video: Input video not found: {video_file}")
        return None
    if start_time is None or end_time is None or start_time >= end_time or start_time < 0:
        LOGGER.error(f"cult_small_video: Invalid start/end times: start={start_time}, end={end_time}")
        return None

    # Ensure output directory exists (should be user-specific dir from Config.DOWNLOAD_LOCATION)
    if not os.path.isdir(output_directory):
        try: os.makedirs(output_directory)
        except OSError as e:
            LOGGER.error(f"cult_small_video: Failed to create output directory {output_directory}: {e}")
            return None
    # Sanitize format and create output name
    format_ = sanitize_filename(format_)
    out_put_file_name = os.path.join(output_directory, f"cut_{str(round(start_time))}_{str(round(end_time))}.{format_.lower()}")
    # --- MODIFIED END ---

    # --- MODIFIED START ---
    # Attempt fast cut using -c copy first
    file_generator_command_copy = [
        "ffmpeg", "-hide_banner",
        # Input seeking (faster for some formats)
        "-ss", str(start_time),
        "-to", str(end_time),
        "-i", video_file,
        "-map", "0", # Map all streams
        "-c", "copy", # Attempt codec copy
        "-avoid_negative_ts", "make_zero", # Handle potential timestamp issues
        out_put_file_name,
    ]
    process_copy = await asyncio.create_subprocess_exec(
        *file_generator_command_copy,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout_copy, stderr_copy = await process_copy.communicate()

    if process_copy.returncode == 0 and os.path.exists(out_put_file_name):
        LOGGER.info(f"FFmpeg cult_small_video (copy) successful: {out_put_file_name}")
        return out_put_file_name
    else:
        LOGGER.warning(f"FFmpeg cult_small_video with copy failed (Code: {process_copy.returncode}). Retrying with re-encode.")
        LOGGER.debug(f"FFmpeg copy stderr:\n{stderr_copy.decode().strip()}")
        # Clean up potentially incomplete copied file
        if os.path.exists(out_put_file_name):
            try: os.remove(out_put_file_name)
            except OSError: pass

        # Fallback to re-encoding if copy failed
        file_generator_command_reencode = [
            "ffmpeg", "-hide_banner",
            "-ss", str(start_time),
            "-to", str(end_time),
            "-i", video_file,
            "-map", "0", # Map all streams
            # Re-encode settings (adjust as needed)
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-async", "1", # Sync audio to timestamps
            "-strict", "-2", # Allow experimental AAC
            out_put_file_name,
        ]
        process_reencode = await asyncio.create_subprocess_exec(
            *file_generator_command_reencode,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout_reencode, stderr_reencode = await process_reencode.communicate()

        if process_reencode.returncode == 0 and os.path.exists(out_put_file_name):
            LOGGER.info(f"FFmpeg cult_small_video (re-encode) successful: {out_put_file_name}")
            return out_put_file_name
        else:
            LOGGER.error(f"FFmpeg cult_small_video Error (re-encode also failed). Code: {process_reencode.returncode}")
            LOGGER.error(f"FFmpeg re-encode stderr:\n{stderr_reencode.decode().strip()}")
            if os.path.exists(out_put_file_name): # Clean up failed attempt
                try: os.remove(out_put_file_name)
                except OSError: pass
            return None
    # --- MODIFIED END ---


async def take_screen_shot(video_file, output_directory, ttl):
    """
    Generates a screenshot (thumbnail) from a video file.

    Parameters:
    - `video_file`: Path to the video file.
    - `output_directory`: Path to the user-specific directory (e.g., .../downloads/userid).
    - `ttl`: Timestamp (in seconds) to generate the screenshot.

    Returns: Path to the generated screenshot JPG file or None on failure.
    """
    # https://stackoverflow.com/a/13891070/4723940
    # --- MODIFIED START ---
    # Validate inputs
    if not os.path.exists(video_file):
        LOGGER.error(f"take_screen_shot: Input video not found: {video_file}")
        return None

    # Ensure output directory exists (should be user-specific dir from Config.DOWNLOAD_LOCATION)
    if not os.path.isdir(output_directory):
        try: os.makedirs(output_directory)
        except OSError as e:
            LOGGER.error(f"take_screen_shot: Failed to create output directory {output_directory}: {e}")
            return None

    # Validate ttl and get video duration if needed
    try:
        probe = ffmpeg.probe(video_file)
        duration = float(probe.get('format', {}).get('duration', 0))
        if ttl is None or ttl < 0 or ttl > duration:
             ttl = min(max(1, duration / 2), 10) # Default to middle or 1s/10s
             LOGGER.warning(f"Invalid TTL for screenshot ({ttl}s), using calculated time: {ttl:.2f}s (Duration: {duration:.2f}s)")
    except ffmpeg.Error as probe_error:
         LOGGER.error(f"Failed to probe video {video_file} for duration: {probe_error}. Using default ttl=1.")
         if ttl is None or ttl < 0: ttl = 1
    except Exception as e:
         LOGGER.error(f"Error getting duration for {video_file}: {e}. Using default ttl=1.")
         if ttl is None or ttl < 0: ttl = 1

    out_put_file_name = os.path.join(output_directory, f"thumbnail_{str(round(time.time()))}.jpg")
    # --- MODIFIED END ---

    # --- MODIFIED START ---
    # Check if input is likely a video file based on extension (basic check)
    video_file_lower = video_file.lower()
    allowed_extensions = (".mkv", ".mp4", ".webm", ".avi", ".mov", ".ogg", ".wmv", ".m4v", ".ts", ".mpg", ".mts", ".m2ts", ".3gp")
    if not video_file_lower.endswith(allowed_extensions):
        LOGGER.warning(f"Cannot take screenshot for non-video file based on extension: {video_file}")
        # return None # Allow ffmpeg to try anyway, it might handle it
    # --- MODIFIED END ---

    file_genertor_command = [
        "ffmpeg", "-hide_banner",
        "-ss", str(ttl),      # Seek to the desired timestamp
        "-i", video_file,     # Input file
        "-vframes", "1",      # Extract only one frame
        "-q:v", "3",          # Quality scale for JPG (2-5 is good)
        "-vf", "scale=320:-1", # Scale width to 320px, maintain aspect ratio
        out_put_file_name,
    ]

    process = await asyncio.create_subprocess_exec(
        *file_genertor_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    e_response = stderr.decode().strip()
    # t_response = stdout.decode().strip() # stdout usually empty for screenshot

    # --- MODIFIED START ---
    # Check return code and log errors
    if process.returncode == 0 and os.path.exists(out_put_file_name):
        LOGGER.info(f"Screenshot taken successfully: {out_put_file_name}")
        return out_put_file_name
    else:
        LOGGER.error(f"FFmpeg take_screen_shot Error (Code: {process.returncode}):\n{e_response}")
        if os.path.exists(out_put_file_name): # Clean up failed attempt
            try: os.remove(out_put_file_name)
            except OSError: pass
        return None
    # --- MODIFIED END ---


async def extractAudios(path_to_file, user_id):
    """
    Extracts all audio streams from a media file.

    Returns: Path to the directory containing extracted files, or None if failed/no streams.
    """
    # --- MODIFIED START ---
    # Use Config.DOWNLOAD_LOCATION structure
    user_download_dir = os.path.join(Config.DOWNLOAD_LOCATION, str(user_id))
    extract_dir = os.path.join(user_download_dir, "extract_audio") # Specific subdir
    # --- MODIFIED END ---

    if not os.path.exists(path_to_file):
        LOGGER.error(f"Input file not found for audio extraction: {path_to_file}")
        return None
    # --- MODIFIED START ---
    # Ensure extract directory exists
    if not os.path.exists(extract_dir):
        try: os.makedirs(extract_dir)
        except OSError as e:
             LOGGER.error(f"Failed to create audio extract directory {extract_dir}: {e}")
             return None
    # --- MODIFIED END ---

    try: # Add try-except for probe
        probeData = ffmpeg.probe(path_to_file)
    except ffmpeg.Error as probe_error:
         LOGGER.error(f"Failed to probe file {path_to_file} for audio extraction: {probe_error}")
         return None

    # with open("data.json",'w') as f:
    #     f.write(json.dumps(probeData))
    audios = []
    streams = probeData.get("streams", [])
    for stream in streams:
        # --- MODIFIED START ---
        # Check codec_type safely
        if stream.get("codec_type") == "audio":
            audios.append(stream)
        # --- MODIFIED END ---

    if not audios:
        LOGGER.warning(f"No audio streams found in {path_to_file}")
        return None # Return None if no audio streams

    extracted_files_count = 0 # Flag to check if any file was actually extracted
    for audio_stream in audios:
        extractcmd = []
        extractcmd.append("ffmpeg")
        extractcmd.append("-hide_banner")
        extractcmd.append("-i")
        extractcmd.append(path_to_file)
        extractcmd.append("-map")
        try:
            index = audio_stream.get("index") # Use .get
            if index is None:
                LOGGER.warning(f"Skipping audio stream with no index: {audio_stream}")
                continue
            extractcmd.append(f"0:{index}") # Map specific audio stream

            # --- MODIFIED START ---
            # Improved filename generation
            tags = audio_stream.get("tags", {})
            lang = tags.get("language", "und") # Default to 'und' (undetermined)
            title = tags.get("title", f"Track_{index}")
            codec = audio_stream.get("codec_name", "audio")
            # Sanitize title more thoroughly
            safe_title = sanitize_filename(title, replacement='_')
            # Use appropriate extension based on codec if possible
            ext_map = {'aac': 'aac', 'mp3': 'mp3', 'opus': 'opus', 'flac': 'flac', 'ac3': 'ac3', 'eac3': 'eac3', 'dts': 'dts', 'truehd': 'thd'}
            output_ext = ext_map.get(codec, 'mka') # Default to mka container
            output_file = f"Audio_{index}.({lang}).{safe_title}.{output_ext}"
            output_filepath = os.path.join(extract_dir, output_file)
            # --- MODIFIED END ---

            extractcmd.append("-c")
            extractcmd.append("copy") # Copy codec
            extractcmd.append(output_filepath)
            LOGGER.info("Audio Extract Command: " + " ".join(extractcmd))

            # --- MODIFIED START ---
            # Use subprocess.run
            process = subprocess.run(extractcmd, capture_output=True, text=True)
            if process.returncode != 0:
                 LOGGER.error(f"FFmpeg extractAudios Error for stream {index}:\n{process.stderr}")
                 if os.path.exists(output_filepath): # Clean failed attempt
                      try: os.remove(output_filepath)
                      except OSError: pass
            else:
                 # LOGGER.info(f"FFmpeg extractAudios Output for stream {index}:\n{process.stdout}")
                 extracted_files_count += 1 # Increment count of successfully extracted files
            # --- MODIFIED END ---
        except Exception as e:
            LOGGER.error(f"Something went wrong processing audio stream index {index}: {e}", exc_info=True)

    # --- MODIFIED START ---
    # Check if any files were actually extracted
    if extracted_files_count > 0 and os.path.exists(extract_dir) and get_path_size(extract_dir) > 0:
        LOGGER.info(f"Successfully extracted {extracted_files_count} audio streams to {extract_dir}")
        return extract_dir
    else:
        LOGGER.warning(f"Audio extraction finished, but no files were successfully extracted to '{extract_dir}'.")
        # Clean up the extract directory if it's empty and was created by us
        if os.path.exists(extract_dir):
            try:
                if not os.listdir(extract_dir):
                     os.rmdir(extract_dir)
            except OSError:
                pass # Ignore if directory not empty or other error
        return None
    # --- MODIFIED END ---


async def extractSubtitles(path_to_file, user_id):
    """
    Extracts all subtitle streams from a media file.

    Returns: Path to the directory containing extracted files, or None if failed/no streams.
    """
    # --- MODIFIED START ---
    # Use Config.DOWNLOAD_LOCATION structure
    user_download_dir = os.path.join(Config.DOWNLOAD_LOCATION, str(user_id))
    extract_dir = os.path.join(user_download_dir, "extract_subtitle") # Specific subdir
    # --- MODIFIED END ---

    if not os.path.exists(path_to_file):
        LOGGER.error(f"Input file not found for subtitle extraction: {path_to_file}")
        return None
    # --- MODIFIED START ---
    # Ensure extract directory exists
    if not os.path.exists(extract_dir):
        try: os.makedirs(extract_dir)
        except OSError as e:
             LOGGER.error(f"Failed to create subtitle extract directory {extract_dir}: {e}")
             return None
    # --- MODIFIED END ---

    try: # Add try-except for probe
        probeData = ffmpeg.probe(path_to_file)
    except ffmpeg.Error as probe_error:
         LOGGER.error(f"Failed to probe file {path_to_file} for subtitle extraction: {probe_error}")
         return None

    # with open("data.json",'w') as f:
    #     f.write(json.dumps(probeData))
    subtitles = []
    streams = probeData.get("streams", [])
    for stream in streams:
        # --- MODIFIED START ---
        # Check codec_type safely
        if stream.get("codec_type") == "subtitle":
             subtitles.append(stream)
        # --- MODIFIED END ---

    if not subtitles:
        LOGGER.warning(f"No subtitle streams found in {path_to_file}")
        return None # Return None if no subtitle streams

    extracted_files_count = 0 # Flag to check if any file was actually extracted
    for subtitle_stream in subtitles:
        extractcmd = []
        extractcmd.append("ffmpeg")
        extractcmd.append("-hide_banner")
        # --- MODIFIED START ---
        # Use -dump_attachment for embedded fonts/files if needed, but complicates things.
        # Stick to mapping the stream for now.
        extractcmd.append("-i")
        extractcmd.append(path_to_file)
        extractcmd.append("-map")
        # --- MODIFIED END ---
        try:
            index = subtitle_stream.get("index") # Use .get
            if index is None:
                LOGGER.warning(f"Skipping subtitle stream with no index: {subtitle_stream}")
                continue
            extractcmd.append(f"0:{index}") # Map specific subtitle stream

            # --- MODIFIED START ---
            # Improved filename generation and codec handling
            tags = subtitle_stream.get("tags", {})
            lang = tags.get("language", "und")
            title = tags.get("title", f"Track_{index}")
            codec = subtitle_stream.get("codec_name", "sub") # e.g., 'srt', 'ass', 'subrip', 'mov_text'
            safe_title = sanitize_filename(title, replacement='_')

            # Determine appropriate output extension
            ext_map = {'srt': 'srt', 'ass': 'ass', 'ssa': 'ass', 'subrip': 'srt', 'mov_text': 'srt', 'webvtt': 'vtt', 'pgs':'sup', 'dvd_subtitle': 'sub'}
            output_ext = ext_map.get(codec, 'mks') # Default to .mks container if unknown/graphical

            output_file = f"Subtitle_{index}.({lang}).{safe_title}.{output_ext}"
            output_filepath = os.path.join(extract_dir, output_file)

            extractcmd.append("-c")
            # If codec is common text-based, specify it for ffmpeg, otherwise copy
            if codec in ext_map and output_ext != 'mks':
                 extractcmd.append(output_ext) # Convert to this text format
            else:
                 extractcmd.append("copy") # Copy if graphical or already in a container

            extractcmd.append(output_filepath)
            # --- MODIFIED END ---

            LOGGER.info("Subtitle Extract Command: " + " ".join(extractcmd))
            # --- MODIFIED START ---
            # Use subprocess.run
            process = subprocess.run(extractcmd, capture_output=True, text=True)
            if process.returncode != 0:
                 LOGGER.error(f"FFmpeg extractSubtitles Error for stream {index}:\n{process.stderr}")
                 if os.path.exists(output_filepath): # Clean failed attempt
                      try: os.remove(output_filepath)
                      except OSError: pass
            else:
                 # LOGGER.info(f"FFmpeg extractSubtitles Output for stream {index}:\n{process.stdout}")
                 extracted_files_count += 1 # Increment count
            # --- MODIFIED END ---
        except Exception as e:
            LOGGER.error(f"Something went wrong processing subtitle stream index {index}: {e}", exc_info=True)

    # --- MODIFIED START ---
    # Check if any files were actually extracted
    if extracted_files_count > 0 and os.path.exists(extract_dir) and get_path_size(extract_dir) > 0:
        LOGGER.info(f"Successfully extracted {extracted_files_count} subtitle streams to {extract_dir}")
        return extract_dir
    else:
        LOGGER.warning(f"Subtitle extraction finished, but no files were successfully extracted to '{extract_dir}'.")
        # Clean up the extract directory if it's empty and was created by us
        if os.path.exists(extract_dir):
            try:
                if not os.listdir(extract_dir):
                     os.rmdir(extract_dir)
            except OSError:
                pass # Ignore if directory not empty or other error
        return None
    # --- MODIFIED END ---

# --- MODIFIED START ---
async def edit_video_metadata(input_path: str, output_path: str, metadata_dict: dict) -> str | None:
    """
    Edits video metadata using ffmpeg by creating a new file.

    Parameters:
    - `input_path`: Path to the input video file.
    - `output_path`: Path for the output video file with edited metadata.
    - `metadata_dict`: Dictionary containing metadata keys ('title', 'description', 'tags').
                       Values should be strings.

    Returns: Output file path if successful, None otherwise.
    """
    if not os.path.exists(input_path):
        LOGGER.error(f"edit_video_metadata: Input file not found: {input_path}")
        return None
    if not metadata_dict:
        LOGGER.warning("edit_video_metadata: No metadata provided to edit.")
        return input_path # Return original path if no edits needed

    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if not os.path.isdir(output_dir):
         try: os.makedirs(output_dir)
         except OSError as e:
             LOGGER.error(f"edit_video_metadata: Failed to create output directory {output_dir}: {e}")
             return None

    LOGGER.info(f"Attempting to edit metadata for: {input_path} -> {output_path}")
    command = [
        "ffmpeg", "-hide_banner",
        "-i", input_path,
        "-map_metadata", "0",          # Copy existing global metadata first
        "-map", "0",                  # Map all streams from input 0
        "-c", "copy",                 # Copy all streams without re-encoding
    ]

    # Add new/updated metadata flags (clears existing keys if set)
    # Use standard metadata keys recognized by ffmpeg/players
    # Ref: https://wiki.multimedia.cx/index.php/FFmpeg_Metadata
    # Ref: https://ffmpeg.org/ffmpeg-formats.html#Metadata-1
    added_meta = False
    if metadata_dict.get("title"):
        command.extend(["-metadata", f"title={metadata_dict['title']}"])
        added_meta = True
    if metadata_dict.get("description"):
        # Use 'comment' or 'description' - 'comment' is often more widely supported
        command.extend(["-metadata", f"comment={metadata_dict['description']}"])
        # command.extend(["-metadata", f"description={metadata_dict['description']}"]) # Less common
        added_meta = True
    if metadata_dict.get("tags"):
        # Tags can go into 'keywords', 'tags', or appended to 'comment'/'genre'
        command.extend(["-metadata", f"keywords={metadata_dict['tags']}"]) # Common field
        # command.extend(["-metadata", f"tags={metadata_dict['tags']}"]) # Another possibility
        added_meta = True
    # Add a generic handler name
    command.extend(["-metadata", "handler_name=MergeBotEdit"])

    # Add output path
    command.append(output_path)

    # If no metadata was actually added, maybe just return original path?
    if not added_meta:
        LOGGER.warning("edit_video_metadata: No valid metadata keys found in dict. Skipping edit.")
        return input_path

    LOGGER.info("Metadata Edit Command: " + " ".join(command))

    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        e_response = stderr.decode().strip()
        # t_response = stdout.decode().strip() # stdout often empty

        if process.returncode != 0:
            LOGGER.error(f"FFmpeg metadata edit failed (Code: {process.returncode}):\n{e_response}")
            if os.path.exists(output_path): # Clean up failed output
                 try: os.remove(output_path)
                 except OSError: pass
            return None # Return None on failure
        else:
            # LOGGER.info(f"FFmpeg metadata edit Output:\n{t_response}")
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                LOGGER.info(f"Metadata edited successfully. Output: {output_path}")
                # Optionally remove the original input file after successful edit
                # try: os.remove(input_path)
                # except OSError as rm_err: LOGGER.warning(f"Could not remove original file after metadata edit: {rm_err}")
                return output_path
            else:
                LOGGER.error("FFmpeg metadata edit command finished successfully, but output file not found or is empty.")
                return None # Return None if output is invalid
    except Exception as e:
        LOGGER.error(f"Error running ffmpeg for metadata edit: {e}", exc_info=True)
        if os.path.exists(output_path): # Clean up potentially partial output
             try: os.remove(output_path)
             except OSError: pass
        return None # Return None on exception
# --- MODIFIED END ---
# --- END OF FILE MERGE-BOT-master/helpers/ffmpeg_helper.py ---
