import tkinter as tk
import time
from camera.camera_controller import CameraController
from gui.camera_gui import CameraGUI
from processing.image_processor import ImageProcessor
from config.settings import CAMERA_SETTINGS, GUI_SETTINGS, PATHS, setup_logging

def main():
    """Initialize and run the camera control application."""
    # Set up logging
    logger = setup_logging(PATHS["log_dir"])
    
    # Initialize modules
    camera_controller = CameraController(CAMERA_SETTINGS, logger)
    image_processor = ImageProcessor(PATHS, logger)
    
    # Initialize Tkinter root
    root = tk.Tk()
    
    # Connect to camera with retries
    max_retries = 3
    for attempt in range(max_retries):
        try:
            success, msg = camera_controller.connect()
            if success:
                logger.info("Camera connected successfully")
                break
            logger.error(f"Connection attempt {attempt + 1} failed: {msg}")
            time.sleep(1)
        except Exception as e:
            logger.error(f"Connection attempt {attempt + 1} error: {e}")
            time.sleep(1)
    else:
        logger.error(f"Failed to connect to camera after {max_retries} attempts")
        root.destroy()
        return
    
    # Initialize GUI
    app = CameraGUI(root, camera_controller, image_processor, GUI_SETTINGS, logger)
    
    # Run Tkinter main loop
    try:
        root.mainloop()
    except Exception as e:
        logger.error(f"Application error: {e}")
    finally:
        camera_controller.stop()
        try:
            if root.winfo_exists():
                root.destroy()
        except tk.TclError:
            logger.debug("Tkinter root already destroyed")

if __name__ == "__main__":
    main()