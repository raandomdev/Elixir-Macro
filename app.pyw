import os
import sys
import json
import pathlib
import time
import asyncio
import threading
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox

# Third-party imports
try:
    import discord_webhook
    import keyboard
    import mouse
    import pyautogui as auto
    import webview
    import pytesseract
    from PIL import ImageGrab, Image
except ImportError as e:
    messagebox.showerror("Import Error", f"Missing module: {e}\nPlease install required packages.")
    sys.exit(1)

# Platform-specific automation
try:
    if sys.platform == "win32":
        try:
            from ahk import AHK
            ahk = AHK()
        except:
            ahk = None
    elif sys.platform == "darwin":
        from pynput.keyboard import Key
        mouse  # already imported
        keyboard
except Exception as e:
    messagebox.showerror("Error", f"Platform automation import failed: {e}")
    sys.exit(1)

# Prevent .pyc files
sys.dont_write_bytecode = True

# ----------------------------------------------------------------------
# Configuration management (replaces data.config)
# ----------------------------------------------------------------------
CONFIG_FILE = "config.json"
CURRENT_VERSION = "1.1.2"

def get_current_version():
    return CURRENT_VERSION

def get_config_path():
    """Return path to config.json in the application directory."""
    if getattr(sys, 'frozen', False):
        base = pathlib.Path(sys.executable).parent.resolve()
    else:
        base = pathlib.Path(__file__).parent.resolve()
    return base / CONFIG_FILE

def read_config():
    """Load configuration from JSON file. Return default if missing."""
    default_config = {
        "settings": {
            "vip_mode": "0",
            "vip+_mode": "0",
            "azerty_mode": "0",
            "reset": "1",
            "merchant": {"enabled": "0", "duration": "60"}
        },
        "discord": {
            "webhook": {
                "enabled": "0",
                "url": "",
                "ping_id": "",
                "ps_link": ""
            }
        },
        "auto_equip": {
            "enabled": "0",
            "aura": "",
            "special_aura": "0"
        },
        "obby": {"enabled": "0"},
        "chalice": {"enabled": "0"},
        "item_collecting": {
            "enabled": "0",
            "spot1": "1", "spot2": "1", "spot3": "1",
            "spot4": "1", "spot5": "1", "spot6": "1",
            "spot7": "1", "spot8": "1"
        },
        "potion_crafting": {
            "enabled": "0",
            "crafting_interval": "30",
            "item_1": "",
            "craft_potion_1": "0",
            "item_2": "",
            "craft_potion_2": "0",
            "item_3": "",
            "craft_potion_3": "0",
            "temporary_auto_add": "0",
            "current_temporary_auto_add": "",
            "potion_crafting": "1"
        },
        "claim_daily_quests": "0",
        "invo_ss": {"enabled": "0", "duration": "60"},
        "item_scheduler_item": {
            "enabled": "0",
            "item_name": "",
            "item_scheduler_quantity": "1",
            "interval": "30"
        },
        "biome_detection": {"enabled": "0"},
        "enabled_dectection": "0",
        "send_min": "100",
        "send_max": "999",
        "mari": {"ping": {"enabled": "0", "id": ""}, "settings": {}},
        "jester": {"ping": {"enabled": "0", "id": ""}, "settings": {}},
        "fishing": {"enabled": "0", "live_preview": "0", "capture_fps": "60", "color_tolerance": "1", "auto_buy": "0"},
        "biome_alerts": {
            "NORMAL": "0", "WINDY": "0", "RAINY": "0", "SNOWY": "0",
            "SAND STORM": "0", "HELL": "0", "STARFALL": "0", "HEAVEN": "0",
            "CORRUPTION": "0", "NULL": "0", "GLITCHED": "0", "DREAMSPACE": "0",
            "CYBERSPACE": "0", "THE CITADEL OF ORDERS": "0"
        },
        "clicks": {
            "aura_storage": [0, 0],
            "regular_tab": [0, 0],
            "special_tab": [0, 0],
            "search_bar": [0, 0],
            "aura_first_slot": [0, 0],
            "equip_button": [0, 0],
            "collection_menu": [0, 0],
            "exit_collection": [0, 0],
            "items_storage": [0, 0],
            "items_tab": [0, 0],
            "items_bar": [0, 0],
            "item_first_slot": [0, 0],
            "item_value": [0, 0],
            "use_button": [0, 0],
            "quest_menu": [0, 0],
            "first_slot": [0, 0],
            "second_slot": [0, 0],
            "third_slot": [0, 0],
            "claim_button": [0, 0],
            "merchant_name_ocr": [0, 0, 0, 0],
            "merchant_open_button": [0, 0],
            "merchant_dialog": [0, 0],
            "merchant_item_name_ocr": [0, 0, 0, 0],
            "merchant_amount_button": [0, 0],
            "merchant_purchase_button": [0, 0],
            "merchant_1_slot_button": [0, 0],
            "potion_search_bar": [0, 0],
            "first_potion_slot": [0, 0],
            "second_potion_slot": [0, 0],
            "third_potion_slot": [0, 0],
            "open_recipe": [0, 0],
            "potion_tab": [0, 0],
            "item_tab": [0, 0],
            "add_button_1": [0, 0],
            "add_button_2": [0, 0],
            "add_button_3": [0, 0],
            "add_button_4": [0, 0],
            "craft_button": [0, 0],
            "auto_add_button": [0, 0]
        }
    }
    cfg_path = get_config_path()
    if cfg_path.exists():
        try:
            with open(cfg_path, 'r') as f:
                user_cfg = json.load(f)
                # deep merge (simple recursive update)
                def deep_merge(a, b):
                    for k in b:
                        if k in a and isinstance(a[k], dict) and isinstance(b[k], dict):
                            deep_merge(a[k], b[k])
                        else:
                            a[k] = b[k]
                deep_merge(default_config, user_cfg)
        except:
            pass
    return default_config

def save_config(cfg):
    """Save configuration to JSON file."""
    cfg_path = get_config_path()
    try:
        with open(cfg_path, 'w') as f:
            json.dump(cfg, f, indent=4)
    except Exception as e:
        messagebox.showerror("Config Error", f"Could not save config: {e}")

# Load config on module import
config_data = read_config()

# ----------------------------------------------------------------------
# OCR engine (replaces data.ocr_engine)
# ----------------------------------------------------------------------
def perform_ocr(x, y, w, h):
    """Capture screen region and return recognized text."""
    try:
        bbox = (x, y, x+w, y+h)
        img = ImageGrab.grab(bbox)
        text = pytesseract.image_to_string(img, config='--psm 6').strip()
        return text
    except Exception as e:
        print(f"OCR error: {e}")
        return ""

def search_text_in_ocr(text, search):
    """Return True if search term is found in OCR text (case-insensitive)."""
    return search.lower() in text.lower()

def check_ocr_text(x, y, w, h, expected):
    """Return True if OCR text contains expected string."""
    return search_text_in_ocr(perform_ocr(x, y, w, h), expected)

def get_ocr_text(x, y, w, h):
    """Return OCR text from region."""
    return perform_ocr(x, y, w, h)

# ----------------------------------------------------------------------
# Biome tracker (replaces data.Tracker)
# ----------------------------------------------------------------------
class BiomeTracker:
    """Monitor Roblox logs for biome changes and send Discord alerts."""

    def __init__(self):
        self.running = False
        self.last_position = 0
        self.log_path = self._find_log_path()
        self.webhook_url = config_data["discord"]["webhook"]["url"]
        self.ping_id = config_data["discord"]["webhook"]["ping_id"]

    def _find_log_path(self):
        """Locate Roblox player log (platform-specific)."""
        if sys.platform == "win32":
            local_app_data = os.getenv('LOCALAPPDATA')
            if local_app_data:
                base = pathlib.Path(local_app_data) / "Roblox" / "logs"
                if base.exists():
                    logs = list(base.glob("*.log"))
                    if logs:
                        # return the most recent
                        return max(logs, key=os.path.getmtime)
        elif sys.platform == "darwin":
            # macOS typical location
            base = pathlib.Path.home() / "Library" / "Logs" / "Roblox"
            if base.exists():
                logs = list(base.glob("*.log"))
                if logs:
                    return max(logs, key=os.path.getmtime)
        return None

    async def monitor_logs(self):
        """Async loop that reads log file and detects biome changes."""
        if not self.log_path:
            print("Roblox log not found.")
            return
        self.running = True
        biome_patterns = {
            "NORMAL": ["Biome changed to Normal"],
            "WINDY": ["Biome changed to Windy"],
            "RAINY": ["Biome changed to Rainy"],
            "SNOWY": ["Biome changed to Snowy"],
            "SAND STORM": ["Biome changed to Sandstorm"],
            "HELL": ["Biome changed to Hell"],
            "STARFALL": ["Biome changed to Starfall"],
            "HEAVEN": ["Biome changed to Heaven"],
            "CORRUPTION": ["Biome changed to Corruption"],
            "NULL": ["Biome changed to Null"],
            "GLITCHED": ["Biome changed to Glitched"],
            "DREAMSPACE": ["Biome changed to Dreamspace"],
            "CYBERSPACE": ["Biome changed to Cyberspace"],
            "THE CITADEL OF ORDERS": ["Biome changed to The Citadel of Orders", "Biome changed to Citadel"]
        }
        while self.running:
            try:
                if not self.log_path.exists():
                    self.log_path = self._find_log_path()
                    await asyncio.sleep(2)
                    continue
                with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    f.seek(self.last_position)
                    lines = f.readlines()
                    self.last_position = f.tell()
                for line in lines:
                    for biome, patterns in biome_patterns.items():
                        if any(p in line for p in patterns):
                            if config_data["biome_alerts"].get(biome) == "1":
                                self._send_alert(biome)
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Log monitor error: {e}")
                await asyncio.sleep(5)

    def _send_alert(self, biome):
        """Send Discord webhook for biome change."""
        if config_data["discord"]["webhook"]["enabled"] != "1" or not self.webhook_url:
            return
        webhook = discord_webhook.DiscordWebhook(url=self.webhook_url)
        if self.ping_id:
            webhook.set_content(f"<@{self.ping_id}>")
        embed = discord_webhook.DiscordEmbed(
            title="Biome Detected!",
            description=f"**{biome}** biome has appeared.",
            color=0xffaa00
        )
        embed.set_footer(text=f"Elixir Macro | {CURRENT_VERSION}")
        webhook.add_embed(embed)
        webhook.execute()

    def stop_monitoring(self):
        self.running = False

# ----------------------------------------------------------------------
# Global helpers (from original app.pyw)
# ----------------------------------------------------------------------
def set_path():
    """Create path.txt with application directory."""
    try:
        if getattr(sys, 'frozen', False):
            base = pathlib.Path(sys.executable).parent.resolve()
            if "_MEIPASS" in str(base) or "_temp_" in str(base):
                base = pathlib.Path(os.path.expanduser("~")) / "Documents" / "Goldens_Macro"
                base.mkdir(exist_ok=True)
        else:
            base = pathlib.Path(__file__).parent.resolve()
        path_file = base / "path.txt"
        with open(path_file, "w") as f:
            f.write(str(base))
    except Exception as e:
        messagebox.showerror("Error", f"Could not set path: {e}")

azerty_replace_dict = {"w": "z", "a": "q"}

def platform_click(x, y, button='left'):
    x, y = int(x), int(y)
    if sys.platform == "win32":
        if ahk:
            ahk.click(x, y, coord_mode="Screen")
        else:
            try:
                auto.moveTo(x, y, duration=0.08)
                auto.click(button=button)
            except:
                mouse.move(x, y)
                mouse.click(button)
    elif sys.platform == "darwin":
        try:
            auto.moveTo(x, y, duration=0.08)
            auto.click(button=button)
        except:
            mouse.move(x, y)
            mouse.click(button)

