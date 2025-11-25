# Utility functions for the Mars blog (image upload helpers, etc.)
import os
import secrets
from PIL import Image
from werkzeug.utils import secure_filename


def save_uploaded_image(file, upload_folder, max_width=1920, max_height=1080):
    """
    Save uploaded image file with resizing and secure filename.
    Returns: (filename, file_path, width, height, file_size)
    """
    # Generate secure random filename
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{secrets.token_urlsafe(16)}.{ext}"
    file_path = os.path.join(upload_folder, filename)
    
    # Ensure upload folder exists
    os.makedirs(upload_folder, exist_ok=True)
    
    # Save and optionally resize
    img = Image.open(file)
    width, height = img.size
    
    # Resize if too large
    if width > max_width or height > max_height:
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        width, height = img.size
    
    # Convert RGBA to RGB if needed (for JPEG)
    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = background
    
    img.save(file_path, optimize=True, quality=85)
    file_size = os.path.getsize(file_path)
    
    return filename, file_path, width, height, file_size


