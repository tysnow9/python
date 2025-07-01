import os
import logging

# Project settings for camera, GUI, and file paths

# Camera settings for IS8502C
CAMERA_SETTINGS = {
    "ip": "100.1.9.31",
    "telnet_port": 23,
    "username": "admin",
    "password": "",
    "image_filename": "image.bmp",
    "timeout": 20,  # Increased from 15 to 20 seconds
    "stream_interval": 2.0,
    "stop_time": "04:20"  # Stop at 11:30 PM by default
}

# GUI settings
GUI_SETTINGS = {
    "window_size": "1200x800",
    "placeholder_image_path": "data/placeholder.bmp"
}

# File paths and image settings
PATHS = {
    "image_dir": "data/images/",
    "log_dir": "data/logs/",
    "image_format": "jpeg",
    "jpeg_quality": 100
}

def setup_logging(log_dir):
    """Set up logging to file and console without duplication."""
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "app.log")

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    logger.handlers.clear()

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        "[%(asctime)s.%(msecs)03d] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "[%(asctime)s.%(msecs)03d] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.propagate = False

    logger.info("Logging initialized")
    return logger