def platform_key_press(key):
    if sys.platform == "win32":
        if ahk:
            ahk.send(key)
        else:
            try:
                auto.press(key)
            except:
                keyboard.write(key)
    elif sys.platform == "darwin":
        keyboard.write(key)

def platform_key_combo(key):
    if sys.platform == "win32":
        if ahk:
            ahk.send(key)
        else:
            try:
                if '+' in key:
                    auto.hotkey(*[k.strip() for k in key.split('+')])
                else:
                    auto.hotkey(key)
            except:
                keyboard.write(key)
    elif sys.platform == "darwin":
        try:
            if key == '{Enter}':
                keyboard.press(Key.enter)
                keyboard.release(Key.enter)
            else:
                keyboard.write(key)
        except:
            keyboard.write(key)

def get_action(file):
    """Read pathing script from paths folder."""
    try:
        with open("path.txt") as pf:
            base = pf.read().strip()
        path_file = pathlib.Path(base) / "paths" / f"{file}.py"
        with open(path_file, 'r') as f:
            return f.read()
    except Exception as e:
        print(f"Failed to load path {file}: {e}")
        return ""

def walk_time_conversion(d):
    if config_data["settings"]["vip+_mode"] == "1":
        return d
    elif config_data["settings"]["vip_mode"] == "1":
        return d * 1.04
    else:
        return d * 1.3

def walk_sleep(d):
    time.sleep(walk_time_conversion(d))

def walk_send(k, t):
    if config_data["settings"]["azerty_mode"] == "1" and k in azerty_replace_dict:
        k = azerty_replace_dict[k]
    if t:
        keyboard.on_press_key(k, lambda _: None)  # dummy
    else:
        keyboard.on_release_key(k, lambda _: None)

# ----------------------------------------------------------------------
# MainLoop class (core macro logic)
# ----------------------------------------------------------------------
class MainLoop:
    def __init__(self):
        self.config_data = config_data
        self.running = threading.Event()
        self.thread = None
        self.tracker = BiomeTracker()
        self.tracker_thread = None
        self.last_quest = datetime.min
        self.last_potion = datetime.min
        self.last_ss = datetime.min
        self.last_item_scheduler = datetime.min
        self.discord_webhook = self.config_data["discord"]["webhook"]["url"]

    def start(self):
        if self.config_data["discord"]["webhook"]["enabled"] == "1" and self.discord_webhook:
            self._send_discord("Macro Started", f"{time.strftime('[%I:%M:%S %p]')}: Macro started.", 0x64ff5e)
        print("Starting Macro!")
        self.running.set()
        self.thread = threading.Thread(target=self.loop_process, daemon=True)
        self.thread.start()
        self._start_biome_detection()

    def stop(self):
        if self.config_data["discord"]["webhook"]["enabled"] == "1" and self.discord_webhook:
            self._send_discord("Macro Stopped", f"{time.strftime('[%I:%M:%S %p]')}: Macro stopped.", 0xff0000)
        self.running.clear()
        if self.tracker:
            self.tracker.stop_monitoring()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

    def _send_discord(self, title, desc, color):
        try:
            webhook = discord_webhook.DiscordWebhook(url=self.discord_webhook)
            embed = discord_webhook.DiscordEmbed(title=title, description=desc, color=color)
            embed.set_footer(text=f"Elixir Macro | {CURRENT_VERSION}")
            webhook.add_embed(embed)
            webhook.execute()
        except:
            pass

    def _start_biome_detection(self):
        def run_async():
            asyncio.run(self.tracker.monitor_logs())
        self.tracker_thread = threading.Thread(target=run_async, daemon=True)
        self.tracker_thread.start()

    def loop_process(self):
        while self.running.is_set():
            try:
                if self.config_data['settings']['reset'] == "1" and sys.platform == "win32":
                    self.activate_window("Roblox")
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
                time.sleep(5)

    # --- Macro action methods (copied from original with small fixes) ---
    def auto_equip(self):
        if self.config_data['auto_equip']['enabled'] != "1":
            return
        try:
            c = self.config_data['clicks']
            time.sleep(1.3)
            platform_click(*c['aura_storage'])
            time.sleep(0.55)
            if self.config_data['auto_equip']['special_aura'] == "0":
                platform_click(*c['regular_tab'])
            else:
                platform_click(*c['special_tab'])
            time.sleep(0.55)
            platform_click(*c['search_bar'])
            time.sleep(0.55)
            platform_key_press(self.config_data['auto_equip']['aura'])
            time.sleep(0.3)
            platform_key_combo('{Enter}')
            time.sleep(0.55)
            platform_click(*c['aura_first_slot'])
            time.sleep(0.55)
            platform_click(*c['equip_button'])
            time.sleep(0.2)
            platform_click(*c['search_bar'])
            time.sleep(0.3)
            platform_key_combo('{Enter}')
            platform_click(*c['aura_storage'])
        except Exception as e:
            messagebox.showerror("Auto Equip", str(e))

    def align_cam(self):
        if self.config_data["settings"]["reset"] != "1":
            return
        try:
            c = self.config_data['clicks']
            platform_click(*c['collection_menu'])
            time.sleep(1)
            platform_click(*c['exit_collection'])
            time.sleep(1)
            if sys.platform == "win32" and ahk:
                ahk.mouse_drag(x=c['exit_collection'][0], y=c['exit_collection'][1]+50,
                               from_position=(c['exit_collection'][0], c['exit_collection'][1]),
                               button='right', coord_mode="Screen")
            elif sys.platform == "darwin":
                mouse.move(c['exit_collection'][0], c['exit_collection'][1])
                mouse.press('right')
                mouse.move(c['exit_collection'][0], c['exit_collection'][1] + 50)
                mouse.release('right')
        except:
            messagebox.showerror("Error", "Camera alignment failed")
        self._reset()

    def _reset(self):
        if self.config_data['settings']['reset'] == "1":
            platform_key_combo('esc')
            time.sleep(0.33)
            platform_key_combo('r')
            time.sleep(0.55)
            platform_key_combo('{Enter}')

    def do_obby(self):
        if self.config_data['obby']['enabled'] == "1":
            try:
                exec(get_action("obby_path"))
            except Exception as e:
                messagebox.showerror("Obby", str(e))

    def item_collecting(self):
        if self.config_data['item_collecting']['enabled'] == "1":
            try:
                exec(get_action("item_collect"))
            except Exception as e:
                messagebox.showerror("Item Collect", str(e))

    def item_scheduler(self):
        if self.config_data['item_scheduler_item']['enabled'] != "1":
            return
        try:
            c = self.config_data['clicks']
            platform_click(*c['items_storage'])
            time.sleep(0.55)
            platform_click(*c['items_tab'])
            time.sleep(0.33)
            platform_click(*c['items_bar'])
            time.sleep(0.33)
            platform_key_combo(self.config_data['item_scheduler_item']['item_name'])
            time.sleep(0.55)
            platform_key_combo('{Enter}')
            time.sleep(0.43)
            platform_click(*c['item_first_slot'])
            time.sleep(0.33)
            platform_click(*c['item_value'])
            time.sleep(0.1)
            platform_click(*c['item_value'])
            time.sleep(0.33)
            platform_key_combo(self.config_data['item_scheduler_item']['item_scheduler_quantity'])
            time.sleep(0.55)
            platform_key_combo('{Enter}')
            time.sleep(0.43)
            platform_click(*c['use_button'])
            time.sleep(0.78)
            platform_click(*c['items_storage'])
        except Exception as e:
            messagebox.showerror("Item Scheduler", str(e))

    def claim_quests(self):
        if self.config_data['claim_daily_quests'] != "1":
            return
        try:
            c = self.config_data['clicks']
            platform_click(*c['quest_menu'])
            time.sleep(0.55)
            platform_click(*c['first_slot'])
            time.sleep(0.38)
            platform_click(*c['claim_button'])
            time.sleep(0.38)
            platform_click(*c['second_slot'])
            time.sleep(0.38)
            platform_click(*c['claim_button'])
            time.sleep(0.38)
            platform_click(*c['third_slot'])
            time.sleep(0.38)
            platform_click(*c['claim_button'])
            time.sleep(0.28)
            platform_click(*c['quest_menu'])
        except Exception as e:
            messagebox.showerror("Quests", str(e))

    def inventory_screenshots(self):
        if self.config_data['invo_ss']['enabled'] != "1":
            return
        try:
            c = self.config_data['clicks']
            time.sleep(0.39)
            platform_click(*c['aura_storage'])
            time.sleep(0.55)
            platform_click(*c['regular_tab'])
            time.sleep(0.55)
            screen_dir = pathlib.Path.cwd() / "images"
            screen_dir.mkdir(exist_ok=True)
            # Aura screenshot
            ss = auto.screenshot()
            path = screen_dir / "inventory_screenshots.png"
            ss.save(path)
            if self.discord_webhook and 'discord.com' in self.discord_webhook:
                self._send_image(path, "Aura Screenshot")
            time.sleep(0.55)
            platform_click(*c['aura_storage'])
            time.sleep(0.55)
            platform_click(*c['items_storage'])
            time.sleep(0.55)
            platform_click(*c['items_tab'])
            time.sleep(0.33)
            ss2 = auto.screenshot()
            path2 = screen_dir / "item_screenshots.png"
            ss2.save(path2)
            if self.discord_webhook:
                self._send_image(path2, "Item Screenshot")
            platform_click(*c['items_storage'])
        except Exception as e:
            messagebox.showerror("Screenshot", str(e))

    def _send_image(self, image_path, title):
        webhook = discord_webhook.DiscordWebhook(url=self.discord_webhook)
        with open(image_path, 'rb') as f:
            webhook.add_file(file=f.read(), filename=image_path.name)
        embed = discord_webhook.DiscordEmbed(title=title, description="")
        embed.set_image(url=f"attachment://{image_path.name}")
        webhook.add_embed(embed)
        webhook.execute()

    def auto_loop_stuff(self):
        now = datetime.now()
        # Potion crafting
        if self.config_data['potion_crafting']['enabled'] == "1":
            interval = int(self.config_data['potion_crafting'].get('crafting_interval', 30))
            if now - self.last_potion >= timedelta(minutes=interval):
                self.do_crafting()
                self.last_potion = now
        # Quests
        if self.config_data['claim_daily_quests'] == "1":
            if now - self.last_quest >= timedelta(minutes=30):
                self.claim_quests()
                self.last_quest = now
        # Screenshots
        if self.config_data['invo_ss']['enabled'] == "1":
            interval = int(self.config_data['invo_ss'].get('duration', 60))
            if now - self.last_ss >= timedelta(minutes=interval):
                self.inventory_screenshots()
                self.last_ss = now
        # Item scheduler
        if self.config_data['item_scheduler_item']['enabled'] == "1":
            interval = int(self.config_data['item_scheduler_item'].get('interval', 30))
            if now - self.last_item_scheduler >= timedelta(minutes=interval):
                self.item_scheduler()
                self.last_item_scheduler = now

    def do_crafting(self):
        # Simplified - call the path script
        if self.config_data['potion_crafting']['enabled'] == "1":
            try:
                exec(get_action("potion_path"))
            except Exception as e:
                messagebox.showerror("Crafting", str(e))

    def activate_window(self, title):
        if sys.platform != "win32":
            return
        try:
            import pywinctl as pwc
            wins = pwc.getWindowsWithTitle(title)
            if wins:
                wins[0].activate()
        except:
            try:
                import pygetwindow as gw
                wins = gw.getWindowsWithTitle(title)
                if wins:
                    wins[0].activate()
            except:
                pass

