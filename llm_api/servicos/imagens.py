import base64
import io

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def decode_image(image_base64: str) -> bytes:
    if not image_base64:
        return b""
    if ',' in image_base64 and image_base64.startswith('data:image'):
        _, data = image_base64.split(',', 1)
    else:
        data = image_base64
    try:
        return base64.b64decode(data)
    except Exception:
        return b""


def _otsu_threshold(gray_img: Image.Image) -> int:
    arr = np.array(gray_img)
    hist, _ = np.histogram(arr, bins=256, range=(0, 255))
    total = arr.size
    if total == 0:
        return 128
    sum_total = np.sum(arr)
    sum_b = 0
    w_b = 0
    w_f = 0
    max_var = 0
    threshold = 128
    for i in range(256):
        w_b += hist[i]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += i * hist[i]
        m_b = sum_b / w_b
        m_f = (sum_total - sum_b) / w_f
        var_between = w_b * w_f * (m_b - m_f) ** 2
        if var_between > max_var:
            max_var = var_between
            threshold = i
    return threshold


def _variant_raw_gray(image_bytes: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != 'L':
        img = img.convert('L')
    return img


def _variant_resized_autocontrast(image_bytes: bytes) -> Image.Image:
    img = _variant_raw_gray(image_bytes)
    max_width = 1600
    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    img = ImageOps.autocontrast(img, cutoff=1)
    return img


def _variant_contrast_sharp(image_bytes: bytes) -> Image.Image:
    img = _variant_resized_autocontrast(image_bytes)
    img = ImageEnhance.Contrast(img).enhance(1.5)
    img = ImageEnhance.Sharpness(img).enhance(1.5)
    return img


def _variant_unsharp(image_bytes: bytes) -> Image.Image:
    img = _variant_resized_autocontrast(image_bytes)
    try:
        img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))
    except Exception:
        pass
    return img


def _variant_median(image_bytes: bytes) -> Image.Image:
    img = _variant_resized_autocontrast(image_bytes)
    try:
        img = img.filter(ImageFilter.MedianFilter(size=3))
    except Exception:
        pass
    return img


def _variant_binarized(image_bytes: bytes) -> Image.Image:
    img = _variant_resized_autocontrast(image_bytes)
    try:
        threshold = _otsu_threshold(img)
        img = img.point(lambda p: 255 if p > threshold else 0, mode='L')
    except Exception:
        pass
    return img


VARIANT_BUILDERS = [
    ("raw_gray", _variant_raw_gray),
    ("resized_autocontrast", _variant_resized_autocontrast),
    ("contrast_sharp", _variant_contrast_sharp),
    ("unsharp", _variant_unsharp),
    ("median", _variant_median),
    ("binarized", _variant_binarized),
]
