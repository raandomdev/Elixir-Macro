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
from data import ocr_engine
import pyautogui as auto
from PIL import Image, ImageGrab, ImageEnhance
import sys
from tkinter import messagebox
try:
    # 
    ahk = None
    mouse = None
    keyboard = None
    if sys.platform == "darwin":
        try:
            import mouse as _mouse, keyboard as _keyboard
            mouse = _mouse
            keyboard = _keyboard
        except Exception as e:
            logging.warning("Mouse/keyboard imports failed on macOS: %s", e)
    else:
        try:
            from ahk import AHK
            ahk = AHK()
        except Exception:
            try:
                import mouse as _mouse, keyboard as _keyboard
                mouse = _mouse
                keyboard = _keyboard
            except Exception as e:
                logging.warning("Neither AutoHotkey nor mouse/keyboard available: %s", e)
except Exception as e:
    logging.warning("Tracker import warning: %s", e)

# Use enhanced OCR engine
perform_ocr = ocr_engine.perform_ocr
search_text_in_ocr = ocr_engine.search_text_in_ocr
check_ocr_text = ocr_engine.check_ocr_text
get_ocr_text = ocr_engine.get_ocr_text

ocr_text = None
last_biome = None
last_aura = None


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
            logging.exception("Error stopping tracker thread: %s", e)

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
                    logging.exception("Tracker OCR capture error: %s", e)
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
                    logging.info("Tracker: biome changed %s -> %s", last_biome, detected)
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
                        logging.exception("Tracker webhook error: %s", e)

            except Exception as e:
                logging.exception("Tracker monitor loop error: %s", e)

            # wait before next poll
            for _ in range(max(1, int(self.poll_interval))):
                if self._stop_event.is_set():
                    break
                time.sleep(1)