# ----------------------------------------------------------------------
# Coordinate capture (for calibration)
# ----------------------------------------------------------------------
class CoordinateCapture:
    def __init__(self, callback):
        self.callback = callback
        self.root = None
        self.canvas = None
        self.start_x = self.start_y = None
        self.mode = 'click'

    def start_capture(self, mode='click'):
        self.mode = mode
        self.root = tk.Tk()
        self.root.attributes('-fullscreen', True, '-alpha', 0.3)
        self.root.config(cursor='cross')
        self.canvas = tk.Canvas(self.root, bg='lightblue', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.root.bind('<Button-1>', self.on_click)
        if mode == 'rect':
            self.root.bind('<B1-Motion>', self.on_drag)
            self.root.bind('<ButtonRelease-1>', self.on_release)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def on_click(self, event):
        if self.mode == 'click':
            self.callback(event.x, event.y)
            self.root.destroy()
        else:
            self.start_x, self.start_y = event.x, event.y

    def on_drag(self, event):
        self.canvas.delete('rect')
        self.canvas.create_rectangle(self.start_x, self.start_y, event.x, event.y,
                                     outline='white', width=2, tag='rect')

    def on_release(self, event):
        w = abs(event.x - self.start_x)
        h = abs(event.y - self.start_y)
        self.callback(self.start_x, self.start_y, w, h)
        self.root.destroy()

    def on_close(self):
        self.callback(None)
        self.root.destroy()

# ----------------------------------------------------------------------
# API for webview
# ----------------------------------------------------------------------
class Api:
    def __init__(self):
        self.main_loop = MainLoop()
        self.hotkeys_registered = False

    def _ensure_hotkeys(self):
        if not self.hotkeys_registered:
            keyboard.add_hotkey('F1', self.start_macro)
            keyboard.add_hotkey('F2', self.stop_macro)
            keyboard.add_hotkey('F3', self.restart_macro)
            self.hotkeys_registered = True

    def update_status(self, state, text):
        webview.evaluate_js(f"window.setStatus('{state}', '{text}')")

    def show_toast(self, message, duration=3000):
        webview.evaluate_js(f"window.showToast('{message}', {duration})")

    def get_config(self):
        return config_data

    def save_config(self, new_config):
        config_data.update(new_config)
        save_config(config_data)
        self.main_loop.config_data = config_data
        return {"status": "ok"}

    def start_macro(self):
        self._ensure_hotkeys()
        self.main_loop.start()
        self.update_status('running', 'RUNNING')
        return {"status": "started"}

    def stop_macro(self):
        self._ensure_hotkeys()
        self.main_loop.stop()
        self.update_status('idle', 'IDLE')
        return {"status": "stopped"}

    def restart_macro(self):
        self.stop_macro()
        time.sleep(1)
        self.start_macro()
        return {"status": "restarted"}

    def test_webhook(self):
        url = config_data.get("discord", {}).get("webhook", {}).get("url", "")
        if url and 'discord.com' in url:
            webhook = discord_webhook.DiscordWebhook(url=url)
            embed = discord_webhook.DiscordEmbed(title="Webhook Test", description="Configuration successful!", color=0x00ff00)
            webhook.add_embed(embed)
            webhook.execute()
            return {"status": "success", "message": "Test sent."}
        return {"status": "error", "message": "Invalid webhook URL."}

    def capture_coordinate(self, mode='click'):
        result = [None]
        event = threading.Event()

        def callback(*coords):
            result[0] = coords
            event.set()

        capture = CoordinateCapture(callback)
        threading.Thread(target=capture.start_capture, args=(mode,), daemon=True).start()
        event.wait(timeout=60)
        coords = result[0]
        if coords is None:
            return {"status": "cancelled"}
        if mode == 'click':
            return {"status": "ok", "x": coords[0], "y": coords[1]}
        else:
            return {"status": "ok", "x": coords[0], "y": coords[1], "width": coords[2], "height": coords[3]}

    def get_mari_settings(self): return config_data.get("mari", {})
    def save_mari_settings(self, s): config_data["mari"] = s; save_config(config_data); return {"status": "ok"}
    def get_jester_settings(self): return config_data.get("jester", {})
    def save_jester_settings(self, s): config_data["jester"] = s; save_config(config_data); return {"status": "ok"}
    def get_biome_alerts(self): return config_data.get("biome_alerts", {})
    def save_biome_alerts(self, a): config_data["biome_alerts"] = a; save_config(config_data); return {"status": "ok"}
    def get_clicks(self): return config_data.get("clicks", {})
    def save_clicks(self, c): config_data["clicks"] = c; save_config(config_data); return {"status": "ok"}
    def get_item_collecting_spots(self):
        return {k: v for k, v in config_data.get("item_collecting", {}).items() if k.startswith("spot")}
    def save_item_collecting_spots(self, s):
        for k, v in s.items():
            config_data["item_collecting"][k] = v
        save_config(config_data)
        return {"status": "ok"}

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Elixir Macro v2.0</title>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700;900&family=Cinzel+Decorative:wght@400;700;900&family=Rajdhani:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
/* All CSS from the original - unchanged */
:root{--gold:#FFD700;--gold-light:#FFE566;--gold-dim:#B8960C;--gold-dark:#7A6000;--black:#000;--black-soft:#0A0A0A;--black-mid:#111;--black-panel:#161616;--black-border:#1E1E1E;--white:#fff;--white-dim:#CCC;--white-faint:#555;--glow:rgba(255,215,0,.35);--green:#00ff88;--red:#ff4444;--blue:#88bbff;}*{margin:0;padding:0;box-sizing:border-box;}body{background:#000;font-family:'Rajdhani',sans-serif;color:var(--white);overflow:hidden;user-select:none;width:100vw;height:100vh;}#ls{position:fixed;inset:0;background:#000;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:9999;overflow:hidden;}.ls-bg{position:absolute;inset:0;background:radial-gradient(ellipse at center,#0a0800,#000 70%);}.ls-stars,.ls-ptcl{position:absolute;inset:0;pointer-events:none;}.star{position:absolute;background:var(--gold);border-radius:50%;animation:twinkle var(--d,3s) ease-in-out infinite var(--dl,0s);opacity:0;}@keyframes twinkle{0%,100%{opacity:0;transform:scale(.5)}50%{opacity:var(--op,.8);transform:scale(1)}}.ls-orb{position:absolute;width:600px;height:600px;border-radius:50%;background:radial-gradient(circle,rgba(255,215,0,.05),transparent 70%);animation:orbP 4s ease-in-out infinite;}@keyframes orbP{0%,100%{transform:scale(.9);opacity:.5}50%{transform:scale(1.1);opacity:1}}.ptcl{position:absolute;width:3px;height:3px;background:var(--gold);border-radius:50%;animation:floatUp var(--d) ease-in infinite var(--dl);opacity:0;box-shadow:0 0 6px var(--gold);}@keyframes floatUp{0%{opacity:0;transform:translateY(0) scale(0)}10%{opacity:1}90%{opacity:.3}100%{opacity:0;transform:translateY(-200px) scale(.5)}}.ls-rings{position:relative;width:200px;height:200px;margin-bottom:40px;}.ring{position:absolute;border-radius:50%;border:2px solid transparent;animation:ringR linear infinite;}.ring:nth-child(1){inset:0;border-top-color:var(--gold);border-right-color:var(--gold-dim);animation-duration:3s;box-shadow:0 0 20px var(--glow),inset 0 0 20px var(--glow);}.ring:nth-child(2){inset:20px;border-bottom-color:var(--gold-light);border-left-color:var(--gold);animation-duration:2s;animation-direction:reverse;}.ring:nth-child(3){inset:40px;border-top-color:var(--gold-dim);border-right-color:var(--gold-light);animation-duration:4s;}.ring-c{position:absolute;inset:60px;border-radius:50%;background:radial-gradient(circle,rgba(255,215,0,.3),rgba(255,215,0,.05));animation:cGlow 2s ease-in-out infinite;display:flex;align-items:center;justify-content:center;}.ring-c::after{content:'⬡';font-size:32px;color:var(--gold);animation:cGlow 2s ease-in-out infinite reverse;text-shadow:0 0 20px var(--gold);}@keyframes ringR{from{transform:rotate(0)}to{transform:rotate(360deg)}}@keyframes cGlow{0%,100%{opacity:.6}50%{opacity:1}}.ls-title{font-family:'Cinzel Decorative',serif;font-size:42px;font-weight:900;color:transparent;background:linear-gradient(180deg,var(--gold-light),var(--gold) 50%,var(--gold-dim));-webkit-background-clip:text;background-clip:text;filter:drop-shadow(0 0 30px rgba(255,215,0,.6));letter-spacing:8px;animation:reveal 1.5s ease-out .3s both;}.ls-sub{font-family:'Cinzel',serif;font-size:14px;letter-spacing:6px;color:var(--gold-dim);margin-top:8px;animation:reveal 1.5s ease-out .6s both;}@keyframes reveal{from{opacity:0;transform:translateY(30px)}to{opacity:1;transform:translateY(0)}}.ls-bar-wrap{width:400px;margin-top:50px;animation:reveal 1s ease-out 1s both;}.ls-bar-lbl{font-size:11px;letter-spacing:4px;color:var(--white-faint);text-transform:uppercase;text-align:center;margin-bottom:10px;}.ls-bar-track{width:100%;height:3px;background:rgba(255,215,0,.1);border-radius:2px;position:relative;}.ls-bar-track::before{content:'';position:absolute;inset:-1px;border-radius:3px;border:1px solid rgba(255,215,0,.15);}.ls-bar-fill{height:100%;background:linear-gradient(90deg,var(--gold-dim),var(--gold-light));border-radius:2px;width:0%;transition:width .1s linear;position:relative;box-shadow:0 0 15px var(--gold),0 0 30px rgba(255,215,0,.3);}.ls-bar-fill::after{content:'';position:absolute;right:-2px;top:-3px;width:4px;height:9px;background:#fff;border-radius:2px;box-shadow:0 0 10px #fff,0 0 20px var(--gold);}.ls-pct{font-family:'Cinzel',serif;font-size:12px;color:var(--gold);text-align:center;margin-top:10px;letter-spacing:2px;}.ls-tip{font-size:11px;color:var(--white-faint);letter-spacing:2px;margin-top:16px;text-align:center;font-style:italic;min-height:16px;transition:opacity .2s;}#app{display:none;width:100vw;height:100vh;background:var(--black);flex-direction:column;position:relative;overflow:hidden;}.app-bg{position:absolute;inset:0;background:radial-gradient(ellipse at 10% 10%,rgba(255,215,0,.03),transparent 50%),radial-gradient(ellipse at 90% 90%,rgba(255,215,0,.02),transparent 50%);pointer-events:none;}.app-grid{position:absolute;inset:0;background-image:linear-gradient(rgba(255,215,0,.015) 1px,transparent 1px),linear-gradient(90deg,rgba(255,215,0,.015) 1px,transparent 1px);background-size:40px 40px;pointer-events:none;}@keyframes appIn{from{opacity:0;transform:scale(.97)}to{opacity:1;transform:scale(1)}}.app-in{animation:appIn .8s cubic-bezier(.16,1,.3,1) forwards;}.tbar{display:flex;align-items:center;justify-content:space-between;height:44px;background:var(--black-mid);border-bottom:1px solid rgba(255,215,0,.12);padding:0 16px;position:relative;z-index:10;flex-shrink:0;}.tbar::after{content:'';position:absolute;bottom:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--gold),transparent);}.tbar-logo{display:flex;align-items:center;gap:10px;}.tbar-icon{width:26px;height:26px;background:linear-gradient(135deg,var(--gold),var(--gold-dim));border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:14px;box-shadow:0 0 10px var(--glow);}.tbar-name{font-family:'Cinzel',serif;font-size:13px;font-weight:700;color:var(--gold);letter-spacing:3px;text-shadow:0 0 10px var(--glow);}.tbar-ver{font-size:10px;color:var(--white-faint);letter-spacing:2px;margin-left:4px;}.tbar-status{display:flex;align-items:center;gap:8px;font-size:11px;letter-spacing:2px;color:var(--white-faint);text-transform:uppercase;}.sdot{width:8px;height:8px;border-radius:50%;background:#333;transition:all .3s;}.sdot.running{background:var(--green);box-shadow:0 0 8px var(--green);animation:pulse 1s infinite;}.sdot.stopped{background:var(--red);box-shadow:0 0 8px var(--red);}.sdot.idle{background:var(--gold-dim);box-shadow:0 0 8px var(--glow);}@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}.content{flex:1;overflow:hidden;position:relative;}.panel-page{display:none;height:100%;padding:14px;overflow-y:auto;gap:10px;flex-wrap:wrap;align-content:flex-start;}.panel-page.active{display:flex;}.panel-page::-webkit-scrollbar{width:3px;}.panel-page::-webkit-scrollbar-thumb{background:var(--gold-dim);border-radius:2px;}.card{background:var(--black-panel);border:1px solid var(--black-border);border-radius:6px;padding:12px 14px;position:relative;overflow:hidden;transition:border-color .2s;animation:fadeUp .3s ease-out;}.card:hover{border-color:rgba(255,215,0,.18);}.card::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(255,215,0,.25),transparent);opacity:0;transition:opacity .2s;}.card:hover::before{opacity:1;}@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}.card-head{font-family:'Cinzel',serif;font-size:11px;font-weight:700;letter-spacing:3px;color:var(--gold);text-transform:uppercase;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid rgba(255,215,0,.1);display:flex;align-items:center;gap:7px;text-shadow:0 0 8px var(--glow);}.divider{width:100%;display:flex;align-items:center;gap:10px;margin:8px 0;}.divider span{font-size:9px;letter-spacing:3px;text-transform:uppercase;color:var(--white-faint);}.divider::before,.divider::after{content:'';flex:1;height:1px;background:rgba(255,215,0,.08);}.g2{display:grid;grid-template-columns:1fr 1fr;gap:10px;width:100%;}.g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;width:100%;}.w100{width:100%;}.chk{display:flex;align-items:center;gap:8px;cursor:pointer;padding:3px 0;}.chk input[type=checkbox]{display:none;}.chk-box{width:15px;height:15px;border:1px solid var(--black-border);border-radius:3px;background:var(--black-mid);display:flex;align-items:center;justify-content:center;transition:all .15s;flex-shrink:0;position:relative;}.chk-box::after{content:'✓';font-size:9px;color:var(--gold);opacity:0;transition:opacity .15s;font-weight:900;}.chk input:checked+.chk-box{background:rgba(255,215,0,.1);border-color:var(--gold-dim);box-shadow:0 0 8px rgba(255,215,0,.2);}.chk input:checked+.chk-box::after{opacity:1;}.chk:hover .chk-box{border-color:var(--gold-dim);}.chk-lbl{font-size:12px;letter-spacing:.5px;color:var(--white-dim);transition:color .15s;}.chk:hover .chk-lbl,.chk input:checked~.chk-lbl{color:var(--white);}.chk.off .chk-lbl{color:var(--white-faint)!important;opacity:.4;}.chk.off{cursor:not-allowed;}.chk-note{font-size:10px;color:var(--gold-dim);margin-left:2px;}.ifield{background:var(--black-mid);border:1px solid var(--black-border);color:var(--white);font-family:'Rajdhani',sans-serif;font-size:12px;letter-spacing:1px;padding:5px 9px;border-radius:4px;outline:none;transition:border-color .2s,box-shadow .2s;width:100%;}.ifield:focus{border-color:var(--gold-dim);box-shadow:0 0 8px rgba(255,215,0,.12);}.ifield::placeholder{color:var(--white-faint);}.ifield.sm{width:64px;}.ifield.md{width:150px;}.ilbl{font-size:10px;letter-spacing:1.5px;color:var(--white-faint);text-transform:uppercase;margin-bottom:4px;}.igroup{display:flex;flex-direction:column;gap:3px;margin-bottom:8px;}.igroup:last-child{margin-bottom:0;}.irow{display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap;}.irow:last-child{margin-bottom:0;}.btn{font-family:'Rajdhani',sans-serif;font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;padding:6px 14px;border:1px solid var(--gold-dim);background:transparent;color:var(--gold);cursor:pointer;border-radius:4px;transition:all .2s;position:relative;overflow:hidden;white-space:nowrap;}.btn::before{content:'';position:absolute;inset:0;background:linear-gradient(135deg,var(--gold),var(--gold-dim));opacity:0;transition:opacity .2s;}.btn:hover{color:var(--black);border-color:var(--gold);}.btn:hover::before{opacity:1;}.btn span{position:relative;z-index:1;}.btn.sm{padding:4px 10px;font-size:9px;}.badge{display:inline-block;background:rgba(255,215,0,.08);border:1px solid rgba(255,215,0,.25);color:var(--gold);font-size:8px;letter-spacing:2px;padding:1px 5px;border-radius:2px;text-transform:uppercase;}.badge.off{background:rgba(80,80,80,.1);border-color:rgba(80,80,80,.3);color:var(--white-faint);}.abar{display:flex;justify-content:center;align-items:center;gap:8px;padding:8px 16px;background:var(--black-mid);border-top:1px solid rgba(255,215,0,.08);flex-shrink:0;position:relative;}.abar::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(255,215,0,.25),transparent);}.abtn{font-family:'Cinzel',serif;font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;padding:7px 22px;border:1px solid;cursor:pointer;border-radius:4px;transition:all .2s;position:relative;overflow:hidden;min-width:120px;}.abtn::after{content:'';position:absolute;top:0;left:-100%;width:60px;height:100%;background:linear-gradient(90deg,transparent,rgba(255,255,255,.08),transparent);transform:skewX(-20deg);}.abtn:hover::after{left:150%;transition:left .5s ease;}.abtn-start{border-color:var(--gold-dim);background:rgba(255,215,0,.04);color:var(--gold);}.abtn-start:hover,.abtn-start.on{background:rgba(255,215,0,.12);box-shadow:0 0 18px rgba(255,215,0,.2);border-color:var(--gold);}.abtn-stop{border-color:rgba(255,68,68,.35);background:rgba(255,68,68,.04);color:#ff7777;}.abtn-stop:hover{background:rgba(255,68,68,.12);box-shadow:0 0 18px rgba(255,68,68,.15);border-color:var(--red);}.abtn-restart{border-color:rgba(100,180,255,.3);background:rgba(100,180,255,.04);color:var(--blue);}.abtn-restart:hover{background:rgba(100,180,255,.12);box-shadow:0 0 18px rgba(100,180,255,.12);}.kh{font-size:9px;opacity:.45;margin-left:3px;}.tabbar{display:flex;background:var(--black-mid);border-top:1px solid rgba(255,215,0,.1);padding:7px 8px;gap:5px;flex-shrink:0;position:relative;z-index:9;justify-content:center;}.tabbar::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(255,215,0,.3),transparent);}.tbtn{font-family:'Rajdhani',sans-serif;font-size:8px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--white-faint);background:rgba(255,255,255,.02);border:1px solid var(--black-border);padding:6px 10px 7px;cursor:pointer;border-radius:50px;display:flex;flex-direction:column;align-items:center;gap:2px;min-width:56px;transition:all .2s cubic-bezier(.34,1.56,.64,1);position:relative;}.tbtn .te{font-size:17px;line-height:1;transition:transform .2s cubic-bezier(.34,1.56,.64,1),filter .2s;filter:grayscale(.6) brightness(.65);}.tbtn:hover{color:var(--white-dim);border-color:rgba(255,215,0,.2);background:rgba(255,215,0,.05);transform:translateY(-2px);}.tbtn:hover .te{transform:scale(1.15);filter:grayscale(0) brightness(1);}.tbtn.active{color:var(--gold);border-color:var(--gold-dim);background:rgba(255,215,0,.09);box-shadow:0 0 14px rgba(255,215,0,.18),inset 0 0 10px rgba(255,215,0,.04);text-shadow:0 0 8px var(--glow);transform:translateY(-3px);}.tbtn.active .te{filter:grayscale(0) brightness(1.1) drop-shadow(0 0 4px rgba(255,215,0,.55));transform:scale(1.1);}.tbtn.active::before{content:'';position:absolute;bottom:0;left:22%;right:22%;height:2px;background:var(--gold);border-radius:2px 2px 0 0;box-shadow:0 0 6px var(--gold);}.toast{position:fixed;top:52px;left:50%;transform:translateX(-50%) translateY(-14px);background:var(--black-panel);border:1px solid var(--gold-dim);color:var(--gold);font-family:'Rajdhani',sans-serif;font-size:12px;letter-spacing:2px;padding:7px 20px;border-radius:50px;opacity:0;transition:all .3s cubic-bezier(.34,1.56,.64,1);pointer-events:none;z-index:2000;white-space:nowrap;box-shadow:0 4px 24px var(--glow);}.toast.on{opacity:1;transform:translateX(-50%) translateY(0);}.modal-wrap{display:none;position:fixed;inset:0;z-index:1500;align-items:center;justify-content:center;}.modal-wrap.on{display:flex;}.modal-bg{position:absolute;inset:0;background:rgba(0,0,0,.75);backdrop-filter:blur(3px);}.modal{position:relative;background:var(--black-panel);border:1px solid rgba(255,215,0,.2);border-radius:8px;padding:20px;min-width:320px;max-width:580px;max-height:82vh;overflow-y:auto;box-shadow:0 0 60px rgba(0,0,0,.8),0 0 30px rgba(255,215,0,.08);animation:mIn .25s cubic-bezier(.16,1,.3,1);}@keyframes mIn{from{opacity:0;transform:scale(.93) translateY(10px)}to{opacity:1;transform:none}}.modal::-webkit-scrollbar{width:3px;}.modal::-webkit-scrollbar-thumb{background:var(--gold-dim);border-radius:2px;}.modal-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;padding-bottom:10px;border-bottom:1px solid rgba(255,215,0,.1);}.modal-title{font-family:'Cinzel',serif;font-size:13px;letter-spacing:3px;color:var(--gold);text-shadow:0 0 8px var(--glow);}.modal-close{background:none;border:none;color:var(--white-faint);font-size:18px;cursor:pointer;padding:0 4px;line-height:1;transition:color .2s;}.modal-close:hover{color:var(--red);}.modal-footer{display:flex;justify-content:flex-end;gap:8px;margin-top:16px;padding-top:10px;border-top:1px solid rgba(255,215,0,.08);}.cr{display:grid;gap:5px;align-items:center;margin-bottom:6px;}.cr.xy{grid-template-columns:1fr 56px 56px auto;}.cr.xywh{grid-template-columns:1fr 48px 48px 48px 48px auto;}.cr-lbl{font-size:11px;color:var(--white-dim);letter-spacing:.3px;}.mini-tabs{display:flex;gap:4px;margin-bottom:12px;border-bottom:1px solid rgba(255,215,0,.08);padding-bottom:8px;flex-wrap:wrap;}.mt-btn{font-family:'Rajdhani',sans-serif;font-size:9px;letter-spacing:2px;text-transform:uppercase;background:none;border:1px solid transparent;color:var(--white-faint);padding:4px 11px;border-radius:4px;cursor:pointer;transition:all .15s;}.mt-btn.active{color:var(--gold);border-color:var(--gold-dim);background:rgba(255,215,0,.08);}.mt-page{display:none;}.mt-page.active{display:block;}.item-row{display:grid;grid-template-columns:1fr 64px;align-items:center;gap:6px;margin-bottom:6px;}.item-row .chk{flex:1;}.biome-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;}.pot-row{display:grid;grid-template-columns:26px 1fr auto;gap:8px;align-items:center;margin-bottom:8px;}.pot-num{font-family:'Cinzel',serif;font-size:10px;color:var(--gold-dim);letter-spacing:1px;}.credits-wrap{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:16px;padding:14px;}.cr-logo{font-family:'Cinzel Decorative',serif;font-size:26px;font-weight:900;color:transparent;background:linear-gradient(180deg,var(--gold-light),var(--gold));-webkit-background-clip:text;background-clip:text;filter:drop-shadow(0 0 18px rgba(255,215,0,.5));letter-spacing:5px;}.cr-role{font-family:'Cinzel',serif;font-size:9px;letter-spacing:4px;color:var(--gold-dim);text-transform:uppercase;margin-bottom:3px;}.cr-name{font-size:13px;color:var(--white-dim);letter-spacing:.5px;}.cr-note{font-size:11px;color:var(--white-faint);line-height:1.9;text-align:center;max-width:360px;}.cr-link{font-family:'Cinzel',serif;font-size:11px;letter-spacing:3px;color:var(--gold);text-decoration:none;border-bottom:1px solid var(--gold-dim);padding-bottom:2px;cursor:pointer;transition:all .2s;}.cr-link:hover{color:var(--gold-light);text-shadow:0 0 10px var(--glow);}.orn{display:flex;align-items:center;gap:10px;color:var(--gold-dim);font-size:11px;}.orn::before,.orn::after{content:'';width:50px;height:1px;}.orn::before{background:linear-gradient(90deg,transparent,var(--gold-dim));}.orn::after{background:linear-gradient(90deg,var(--gold-dim),transparent);}
</style>
</head>
<body>

<!-- ═══ LOADING SCREEN ═══ -->
<div id="ls">
  <div class="ls-bg"></div>
  <div class="ls-stars" id="ls-stars"></div>
  <div class="ls-ptcl" id="ls-ptcl"></div>
  <div class="ls-orb"></div>
  <div class="ls-rings">
    <div class="ring"></div><div class="ring"></div><div class="ring"></div>
    <div class="ring-c"></div>
  </div>
  <div class="ls-title">ELIXIR</div>
  <div class="ls-sub">A <em>Sol's RNG</em> Macro</div>
  <div class="ls-bar-wrap">
    <div class="ls-bar-lbl">Initializing Systems</div>
    <div class="ls-bar-track"><div class="ls-bar-fill" id="ls-bar"></div></div>
    <div class="ls-pct" id="ls-pct">0%</div>
    <div class="ls-tip" id="ls-tip">Loading configuration...</div>
  </div>
</div>

<!-- ═══ MAIN APP ═══ -->
<div id="app">
  <div class="app-bg"></div><div class="app-grid"></div>

  <!-- Titlebar -->
  <div class="tbar">
    <div class="tbar-logo">
      <div class="tbar-icon">E</div>
      <div class="tbar-name">ELIXIR <span class="tbar-ver">v1.1.2</span></div>
    </div>
    <div class="tbar-status">
      <div class="sdot idle" id="sdot"></div>
      <span id="stext">IDLE</span>
    </div>
  </div>

  <!-- Content -->
  <div class="content">

    <!-- MAIN -->
    <div class="panel-page active" id="tab-main">
      <div class="g2">
        <div class="card">
          <div class="card-head">✦ Miscellaneous</div>
          <label class="chk"><input type="checkbox" id="obby__enabled"><span class="chk-box"></span><span class="chk-lbl">Do Obby <span class="chk-note">(30% Luck / Loop)</span></span></label>
          <label class="chk"><input type="checkbox" id="chalice__enabled"><span class="chk-box"></span><span class="chk-lbl">Auto Chalice <span class="chk-note">(30% Luck)</span></span></label>
          <button class="btn sm" onclick="openModal('modal-pathing1')"><span>Record Pathing</span></button>
        </div>
        <div class="card">
          <div class="card-head">⚙ Auto Equip</div>
          <label class="chk"><input type="checkbox" id="auto_equip__enabled"><span class="chk-box"></span><span class="chk-lbl">Enable Auto Equip</span></label>
          <div style="margin-top:10px;"><button class="btn sm" onclick="openModal('modal-autoequip')"><span>Configure Search</span></button></div>
        </div>
      </div>
      <div class="card w100">
        <div class="card-head">◈ Item Collection &amp; Pathing</div>
        <div class="irow">
          <label class="chk"><input type="checkbox" id="item_collecting__enabled"><span class="chk-box"></span><span class="chk-lbl">Enable Item Collection</span></label>
          <button class="btn sm" onclick="openModal('modal-clicks')"><span>Assign Clicks</span></button>
          <button class="btn sm" onclick="openModal('modal-paths')"><span>Paths</span></button>
        </div>
      </div>
    </div>

    <!-- DISCORD -->
    <div class="panel-page" id="tab-discord">
      <div class="card w100">
        <div class="card-head">🔗 Webhook</div>
        <div class="irow" style="margin-bottom:12px;">
          <label class="chk"><input type="checkbox" id="discord__webhook__enabled"><span class="chk-box"></span><span class="chk-lbl">Enable Webhook</span></label>
          <button class="btn sm" onclick="testWebhook()"><span>Test Webhook</span></button>
        </div>
        <div class="divider"><span>Connection</span></div>
        <div class="igroup"><div class="ilbl">Webhook URL</div><input class="ifield" id="discord__webhook__url" placeholder="https://discord.com/api/webhooks/..."></div>
        <div class="g2" style="margin-top:4px;">
          <div class="igroup"><div class="ilbl">User / Role ID to Ping</div><input class="ifield" id="discord__webhook__ping_id" placeholder="ID or &amp;roleid"></div>
          <div class="igroup"><div class="ilbl">Private Server Link</div><input class="ifield" id="discord__webhook__ps_link" placeholder="roblox.com/games/..."></div>
        </div>
        <div class="divider" style="margin-top:4px;"><span>Screenshots</span></div>
        <div class="irow">
          <label class="chk"><input type="checkbox" id="invo_ss__enabled"><span class="chk-box"></span><span class="chk-lbl">Inventory Screenshots</span></label>
          <span style="font-size:10px;color:var(--white-faint);letter-spacing:1px;">Duration (min):</span>
          <input class="ifield sm" id="invo_ss__duration" placeholder="60">
        </div>
      </div>
    </div>

    <!-- CRAFTING -->
    <div class="panel-page" id="tab-crafting">
      <div class="card w100">
        <div class="card-head">⚗ Potion Crafting</div>
        <div class="irow" style="margin-bottom:12px;">
          <label class="chk"><input type="checkbox" id="potion_crafting__enabled"><span class="chk-box"></span><span class="chk-lbl">Enable Potion Crafting</span></label>
          <label class="chk"><input type="checkbox" id="potion_crafting__temporary_auto_add"><span class="chk-box"></span><span class="chk-lbl">Auto Add Switcher</span></label>
          <label class="chk"><input type="checkbox" id="potion_crafting__potion_crafting"><span class="chk-box"></span><span class="chk-lbl">Potion Crafting Mode</span></label>
          <button class="btn sm" onclick="openModal('modal-crafting-clicks')"><span>Assign Crafting</span></button>
        </div>
        <div class="divider"><span>Potions</span></div>
        <div style="margin:10px 0;">
          <div class="pot-row"><span class="pot-num">01</span><input class="ifield md" id="potion_crafting__item_1" placeholder="e.g. Fortune"><label class="chk"><input type="checkbox" id="potion_crafting__craft_potion_1"><span class="chk-box"></span><span class="chk-lbl">Craft Potion 1</span></label></div>
          <div class="pot-row"><span class="pot-num">02</span><input class="ifield md" id="potion_crafting__item_2" placeholder="e.g. Lucky Potion"><label class="chk"><input type="checkbox" id="potion_crafting__craft_potion_2"><span class="chk-box"></span><span class="chk-lbl">Craft Potion 2</span></label></div>
          <div class="pot-row"><span class="pot-num">03</span><input class="ifield md" id="potion_crafting__item_3" placeholder="e.g. Heavenly"><label class="chk"><input type="checkbox" id="potion_crafting__craft_potion_3"><span class="chk-box"></span><span class="chk-lbl">Craft Potion 3</span></label></div>
        </div>
        <div class="divider"><span>Timing</span></div>
        <div class="g2" style="margin-top:8px;">
          <div class="igroup"><div class="ilbl">Auto Add Potion Name</div><input class="ifield sm" id="potion_crafting__current_temporary_auto_add" placeholder="e.g. Heavenly Potion"></div>
          <div class="igroup"><div class="ilbl">Crafting Interval (min)</div><input class="ifield sm" id="potion_crafting__crafting_interval" placeholder="30"></div>
        </div>
      </div>
    </div>

    <!-- SETTINGS -->
    <div class="panel-page" id="tab-settings">
      <div class="card w100">
        <div class="card-head">◆ General</div>
        <div class="g2">
          <div>
            <label class="chk" style="margin-bottom:9px;"><input type="checkbox" id="settings__vip_mode"><span class="chk-box"></span><span class="chk-lbl">VIP Game Pass</span></label>
            <label class="chk" style="margin-bottom:9px;"><input type="checkbox" id="settings__vip+_mode"><span class="chk-box"></span><span class="chk-lbl">VIP+ Mode</span></label>
            <label class="chk"><input type="checkbox" id="settings__azerty_mode"><span class="chk-box"></span><span class="chk-lbl">Azerty Keyboard Layout</span></label>
          </div>
          <div>
            <label class="chk" style="margin-bottom:9px;"><input type="checkbox" id="settings__reset"><span class="chk-box"></span><span class="chk-lbl">Reset and Align</span></label>
            <label class="chk"><input type="checkbox" id="claim_daily_quests"><span class="chk-box"></span><span class="chk-lbl">Claim Quests <span class="chk-note">(30 min)</span></span></label>
          </div>
        </div>
      </div>
    </div>

    <!-- MERCHANT -->
    <div class="panel-page" id="tab-merchant">
      <div class="card w100">
        <div class="card-head">⚜ Mari</div>
        <div class="irow">
          <label class="chk"><input type="checkbox" id="mari__ping__enabled"><span class="chk-box"></span><span class="chk-lbl">Ping if Mari?</span></label>
          <span style="font-size:10px;color:var(--white-faint);">Ping ID:</span>
          <input class="ifield sm" id="mari__ping__id" placeholder="ID or &amp;roleid">
          <button class="btn sm" onclick="openModal('modal-mari')"><span>Mari Settings</span></button>
        </div>
      </div>
      <div class="card w100">
        <div class="card-head">🃏 Jester</div>
        <div class="irow">
          <label class="chk"><input type="checkbox" id="jester__ping__enabled"><span class="chk-box"></span><span class="chk-lbl">Ping if Jester?</span></label>
          <span style="font-size:10px;color:var(--white-faint);">Ping ID:</span>
          <input class="ifield sm" id="jester__ping__id" placeholder="ID or &amp;roleid">
          <button class="btn sm" onclick="openModal('modal-jester')"><span>Jester Settings</span></button>
        </div>
      </div>
      <div class="card w100">
        <div class="card-head">🧭 Merchant Teleporter</div>
        <div class="irow">
          <label class="chk"><input type="checkbox" id="settings__merchant__enabled"><span class="chk-box"></span><span class="chk-lbl">Enable Merchant Teleporter</span></label>
          <span style="font-size:10px;color:var(--white-faint);">Duration (min):</span>
          <input class="ifield sm" id="settings__merchant__duration" placeholder="60">
          <button class="btn sm" onclick="openModal('modal-merchant-cal')"><span>Merchant Calibration</span></button>
        </div>
      </div>
    </div>

    <!--FISHING-->
    <div class="panel-page" id="tab-fishing">
      <div class="card w100">
        <div class="card-head">🎣 Fishing</div>
        <div class="irow">
          <label class="chk"><input type="checkbox" id="fishing__enabled"><span class="chk-box"></span><span class="chk-lbl">Enable Fishing</span></label>
          <label class="chk"><input type="checkbox" id="fishing__live_preview"><span class="chk-box"></span><span class="chk-lbl">Live Preview</span></label>
          <label class="btn sm" style="margin-top:10px;" onclick="openModal('modal-fishing')"><span>Fishing Calibrations</span></label>
        </div>
        <div class="igroup"><div class="ilbl">Capture FPS</div><input class="ifield sm" id="fishing__capture_fps" placeholder="60"></div>
        <div class="igroup"><div class="ilbl">Color Tolerance</div><input class="ifield sm" id="fishing__color_tolerance" placeholder="1"></div>
      </div>
      <div class="card w100">
        <div class="card-head">Fish AutoBuy</div>
        <div class="irow">
          <label class="chk"><input type="checkbox" id="fishing__auto_buy"><span class="chk-box"></span><span class="chk-lbl">Enable Auto Buy</span></label>
          <button class="btn sm" onclick="openModal('fishing-autobuy-cal')"><span>Auto Buy Calibration</span></button>
        </div>
        <div class="divider"><span>Auto Buy </span></div>
        <div style="margin:10px 0;">
          <div class="pot-row"><span class="pot-num">01</span><input class="ifield md" id="" placeholder="e.g. Fortune"><label class="chk"><input type="checkbox" id="potion_crafting__craft_potion_1"><span class="chk-box"></span><span class="chk-lbl">Craft Potion 1</span></label></div>
        </div>
      </div>

    </div>
    <!-- EXTRAS -->
    <div class="panel-page" id="tab-extras">
      <div class="g2">
        <div class="card">
          <div class="card-head">🗓 Item Scheduler</div>
          <label class="chk" style="margin-bottom:10px;"><input type="checkbox" id="item_scheduler_item__enabled"><span class="chk-box"></span><span class="chk-lbl">Enable Item Scheduler</span></label>
          <div class="igroup"><div class="ilbl">Item Name</div><input class="ifield" id="item_scheduler_item__name" placeholder="e.g. Fortune I"></div>
          <div class="g2">
            <div class="igroup"><div class="ilbl">Quantity</div><input class="ifield sm" id="item_scheduler_item__quantity" placeholder="1"></div>
            <div class="igroup"><div class="ilbl">Interval (min)</div><input class="ifield sm" id="item_scheduler_item__interval" placeholder="30"></div>
          </div>
        </div>
        <div class="card">
          <div class="card-head">🌍 Detection</div>
          <label class="chk" style="margin-bottom:9px;"><input type="checkbox" id="biome_detection__enabled"><span class="chk-box"></span><span class="chk-lbl">Enable Biome Detection</span></label>
          <label class="chk" style="margin-bottom:9px;"><input type="checkbox" id="enabled_dectection"><span class="chk-box"></span><span class="chk-lbl">Enable Aura Detection</span></label>
          <div class="g2" style="margin-bottom:8px;">
            <div class="igroup"><div class="ilbl">Ping Min</div><input class="ifield sm" id="send_min" placeholder="100"></div>
            <div class="igroup"><div class="ilbl">Ping Max</div><input class="ifield sm" id="send_max" placeholder="999"></div>
          </div>
          <button class="btn sm" onclick="openModal('modal-biomes')"><span>Configure Biomes</span></button>
        </div>
      </div>
    </div>

    <!-- CREDITS -->
    <div class="panel-page" id="tab-credits">
      <div class="credits-wrap w100" style="height:100%;">
        <div class="cr-logo">ELIXIR</div>
        <div class="orn">⬡</div>
        <div style="text-align:center;"><div class="cr-role">Owners</div><div class="cr-name">Golden <span style="color:var(--white-faint);font-size:11px;">(spacedev0572)</span></div></div>
        <div style="text-align:center;"><div class="cr-role">Developers</div><div class="cr-name">Golden <span style="color:var(--white-faint);font-size:11px;">(spacedev0572)</span></div><div class="cr-name" style="margin-top:3px;">Chaseee <span style="color:var(--white-faint);font-size:11px;">(chaseeee111)</span></div></div>
        <div style="text-align:center;"><div class="cr-role">In Contribution</div><div class="cr-note">Inspired by <span style="color:var(--white-dim);">Dolphsol Macro</span>, the first Sol's RNG Macro.<br><span style="color:var(--white-dim);">Radiance Macro</span> — config.py &amp; pathing system (LPS)<br><span style="color:var(--white-dim);">OysterDetecter</span> by vexthecoder — log reading detection</div></div>
        <div class="orn">⬡</div>
        <a class="cr-link" onclick="window.open('https://discord.gg/JsMM299RF7','_blank')">Join the Server ↗</a>
      </div>
    </div>

  </div><!-- /content -->

  <!-- Action Bar -->
  <div class="abar">
    <button class="abtn abtn-start" id="btn-start" onclick="startMacro()">START <span class="kh">F1</span></button>
    <button class="abtn abtn-stop" onclick="stopMacro()">STOP <span class="kh">F2</span></button>
    <button class="abtn abtn-restart" onclick="restartMacro()">RESTART <span class="kh">F3</span></button>
  </div>

  <!-- Tab Bar (bottom) -->
  <div class="tabbar">
    <button class="tbtn active" data-tab="main"><span class="te">🏠</span>Main</button>
    <button class="tbtn" data-tab="discord"><span class="te">💬</span>Discord</button>
    <button class="tbtn" data-tab="crafting"><span class="te">⚗️</span>Crafting</button>
    <button class="tbtn" data-tab="settings"><span class="te">⚙️</span>Settings</button>
    <button class="tbtn" data-tab="merchant"><span class="te">🛒</span>Merchant</button>
    <button class="tbtn" data-tab="fishing"><span class="te">🎣</span>Fishing</button>
    <button class="tbtn" data-tab="extras"><span class="te">✨</span>Extras</button>
    <button class="tbtn" data-tab="credits"><span class="te">👑</span>Credits</button>
  </div>
</div>

<!-- Toast -->
<div class="toast" id="toast"></div>

<!-- ═══ MODALS ═══ -->

<!-- Record Pathing -->
<div class="modal-wrap" id="modal-pathing1">
  <div class="modal-bg" onclick="closeModal('modal-pathing1')"></div>
  <div class="modal">
    <div class="modal-head"><span class="modal-title"> Record Pathing</span><button class="modal-close" onclick="closeModal('modal-pathing1')">✕</button></div>
    <p style="font-size:11px;color:var(--white-faint);margin-bottom:12px;line-height:1.7;"">Record your pathing for Obby and Chailce - Remember, they will not be perfect</p>
    <div class="igroup"><div class="ilbl">Obby Pathing</div></div>
    <button class="btn" onclick="startPathing('obby')"><span>Record Pathing for - Obby</span></button>
    <button class="btn" onclick="startPathing('chalice')"><span>Record Pathing for - Chalice</span></button>
    <div class="moda-footer"><button class="btn" onclick="saveAndClose('modal-pathing1')"><span>Close &amp; Save</span></button></div>
  </div>
</div>

<!-- Auto Equip -->
<div class="modal-wrap" id="modal-autoequip">
  <div class="modal-bg" onclick="closeModal('modal-autoequip')"></div>
  <div class="modal">
    <div class="modal-head"><span class="modal-title">⚙ Auto Equip</span><button class="modal-close" onclick="closeModal('modal-autoequip')">✕</button></div>
    <p style="font-size:11px;color:var(--white-faint);margin-bottom:12px;line-height:1.7;">Enter the aura name for search. The first result will be equipped — be specific.</p>
    <div class="igroup"><div class="ilbl">Aura Name</div><input class="ifield" id="auto_equip__aura" placeholder="e.g. Crystalized"></div>
    <label class="chk" style="margin-top:8px;"><input type="checkbox" id="auto_equip__special_aura"><span class="chk-box"></span><span class="chk-lbl">Search in Special Auras</span></label>
    <div class="modal-footer"><button class="btn" onclick="saveAndClose('modal-autoequip')"><span>Save &amp; Close</span></button></div>
  </div>
</div>

<!-- Paths -->
<div class="modal-wrap" id="modal-paths">
  <div class="modal-bg" onclick="closeModal('modal-paths')"></div>
  <div class="modal" style="max-width:280px;">
    <div class="modal-head"><span class="modal-title">◈ Paths</span><button class="modal-close" onclick="closeModal('modal-paths')">✕</button></div>
    <p style="font-size:10px;color:var(--white-faint);margin-bottom:12px;letter-spacing:1px;">Toggle which collection spots to visit.</p>
    <div id="paths-list"></div>
    <div class="modal-footer"><button class="btn" onclick="saveAndClose('modal-paths')"><span>Save &amp; Close</span></button></div>
  </div>
</div>

<!-- Assign Clicks (UPDATED) -->
<div class="modal-wrap" id="modal-clicks">
  <div class="modal-bg" onclick="closeModal('modal-clicks')"></div>
  <div class="modal" style="max-width:650px;">
    <div class="modal-head"><span class="modal-title">◈ Assign Clicks</span><button class="modal-close" onclick="closeModal('modal-clicks')">✕</button></div>
    <div class="mini-tabs" id="clicks-tabs">
      <button class="mt-btn active" data-page="aura">Auras Storage</button>
      <button class="mt-btn" data-page="collection">Collection Menu</button>
      <button class="mt-btn" data-page="items">Items Menu</button>
      <button class="mt-btn" data-page="quest">Quest Menu</button>
    </div>
    <div id="clicks-aura" class="mt-page active" style="padding:10px 0;"></div>
    <div id="clicks-collection" class="mt-page" style="padding:10px 0;"></div>
    <div id="clicks-items" class="mt-page" style="padding:10px 0;"></div>
    <div id="clicks-quest" class="mt-page" style="padding:10px 0;"></div>
    <div class="modal-footer"><button class="btn" onclick="saveClicksModal()"><span>Save Calibration</span></button></div>
  </div>
</div>

<!-- Crafting Clicks (UPDATED) -->
<div class="modal-wrap" id="modal-crafting-clicks">
  <div class="modal-bg" onclick="closeModal('modal-crafting-clicks')"></div>
  <div class="modal" style="max-width:600px;">
    <div class="modal-head"><span class="modal-title">⚗ Assign Crafting</span><button class="modal-close" onclick="closeModal('modal-crafting-clicks')">✕</button></div>
    <div id="crafting-clicks-body" style="padding:10px 0;"></div>
    <div class="modal-footer"><button class="btn" onclick="saveCraftingClicksModal()"><span>Save Calibration</span></button></div>
  </div>
</div>

<!-- Mari Settings -->
<div class="modal-wrap" id="modal-mari">
  <div class="modal-bg" onclick="closeModal('modal-mari')"></div>
  <div class="modal" style="max-width:380px;">
    <div class="modal-head"><span class="modal-title">⚜ Mari Settings</span><button class="modal-close" onclick="closeModal('modal-mari')">✕</button></div>
    <p style="font-size:10px;color:var(--white-faint);margin-bottom:10px;letter-spacing:1px;">Toggle items to buy and set quantity.</p>
    <div id="mari-items-list"></div>
    <div class="modal-footer"><button class="btn" onclick="saveAndClose('modal-mari')"><span>Save &amp; Close</span></button></div>
  </div>
</div>

<!-- Jester Settings -->
<div class="modal-wrap" id="modal-jester">
  <div class="modal-bg" onclick="closeModal('modal-jester')"></div>
  <div class="modal" style="max-width:380px;">
    <div class="modal-head"><span class="modal-title">🃏 Jester Settings</span><button class="modal-close" onclick="closeModal('modal-jester')">✕</button></div>
    <p style="font-size:10px;color:var(--white-faint);margin-bottom:10px;letter-spacing:1px;">Toggle items to buy and set quantity.</p>
    <div id="jester-items-list"></div>
    <div class="modal-footer"><button class="btn" onclick="saveAndClose('modal-jester')"><span>Save &amp; Close</span></button></div>
  </div>
</div>

<!-- Merchant Calibration (UPDATED) -->
<div class="modal-wrap" id="modal-merchant-cal">
  <div class="modal-bg" onclick="closeModal('modal-merchant-cal')"></div>
  <div class="modal" style="max-width:700px;">
    <div class="modal-head"><span class="modal-title">🧭 Merchant Calibration</span><button class="modal-close" onclick="closeModal('modal-merchant-cal')">✕</button></div>
    <p style="font-size:10px;color:var(--white-faint);margin-bottom:12px;letter-spacing:1px;">OCR fields require X, Y, W, H. Standard fields require X, Y.</p>
    <div id="merchant-cal-body" style="padding:10px 0;"></div>
    <div class="modal-footer"><button class="btn" onclick="saveMerchantCalModal()"><span>Save Calibration</span></button></div>
  </div>
</div>

<!-- Biome Selector -->
<div class="modal-wrap" id="modal-biomes">
  <div class="modal-bg" onclick="closeModal('modal-biomes')"></div>
  <div class="modal" style="max-width:360px;">
    <div class="modal-head"><span class="modal-title">🌍 Configure Biomes</span><button class="modal-close" onclick="closeModal('modal-biomes')">✕</button></div>
    <p style="font-size:10px;color:var(--white-faint);margin-bottom:12px;letter-spacing:1px;">Select biomes that trigger a webhook alert.</p>
    <div class="biome-grid" id="biome-list"></div>
    <div class="modal-footer"><button class="btn" onclick="saveAndClose('modal-biomes')"><span>Save &amp; Close</span></button></div>
  </div>
</div>
<!-- Fishing Modal-->
<div class="modal-wrap" id="modal-fishing">
  <div class="modal-bg" onclick="closeModal('modal-fishing')"></div>
  <div class="modal" style="max-width:360px;">
    <div class="modal-head"><span class="modal-title">🎣 Fishing Calibration</span><button class="modal-close" onclick="closeModal('modal-fishing')">✕</button></div>
  </div>
</div>

<script>
// LOADING SCREEN
const TIPS=['Loading configuration...','Initializing pathing system...','Connecting webhook services...','Calibrating item detection...','Syncing biome sensors...','Preparing auto-equip module...','Almost ready...'];

function mkStars(){
  const c=document.getElementById('ls-stars');
  for(let i=0;i<120;i++){
    const s=document.createElement('div'); s.className='star';
    const sz=Math.random()*2.5+.5;
    s.style.cssText=`width:${sz}px;height:${sz}px;left:${Math.random()*100}%;top:${Math.random()*100}%;--d:${Math.random()*4+2}s;--op:${Math.random()*.6+.2};--dl:${Math.random()*4}s;`;
    c.appendChild(s);
  }
}
function mkParticles(){
  const c=document.getElementById('ls-ptcl');
  for(let i=0;i<20;i++){
    const p=document.createElement('div'); p.className='ptcl';
    p.style.cssText=`left:${30+Math.random()*40}%;bottom:${20+Math.random()*20}%;--d:${Math.random()*3+2}s;--dl:${Math.random()*4}s;`;
    c.appendChild(p);
  }
}

function runLoader(){
  mkStars(); mkParticles();
  const bar=document.getElementById('ls-bar'), pct=document.getElementById('ls-pct'), tip=document.getElementById('ls-tip');
  let prog=0, tipI=0;
  const iv=setInterval(()=>{
    prog=Math.min(100,prog+Math.random()*8+4);
    bar.style.width=prog+'%'; pct.textContent=Math.round(prog)+'%';
    const ni=Math.floor((prog/100)*TIPS.length);
    if(ni!==tipI&&ni<TIPS.length){ tipI=ni; tip.style.opacity=0; setTimeout(()=>{ tip.textContent=TIPS[tipI]; tip.style.opacity=1; },200); }
    if(prog>=100){ clearInterval(iv); setTimeout(launch,600); }
  },120);
}

function launch(){
  const ls=document.getElementById('ls'), app=document.getElementById('app');
  ls.style.transition='opacity .8s ease, transform .8s ease';
  ls.style.opacity=0; ls.style.transform='scale(1.05)';
  setTimeout(()=>{
    ls.style.display='none'; app.style.display='flex'; app.classList.add('app-in');
    loadConfig();
  },800);
}

// UI FUNCTIONS
window.showToast = function(message, duration = 3000) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('on');
    setTimeout(() => toast.classList.remove('on'), duration);
};

window.setStatus = function(state, text) {
    const dot = document.getElementById('sdot');
    const stext = document.getElementById('stext');
    dot.className = 'sdot ' + state;
    stext.textContent = text;
};

function setConfigValues(config, prefix = '') {
    for (const [key, value] of Object.entries(config)) {
        const id = prefix ? prefix + '__' + key : key;
        const element = document.getElementById(id);
        if (element) {
            if (element.type === 'checkbox') {
                element.checked = value === '1' || value === true;
            } else {
                element.value = value;
            }
        } else if (typeof value === 'object' && value !== null) {
            setConfigValues(value, id);
        }
    }
}

function gatherConfig() {
    const config = {};
    const inputs = document.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
        // Skip inputs inside modals
        if (input.closest('.modal-wrap')) return;
        if (input.id && input.id !== 'toast') {
            const parts = input.id.split('__');
            let obj = config;
            for (let i = 0; i < parts.length - 1; i++) {
                const part = parts[i];
                if (!obj[part]) obj[part] = {};
                obj = obj[part];
            }
            const last = parts[parts.length - 1];
            if (input.type === 'checkbox') {
                obj[last] = input.checked ? '1' : '0';
            } else {
                obj[last] = input.value;
            }
        }
    });
    return config;
}

