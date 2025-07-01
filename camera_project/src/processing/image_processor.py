import os
from datetime import datetime
from PIL import Image, ImageTk, ImageDraw, ImageFont
import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor

class ImageProcessor:
    def __init__(self, settings, logger):
        self.logger = logger
        self.image_dir = settings.get("image_dir", "data/images/")
        self.image_format = settings.get("image_format", "jpeg").lower()
        self.jpeg_quality = settings.get("jpeg_quality", 90)
        os.makedirs(self.image_dir, exist_ok=True)
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.logger.info(f"ImageProcessor initialized: image_dir={self.image_dir}, format={self.image_format}")

    def resize_image(self, image, width, height, margin=0, max_width=None, max_height=None):
        if isinstance(image, np.ndarray):
            img_height, img_width = image.shape[:2]
        else:
            img_width, img_height = image.size
        
        target_width = width - 2 * margin
        target_height = height - 2 * margin
        
        aspect_ratio = img_width / img_height
        if target_width / target_height > aspect_ratio:
            new_height = target_height
            new_width = int(new_height * aspect_ratio)
        else:
            new_width = target_width
            new_height = int(new_width / aspect_ratio)

        if max_width and max_height:
            new_width = min(new_width, max_width)
            new_height = min(new_height, max_height)
            if new_width / new_height > aspect_ratio:
                new_width = int(new_height * aspect_ratio)
            else:
                new_height = int(new_width / aspect_ratio)

        new_width = max(1, new_width)
        new_height = max(1, new_height)

        if isinstance(image, np.ndarray):
            resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
            return resized
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        return resized

    def convert_to_photo(self, image):
        if isinstance(image, np.ndarray):
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(image_rgb)
        else:
            pil_image = image
        photo = ImageTk.PhotoImage(pil_image)
        return photo

    def save_image(self, image):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        ext = self.image_format
        filename = f"image_{timestamp}.{ext}"
        filepath = os.path.join(self.image_dir, filename)
        
        def save_to_file(img, path, fmt, quality):
            try:
                if isinstance(img, np.ndarray):
                    if fmt == "jpeg":
                        cv2.imwrite(path, img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
                    else:
                        cv2.imwrite(path, img)
                else:
                    if fmt == "jpeg":
                        img.save(path, "JPEG", quality=quality)
                    else:
                        img.save(path)
                self.logger.info(f"Saved {filename}")
                return True, f"Saved {filename}"
            except Exception as e:
                self.logger.error(f"Error saving {filename}: {e}")
                return False, f"Error saving {filename}: {e}"

        future = self.executor.submit(save_to_file, image, filepath, ext, self.jpeg_quality)
        return future.result(timeout=10)

    def load_placeholder(self, path):
        try:
            img = Image.open(path)
            self.logger.info(f"Loaded placeholder from {path}")
            return img
        except Exception as e:
            self.logger.warning(f"Failed to load placeholder from {path}: {e}")
            img = Image.new("RGB", (400, 400))
            draw = ImageDraw.Draw(img)
            for y in range(400):
                r = 30 + (y * (60 - 30) // 400)
                g = 30 + (y * (60 - 30) // 400)
                b = 50 + (y * (80 - 50) // 400)
                draw.line((0, y, 400, y), fill=(r, g, b))
            try:
                font = ImageFont.truetype("arial.ttf", 40)
            except:
                font = ImageFont.load_default()
            draw.text((20, 160), "IS8502C Camera", fill="white", font=font)
            self.logger.info("Generated fallback placeholder image")
            return img