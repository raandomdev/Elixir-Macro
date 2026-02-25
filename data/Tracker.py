import os
import re
import json
import requests
import time
import logging
import threading
from pathlib import Path
import discord_webhook as discord
from datetime import datetime
from data import config as ok
import pyautogui as auto
from PIL import Image, ImageGrab, ImageEnhance
import numpy as np
from difflib import SequenceMatcher
import easyocr, sys
from tkinter import messagebox
try:
    if sys.platform == "darwin":
        import mouse, keyboard
        print("macOS detected.. using mouse, keyboard imports.")
    else:
        from ahk import AHK
        ahk = AHK()
        print("Windows detected.. using AutoHotkey import.")
except:
    messagebox.showerror("Error", "Error on loading basic imports, please redownload this software and try again.\nIf this continues, please report this to Golden (@spacedev0527).")
    sys.exit(1)

# Initialize EasyOCR reader - works on both Windows and macOS
try:
    ocr_reader = easyocr.Reader(['en'])
    print("EasyOCR initialized successfully")
except Exception as e:
    print(f"EasyOCR initialization failed: {e}")
    # Fallback to pytesseract if EasyOCR fails
    try:
        import pytesseract
        from PIL import Image
        print("Fallback to pytesseract initialized")
        ocr_reader = None
    except ImportError:
        messagebox.showerror("OCR Error", "Neither EasyOCR nor pytesseract could be initialized. Please install EasyOCR: pip install easyocr")
        sys.exit(1)
ocr_text = None
last_biome = None
last_aura = None
def perform_ocr(image):
    """
    Perform OCR using EasyOCR or fallback to pytesseract
    Works on both Windows and macOS
    Returns the extracted text in lowercase
    """
    global ocr_reader
    
    # Enhance image for better OCR
    enhanced_image = ImageEnhance.Contrast(image).enhance(2.0)
    enhanced_image = ImageEnhance.Sharpness(enhanced_image).enhance(2.0)
    
    if ocr_reader is not None:
        # Use EasyOCR
        try:
            image_array = np.array(enhanced_image)
            results = ocr_reader.readtext(image_array)
            text = ' '.join([result[1] for result in results]).strip().lower().replace('\n', ' ')
            global ocr_text
            ocr_text = text
            return text
        except Exception as e:
            print(f"EasyOCR error: {e}")
            return ""
    else:
        # Fallback to pytesseract
        try:
            import pytesseract
            text = pytesseract.image_to_string(enhanced_image, config='--psm 6').strip().lower().replace('\n', ' ')
            return text
        except Exception as e:
            print(f"Pytesseract error: {e}")
            return ""

def search_text_in_ocr(image, search_text):
    """
    Search for specific text within OCR results.
    Returns True if text is found, False otherwise.
    
    Args:
        image: PIL Image to perform OCR on
        search_text: Text to search for (will be converted to lowercase)
    
    Returns:
        bool: True if search_text is found in the OCR result
    
    Example:
        if search_text_in_ocr(screenshot, "merchant"):
            # Do something
    """
    extracted_text = perform_ocr(image)
    search_text_lower = search_text.lower().strip()
    return search_text_lower in extracted_text

def check_ocr_text(x1, y1, x2, y2, search_text):
    """
    Take a screenshot of a region and search for text within it.
    
    Args:
        x1, y1: Top-left corner of region
        x2, y2: Bottom-right corner of region
        search_text: Text to search for
    
    Returns:
        bool: True if text is found in the region
    
    Example:
        if check_ocr_text(100, 100, 300, 200, "quest"):
            # Execute quest functions
    """
    try:
        screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        return search_text_in_ocr(screenshot, search_text)
    except Exception as e:
        print(f"Error in check_ocr_text: {e}")
        return False


class Tracker:
    """Simple Tracker class to provide start/stop monitoring and maintain last_biome."""
    def __init__(self, poll_interval=5):
        self._thread = None
        self._stop_event = threading.Event()
        self.poll_interval = poll_interval

    def start_monitoring(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop_monitoring(self):
        try:
            self._stop_event.set()
            if self._thread:
                self._thread.join(timeout=2)
        except Exception as e:
            print(f"Error stopping tracker thread: {e}")

    def _monitor_loop(self):
        global last_biome
        biomes = [
            "normal", "windy", "rainy", "snowy", "sand storm",
            "hell", "starfall", "corruption", "null", "glitched", "dreamspace"
        ]

        while not self._stop_event.is_set():
            try:
                region = ok.config_data.get('clicks', {}).get('biome_region', [0, 0, 0, 0])
                x, y, w, h = map(int, region)
                x2, y2 = x + w, y + h

                # perform OCR
                try:
                    img = ImageGrab.grab(bbox=(x, y, x2, y2))
                    text = perform_ocr(img) or ""
                except Exception as e:
                    print(f"Tracker OCR capture error: {e}")
                    text = ""

                text = (text or "").lower()
                detected = None
                for b in biomes:
                    if b in text:
                        detected = b
                        break

                if not detected:
                    # fallback to check_ocr_text which also does its own grab
                    for b in biomes:
                        try:
                            if check_ocr_text(x, y, x2, y2, b):
                                detected = b
                                break
                        except Exception:
                            continue

                if detected and detected != last_biome:
                    print(f"Tracker: biome changed {last_biome} -> {detected}")
                    last_biome = detected
                    # send webhook if configured
                    try:
                        if ok.config_data.get('discord', {}).get('enabled') == '1':
                            webhook_url = ok.config_data.get('discord', {}).get('webhook', {}).get('url')
                            if webhook_url and 'discord' in webhook_url:
                                wb = discord.DiscordWebhook(url=webhook_url)
                                embed = discord.DiscordEmbed(title="Biome Change", description=f"Detected biome: {detected.upper()} ({time.strftime('%I:%M:%S %p')})")
                                embed.set_color(0x64ff5e)
                                wb.add_embed(embed)
                                wb.execute()
                    except Exception as e:
                        print(f"Tracker webhook error: {e}")

            except Exception as e:
                print(f"Tracker monitor loop error: {e}")

            # wait before next poll
            for _ in range(max(1, int(self.poll_interval))):
                if self._stop_event.is_set():
                    break
                time.sleep(1)