async function loadConfig() {
    const config = await pywebview.api.get_config();
    setConfigValues(config);
    setStatus('idle', 'IDLE');
}

async function saveConfig() {
    const newConfig = gatherConfig();
    const result = await pywebview.api.save_config(newConfig);
    if (result.status === 'ok') {
        showToast('Settings saved');
    }
}

// Macro control
window.startMacro = async () => {
    const result = await pywebview.api.start_macro();
    if (result.status === 'started') showToast('Macro started');
};
window.stopMacro = async () => {
    const result = await pywebview.api.stop_macro();
    if (result.status === 'stopped') showToast('Macro stopped');
};
window.restartMacro = () => pywebview.api.restart_macro();

window.testWebhook = async () => {
    const result = await pywebview.api.test_webhook();
    showToast(result.message);
};

// Modal handling
window.openModal = async (modalId) => {
    document.getElementById(modalId).classList.add('on');
    if (modalId === 'modal-mari') {
        const settings = await pywebview.api.get_mari_settings();
        populateMariModal(settings);
    } else if (modalId === 'modal-jester') {
        const settings = await pywebview.api.get_jester_settings();
        populateJesterModal(settings);
    } else if (modalId === 'modal-biomes') {
        const alerts = await pywebview.api.get_biome_alerts();
        populateBiomeModal(alerts);
    } else if (modalId === 'modal-paths') {
        const spots = await pywebview.api.get_item_collecting_spots();
        populatePathsModal(spots);
    } else if (modalId === 'modal-clicks') {
        const clicks = await pywebview.api.get_clicks();
        populateClicksModal(clicks);
    } else if (modalId === 'modal-crafting-clicks') {
        const clicks = await pywebview.api.get_clicks();
        populateCraftingClicksModal(clicks);
    } else if (modalId === 'modal-merchant-cal') {
        const clicks = await pywebview.api.get_clicks();
        populateMerchantCalModal(clicks);
    }
};

