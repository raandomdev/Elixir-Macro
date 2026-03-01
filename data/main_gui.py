import os, sys, json
import time
from time import sleep
from tkinter import messagebox, filedialog, ttk
import tkinter as tk
import discord_webhook
from data import config

keyboard = None
mouse    = None
ahk      = None
pynput_keyboard = None
pynput_mouse    = None

IS_WIN   = sys.platform == "win32"
IS_MAC   = sys.platform == "darwin"
IS_LINUX = not IS_WIN and not IS_MAC

if IS_WIN:
    try:
        from ahk import AHK
        ahk = AHK()
        print("Windows: AutoHotkey loaded successfully.")
    except Exception as ahk_err:
        print(f"AHK unavailable ({ahk_err}), falling back to keyboard/mouse.")
        ahk = None

    if ahk is None:
        try:
            import keyboard as _kbd
            import mouse as _mouse
            keyboard = _kbd
            mouse    = _mouse
            print("Windows fallback: keyboard + mouse modules loaded.")
        except Exception as e:
            print(f"keyboard/mouse import failed: {e}")

elif IS_MAC:
    try:
        from pynput import keyboard as _pynput_kbd
        from pynput import mouse as _pynput_mouse
        from pynput.keyboard import Key as PynputKey, Controller as KbdController
        from pynput.mouse import Button as PynputButton, Controller as MouseController
        pynput_keyboard = KbdController()
        pynput_mouse    = MouseController()
        print("macOS: pynput loaded successfully.")
    except Exception as e:
        print(f"pynput unavailable ({e}), trying keyboard module fallback.")
        try:
            import keyboard as _kbd
            import mouse   as _mouse
            keyboard = _kbd
            mouse    = _mouse
        except Exception as e2:
            print(f"keyboard/mouse also unavailable: {e2}")

else:
    try:
        import keyboard as _kbd
        import mouse as _mouse
        keyboard = _kbd
        mouse    = _mouse
        print("Linux: keyboard + mouse modules loaded.")
    except Exception as e:
        print(f"keyboard/mouse import failed on Linux: {e}")

import pyautogui as auto
auto.FAILSAFE = False   # prevent pyautogui raising exception on corner position

from data import Tracker
from data import ocr_engine
import asyncio
from PIL import Image, ImageGrab, ImageEnhance
import threading
from datetime import datetime, timedelta
import webbrowser
import sv_ttk

perform_ocr        = ocr_engine.perform_ocr
search_text_in_ocr = ocr_engine.search_text_in_ocr
check_ocr_text     = ocr_engine.check_ocr_text
get_ocr_text       = ocr_engine.get_ocr_text
ocr_text           = None
_AHK_SPECIAL = {
    "enter": "{Enter}", "return": "{Enter}",
    "esc":   "{Escape}", "escape": "{Escape}",
    "tab":   "{Tab}",
    "space": "{Space}",
    "backspace": "{Backspace}",
    "delete": "{Delete}", "del": "{Delete}",
    "up": "{Up}", "down": "{Down}", "left": "{Left}", "right": "{Right}",
    "f1":  "{F1}",  "f2":  "{F2}",  "f3":  "{F3}",  "f4":  "{F4}",
    "f5":  "{F5}",  "f6":  "{F6}",  "f7":  "{F7}",  "f8":  "{F8}",
    "f9":  "{F9}",  "f10": "{F10}", "f11": "{F11}", "f12": "{F12}",
}

# pynput special key map
_PYNPUT_SPECIAL = None
if IS_MAC:
    try:
        from pynput.keyboard import Key as _PK
        _PYNPUT_SPECIAL = {
            "enter": _PK.enter, "return": _PK.enter,
            "esc":   _PK.esc,   "escape": _PK.esc,
            "tab":   _PK.tab,
            "space": _PK.space,
            "backspace": _PK.backspace,
            "delete": _PK.delete, "del": _PK.delete,
            "up": _PK.up, "down": _PK.down, "left": _PK.left, "right": _PK.right,
            "f1":  _PK.f1,  "f2":  _PK.f2,  "f3":  _PK.f3,  "f4":  _PK.f4,
            "f5":  _PK.f5,  "f6":  _PK.f6,  "f7":  _PK.f7,  "f8":  _PK.f8,
            "f9":  _PK.f9,  "f10": _PK.f10, "f11": _PK.f11, "f12": _PK.f12,
        }
    except Exception:
        pass

def _normalize_key(key: str) -> str:
    """Strip AHK-style braces so we get a plain name, e.g. '{Enter}' → 'enter'."""
    k = key.strip()
    if k.startswith("{") and k.endswith("}"):
        k = k[1:-1]
    return k.lower()

def platform_click(x, y, button="left"):
    """Click at absolute screen coordinates."""
    x, y = int(x), int(y)
    try:
        if IS_WIN and ahk:
            ahk.click(x, y, coord_mode="Screen")
            return
        if IS_MAC and pynput_mouse:
            from pynput.mouse import Button as _Btn
            btn = _Btn.left if button == "left" else _Btn.right
            pynput_mouse.position = (x, y)
            pynput_mouse.click(btn)
            return
        if mouse is not None:
            mouse.move(x, y)
            mouse.click(button)
            return
    except Exception as e:
        print(f"platform_click primary failed: {e}")
    try:
        auto.click(x, y, button=button)
    except Exception as e:
        print(f"platform_click pyautogui fallback failed: {e}")

def platform_key_press(text: str):
    """
    Type a string of characters (e.g. a search query).
    NOT for special keys – use platform_key_combo for those.
    """
    try:
        if IS_WIN and ahk:
            ahk.type(text)
            return
        if IS_MAC and pynput_keyboard:
            pynput_keyboard.type(text)
            return
        if keyboard is not None:
            keyboard.write(text)
            return
    except Exception as e:
        print(f"platform_key_press primary failed: {e}")
    try:
        auto.typewrite(text, interval=0.03)
    except Exception as e:
        print(f"platform_key_press pyautogui fallback failed: {e}")

def platform_key_combo(key: str):
    """
    Press and release a single key.
    Accepts:
      - plain names:  'enter', 'esc', 'r', 'e', 'f', 'space'
      - AHK-style:    '{Enter}', '{Escape}'
    """
    plain = _normalize_key(key)
    try:
        if IS_WIN and ahk:
            ahk_key = _AHK_SPECIAL.get(plain, plain)
            ahk.send(ahk_key)
            return
        if IS_MAC and pynput_keyboard:
            if _PYNPUT_SPECIAL and plain in _PYNPUT_SPECIAL:
                pynput_keyboard.press(_PYNPUT_SPECIAL[plain])
                pynput_keyboard.release(_PYNPUT_SPECIAL[plain])
            else:
                pynput_keyboard.press(plain)
                pynput_keyboard.release(plain)
            return
        if keyboard is not None:
            keyboard.press_and_release(plain)
            return
    except Exception as e:
        print(f"platform_key_combo primary failed (key={key!r}): {e}")
    try:
        _pyag_map = {
            "enter": "enter", "return": "enter",
            "esc": "escape", "escape": "escape",
            "tab": "tab", "space": "space",
            "backspace": "backspace", "delete": "delete",
            "up": "up", "down": "down", "left": "left", "right": "right",
        }
        pg_key = _pyag_map.get(plain, plain)
        auto.press(pg_key)
    except Exception as e:
        print(f"platform_key_combo pyautogui fallback failed: {e}")


def platform_key_down(key: str):
    plain = _normalize_key(key)
    try:
        if IS_WIN and ahk:
            ahk.key_down(plain)
            return
        if IS_MAC and pynput_keyboard:
            if _PYNPUT_SPECIAL and plain in _PYNPUT_SPECIAL:
                pynput_keyboard.press(_PYNPUT_SPECIAL[plain])
            else:
                pynput_keyboard.press(plain)
            return
        if keyboard is not None:
            keyboard.press(plain)
            return
    except Exception as e:
        print(f"platform_key_down failed: {e}")
    try:
        auto.keyDown(plain)
    except Exception as e:
        print(f"platform_key_down pyautogui fallback failed: {e}")


