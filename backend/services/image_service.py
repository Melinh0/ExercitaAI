import os
import re
import fitz
from werkzeug.utils import secure_filename

from config import Config

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg'}


def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def extract_images_from_pdf(pdf_path, destination_folder):
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)
    doc = fitz.open(pdf_path)
    image_names = []
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    base_name = re.sub(r'[^\w\-_]', '_', base_name)
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        image_name = f"{base_name}_pag{page_num+1:03d}.png"
        full_path = os.path.join(destination_folder, image_name)
        pix.save(full_path)
        image_names.append(image_name)
    doc.close()
    return image_names


def save_uploaded_images(files, destination_folder, max_files=None):
    if max_files is None:
        max_files = Config.UPLOAD_MAX_FILES
    os.makedirs(destination_folder, exist_ok=True)
    saved_count = 0
    saved_names = []
    for file in files:
        if saved_count >= max_files:
            break
        if file and allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
            original_filename = secure_filename(file.filename)
            name, ext = os.path.splitext(original_filename)
            if not ext:
                ext = '.png'
            counter = 1
            new_filename = original_filename
            while os.path.exists(os.path.join(destination_folder, new_filename)):
                new_filename = f"{name}_{counter}{ext}"
                counter += 1
            file.save(os.path.join(destination_folder, new_filename))
            saved_count += 1
            saved_names.append(new_filename)
    return saved_count, saved_names