window.closeModal = (modalId) => {
    document.getElementById(modalId).classList.remove('on');
};

window.saveAndClose = async (modalId) => {
    if (modalId === 'modal-mari') {
        const currentMari = await pywebview.api.get_mari_settings();
        const newSettings = {};
        const container = document.getElementById('mari-items-list');
        const rows = container.querySelectorAll('.item-row');
        rows.forEach((row, index) => {
            const chk = row.querySelector('input[type="checkbox"]');
            const qty = row.querySelector('input[type="text"]');
            if (chk && qty) {
                const itemName = chk.id.replace('mari_', '').replace(/_/g, ' ');
                newSettings[itemName] = chk.checked ? '1' : '0';
                newSettings[(index+1).toString()] = qty.value;
            }
        });
        const merged = { ...currentMari, settings: { ...currentMari.settings, ...newSettings } };
        await pywebview.api.save_mari_settings(merged);
    } else if (modalId === 'modal-jester') {
        const currentJester = await pywebview.api.get_jester_settings();
        const newSettings = {};
        const container = document.getElementById('jester-items-list');
        const rows = container.querySelectorAll('.item-row');
        rows.forEach((row, index) => {
            const chk = row.querySelector('input[type="checkbox"]');
            const qty = row.querySelector('input[type="text"]');
            if (chk && qty) {
                const itemName = chk.id.replace('jester_', '').replace(/_/g, ' ');
                newSettings[itemName] = chk.checked ? '1' : '0';
                newSettings[(index+1).toString()] = qty.value;
            }
        });
        const merged = { ...currentJester, settings: { ...currentJester.settings, ...newSettings } };
        await pywebview.api.save_jester_settings(merged);
    } else if (modalId === 'modal-biomes') {
        const currentAlerts = await pywebview.api.get_biome_alerts();
        const newAlerts = {};
        const container = document.getElementById('biome-list');
        container.querySelectorAll('input[type="checkbox"]').forEach(chk => {
            const biome = chk.id.replace('biome_', '').replace(/_/g, ' ');
            newAlerts[biome] = chk.checked ? '1' : '0';
        });
        const merged = { ...currentAlerts, ...newAlerts };
        await pywebview.api.save_biome_alerts(merged);
    } else if (modalId === 'modal-paths') {
        const currentSpots = await pywebview.api.get_item_collecting_spots();
        const newSpots = {};
        const container = document.getElementById('paths-list');
        container.querySelectorAll('input[type="checkbox"]').forEach(chk => {
            newSpots[chk.id] = chk.checked ? '1' : '0';
        });
        const merged = { ...currentSpots, ...newSpots };
        await pywebview.api.save_item_collecting_spots(merged);
    } else {
        await saveConfig();
    }
    closeModal(modalId);
    showToast('Settings saved');
};