def platform_key_up(key: str):
    plain = _normalize_key(key)
    try:
        if IS_WIN and ahk:
            ahk.key_up(plain)
            return
        if IS_MAC and pynput_keyboard:
            if _PYNPUT_SPECIAL and plain in _PYNPUT_SPECIAL:
                pynput_keyboard.release(_PYNPUT_SPECIAL[plain])
            else:
                pynput_keyboard.release(plain)
            return
        if keyboard is not None:
            keyboard.release(plain)
            return
    except Exception as e:
        print(f"platform_key_up failed: {e}")
    try:
        auto.keyUp(plain)
    except Exception as e:
        print(f"platform_key_up pyautogui fallback failed: {e}")

DEFAULT_FONT      = "Segoe UI"
DEFAULT_FONT_BOLD = "Segoe UI Semibold"
MAX_WIDTH         = 1000

class App(tk.Tk):
    def __init__(self, config_key=None):
        super().__init__()
        self.title(f"Elixir Macro v{config.get_current_version()}")
        self.geometry("670x335")
        self.resizable(False, False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        sv_ttk.set_theme("dark")

        self.coord_vars  = {}
        self.config_key  = config_key
        self.begin_x     = None
        self.begin_y     = None
        self.end_x       = None
        self.end_y       = None
        self.tk_var_list = config.generate_tk_list()
        self.main_loop   = MainLoop()

        self.tab_control = ttk.Notebook(master=self)
        self.tab_control.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.main_tab     = ttk.Frame(self.tab_control)
        self.discord_tab  = ttk.Frame(self.tab_control)
        self.crafting_tab = ttk.Frame(self.tab_control)
        self.settings_tab = ttk.Frame(self.tab_control)
        self.merchant_tab = ttk.Frame(self.tab_control)
        self.extras_tab   = ttk.Frame(self.tab_control)
        self.credits_tab  = ttk.Frame(self.tab_control)

        self.tab_control.add(self.main_tab,     text="Main")
        self.tab_control.add(self.discord_tab,  text="Discord")
        self.tab_control.add(self.crafting_tab, text="Crafting")
        self.tab_control.add(self.settings_tab, text="Settings")
        self.tab_control.add(self.merchant_tab, text="Merchant")
        self.tab_control.add(self.extras_tab,   text="Extras")
        self.tab_control.add(self.credits_tab,  text="Credits")
        self.tab_control.grid(padx=10)

        buttons_frame = ttk.Frame(master=self)
        buttons_frame.grid(row=1, column=0, pady=(5, 8), padx=6, sticky="s")

        ttk.Button(master=buttons_frame, text="Start - F1",   command=self.start,   width=15).grid(row=0, column=0, padx=4, pady=4)
        ttk.Button(master=buttons_frame, text="Stop - F2",    command=self.stop,    width=15).grid(row=0, column=1, padx=4, pady=4)
        ttk.Button(master=buttons_frame, text="Restart - F3", command=self.restart, width=15).grid(row=0, column=2, padx=4, pady=4)

        self._register_hotkeys()

        self.setup_main_tab()
        self.setup_discord_tab()
        self.setup_crafting_tab()
        self.setup_settings_tab()
        self.setup_merchant_tab()
        self.setup_extras_tab()
        self.setup_credits_tab()

    def _register_hotkeys(self):
        """Register F1/F2/F3 hotkeys using whatever backend is available."""
        try:
            if IS_WIN and ahk:
                ahk.add_hotkey("F1", callback=self.start)
                ahk.add_hotkey("F2", callback=self.stop)
                ahk.add_hotkey("F3", callback=self.restart)
                ahk.start_hotkeys()
                print("AHK hotkeys registered (F1/F2/F3).")
                return
        except Exception as e:
            print(f"AHK hotkey registration failed: {e}")

        try:
            if keyboard is not None:
                keyboard.add_hotkey("F1", self.start)
                keyboard.add_hotkey("F2", self.stop)
                keyboard.add_hotkey("F3", self.restart)
                print("keyboard module hotkeys registered (F1/F2/F3).")
                return
        except Exception as e:
            print(f"keyboard hotkey registration failed: {e}")

        print("Hotkeys unavailable; use the GUI buttons to start/stop.")

    def setup_main_tab(self):
        miscalance_frame = ttk.LabelFrame(master=self.main_tab, text="-")
        miscalance_frame.grid(row=0, column=0, sticky="w", padx=(1, 1))
        ttk.Label(master=miscalance_frame, text="Miscellaneous", font=("Segoe UI Semibold", 20, "bold")).grid(row=0, column=0)
        ttk.Checkbutton(master=miscalance_frame, text="Do Obby (30% Luck Boost Every 2 Mins)",
                        variable=self.tk_var_list['obby']['enabled'],
                        command=self.save_config).grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Checkbutton(master=miscalance_frame, text="Auto Chalice",
                        variable=self.tk_var_list['chalice']['enabled'], state="disabled",
                        command=self.save_config).grid(row=3, column=0, padx=5, pady=5, sticky="w")

        ttk.Label(master=miscalance_frame, text="Auto Equip", font=("Segoe UI Semibold", 20, "bold")).grid(row=0, column=1)
        ttk.Checkbutton(master=miscalance_frame, text="Enable Auto Equip",
                        variable=self.tk_var_list['auto_equip']['enabled'],
                        command=self.save_config).grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ttk.Button(master=miscalance_frame, text="Configure Search", width=25,
                   command=self.open_auto_equip_window).grid(column=1, row=3, padx=5, pady=5)

        paths_frame = ttk.LabelFrame(master=self.main_tab)
        paths_frame.grid(row=1, column=0, sticky="w", padx=(1, 1))
        ttk.Checkbutton(master=paths_frame, text="Enable Item Collection",
                        variable=self.tk_var_list['item_collecting']['enabled'],
                        command=self.save_config).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Button(master=paths_frame, text="Assign Clicks",
                   command=self.open_assign_clicks_gui).grid(row=0, column=1, sticky="w", padx=5, pady=5)
        ttk.Button(master=paths_frame, text="Paths",
                   command=self.pathing_ui).grid(row=0, column=2, sticky="w", padx=5, pady=5)

    def setup_discord_tab(self):
        def test_webhook():
            url = config.config_data["discord"]["webhook"]["url"]
            if 'discord.com' in url and 'https://' in url:
                wh = discord_webhook.DiscordWebhook(url=url)
                embed = discord_webhook.DiscordEmbed(title="Webhook Test!", description="Correctly configured to Elixir Macro!")
                embed.set_color(0x00ff00)
                wh.add_embed(embed)
                wh.execute()

        webhook_frame = ttk.Frame(master=self.discord_tab)
        webhook_frame.grid(row=0, column=0, sticky="news", padx=5, pady=5)
        ttk.Label(master=webhook_frame, text="Webhook", font=("Segoe UI Semibold", 20, "bold")).grid(row=0, column=0, padx=5, pady=5)
        ttk.Checkbutton(master=webhook_frame, text="Enable Webhook",
                        variable=self.tk_var_list['discord']['webhook']['enabled'],
                        command=self.save_config).grid(row=0, column=1, padx=5, pady=2, sticky="w")
        ttk.Button(master=webhook_frame, text="Test Webhook", command=test_webhook).grid(row=6, column=2, padx=5, pady=2, sticky="w")
        ttk.Label(master=webhook_frame, text="Webhook URL").grid(row=2, column=0, padx=5, pady=2, sticky="w")
        wh_url = ttk.Entry(master=webhook_frame, width=30, textvariable=self.tk_var_list['discord']['webhook']['url'])
        wh_url.grid(row=2, column=1, padx=5, pady=2)
        wh_url.bind("<FocusOut>", lambda e: self.save_config())
        ttk.Label(master=webhook_frame, text="User/Role ID to ping").grid(row=4, column=0, padx=5, pady=2, sticky="w")
        ping = ttk.Entry(master=webhook_frame, width=30, textvariable=self.tk_var_list['discord']['webhook']['ping_id'])
        ping.grid(row=4, column=1, padx=5, pady=2)
        ping.bind("<FocusOut>", lambda e: self.save_config())
        ttk.Label(master=webhook_frame, text="Private Server Link:").grid(row=5, column=0, padx=5, pady=2, sticky="w")
        ps = ttk.Entry(master=webhook_frame, width=30, textvariable=self.tk_var_list['discord']['webhook']['ps_link'])
        ps.grid(row=5, column=1, padx=5, pady=2)
        ttk.Checkbutton(master=webhook_frame, text="Inventory Screenshots",
                        variable=self.tk_var_list['invo_ss']['enabled'],
                        command=self.save_config).grid(row=6, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(master=webhook_frame, text="Duration:").grid(row=6, column=1, padx=5, pady=5, sticky="w")
        ttk.Entry(master=webhook_frame, textvariable=self.tk_var_list['invo_ss']['duration'], width=6).grid(row=6, column=1, padx=5, pady=2)

    def setup_crafting_tab(self):
        crafting_frame = ttk.Frame(master=self.crafting_tab)
        crafting_frame.grid(row=0, column=0, sticky="n", padx=(1, 1))
        ttk.Label(master=crafting_frame, text="Potion Crafting", font=("Segoe UI Semibold", 20, "bold")).grid(row=0, column=1, columnspan=4)
        ttk.Checkbutton(master=crafting_frame, text="Enable Potion Crafting",
                        variable=self.tk_var_list['potion_crafting']['enabled'],
                        command=self.save_config).grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ttk.Entry(crafting_frame, textvariable=self.tk_var_list['potion_crafting']['item_1'], width=20).grid(row=3, column=1, padx=5, pady=5, sticky="w")
        ttk.Entry(crafting_frame, textvariable=self.tk_var_list['potion_crafting']['item_2'], width=20).grid(row=4, column=1, padx=5, pady=5, sticky="w")
        ttk.Entry(crafting_frame, textvariable=self.tk_var_list['potion_crafting']['item_3'], width=20).grid(row=5, column=1, padx=5, pady=5, sticky="w")
        ttk.Checkbutton(master=crafting_frame, text="Craft Potion 1",
                        variable=self.tk_var_list['potion_crafting']['craft_potion_1'],
                        command=self.save_config).grid(row=3, column=2, padx=5, pady=5, sticky="w")
        ttk.Checkbutton(master=crafting_frame, text="Craft Potion 2",
                        variable=self.tk_var_list['potion_crafting']['craft_potion_2'],
                        command=self.save_config).grid(row=4, column=2, padx=5, pady=5, sticky="w")
        ttk.Checkbutton(master=crafting_frame, text="Craft Potion 3",
                        variable=self.tk_var_list['potion_crafting']['craft_potion_3'],
                        command=self.save_config).grid(row=5, column=2, padx=5, pady=5, sticky="w")
        ttk.Checkbutton(master=crafting_frame, text="Auto Add Swicher",
                        variable=self.tk_var_list['potion_crafting']['temporary_auto_add'],
                        command=self.save_config).grid(row=2, column=2, padx=5, pady=5, sticky="w")
        ttk.Checkbutton(master=crafting_frame, text="Potion Crafting",
                        variable=self.tk_var_list['potion_crafting']['potion_crafting'],
                        command=self.save_config).grid(row=2, column=3, padx=5, pady=5, sticky="w")
        ttk.Button(master=crafting_frame, text="Assign Crafting",
                   command=self.open_crafting_clicks).grid(row=2, column=4, padx=5, pady=5, sticky="w")
        ttk.Label(master=crafting_frame, text="Auto add potion (every loop):").grid(row=3, column=3, padx=5, pady=5, sticky="w")
        ttk.Entry(master=crafting_frame, textvariable=self.tk_var_list['potion_crafting']['current_temporary_auto_add'], width=14).grid(row=3, column=4, padx=5, pady=2, sticky="w")
        ttk.Label(master=crafting_frame, text="Crafting interval (minutes):").grid(row=4, column=3, padx=5, pady=2, sticky="w")
        ttk.Entry(master=crafting_frame, textvariable=self.tk_var_list['potion_crafting']['crafting_interval'], width=6).grid(row=4, column=4, padx=5, pady=2, sticky="w")

    def setup_settings_tab(self):
        settings_frame = ttk.LabelFrame(master=self.settings_tab)
        settings_frame.grid(row=0, column=0, sticky="n", padx=(1, 1))
        ttk.Label(master=settings_frame, text="General", font=("Segoe UI Semibold", 20, "bold")).grid(row=0, column=0)
        ttk.Checkbutton(master=settings_frame, text="VIP Game Pass",
                        variable=self.tk_var_list['settings']['vip_mode'],
                        command=self.save_config).grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Checkbutton(master=settings_frame, text="VIP+ Mode",
                        variable=self.tk_var_list['settings']['vip+_mode'],
                        command=self.save_config).grid(row=3, column=0, padx=5, pady=5, sticky="w")
        ttk.Checkbutton(master=settings_frame, text="Azerty Keyboard Layout",
                        variable=self.tk_var_list['settings']['azerty_mode'],
                        command=self.save_config).grid(row=4, column=0, padx=5, pady=5, sticky="w")
        ttk.Checkbutton(master=settings_frame, text="Reset and Align",
                        variable=self.tk_var_list['settings']['reset'],
                        command=self.save_config).grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ttk.Checkbutton(master=settings_frame, text="Claim Quests (30 minutes)",
                        variable=self.tk_var_list['claim_daily_quests'],
                        command=self.save_config).grid(row=3, column=1, padx=5, pady=5, sticky="w")

    def setup_merchant_tab(self):
        merchant_frame = ttk.LabelFrame(master=self.merchant_tab, text="Mari")
        merchant_frame.grid(row=0, column=0, sticky="w", padx=(1, 1))
        ttk.Button(state="disabled", master=merchant_frame, text="Mari Settings",    command=self.open_mari_settings).grid(row=2, column=3, padx=5, pady=5, sticky="w")
        ttk.Checkbutton(state="disabled", master=merchant_frame, text="Ping if Mari? (User Ping Id/Role Ping ID: &roleid):",
                        variable=self.tk_var_list['mari']['ping_enabled'],
                        command=self.save_config, onvalue='1', offvalue='0').grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ttk.Entry(state="disabled", master=merchant_frame, textvariable=self.tk_var_list['mari']['ping_id'], width=6).grid(row=2, column=2, padx=5, pady=5, sticky="w")

        jester_frame = ttk.LabelFrame(master=self.merchant_tab, text="Jester")
        jester_frame.grid(row=1, column=0, sticky="n", padx=(1, 1))
        ttk.Checkbutton(state="disabled", master=jester_frame, text="Ping if Jester? (User Ping Id/Role Ping ID: &roleid):",
                        variable=self.tk_var_list['jester']['ping_enabled'],
                        command=self.save_config, onvalue='1', offvalue='0').grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ttk.Entry(state="disabled", master=jester_frame, textvariable=self.tk_var_list['jester']['ping_id'], width=6).grid(row=2, column=2, padx=5, pady=5, sticky="w")
        ttk.Button(state="disabled", master=jester_frame, text="Jester Settings",   command=self.open_jester_settings).grid(row=2, column=3, padx=5, pady=5, sticky="w")

        merchant_wh_frame = ttk.LabelFrame(master=self.merchant_tab, text="Merchant")
        merchant_wh_frame.grid(row=2, column=0, sticky="w", padx=(1, 1))
        ttk.Checkbutton(state="disabled", master=merchant_wh_frame, text="Enable Merchant Teleporter",
                        variable=self.tk_var_list['settings']['merchant']['enabled'],
                        command=self.save_config, onvalue='1', offvalue='0').grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(master=merchant_wh_frame, text="Duration:").grid(row=2, column=2, padx=5, pady=5, sticky="w")
        mt = ttk.Entry(state="disabled", master=merchant_wh_frame,
                       textvariable=self.tk_var_list['settings']['merchant']['duration'], width=6)
        mt.grid(row=2, column=3, padx=5, pady=5, sticky="w")
        mt.bind("<FocusOut>", lambda e: self.save_config())
        ttk.Button(state="disabled", master=merchant_wh_frame, text="Merchant Calibration",
                   command=self.open_merchant_calibration).grid(row=2, column=4, padx=5, pady=5, sticky="w")

    def setup_extras_tab(self):
        items_stuff = ttk.Frame(master=self.extras_tab)
        items_stuff.grid(row=0, column=0, sticky="n", padx=(5, 0))
        ttk.Label(master=items_stuff, text="Item Scheduler", font=("Segoe UI Semibold", 20, "bold")).grid(row=0, padx=5)
        ttk.Checkbutton(master=items_stuff, text="Enable Item Scheduler",
                        variable=self.tk_var_list['item_scheduler_item']['enabled'],
                        command=self.save_config).grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(master=items_stuff, textvariable=self.tk_var_list['item_scheduler_item']['item_name'], width=20).grid(row=3, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(master=items_stuff, text="Quantity:", justify="left").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(master=items_stuff, width=6, textvariable=self.tk_var_list['item_scheduler_item']['item_scheduler_quantity']).grid(row=4, column=1, padx=5, pady=2, sticky="w")
        ttk.Label(master=items_stuff, text="Item Interval:").grid(row=5, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(master=items_stuff, width=6, textvariable=self.tk_var_list['item_scheduler_item']['interval']).grid(row=5, column=1, padx=5, pady=2, sticky="w")

        biome_config = ttk.Frame(master=self.extras_tab)
        biome_config.grid(row=0, column=2, sticky="n", padx=(5, 0))
        ttk.Label(master=biome_config, text="Detection", font=("Segoe UI Semibold", 20, "bold")).grid(row=0, column=0)
        ttk.Checkbutton(master=biome_config, text="Enable Biome Detection",
                        variable=self.tk_var_list['biome_detection']['enabled'],
                        command=self.save_config).grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Checkbutton(master=biome_config, text="Enable Aura Detection",
                        variable=self.tk_var_list['enabled_dectection'],
                        command=self.save_config).grid(row=3, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(master=biome_config, text="Ping Min:", justify="left").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(master=biome_config, textvariable=self.tk_var_list['send_min'], width=8).grid(row=4, column=1, padx=5, pady=2, sticky="w")
        ttk.Label(master=biome_config, text="Ping Max:", justify="left").grid(row=5, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(master=biome_config, textvariable=self.tk_var_list['send_max'], width=8).grid(row=5, column=1, padx=5, pady=2, sticky="w")
        ttk.Button(master=biome_config, text="Configure Biomes", command=self.set_biome_region).grid(row=2, column=1, padx=5, pady=5, sticky="w")

    def setup_credits_tab(self):
        credits_frame = ttk.Frame(master=self.credits_tab, width=570)
        credits_frame.grid(row=0, column=0, padx=(1, 0))
        credits_text = """
Owners:
Golden (spacedev0572)

Developers:
Golden (spacedev0572) | Chaseee (chaseeee111)

In Contribution:
This macro was inspired by Dolphsol Macro, the first
Sol's RNG Macro to be created! (Also he's a chill man!!)
Radiance Macro, using config.py and the pathing system (LPS)
OysterDetecter (by vexthecoder), using log reading detection.
"""
        ttk.Label(master=credits_frame, text=credits_text, font=("Segoe UI", 10)).grid(row=1, column=1, rowspan=2, padx=56, pady=(17, 30), sticky="n")
        join_server = ttk.Label(master=credits_frame, text="Join the Server!", font=("Segoe UI", 14, "underline"), cursor="hand2")
        join_server.grid(row=2, column=0, padx=6, pady=(0, 6))
        join_server.bind("<Button-1>", lambda event: webbrowser.open('https://discord.gg/JsMM299RF7'))


    def start(self):
        config.save_tk_list(self.tk_var_list)
        config.save_config(config.config_data)
        self.iconify()
        self.main_loop.start()

    def stop(self):
        config.save_tk_list(self.tk_var_list)
        config.save_config(config.config_data)
        self.deiconify()
        self.main_loop.stop()
        self.lift()

    def restart(self):
        """Restart the application by re-launching the interpreter."""
        try:
            self.main_loop.stop()
        except Exception:
            pass
        python = sys.executable
        os.execv(python, [python] + sys.argv)

    def show_message(self, title="", message="", error=False):
        if error:
            messagebox.showerror(title=title, message=message)
        else:
            messagebox.showinfo(title=title, message=message)

    def save_config(self):
        config.save_config(config.config_data)
        config.save_tk_list(self.tk_var_list)

    def save_window_settings(self, window):
        config.save_tk_list(self.tk_var_list)
        config.save_config(config.config_data)
        window.destroy()

    def open_auto_equip_window(self):
        """Renamed to avoid overwriting the method reference."""
        win = tk.Toplevel()
        win.title("Auto Equip")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        frame = ttk.Frame(master=win)
        frame.pack(expand=True, fill="both")
        ttk.Label(master=frame, text="Enter aura name to be used for search.\nThe first result will be equipped so be specific.").grid(row=0, column=0, columnspan=2, padx=5, pady=5)
        ttk.Entry(master=frame, textvariable=self.tk_var_list['auto_equip']['aura']).grid(row=1, column=0, columnspan=2, padx=5, pady=5)
        ttk.Checkbutton(master=frame, text="Search in Special Auras",
                        variable=self.tk_var_list['auto_equip']['special_aura'],
                        command=self.save_config, onvalue="1", offvalue="0").grid()
        ttk.Button(master=frame, text="Submit", command=lambda: self.save_window_settings(win)).grid(pady=5)

    def open_assign_clicks_gui(self):
        """Renamed to avoid overwriting the method reference."""
        win = tk.Toplevel()
        win.title("Assign Clicks")
        win.resizable(False, False)
        win.attributes("-topmost", True)

        tabview = ttk.Notebook(master=win)
        tabview.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        win.grid_rowconfigure(0, weight=1)
        win.grid_columnconfigure(0, weight=1)

        aura_tab       = ttk.Frame(tabview)
        collection_tab = ttk.Frame(tabview)
        items_tab      = ttk.Frame(tabview)
        quest_tab      = ttk.Frame(tabview)

        tabview.add(aura_tab,       text="Auras Storage")
        tabview.add(collection_tab, text="Collection Menu")
        tabview.add(items_tab,      text="Items Menu")
        tabview.add(quest_tab,      text="Quest Menu")

        aura_settings = [
            ("Aura Storage:",     "aura_storage"),
            ("Regular Aura Tab:", "regular_tab"),
            ("Special Aura Tab:", "special_tab"),
            ("Aura Search Bar:",  "search_bar"),
            ("First Aura Slot:",  "aura_first_slot"),
            ("Equip Button:",     "equip_button"),
        ]
        collection_settings = [
            ("Collection Menu:", "collection_menu"),
            ("Exit Collection:", "exit_collection"),
        ]
        items_settings = [
            ("Items Storage:",   "items_storage"),
            ("Items Tab:",       "items_tab"),
            ("Items Search Bar:","items_bar"),
            ("Items First Slot:","item_first_slot"),
            ("Quantity Bar:",    "item_value"),
            ("Use Button:",      "use_button"),
        ]
        quest_settings = [
            ("Quest Menu:",   "quest_menu"),
            ("First Slot:",   "first_slot"),
            ("Second Slot:",  "second_slot"),
            ("Third Slot:",   "third_slot"),
            ("Claim Button:", "claim_button"),
        ]

        def create_click_fields(parent, settings):
            for i, (label_text, ck) in enumerate(settings):
                ttk.Label(parent, text=label_text).grid(row=i, column=0, padx=5, pady=2, sticky="w")
                x_e = ttk.Entry(parent, width=6, textvariable=self.tk_var_list['clicks'][ck][0])
                x_e.grid(row=i, column=1, padx=5, pady=2)
                y_e = ttk.Entry(parent, width=6, textvariable=self.tk_var_list['clicks'][ck][1])
                y_e.grid(row=i, column=2, padx=5, pady=2)
                ttk.Button(parent, text="Assign Click!",
                           command=lambda k=ck, x=x_e, y=y_e: self.start_capture_thread(k, x, y)
                           ).grid(row=i, column=3, padx=5, pady=2)

        create_click_fields(aura_tab,       aura_settings)
        create_click_fields(collection_tab, collection_settings)
        create_click_fields(items_tab,      items_settings)
        create_click_fields(quest_tab,      quest_settings)

        ttk.Button(master=aura_tab, text="Save Calibration",
                   command=lambda: self.save_window_settings(win)).grid(row=7, column=1, padx=5, pady=2)

    def open_crafting_clicks(self):
        """Renamed to avoid overwriting the method reference."""
        win = tk.Toplevel()
        win.title("Crafting")
        win.attributes("-topmost", True)
        win.resizable(False, False)
        frame = ttk.Frame(master=win)
        frame.pack(fill="both", expand=True)

        crafting_settings = [
            ("First Potion Slot:",  "first_potion_slot"),
            ("Second Potion Slot:", "second_potion_slot"),
            ("Third Potion Slot:",  "third_potion_slot"),
            ("Potion Tab Craft",    "potion_tab"),
            ("Item Tab Craft",      "item_tab"),
            ("Open Recipe Book",    "open_recipe"),
            ("Add button 1",        "add_button_1"),
            ("Add button 2",        "add_button_2"),
            ("Add button 3",        "add_button_3"),
            ("Add button 4",        "add_button_4"),
            ("Craft button",        "craft_button"),
            ("Potion Search bar:",  "potion_search_bar"),
            ("Auto Add button",     "auto_add_button"),
        ]
        for i, (label_text, ck) in enumerate(crafting_settings, start=1):
            ttk.Label(master=frame, text=label_text).grid(row=i, column=0, padx=5, pady=2, sticky="w")
            x_e = ttk.Entry(master=frame, textvariable=self.tk_var_list['clicks'][ck][0], width=6)
            x_e.grid(row=i, column=1, padx=5, pady=2)
            y_e = ttk.Entry(master=frame, textvariable=self.tk_var_list['clicks'][ck][1], width=6)
            y_e.grid(row=i, column=2, padx=5, pady=2)
            ttk.Button(master=frame, text="Assign Click!",
                       command=lambda k=ck, x=x_e, y=y_e: self.start_capture_thread(k, x, y)
                       ).grid(row=i, column=3, padx=5, pady=2)

    def pathing_ui(self):
        win = tk.Toplevel()
        win.title("Paths Window")
        win.attributes("-topmost", True)
        win.resizable(False, False)
        frame = ttk.Labelframe(master=win, text="Paths")
        frame.pack(fill="both", expand=True)
        for i in range(8):
            ttk.Checkbutton(master=frame, text=str(i + 1), width=4,
                            variable=self.tk_var_list['item_collecting'][f'spot{i+1}'],
                            command=self.save_config,
                            onvalue='1', offvalue='0').grid(row=i, column=0, sticky='e')

    def open_mari_settings(self):
        win = tk.Toplevel()
        win.title("Mari Settings")
        win.resizable(False, False)
        win.attributes('-topmost', True)
        mari_items = ["Void Coin","Lucky Penny","Mixed Potion","Lucky Potion","Lucky Potion L",
                      "Lucky Potion XL","Speed Potion","Speed Potion L","Speed Potion XL","Gear A","Gear B"]
        numbers = [str(i) for i in range(1, 12)]
        for i, item in enumerate(mari_items, start=1):
            if item not in self.tk_var_list['mari']['settings']:
                self.tk_var_list['mari']['settings'][item] = tk.StringVar(value="0")
            ttk.Checkbutton(master=win, text=item,
                            variable=self.tk_var_list['mari']['settings'][item],
                            command=self.save_config,
                            onvalue='1', offvalue='0').grid(row=i, column=0, padx=5, pady=5, sticky="w")
        for i, num in enumerate(numbers, start=1):
            if num not in self.tk_var_list['mari']['settings']:
                self.tk_var_list['mari']['settings'][num] = tk.StringVar(value="0")
            e = ttk.Entry(master=win, textvariable=self.tk_var_list['mari']['settings'][num], width=4)
            e.grid(row=i, column=1, padx=5, pady=5, sticky="w")
            e.bind("<FocusOut>", lambda ev: self.save_config())

    def open_jester_settings(self):
        win = tk.Toplevel()
        win.title("Jester Settings")
        win.resizable(False, False)
        win.attributes('-topmost', True)
        jester_items = ["Oblivion Potion","Heavenly Potion","Rune of Everything","Rune of Dust",
                        "Rune of Nothing","Rune Of Corruption","Rune Of Hell","Rune of Galaxy",
                        "Rune of Rainstorm","Rune of Frost","Rune of Wind","Strange Potion",
                        "Lucky Potion","Stella's Candle","Merchant Tracker","Random Potion Sack"]
        for i, item in enumerate(jester_items, start=1):
            if item not in self.tk_var_list['jester']['settings']:
                self.tk_var_list['jester']['settings'][item] = tk.StringVar(value="0")
            ttk.Checkbutton(master=win, text=item,
                            variable=self.tk_var_list['jester']['settings'][item],
                            command=self.save_config,
                            onvalue='1', offvalue='0').grid(row=i, column=0, padx=5, pady=5, sticky="w")
        for i in range(1, 17):
            num = str(i)
            if num not in self.tk_var_list['jester']['settings']:
                self.tk_var_list['jester']['settings'][num] = tk.StringVar(value="0")
            e = ttk.Entry(master=win, textvariable=self.tk_var_list['jester']['settings'][num], width=4)
            e.grid(row=i, column=1, padx=5, pady=5, sticky="w")
            e.bind("<FocusOut>", lambda ev: self.save_config())

    def open_merchant_calibration(self):
        win = tk.Toplevel()
        win.title("Merchant Calibration")
        win.resizable(False, False)
        merchant_cali = [
            ("Merchant Open Button",  "merchant_open_button"),
            ("Merchant Dialogue Box", "merchant_dialog"),
            ("Amount Button Entry",   "merchant_amount_button"),
            ("Purchase Button",       "merchant_purchase_button"),
            ("First Item Slot",       "merchant_1_slot_button"),
            ("Merchant Name OCR",     "merchant_name_ocr"),
            ("Item Name OCR",         "merchant_item_name_ocr"),
        ]
        for i, (label_text, ck) in enumerate(merchant_cali, start=1):
            is_ocr = "ocr" in label_text.lower()
            if is_ocr:
                ttk.Label(master=win, text=f"{label_text} (X, Y, W, H):").grid(row=i, column=0, padx=5, pady=5, sticky="w")
                x_e = ttk.Entry(master=win, textvariable=self.tk_var_list['clicks'][ck][0], width=6); x_e.grid(row=i, column=1, padx=5, pady=5)
                y_e = ttk.Entry(master=win, textvariable=self.tk_var_list['clicks'][ck][1], width=6); y_e.grid(row=i, column=2, padx=5, pady=5)
                w_e = ttk.Entry(master=win, textvariable=self.tk_var_list['clicks'][ck][2], width=6); w_e.grid(row=i, column=3, padx=5, pady=5)
                h_e = ttk.Entry(master=win, textvariable=self.tk_var_list['clicks'][ck][3], width=6); h_e.grid(row=i, column=4, padx=5, pady=5)
                btn = ttk.Button(master=win, text="Assign Click! (Drag)",
                                 command=lambda k=ck, x=x_e, y=y_e, w=w_e, h=h_e: self.start_capture_thread(k, x, y, w, h))
            else:
                ttk.Label(master=win, text=f"{label_text} (X, Y):").grid(row=i, column=0, padx=5, pady=5, sticky="w")
                x_e = ttk.Entry(master=win, textvariable=self.tk_var_list['clicks'][ck][0], width=6); x_e.grid(row=i, column=1, padx=5, pady=5)
                y_e = ttk.Entry(master=win, textvariable=self.tk_var_list['clicks'][ck][1], width=6); y_e.grid(row=i, column=2, padx=5, pady=5)
                btn = ttk.Button(master=win, text="Assign Click!",
                                 command=lambda k=ck, x=x_e, y=y_e: self.start_capture_thread(k, x, y))
            btn.grid(row=i, column=5, padx=5, pady=5)
        ttk.Button(master=win, text="Save Calibration",
                   command=lambda: self.save_window_settings(win)).grid(row=len(merchant_cali)+1, column=0, columnspan=6, pady=10)

    def set_biome_region(self):
        win = tk.Toplevel()
        win.title("Select Biomes")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        frame = ttk.LabelFrame(master=win)
        frame.pack(expand=True, fill="both")
        biomes = ["NORMAL","WINDY","RAINY","SNOWY","SAND STORM","HELL","STARFALL","HEAVEN",
                  "CORRUPTION","NULL","GLITCHED","DREAMSPACE","CYBERSPACE","THE CITADEL OF ORDERS"]
        for i, biome in enumerate(biomes):
            state = "disabled" if biome in ["GLITCHED","DREAMSPACE"] else "normal"
            if biome not in self.tk_var_list['biome_alerts']:
                self.tk_var_list['biome_alerts'][biome] = tk.StringVar(value="0")
            ttk.Checkbutton(master=frame, text=biome, state=state,
                            variable=self.tk_var_list['biome_alerts'][biome],
                            command=self.save_config,
                            onvalue="1", offvalue="0").grid(row=i, column=0, padx=5, pady=5, sticky="w")

    # ── Snipping / coordinate capture ────────────────────────────────────

    def start_capture_thread(self, config_key, x_entry, y_entry, w_entry=None, h_entry=None):
        # Store capture state on a private namespace to avoid conflicts
        self._cap = {
            "config_key": config_key,
            "x_entry": x_entry,
            "y_entry": y_entry,
            "w_entry": w_entry,
            "h_entry": h_entry,
            "begin_x": None,
            "begin_y": None,
        }
        self._snipping_window = tk.Toplevel()
        self._snipping_window.attributes("-fullscreen", True)
        self._snipping_window.attributes("-alpha", 0.3)
        self._canvas = tk.Canvas(self._snipping_window, bg="lightblue", highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)
        self._snipping_window.bind("<Button-1>",        self._on_cap_click)
        self._snipping_window.bind("<B1-Motion>",       self._on_cap_drag)
        self._snipping_window.bind("<ButtonRelease-1>", self._on_cap_release)
        self._snipping_window.protocol("WM_DELETE_WINDOW", self._on_cap_close)

    def _on_cap_close(self):
        if hasattr(self, '_snipping_window'):
            try:
                self._snipping_window.destroy()
            except Exception:
                pass

    def _on_cap_click(self, event):
        self._cap["begin_x"] = event.x
        self._cap["begin_y"] = event.y
        self._canvas.delete("sel")

    def _on_cap_drag(self, event):
        c = self._cap
        self._canvas.delete("sel")
        self._canvas.create_rectangle(c["begin_x"], c["begin_y"], event.x, event.y,
                                      outline="white", width=2, tag="sel")
        self._update_entries(event.x, event.y)

    def _on_cap_release(self, event):
        self._update_entries(event.x, event.y)
        c = self._cap
        width  = abs(event.x - (c["begin_x"] or event.x))
        height = abs(event.y - (c["begin_y"] or event.y))
        ck = c["config_key"].lower().replace('x','').replace('y','')
        config.config_data['clicks'][ck] = [event.x, event.y, width, height]
        config.save_config(config.config_data)
        self._on_cap_close()

    def _update_entries(self, x, y):
        c = self._cap
        width  = abs(x - (c["begin_x"] or x))
        height = abs(y - (c["begin_y"] or y))
        for entry, val in [(c["x_entry"], x), (c["y_entry"], y),
                           (c["w_entry"], width), (c["h_entry"], height)]:
            if entry and entry.winfo_exists():
                entry.delete(0, 'end')
                entry.insert(0, str(val))


# ─────────────────────────────────────────────
#  Config aliases (module-level, loaded once)
# ─────────────────────────────────────────────
def _cc(key):
    return config.config_data['clicks'][key]

aura_storage           = _cc('aura_storage')
regular_tab            = _cc('regular_tab')
special_tab            = _cc('special_tab')
search_bar             = _cc('search_bar')
aura_first_slot        = _cc('aura_first_slot')
equip_button           = _cc('equip_button')
collection_menu        = _cc('collection_menu')
exit_collection        = _cc('exit_collection')
items_storage          = _cc('items_storage')
items_tab              = _cc('items_tab')
items_bar              = _cc('items_bar')
item_value             = _cc('item_first_slot')
quanity_bar            = _cc('item_value')
use_button             = _cc('use_button')
quest_menu             = _cc('quest_menu')
daily_tab              = _cc('daily_tab')
first_slot             = _cc('first_slot')
second_slot            = _cc('second_slot')
third_slot             = _cc('third_slot')
claim_button           = _cc('claim_button')
merchant_name_ocr      = _cc('merchant_name_ocr')
merchant_open_button   = _cc('merchant_open_button')
merchant_dialog        = _cc('merchant_dialog')
merchant_item_name_ocr = _cc('merchant_item_name_ocr')
merchant_amount_button = _cc('merchant_amount_button')
merchant_purchase_button = _cc('merchant_purchase_button')
merchant_1_slot_button = _cc('merchant_1_slot_button')

last_log_position  = 0
monitoring_active  = False
monitoring_thread  = None
lock               = threading.Lock()

azerty_replace_dict = {"w": "z", "a": "q"}


# ─────────────────────────────────────────────
#  Path / walk helpers
# ─────────────────────────────────────────────
def get_action(file):
    with open("path.txt") as path_file:
        base = path_file.read().strip()
    action_path = os.path.join(base, "paths", f"{file}.py")
    with open(action_path) as f:
        return f.read()


def walk_time_conversion(d):
    if config.config_data["settings"]["vip+_mode"] == "1":
        return d
    elif config.config_data["settings"]["vip_mode"] == "1":
        return d * 1.04
    else:
        return d * 1.3


def walk_sleep(d):
    sleep(walk_time_conversion(d))


def walk_send(k: str, press: bool):
    """Hold (press=True) or release (press=False) a movement key."""
    if config.config_data["settings"]["azerty_mode"] == "1" and k in azerty_replace_dict:
        k = azerty_replace_dict[k]
    if press:
        platform_key_down(k)
    else:
        platform_key_up(k)


# ─────────────────────────────────────────────
#  Main macro loop
# ─────────────────────────────────────────────
running      = False
initialized  = False
main_process = None


class MainLoop:
    def __init__(self):
        self.config_data      = config.read_config()
        self.macro_started    = False
        self.has_discord_enabled = False
        self.discord_webhook  = self.config_data["discord"]["webhook"]["url"]
        self.running          = threading.Event()
        self.thread           = None
        self.tracker_thread   = None
        try:
            self.tracker = Tracker.BiomeTracker()
        except Exception as e:
            print(f"BiomeTracker init error: {e}")
            self.tracker = None
        self.last_quest          = datetime.min
        self.last_item           = datetime.min
        self.last_potion         = datetime.min
        self.last_merchant       = datetime.min
        self.last_potion_3       = datetime.min
        self.last_ss             = datetime.min
        self.last_item_scheduler = datetime.min

    def start(self):
        try:
            self.config_data = config.read_config()
            self.discord_webhook = self.config_data["discord"]["webhook"]["url"]
            if self.config_data["discord"]["webhook"]["enabled"] == "1":
                wh = discord_webhook.DiscordWebhook(url=self.discord_webhook)
                embed = discord_webhook.DiscordEmbed(
                    title="Macro Started",
                    description=(f"{time.strftime('[%I:%M:%S %p]')}: Macro started.\n\n"
                                 f"**Version:** {config.get_current_version()}\n"
                                 f"**Support:** https://discord.gg/JsMM299RF7")
                )
                embed.set_footer(text=f"Elixir Macro | {config.get_current_version()}")
                embed.set_color(0x64ff5e)
                wh.add_embed(embed)
                wh.execute()
            print("Starting Macro!")
            self.running.set()
            self.thread = threading.Thread(target=self.loop_process, daemon=True)
            self.thread.start()
            self.run_biome_detection()
        except Exception as e:
            messagebox.showerror("Error", f"Error starting the macro: {e}")

    def stop(self):
        print("Stopping macro...")
        self.running.clear()
        try:
            if self.config_data["discord"]["webhook"]["enabled"] == "1":
                wh = discord_webhook.DiscordWebhook(url=self.discord_webhook)
                embed = discord_webhook.DiscordEmbed(
                    title="Macro Stopped",
                    description=(f"{time.strftime('[%I:%M:%S %p]')}: Macro stopped.\n\n"
                                 f"**Version:** {config.get_current_version()}")
                )
                embed.set_footer(text=f"Elixir Macro | {config.get_current_version()}")
                embed.set_color(0xff0000)
                wh.add_embed(embed)
                wh.execute()
        except Exception as e:
            print(f"Webhook stop notification failed: {e}")
        try:
            if self.tracker:
                self.tracker.stop_monitoring()
            if self.tracker_thread and self.tracker_thread.is_alive():
                self.tracker_thread.join(timeout=2)
        except Exception as e:
            print(f"Error stopping tracker: {e}")
        if self.thread is not None:
            try:
                self.thread.join(timeout=2)
            except Exception as e:
                print(f"Error stopping main thread: {e}")
            finally:
                self.thread = None

    def run_biome_detection(self):
        print("Starting biome detection...")
        if not self.tracker:
            print("No tracker available; skipping biome detection.")
            return
        def _runner():
            try:
                asyncio.run(self.tracker.monitor_logs())
            except Exception as e:
                print(f"Tracker thread error: {e}")
        self.tracker_thread = threading.Thread(target=_runner, daemon=True)
        self.tracker_thread.start()

    def loop_process(self):
        print("Main loop started.")
        while self.running.is_set():
            try:
                if IS_WIN and config.config_data['settings']['reset'] == "1":
                    self.activate_window(titles="Roblox")
                time.sleep(1)
                self.auto_equip()
                time.sleep(1)
                self.align_cam()
                time.sleep(1)
                self.item_scheduler()
                time.sleep(1)
                self.auto_loop_stuff()
                time.sleep(1)
                self.do_obby()
                time.sleep(1)
                self.item_collecting()
                time.sleep(1)
            except Exception as e:
                print(f"Loop error: {e}")
                messagebox.showerror("Main Loop Error", str(e))
                if not self.running.is_set():
                    break
                time.sleep(5)
        print("Main loop stopped.")


    def auto_equip(self):
        if config.config_data['auto_equip']['enabled'] != "1":
            return
        try:
            time.sleep(1.3)
            platform_click(aura_storage[0], aura_storage[1])
            time.sleep(0.55)
            if config.config_data['auto_equip']['special_aura'] == "0":
                platform_click(regular_tab[0], regular_tab[1])
            else:
                platform_click(special_tab[0], special_tab[1])
            time.sleep(0.55)
            platform_click(search_bar[0], search_bar[1])
            time.sleep(0.55)
            platform_key_press(config.config_data['auto_equip']['aura'])
            time.sleep(0.3)
            platform_key_combo("enter")
            time.sleep(0.55)
            platform_click(aura_first_slot[0], aura_first_slot[1])
            time.sleep(0.55)
            platform_click(equip_button[0], equip_button[1])
            time.sleep(0.2)
            platform_click(search_bar[0], search_bar[1])
            time.sleep(0.3)
            platform_key_combo("enter")
            platform_click(aura_storage[0], aura_storage[1])
            time.sleep(0.4)
        except Exception as e:
            messagebox.showerror("Auto Equip Error", str(e))

    def align_cam(self):
        if config.config_data["settings"]["reset"] != "1":
            self.reset()
            return
        try:
            platform_click(collection_menu[0], collection_menu[1])
            time.sleep(1)
            platform_click(exit_collection[0], exit_collection[1])
            time.sleep(1)
            if IS_WIN and ahk:
                ahk.mouse_drag(x=exit_collection[0], y=exit_collection[1],
                               from_position=(exit_collection[0], exit_collection[1]),
                               button='right', coord_mode="Screen", send_mode="Input")
            else:
                try:
                    auto.moveTo(exit_collection[0], exit_collection[1])
                    auto.dragTo(exit_collection[0], exit_collection[1] + 50, button='right', duration=0.2)
                except Exception as e:
                    print(f"Camera align drag failed: {e}")
        except Exception as e:
            messagebox.showerror("Align Cam Error", str(e))
        self.reset()

    def reset(self):
        if config.config_data['settings']['reset'] != "1":
            return
        platform_key_combo("esc")
        sleep(0.33)
        platform_key_combo("r")
        sleep(0.55)
        platform_key_combo("enter")

    def collect(self):
        for _ in range(6):
            platform_key_combo("e")
            sleep(0.1)
            platform_key_combo("f")

    def do_obby(self):
        if config.config_data['obby']['enabled'] != "1":
            return
        try:
            exec(get_action("obby_path"))
        except Exception as e:
            messagebox.showerror("Obby Error", str(e))

    def do_crafting(self):
        if config.config_data['potion_crafting']['enabled'] != "1":
            return
        try:
            exec(get_action("potion_path"))
        except Exception as e:
            messagebox.showerror("Crafting Error", str(e))

    def crafting(self):
        try:
            sp = config.config_data['clicks']['potion_search_bar']
            fs = config.config_data['clicks']['first_potion_slot']
            ss = config.config_data['clicks']['second_potion_slot']
            ts = config.config_data['clicks']['third_potion_slot']
            orb = config.config_data['clicks']['open_recipe']
            pt  = config.config_data['clicks']['potion_tab']
            it  = config.config_data['clicks']['item_tab']
            ab1 = config.config_data['clicks']['add_button_1']
            ab2 = config.config_data['clicks']['add_button_2']
            ab3 = config.config_data['clicks']['add_button_3']
            ab4 = config.config_data['clicks']['add_button_4']
            cb  = config.config_data['clicks']['craft_button']
            aab = config.config_data['clicks']['auto_add_button']

            valid_potions = ["Fortune","Speed Potion","Lucky Potion","Heavenly","Godly","Potion of bound"]

            use_potion_tab = config.config_data["potion_crafting"]["potion_crafting"] == "1"
            tab_btn = pt if use_potion_tab else it

            def _craft(slot_btn, item_key):
                item = config.config_data['potion_crafting'][item_key]
                if item not in valid_potions:
                    return
                if slot_btn == fs:
                    platform_click(tab_btn[0], tab_btn[1]); sleep(0.55)
                platform_click(sp[0], sp[1]); sleep(0.55)
                platform_key_press(item); sleep(0.78)
                platform_click(slot_btn[0], slot_btn[1]); sleep(0.55)
                platform_click(orb[0], orb[1]); sleep(1)
                for ab in [ab1, ab2, ab3, ab4]:
                    platform_click(ab[0], ab[1]); sleep(0.38)
                platform_click(cb[0], cb[1]); sleep(0.78)

            def _auto_add():
                platform_click(sp[0], sp[1]); sleep(0.78)
                platform_key_press(config.config_data['potion_crafting']['current_temporary_auto_add']); sleep(0.78)
                platform_key_combo("enter"); sleep(0.48)
                platform_click(fs[0], fs[1]); sleep(0.38)
                platform_click(aab[0], aab[1]); sleep(0.38)
                platform_key_combo("f")

            if config.config_data['potion_crafting']['craft_potion_1'] == "1":
                _craft(fs, 'item_1')
            if config.config_data['potion_crafting']['craft_potion_2'] == "1":
                _craft(ss, 'item_2')
            if config.config_data['potion_crafting']['craft_potion_3'] == "1":
                _craft(ts, 'item_3')
            if config.config_data['potion_crafting']['temporary_auto_add'] == "1":
                _auto_add()
            self.reset()
        except Exception as e:
            messagebox.showerror("Crafting Error", str(e))

    def chalice(self):
        return None

    def claim_quests(self):
        if config.config_data['claim_daily_quests'] != "1":
            return
        try:
            platform_click(quest_menu[0], quest_menu[1]); sleep(0.55)
            for slot in [first_slot, second_slot, third_slot]:
                platform_click(slot[0], slot[1]); sleep(0.38)
                platform_click(claim_button[0], claim_button[1]); sleep(0.38)
            platform_click(quest_menu[0], quest_menu[1])
        except Exception as e:
            messagebox.showerror("Quest Error", str(e))

    def item_collecting(self):
        if config.config_data['item_collecting']['enabled'] != "1":
            return
        try:
            exec(get_action("item_collect"))
        except Exception as e:
            messagebox.showerror("Item Collecting Error", str(e))

    def item_scheduler(self):
        if config.config_data['item_scheduler_item']['enabled'] != "1":
            return
        try:
            platform_click(items_storage[0], items_storage[1]); sleep(0.55)
            platform_click(items_tab[0], items_tab[1]); sleep(0.33)
            platform_click(items_bar[0], items_bar[1]); sleep(0.33)
            platform_key_press(config.config_data['item_scheduler_item']['item_name']); sleep(0.55)
            platform_key_combo("enter"); sleep(0.43)
            platform_click(item_value[0], item_value[1]); sleep(0.33)
            platform_click(quanity_bar[0], quanity_bar[1]); sleep(0.1)
            platform_click(quanity_bar[0], quanity_bar[1]); sleep(0.33)
            platform_key_press(config.config_data['item_scheduler_item']['item_scheduler_quantity']); sleep(0.55)
            platform_key_combo("enter"); sleep(0.43)
            platform_click(use_button[0], use_button[1]); sleep(0.78)
            platform_click(items_storage[0], items_storage[1])
        except Exception as e:
            messagebox.showerror("Scheduler Error", str(e))

    def inventory_screenshots(self):
        if config.config_data['invo_ss']['enabled'] != "1":
            return
        try:
            sleep(0.39)
            platform_click(aura_storage[0], aura_storage[1]); sleep(0.55)
            platform_click(regular_tab[0], regular_tab[1]); sleep(0.55)

            ss_dir = os.path.join(os.getcwd(), "images")
            os.makedirs(ss_dir, exist_ok=True)

            def _send_screenshot(path, title):
                if 'discord.com' not in self.discord_webhook:
                    return
                wh = discord_webhook.DiscordWebhook(url=self.discord_webhook)
                embed = discord_webhook.DiscordEmbed(title=title, description="")
                fname = os.path.basename(path)
                if os.path.exists(path):
                    with open(path, 'rb') as f:
                        wh.add_file(file=f.read(), filename=fname)
                    embed.set_image(url=f"attachment://{fname}")
                wh.add_embed(embed)
                wh.execute()

            ss = auto.screenshot()
            ss_path = os.path.join(ss_dir, "inventory_screenshots.png")
            ss.save(ss_path)
            _send_screenshot(ss_path, "**Aura Screenshot!**")

            platform_click(aura_storage[0], aura_storage[1]); sleep(0.55)
            platform_click(items_storage[0], items_storage[1]); sleep(0.55)
            platform_click(items_tab[0], items_tab[1]); sleep(0.33)

            ss2 = auto.screenshot()
            ss2_path = os.path.join(ss_dir, "item_screenshots.png")
            ss2.save(ss2_path)
            _send_screenshot(ss2_path, "**Item Screenshot!**")

            platform_click(items_storage[0], items_storage[1])
        except Exception as e:
            messagebox.showerror("Inventory Screenshots", str(e))

    def auto_loop_stuff(self):
        # Crafting
        if config.config_data['potion_crafting']['enabled'] == "1":
            try:
                interval = timedelta(minutes=int(config.config_data['potion_crafting']['crafting_interval']))
            except (ValueError, TypeError):
                interval = timedelta(minutes=20)
            if datetime.now() - self.last_potion >= interval:
                self.do_crafting()
                self.last_potion = datetime.now()

        # Quests
        if config.config_data['claim_daily_quests'] == "1":
            if datetime.now() - self.last_quest >= timedelta(minutes=30):
                self.claim_quests()
                self.last_quest = datetime.now()

        # Inventory screenshots
        if config.config_data['invo_ss']['enabled'] == "1":
            try:
                ss_delta = timedelta(minutes=int(config.config_data['invo_ss']['duration']))
            except (ValueError, TypeError):
                ss_delta = timedelta(minutes=60)
            if datetime.now() - self.last_ss >= ss_delta:
                self.inventory_screenshots()
                self.last_ss = datetime.now()

        # Item scheduler
        if config.config_data['item_scheduler_item']['enabled'] == "1":
            try:
                item_delta = timedelta(minutes=int(config.config_data['item_scheduler_item']['interval']))
            except (ValueError, TypeError):
                item_delta = timedelta(minutes=20)
                self.send_webhook(
                    "Configuration Warning",
                    f"Invalid item scheduler interval. Defaulting to 20 minutes.",
                    0xffff00
                )
            if datetime.now() - self.last_item_scheduler >= item_delta:
                self.item_scheduler()
                self.last_item_scheduler = datetime.now()

    def send_webhook(self, title, description, color, urgent=False):
        try:
            if self.config_data["discord"]["webhook"]["enabled"] != "1":
                return
            wh = discord_webhook.DiscordWebhook(url=self.discord_webhook)
            if urgent:
                ping_id = self.config_data['discord']['webhook']['ping_id']
                wh.set_content(f"<@{ping_id}>")
            embed = discord_webhook.DiscordEmbed(title=title, description=description)
            embed.set_footer(text=f"Elixir Macro | {config.get_current_version()}")
            embed.set_color(color)
            wh.add_embed(embed)
            wh.execute()
        except Exception as e:
            print(f"Webhook send error: {e}")

    def activate_window(self, titles=""):
        """Windows-only: bring Roblox window to the foreground."""
        if not IS_WIN:
            return
        try:
            import pywinctl as pwc
        except ImportError:
            print("pywinctl not available; skipping window activation.")
            return
        try:
            all_titles = pwc.getAllTitles()
            for wt in all_titles:
                if titles in wt:
                    pwc.getWindowsWithTitle(wt)[0].activate()
                    return
        except Exception as e:
            print(f"activate_window failed: {e}")