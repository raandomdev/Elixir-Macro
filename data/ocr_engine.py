import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import sys
from difflib import SequenceMatcher
import re

try:
    import easyocr
    ocr_reader = easyocr.Reader(['en'])
except Exception:
    ocr_reader = None
    try:
        import pytesseract
    except ImportError:
        pass

CHAR_FIXES = {
    '0': 'O',
    '1': 'l',
    '5': 'S',
    '8': 'B',
    '|': 'l',
}


def prep_image(image, contrast=2.0, sharp=2.0, bright=1.1):
    try:
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        image = ImageEnhance.Contrast(image).enhance(contrast)
        image = ImageEnhance.Sharpness(image).enhance(sharp)
        image = ImageEnhance.Brightness(image).enhance(bright)
        image = image.filter(ImageFilter.SHARPEN)
        
        return image
    except Exception:
        return image


def clean_text(text):
    for char, fix in CHAR_FIXES.items():
        text = text.replace(char, fix)
    
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('\n', ' ')
    
    return text.strip()


def fuzzy_match(text, target, threshold=0.75):
    target = target.lower().strip()
    text = text.lower().strip()
    
    if target in text:
        return True
    
    ratio = SequenceMatcher(None, text, target).ratio()
    return ratio >= threshold


def perform_ocr(image, min_conf=0.3, letters=False):
    global ocr_reader
    
    try:
        image = prep_image(image)
        
        if ocr_reader is not None:
            try:
                img_arr = np.array(image)
                results = ocr_reader.readtext(img_arr)
                
                texts = []
                for detection in results:
                    text = detection[1]
                    conf = detection[2]
                    
                    if conf >= min_conf:
                        texts.append(text)
                
                text = ' '.join(texts).strip().lower()
                cleaned = clean_text(text)
                if letters:
                    letters_only = re.sub(r'[^A-Za-z ]+', '', cleaned)
                    letters_only = re.sub(r'\s+', ' ', letters_only).strip()
                    return letters_only
                return cleaned
            except Exception:
                return ""
        else:
            try:
                import pytesseract
                text = pytesseract.image_to_string(
                    image,
                    config='--psm 6 --oem 3'
                ).strip().lower()
                cleaned = clean_text(text)
                if letters:
                    letters_only = re.sub(r'[^A-Za-z ]+', '', cleaned)
                    letters_only = re.sub(r'\s+', ' ', letters_only).strip()
                    return letters_only
                return cleaned
            except Exception:
                return ""
    
    except Exception:
        return ""


def search_text_in_ocr(image, search_text, use_fuzzy=True, fuzzy_threshold=0.75):
    try:
        text = perform_ocr(image)
        search_text = search_text.lower().strip()
        
        if search_text in text:
            return True
        
        if use_fuzzy:
            return fuzzy_match(text, search_text, fuzzy_threshold)
        
        return False
    except Exception:
        return False


def check_ocr_text(x1, y1, x2, y2, search_text, use_fuzzy=True):
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        return search_text_in_ocr(img, search_text, use_fuzzy=use_fuzzy)
    except Exception:
        return False


def get_ocr_text(image):
    return perform_ocr(image)


def perform_ocr_letters(image, min_conf=0.3):
    """Return OCR output restricted to letters and spaces."""
    return perform_ocr(image, min_conf=min_conf, letters=True)