// Helper to create a click field row
function createClickRow(labelText, key, isOcr = false, values = [0,0,0,0]) {
    const row = document.createElement('div');
    row.className = isOcr ? 'cr xywh' : 'cr xy';
    row.style.marginBottom = '10px';
    
    const label = document.createElement('span');
    label.className = 'cr-lbl';
    label.textContent = labelText;
    row.appendChild(label);
    
    const xInput = document.createElement('input');
    xInput.type = 'text';
    xInput.className = 'ifield sm';
    xInput.value = values[0];
    xInput.dataset.key = key;
    xInput.dataset.index = '0';
    row.appendChild(xInput);
    
    const yInput = document.createElement('input');
    yInput.type = 'text';
    yInput.className = 'ifield sm';
    yInput.value = values[1];
    yInput.dataset.key = key;
    yInput.dataset.index = '1';
    row.appendChild(yInput);
    
    if (isOcr) {
        const wInput = document.createElement('input');
        wInput.type = 'text';
        wInput.className = 'ifield sm';
        wInput.value = values[2];
        wInput.dataset.key = key;
        wInput.dataset.index = '2';
        row.appendChild(wInput);
        
        const hInput = document.createElement('input');
        hInput.type = 'text';
        hInput.className = 'ifield sm';
        hInput.value = values[3];
        hInput.dataset.key = key;
        hInput.dataset.index = '3';
        row.appendChild(hInput);
    }
    
    const assignBtn = document.createElement('button');
    assignBtn.className = 'btn sm';
    assignBtn.innerHTML = '<span>Assign Click!</span>';
    assignBtn.onclick = async () => {
        const mode = isOcr ? 'rect' : 'click';
        const result = await pywebview.api.capture_coordinate(mode);
        if (result.status === 'ok') {
            xInput.value = result.x;
            yInput.value = result.y;
            if (isOcr) {
                wInput.value = result.width;
                hInput.value = result.height;
            }
        } else if (result.status === 'cancelled') {
            showToast('Capture cancelled');
        }
    };
    row.appendChild(assignBtn);
    
    return row;
}

// Populate Assign Clicks modal
function populateClicksModal(clicks) {
    // Aura tab
    const auraContainer = document.getElementById('clicks-aura');
    auraContainer.innerHTML = '';
    const auraFields = [
        { label: 'Aura Storage:', key: 'aura_storage' },
        { label: 'Regular Aura Tab:', key: 'regular_tab' },
        { label: 'Special Aura Tab:', key: 'special_tab' },
        { label: 'Aura Search Bar:', key: 'search_bar' },
        { label: 'First Aura Slot:', key: 'aura_first_slot' },
        { label: 'Equip Button:', key: 'equip_button' }
    ];
    auraFields.forEach(field => {
        const values = clicks[field.key] || [0,0,0,0];
        auraContainer.appendChild(createClickRow(field.label, field.key, false, values));
    });
    
    // Collection tab
    const collectionContainer = document.getElementById('clicks-collection');
    collectionContainer.innerHTML = '';
    const collectionFields = [
        { label: 'Collection Menu:', key: 'collection_menu' },
        { label: 'Exit Collection:', key: 'exit_collection' }
    ];
    collectionFields.forEach(field => {
        const values = clicks[field.key] || [0,0,0,0];
        collectionContainer.appendChild(createClickRow(field.label, field.key, false, values));
    });
    
    // Items tab
    const itemsContainer = document.getElementById('clicks-items');
    itemsContainer.innerHTML = '';
    const itemsFields = [
        { label: 'Items Storage:', key: 'items_storage' },
        { label: 'Items Tab:', key: 'items_tab' },
        { label: 'Items Search Bar:', key: 'items_bar' },
        { label: 'Items First Slot:', key: 'item_first_slot' },
        { label: 'Quantity Bar:', key: 'item_value' },
        { label: 'Use Button:', key: 'use_button' }
    ];
    itemsFields.forEach(field => {
        const values = clicks[field.key] || [0,0,0,0];
        itemsContainer.appendChild(createClickRow(field.label, field.key, false, values));
    });
    
    // Quest tab
    const questContainer = document.getElementById('clicks-quest');
    questContainer.innerHTML = '';
    const questFields = [
        { label: 'Quest Menu:', key: 'quest_menu' },
        { label: 'First Slot:', key: 'first_slot' },
        { label: 'Second Slot:', key: 'second_slot' },
        { label: 'Third Slot:', key: 'third_slot' },
        { label: 'Claim Button:', key: 'claim_button' }
    ];
    questFields.forEach(field => {
        const values = clicks[field.key] || [0,0,0,0];
        questContainer.appendChild(createClickRow(field.label, field.key, false, values));
    });
    
    // Tab switching inside modal
    document.querySelectorAll('#clicks-tabs .mt-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#clicks-tabs .mt-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('#modal-clicks .mt-page').forEach(p => p.classList.remove('active'));
            document.getElementById('clicks-' + btn.dataset.page).classList.add('active');
        });
    });
}

// Save Assign Clicks modal (MERGE)
async function saveClicksModal() {
    const currentClicks = await pywebview.api.get_clicks();
    const newClicks = {};
    const rows = document.querySelectorAll('#modal-clicks .cr');
    rows.forEach(row => {
        const inputs = row.querySelectorAll('input');
        if (inputs.length >= 2) {
            const key = inputs[0].dataset.key;
            const values = Array.from(inputs).map(inp => inp.value);
            newClicks[key] = values;
        }
    });
    const merged = { ...currentClicks, ...newClicks };
    const result = await pywebview.api.save_clicks(merged);
    if (result.status === 'ok') {
        showToast('Clicks saved');
        closeModal('modal-clicks');
    }
}

// Populate Crafting Clicks modal
function populateCraftingClicksModal(clicks) {
    const container = document.getElementById('crafting-clicks-body');
    container.innerHTML = '';
    const fields = [
        { label: 'First Potion Slot:', key: 'first_potion_slot' },
        { label: 'Second Potion Slot:', key: 'second_potion_slot' },
        { label: 'Third Potion Slot:', key: 'third_potion_slot' },
        { label: 'Potion Tab Craft:', key: 'potion_tab' },
        { label: 'Item Tab Craft:', key: 'item_tab' },
        { label: 'Open Recipe Book:', key: 'open_recipe' },
        { label: 'Add button 1:', key: 'add_button_1' },
        { label: 'Add button 2:', key: 'add_button_2' },
        { label: 'Add button 3:', key: 'add_button_3' },
        { label: 'Add button 4:', key: 'add_button_4' },
        { label: 'Craft button:', key: 'craft_button' },
        { label: 'Potion Search bar:', key: 'potion_search_bar' },
        { label: 'Auto Add button:', key: 'auto_add_button' }
    ];
    fields.forEach(field => {
        const values = clicks[field.key] || [0,0,0,0];
        container.appendChild(createClickRow(field.label, field.key, false, values));
    });
}

// Save Crafting Clicks modal (MERGE)
async function saveCraftingClicksModal() {
    const currentClicks = await pywebview.api.get_clicks();
    const newClicks = {};
    const rows = document.querySelectorAll('#crafting-clicks-body .cr');
    rows.forEach(row => {
        const inputs = row.querySelectorAll('input');
        if (inputs.length >= 2) {
            const key = inputs[0].dataset.key;
            const values = Array.from(inputs).map(inp => inp.value);
            newClicks[key] = values;
        }
    });
    const merged = { ...currentClicks, ...newClicks };
    const result = await pywebview.api.save_clicks(merged);
    if (result.status === 'ok') {
        showToast('Crafting clicks saved');
        closeModal('modal-crafting-clicks');
    }
}

// Populate Merchant Calibration modal
function populateMerchantCalModal(clicks) {
    const container = document.getElementById('merchant-cal-body');
    container.innerHTML = '';
    const fields = [
        { label: 'Merchant Open Button:', key: 'merchant_open_button', ocr: false },
        { label: 'Merchant Dialogue Box:', key: 'merchant_dialog', ocr: false },
        { label: 'Amount Button Entry:', key: 'merchant_amount_button', ocr: false },
        { label: 'Purchase Button:', key: 'merchant_purchase_button', ocr: false },
        { label: 'First Item Slot:', key: 'merchant_1_slot_button', ocr: false },
        { label: 'Merchant Name OCR:', key: 'merchant_name_ocr', ocr: true },
        { label: 'Item Name OCR:', key: 'merchant_item_name_ocr', ocr: true }
    ];
    fields.forEach(field => {
        const values = clicks[field.key] || [0,0,0,0];
        container.appendChild(createClickRow(field.label, field.key, field.ocr, values));
    });
}

// Save Merchant Calibration modal (MERGE)
async function saveMerchantCalModal() {
    const currentClicks = await pywebview.api.get_clicks();
    const newClicks = {};
    const rows = document.querySelectorAll('#merchant-cal-body .cr');
    rows.forEach(row => {
        const inputs = row.querySelectorAll('input');
        if (inputs.length >= 2) {
            const key = inputs[0].dataset.key;
            const values = Array.from(inputs).map(inp => inp.value);
            newClicks[key] = values;
        }
    });
    const merged = { ...currentClicks, ...newClicks };
    const result = await pywebview.api.save_clicks(merged);
    if (result.status === 'ok') {
        showToast('Merchant calibration saved');
        closeModal('modal-merchant-cal');
    }
}

function populateMariModal(settings) {
    const container = document.getElementById('mari-items-list');
    container.innerHTML = '';
    const items = [
        "Void Coin", "Lucky Penny", "Mixed Potion", "Lucky Potion", "Lucky Potion L",
        "Lucky Potion XL", "Speed Potion", "Speed Potion L", "Speed Potion XL",
        "Gear A", "Gear B"
    ];
    items.forEach((item, idx) => {
        const row = document.createElement('div');
        row.className = 'item-row';
        const chk = document.createElement('label');
        chk.className = 'chk';
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.id = `mari_${item.replace(/\\s+/g, '_')}`;
        input.checked = settings.settings?.[item] === '1';
        const box = document.createElement('span');
        box.className = 'chk-box';
        const lbl = document.createElement('span');
        lbl.className = 'chk-lbl';
        lbl.textContent = item;
        chk.appendChild(input);
        chk.appendChild(box);
        chk.appendChild(lbl);
        const qty = document.createElement('input');
        qty.type = 'text';
        qty.className = 'ifield sm';
        qty.id = `mari_qty_${idx+1}`;
        qty.value = settings.settings?.[(idx+1).toString()] || '';
        row.appendChild(chk);
        row.appendChild(qty);
        container.appendChild(row);
    });
}

function populateBiomeModal(alerts) {
    const container = document.getElementById('biome-list');
    container.innerHTML = '';
    const biomes = ["NORMAL", "WINDY", "RAINY", "SNOWY", "SAND STORM", "HELL", "STARFALL", "HEAVEN", "CORRUPTION", "NULL", "GLITCHED", "DREAMSPACE", "CYBERSPACE", "THE CITADEL OF ORDERS"];
    biomes.forEach(biome => {
        const label = document.createElement('label');
        label.className = 'chk';
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.id = `biome_${biome.replace(/\\s+/g, '_')}`;
        input.checked = alerts[biome] === '1';
        const box = document.createElement('span');
        box.className = 'chk-box';
        const span = document.createElement('span');
        span.className = 'chk-lbl';
        span.textContent = biome;
        label.appendChild(input);
        label.appendChild(box);
        label.appendChild(span);
        container.appendChild(label);
    });
}

function populatePathsModal(spots) {
    const container = document.getElementById('paths-list');
    container.innerHTML = '';
    for (let i = 1; i <= 8; i++) {
        const label = document.createElement('label');
        label.className = 'chk';
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.id = `spot${i}`;
        input.checked = spots[`spot${i}`] === '1';
        const box = document.createElement('span');
        box.className = 'chk-box';
        const span = document.createElement('span');
        span.className = 'chk-lbl';
        span.textContent = `Spot ${i}`;
        label.appendChild(input);
        label.appendChild(box);
        label.appendChild(span);
        container.appendChild(label);
    }
}

function populateJesterModal(settings) {
    const container = document.getElementById('jester-items-list');
    container.innerHTML = '';
    const items = [
        "Oblivion Potion", "Heavenly Potion", "Rune of Everything", "Rune of Dust",
        "Rune of Nothing", "Rune Of Corruption", "Rune Of Hell", "Rune of Galaxy",
        "Rune of Rainstorm", "Rune of Frost", "Rune of Wind", "Strange Potion",
        "Lucky Potion", "Stella's Candle", "Merchant Tracker", "Random Potion Sack"
    ];
    items.forEach((item, idx) => {
        const row = document.createElement('div');
        row.className = 'item-row';
        const chk = document.createElement('label');
        chk.className = 'chk';
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.id = `jester_${item.replace(/\\s+/g, '_')}`;
        input.checked = settings.settings?.[item] === '1';
        const box = document.createElement('span');
        box.className = 'chk-box';
        const lbl = document.createElement('span');
        lbl.className = 'chk-lbl';
        lbl.textContent = item;
        chk.appendChild(input);
        chk.appendChild(box);
        chk.appendChild(lbl);
        const qty = document.createElement('input');
        qty.type = 'text';
        qty.className = 'ifield sm';
        qty.id = `jester_qty_${idx+1}`;
        qty.value = settings.settings?.[(idx+1).toString()] || '';
        row.appendChild(chk);
        row.appendChild(qty);
        container.appendChild(row);
    });
}

// Tab switching
document.querySelectorAll('.tbtn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tbtn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        document.querySelectorAll('.panel-page').forEach(p => p.classList.remove('active'));
        document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    });
});

window.addEventListener('load', () => {
    runLoader();
});
</script>
</body>
"""

# --- Main entry point ---
if __name__ == '__main__':
    set_path()
    api = Api()
    window = webview.create_window(
        title=f"Elixir Macro v{get_current_version()}",
        html=HTML,
        js_api=api,
        width=700,
        height=440,
        resizable=False,
        easy_drag=False
    )
    webview.start(icon="icon.ico" if os.path.exists("icon.ico") else None)
