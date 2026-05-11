import asyncio
import json
import logging
import os
import re
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import keyboard
import requests
import ttkbootstrap as tb
from tkinter import messagebox, ttk
from ttkbootstrap.constants import *

# Optional dependencies
try:
    import pyautogui
    PYAutoGUI_AVAILABLE = True
except ImportError:
    PYAutoGUI_AVAILABLE = False
    print("Warning: pyautogui not installed. Click simulation will be disabled.")

try:
    from discord_webhook import DiscordWebhook, DiscordEmbed
    DISCORD_WEBHOOK_AVAILABLE = True
except ImportError:
    DISCORD_WEBHOOK_AVAILABLE = False
    print("Warning: discord-webhook not installed. Image sending will be disabled.")

try:
    from PIL import ImageGrab
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    print("Warning: Pillow not installed. Screenshots will be disabled.")

CURRENT_VERSION = "1.3.0"

# ---------------------------- Config Path ----------------------------
def get_config_path():
    if sys.platform == "darwin":
        app_support = Path.home() / "Library" / "Application Support" / "ElixirMacro"
    else:
        if sys.platform == "win32":
            base = Path(os.getenv('APPDATA', Path.home() / 'AppData/Roaming'))
        else:
            base = Path.home() / ".config"
        app_support = base / "ElixirMacro"
    app_support.mkdir(parents=True, exist_ok=True)
    return app_support / "settings.json"

def deep_merge(a, b):
    for k in b:
        if k in a and isinstance(a[k], dict) and isinstance(b[k], dict):
            deep_merge(a[k], b[k])
        else:
            a[k] = b[k]

def read_config():
    default_config = {
        "discord": {
            "webhook": {
                "enabled": "0",
                "url": "",
                "ping_id": "",
                "ps_link": ""
            }
        },
        "enable_aura_detection": "1",
        "biome_detection": "1",
        "biome_alerts": {
            "NORMAL": "0", "WINDY": "0", "RAINY": "0", "SNOWY": "0", "EGGLAND": "0",
            "SAND STORM": "0", "HELL": "0", "STARFALL": "0", "HEAVEN": "0",
            "CORRUPTION": "0", "NULL": "0", "GLITCHED": "0", "DREAMSPACE": "0",
            "CYBERSPACE": "0", "THE CITADEL OF ORDERS": "0"
        },
        "anti-afk": {
            "enabled": "0",
            "mode": "Auto Click",
            "interval_seconds": "30"
        },
        "potion_crafting": {
            "enabled": "0",
            "crafting_interval": "30"
        },
        "claim_daily_quests": "0",
        "invo_ss": {"enabled": "0", "duration": "60"},
        "item_scheduler_item": {
            "enabled": "0",
            "item_name": "",
            "item_scheduler_quantity": "1",
            "interval": "30",
            "enable_only_if_biome": "0",
            "biome": []
        },
        "settings": {
            "azerty_mode": "0",
            "vip_mode": "0",
            "vip+_mode": "0",
            "click_delay": "0.55"
        },
        "clicks": {
            "items_storage": [0, 0],
            "items_tab": [0, 0],
            "items_bar": [0, 0],
            "item_first_slot": [0, 0],
            "item_value": [0, 0],
            "use_button": [0, 0],
            "quest_menu": [0, 0],
            "first_slot": [0, 0],
            "claim_button": [0, 0],
            "second_slot": [0, 0],
            "third_slot": [0, 0],
            "aura_storage": [0, 0],
            "regular_tab": [0, 0]
        }
    }
    cfg_path = get_config_path()
    if cfg_path.exists():
        try:
            with open(cfg_path, 'r') as f:
                user_cfg = json.load(f)
                deep_merge(default_config, user_cfg)
        except Exception as e:
            print(f"Error reading config: {e}")
    return default_config

def save_config(cfg):
    cfg_path = get_config_path()
    try:
        with open(cfg_path, 'w') as f:
            json.dump(cfg, f, indent=4)
    except Exception as e:
        messagebox.showerror("Config Error", f"Could not save config: {e}")

# ---------------------------- Helper Functions ----------------------------
def get_action(file):
    """Read pathing script from paths folder."""
    try:
        if getattr(sys, 'frozen', False):
            base_path = Path(sys.executable).parent.resolve()
        else:
            base_path = Path(__file__).parent.resolve()
        path_file = base_path / "paths" / f"{file}.py"
        if path_file.exists():
            with open(path_file, 'r') as f:
                return f.read()
        else:
            print(f"Path file not found: {path_file}")
            return ""
    except Exception as e:
        print(f"Failed to load path {file}: {e}")
        return ""

azerty_replace_dict = {"w": "z", "a": "q"}

def walk_time_conversion(d, config):
    if config.get("settings", {}).get("vip+_mode") == "1":
        return d
    elif config.get("settings", {}).get("vip_mode") == "1":
        return d * 1.04
    else:
        return d * 1.3

def walk_sleep(d, config):
    time.sleep(walk_time_conversion(d, config))

def walk_send(k, t, config):
    if config.get("settings", {}).get("azerty_mode") == "1" and k in azerty_replace_dict:
        k = azerty_replace_dict[k]
    if t:
        keyboard.press(k)
    else:
        keyboard.release(k)

def platform_click(x, y):
    if PYAutoGUI_AVAILABLE:
        pyautogui.click(x, y)
    else:
        print(f"Click at ({x},{y}) - pyautogui not installed")

def platform_key_press(key):
    keyboard.press(key)
    time.sleep(0.05)
    keyboard.release(key)

def platform_key_combo(keys):
    if '+' in keys:
        parts = keys.split('+')
        for p in parts:
            keyboard.press(p)
        for p in reversed(parts):
            keyboard.release(p)
    else:
        keyboard.press(keys)
        time.sleep(0.05)
        keyboard.release(keys)

# ---------------------------- BiomeTracker (fixed webhook) ----------------------------
class BiomeTracker:
    def __init__(self, config, log_callback=None):
        self.config = config
        self.log_callback = log_callback
        self.biomes = self._load_biome_data()
        self.auras = self._load_aura_data()
        self.current_biome = None
        self.biome_counts = {}
        self._update_webhook_settings()
        self.last_aura = None
        self.last_processed_position = 0
        self.last_sent_biome = None
        self.last_sent_aura = None
        self._running = False
        self._setup_logging()

    def _update_webhook_settings(self):
        webhook_cfg = self.config.get("discord", {}).get("webhook", {})
        self.webhook_enabled = webhook_cfg.get("enabled", "0") == "1"
        self.webhook_url = webhook_cfg.get("url", "")
        self.private_server_link = webhook_cfg.get("ps_link", "")
        self.user_id = webhook_cfg.get("ping_id", "")

    def _log(self, message, level=logging.INFO):
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def _setup_logging(self):
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%m-%d-%Y %H-%M-%S")
        log_filename = log_dir / f"{timestamp} biome_tracker.log"
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_filename),
                logging.StreamHandler()
            ],
            force=True,
        )

    def _load_biome_data(self):
        try:
            response = requests.get(
                "https://raw.githubusercontent.com/vexsyx/OysterDetector/refs/heads/main/data/biome-data.json",
                timeout=5
            )
            response.raise_for_status()
            biome_list = response.json()
            self._log(f"Loaded biome data from {response.url}")
            return {biome["name"]: biome for biome in biome_list if "name" in biome}
        except Exception as e:
            self._log(f"Failed to load biome data: {str(e)}", logging.ERROR)
            return {}

    def _load_aura_data(self):
        try:
            response = requests.get(
                "https://raw.githubusercontent.com/vexsyx/OysterDetector/refs/heads/main/data/aura-data.json",
                timeout=5
            )
            response.raise_for_status()
            aura_list = response.json()
            self._log(f"Loaded aura data from {response.url}")
            return {aura["identifier"]: aura for aura in aura_list if "identifier" in aura}
        except Exception as e:
            self._log(f"Failed to load aura data: {str(e)}", logging.ERROR)
            return {}

    def _get_log_dir(self):
        if sys.platform == "win32":
            local_app_data = os.getenv('LOCALAPPDATA')
            if local_app_data:
                return Path(local_app_data) / "Roblox" / "logs"
        elif sys.platform == "darwin":
            return Path.home() / "Library" / "Logs" / "Roblox"
        return None

    async def monitor_logs(self):
        self._running = True
        log_dir = self._get_log_dir()
        if not log_dir or not log_dir.exists():
            self._log("Roblox log directory not found.", logging.ERROR)
            return

        latest_log = max(log_dir.glob("*.log"), key=os.path.getmtime, default=None)
        if latest_log:
            self.last_processed_position = latest_log.stat().st_size
        else:
            self.last_processed_position = 0

        while self._running:
            try:
                latest_log = max(log_dir.glob("*.log"), key=os.path.getmtime, default=None)
                if not latest_log or not latest_log.exists():
                    await asyncio.sleep(5)
                    continue

                with open(latest_log, "r", errors="ignore") as f:
                    if latest_log.stat().st_size < self.last_processed_position:
                        self.last_processed_position = 0
                    f.seek(self.last_processed_position)
                    lines = f.readlines()
                    self.last_processed_position = f.tell()
                    for line in lines:
                        await self._process_log_entry(line)
                await asyncio.sleep(1)
            except Exception as e:
                self._log(f"Log monitoring error: {str(e)}", logging.ERROR)
                await asyncio.sleep(5)

    async def _process_log_entry(self, line):
        try:
            self._detect_biome_change(line)
            self._check_aura_equipped(line)
        except Exception as e:
            self._log(f"Log processing error: {str(e)}", logging.ERROR)

    def _detect_biome_change(self, line):
        if "[BloxstrapRPC]" not in line:
            return
        if self.config.get("biome_detection", "0") != "1":
            return
        try:
            json_str = line.split("[BloxstrapRPC] ")[1]
            data = json.loads(json_str)
            hover_text = data.get("data", {}).get("largeImage", {}).get("hoverText", "")
            if hover_text in self.biomes and self.current_biome != hover_text:
                self._handle_new_biome(hover_text)
        except (IndexError, json.JSONDecodeError):
            pass
        except Exception as e:
            self._log(f"Biome detection error: {str(e)}", logging.ERROR)

    def _handle_new_biome(self, biome_name):
        try:
            self.current_biome = biome_name
            self.biome_counts[biome_name] = self.biome_counts.get(biome_name, 0) + 1
            self._log(f"Biome detected: {biome_name}")
            if biome_name != self.last_sent_biome:
                biome_data = self.biomes.get(biome_name)
                if not biome_data:
                    return
                special_biomes = ["GLITCHED", "DREAMSPACE", "CYBERSPACE", "THE CITADEL OF ORDERS"]
                should_send = biome_name in special_biomes or self.config.get('biome_alerts', {}).get(biome_name) == "1"
                if should_send:
                    color = int(biome_data.get("visuals", {}).get("primary_hex", "FFFFFF"), 16)
                    self._send_webhook(
                        title="Biome Detected",
                        description=f"# - {biome_name}",
                        color=color,
                        thumbnail=biome_data.get("visuals", {}).get("preview_image"),
                        urgent=biome_name in special_biomes,
                        is_aura=False,
                    )
                self.last_sent_biome = biome_name
        except Exception as e:
            self._log(f"Biome handling error: {str(e)}", logging.ERROR)

    def _check_aura_equipped(self, line):
        if "[BloxstrapRPC]" not in line:
            return
        if self.config.get("enable_aura_detection", "0") != "1":
            return
        try:
            json_str = line.split("[BloxstrapRPC] ")[1]
            data = json.loads(json_str)
            state = data.get("data", {}).get("state", "")
            match = re.search(r'Equipped "(.*?)"', state)
            if match:
                aura_name = match.group(1)
                if aura_name in self.auras:
                    self._process_aura(aura_name)
        except (IndexError, json.JSONDecodeError):
            pass

    def _process_aura(self, aura_name):
        try:
            aura = self.auras.get(aura_name)
            if not aura:
                return
            aura_data = aura.get("properties", {})
            visuals = aura.get("visuals", {})
            thumbnail = visuals.get("preview_image")
            base_chance = aura_data.get("base_chance", 0)
            rarity = base_chance
            obtained_biome = None
            biome_amplifier = aura_data.get("biome_amplifier", ["None", 1])
            if isinstance(biome_amplifier, list) and len(biome_amplifier) >= 2:
                if biome_amplifier[0] != "None" and (self.current_biome == biome_amplifier[0] or self.current_biome == "GLITCHED"):
                    rarity /= max(biome_amplifier[1], 0.001)
                    obtained_biome = self.current_biome
            rarity = int(rarity)
            if aura_data.get("rank") == "challenged":
                color = 0x808090
            else:
                if rarity <= 999:
                    color = 0xFFFFFF
                elif rarity <= 9999:
                    color = 0xFFC0CB
                elif rarity <= 99998:
                    color = 0xFFA500
                elif rarity <= 999999:
                    color = 0xFFFF00
                elif rarity <= 9999999:
                    color = 0xFF1493
                elif rarity <= 99999998:
                    color = 0x00008B
                elif rarity <= 999999999:
                    color = 0x8B0000
                else:
                    color = 0x00FFFF
            fields = []
            if base_chance == 0:
                rarity_str = "Unobtainable"
            else:
                rarity_str = f"1 in {rarity:,}"
            fields.append({"name": "Rarity", "value": rarity_str, "inline": True})
            if obtained_biome:
                fields.append({"name": "Obtained From", "value": obtained_biome, "inline": True})
            self._log(f"Aura equipped: {aura_name} (1 in {rarity:,})")
            if aura_name != self.last_sent_aura:
                self._send_webhook(
                    title="**Aura Detection**",
                    description=f"## {time.strftime('[%I:%M:%S %p]')} \n ## > Aura found/last equipped: {aura_name}",
                    color=color,
                    thumbnail=thumbnail,
                    is_aura=True,
                    fields=fields,
                )
                self.last_sent_aura = aura_name
        except Exception as e:
            self._log(f"Aura processing error: {str(e)}", logging.ERROR)

    def _send_webhook(self, title, description, color, thumbnail=None, urgent=False, is_aura=False, fields=None):
        if not self.webhook_enabled:
            self._log("Webhook disabled. Not sending.", logging.INFO)
            return
        if not self.webhook_url:
            self._log("Webhook URL not set.", logging.WARNING)
            return
        try:
            current_time = datetime.now().isoformat()
            embed = {
                "title": title,
                "description": description,
                "color": color,
                "timestamp": current_time,
                "footer": {"text": "Elixir Macro", "icon_url": "https://goldfish-cool.github.io/Goldens-Macro/golden_pfp.png"},
            }
            if fields:
                embed["fields"] = fields
            elif not is_aura:
                ps_link = self.private_server_link if self.private_server_link.strip() else "(no private server link)"
                embed["fields"] = [{"name": "Private Server Link", "value": ps_link}]
            if thumbnail:
                embed["thumbnail"] = {"url": thumbnail}
            content = ""
            if urgent:
                content += "@everyone "
            if is_aura and self.user_id.strip():
                content += f"<@{self.user_id}>"
            payload = {"content": content.strip(), "embeds": [embed]}
            threading.Thread(target=self._send_webhook_sync, args=(payload,), daemon=True).start()
        except Exception as e:
            self._log(f"Webhook creation error: {str(e)}", logging.ERROR)

    def _send_webhook_sync(self, payload):
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            if response.status_code == 429:
                retry_after = response.json().get("retry_after", 5)
                self._log(f"Rate limited, retrying in {retry_after}s", logging.WARNING)
                time.sleep(retry_after)
                self._send_webhook_sync(payload)
            else:
                response.raise_for_status()
                self._log(f"Webhook sent: {payload['embeds'][0]['title']}", logging.INFO)
        except Exception as e:
            self._log(f"Webhook failed: {str(e)}", logging.ERROR)

    def stop_monitoring(self):
        self._running = False

# ---------------------------- TrackerController ----------------------------
class TrackerController:
    def __init__(self, config, log_callback):
        self.tracker = None
        self.loop = None
        self.thread = None
        self.config = config
        self.log_callback = log_callback

    def start(self):
        if self.tracker and self.tracker._running:
            return
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        self.loop = asyncio.get_event_loop()
        self.tracker = BiomeTracker(self.config, self.log_callback)
        self.tracker_task = self.loop.create_task(self.tracker.monitor_logs())
        try:
            self.loop.run_until_complete(self.tracker_task)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.log_callback(f"Tracker error: {e}", logging.ERROR)
        finally:
            self.loop.close()

    def stop(self):
        if self.tracker:
            self.tracker.stop_monitoring()
            if self.loop and self.loop.is_running():
                self.loop.call_soon_threadsafe(self.tracker_task.cancel)

    def update_config(self, new_config):
        self.config = new_config
        if self.tracker:
            self.tracker.config = new_config
            self.tracker._update_webhook_settings()

# ---------------------------- AntiAFKController ----------------------------
class AntiAFKController:
    def __init__(self, config, log_callback):
        self.config = config
        self.log_callback = log_callback
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return
        if not PYAutoGUI_AVAILABLE:
            self.log_callback("Anti-AFK requires pyautogui", logging.ERROR)
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.log_callback("Anti-AFK started", logging.INFO)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
        self.log_callback("Anti-AFK stopped", logging.INFO)

    def _run(self):
        while self._running:
            try:
                enabled = self.config.get("anti-afk", {}).get("enabled", "0") == "1"
                if not enabled:
                    time.sleep(1)
                    continue
                mode = self.config.get("anti-afk", {}).get("mode", "Auto Click")
                interval = float(self.config.get("anti-afk", {}).get("interval_seconds", "30"))
                interval = max(1.0, interval)
                if mode == "Auto Click":
                    pyautogui.click()
                    self.log_callback("Anti-AFK: Auto-click", logging.INFO)
                elif mode == "Random Jump":
                    pyautogui.press('space')
                    self.log_callback("Anti-AFK: Jump", logging.INFO)
                elif mode == "Both":
                    pyautogui.click()
                    time.sleep(0.2)
                    pyautogui.press('space')
                    self.log_callback("Anti-AFK: Click+Jump", logging.INFO)
                else:
                    pyautogui.click()
                for _ in range(int(interval)):
                    if not self._running:
                        break
                    time.sleep(1)
            except Exception as e:
                self.log_callback(f"Anti-AFK error: {e}", logging.ERROR)
                time.sleep(5)

    def update_config(self, new_config):
        self.config = new_config

# ---------------------------- Action Controllers (Crafting, Quests, Screenshots, Scheduler) ----------------------------
class ActionController:
    def __init__(self, config, log_callback):
        self.config = config
        self.log_callback = log_callback
        self._running = False
        self._thread = None
        self.last_potion = datetime.now()
        self.last_quest = datetime.now()
        self.last_ss = datetime.now()
        self.last_item_scheduler = datetime.now()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.log_callback("Auto actions started", logging.INFO)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
        self.log_callback("Auto actions stopped", logging.INFO)

    def _run(self):
        while self._running:
            try:
                now = datetime.now()
                # Potion crafting
                if self.config.get("potion_crafting", {}).get("enabled") == "1":
                    interval_min = int(self.config.get("potion_crafting", {}).get("crafting_interval", 30))
                    if now - self.last_potion >= timedelta(minutes=interval_min):
                        self.do_crafting()
                        self.last_potion = now
                # Daily quests
                if self.config.get("claim_daily_quests") == "1":
                    if now - self.last_quest >= timedelta(minutes=30):
                        self.claim_quests()
                        self.last_quest = now
                # Inventory screenshots
                if self.config.get("invo_ss", {}).get("enabled") == "1":
                    interval_min = int(self.config.get("invo_ss", {}).get("duration", 60))
                    if now - self.last_ss >= timedelta(minutes=interval_min):
                        self.inventory_screenshots()
                        self.last_ss = now
                # Item scheduler
                if self.config.get("item_scheduler_item", {}).get("enabled") == "1":
                    interval_min = int(self.config.get("item_scheduler_item", {}).get("interval", 30))
                    if now - self.last_item_scheduler >= timedelta(minutes=interval_min):
                        executed = self.item_scheduler()
                        if executed or self.config.get("item_scheduler_item", {}).get("enable_only_if_biome") != "1":
                            self.last_item_scheduler = now
                time.sleep(30)  # check every 30 seconds
            except Exception as e:
                self.log_callback(f"Auto actions error: {e}", logging.ERROR)
                time.sleep(60)

    def do_crafting(self):
        self.log_callback("Running potion crafting...", logging.INFO)
        action_code = get_action("potion_path")
        if action_code:
            try:
                exec(action_code, {"platform_click": platform_click, "platform_key_press": platform_key_press,
                                   "platform_key_combo": platform_key_combo, "time": time, "config": self.config,
                                   "walk_sleep": walk_sleep, "walk_send": walk_send, "walk_time_conversion": walk_time_conversion})
            except Exception as e:
                self.log_callback(f"Crafting error: {e}", logging.ERROR)
        else:
            self.log_callback("No potion_path.py found in 'paths' folder", logging.WARNING)

    def claim_quests(self):
        if self.config.get('claim_daily_quests') != "1":
            return
        self.log_callback("Claiming daily quests...", logging.INFO)
        try:
            c = self.config.get('clicks', {})
            click_delay = float(self.config.get("settings", {}).get("click_delay", 0.55))
            platform_click(*c.get('quest_menu', [0, 0]))
            time.sleep(0.55 + click_delay)
            platform_click(*c.get('first_slot', [0, 0]))
            time.sleep(0.38 + click_delay)
            platform_click(*c.get('claim_button', [0, 0]))
            time.sleep(0.38 + click_delay)
            platform_click(*c.get('second_slot', [0, 0]))
            time.sleep(0.38 + click_delay)
            platform_click(*c.get('claim_button', [0, 0]))
            time.sleep(0.38 + click_delay)
            platform_click(*c.get('third_slot', [0, 0]))
            time.sleep(0.38 + click_delay)
            platform_click(*c.get('claim_button', [0, 0]))
            time.sleep(0.28 + click_delay)
            platform_click(*c.get('quest_menu', [0, 0]))
        except Exception as e:
            self.log_callback(f"Quest claim error: {e}", logging.ERROR)

    def inventory_screenshots(self):
        if self.config.get('invo_ss', {}).get('enabled') != "1":
            return
        if not PILLOW_AVAILABLE:
            self.log_callback("Pillow not installed, cannot take screenshots", logging.ERROR)
            return
        self.log_callback("Taking inventory screenshots...", logging.INFO)
        try:
            c = self.config.get('clicks', {})
            click_delay = float(self.config.get("settings", {}).get("click_delay", 0.55))
            time.sleep(0.39 + click_delay)
            platform_click(*c.get('aura_storage', [0, 0]))
            time.sleep(0.55 + click_delay)
            platform_click(*c.get('regular_tab', [0, 0]))
            time.sleep(0.55 + click_delay)
            screen_dir = Path("images")
            screen_dir.mkdir(parents=True, exist_ok=True)
            ss = pyautogui.screenshot() if PYAutoGUI_AVAILABLE else ImageGrab.grab()
            path = screen_dir / "inventory_screenshots.png"
            ss.save(path)
            # Send via webhook if enabled
            webhook_url = self.config.get('discord', {}).get('webhook', {}).get('url', '')
            if webhook_url and DISCORD_WEBHOOK_AVAILABLE:
                self._send_image(path, "Aura Screenshot", webhook_url)
            time.sleep(0.55 + click_delay)
            platform_click(*c.get('aura_storage', [0, 0]))
            time.sleep(0.55 + click_delay)
            platform_click(*c.get('items_storage', [0, 0]))
            time.sleep(0.55 + click_delay)
            platform_click(*c.get('items_tab', [0, 0]))
            time.sleep(0.33 + click_delay)
            ss2 = pyautogui.screenshot() if PYAutoGUI_AVAILABLE else ImageGrab.grab()
            path2 = screen_dir / "item_screenshots.png"
            ss2.save(path2)
            if webhook_url and DISCORD_WEBHOOK_AVAILABLE:
                self._send_image(path2, "Item Screenshot", webhook_url)
            platform_click(*c.get('items_storage', [0, 0]))
        except Exception as e:
            self.log_callback(f"Screenshot error: {e}", logging.ERROR)

    def _send_image(self, image_path, title, webhook_url):
        try:
            webhook = DiscordWebhook(url=webhook_url)
            with open(image_path, 'rb') as f:
                webhook.add_file(file=f.read(), filename=image_path.name)
            embed = DiscordEmbed(title=title, description="")
            embed.set_image(url=f"attachment://{image_path.name}")
            webhook.add_embed(embed)
            webhook.execute()
            self.log_callback(f"Sent {title} to Discord", logging.INFO)
        except Exception as e:
            self.log_callback(f"Send image error: {e}", logging.ERROR)

    def item_scheduler(self):
        if self.config.get('item_scheduler_item', {}).get('enabled') != "1":
            return False
        self.log_callback("Running item scheduler...", logging.INFO)
        try:
            c = self.config.get('clicks', {})
            click_delay = float(self.config.get("settings", {}).get("click_delay", 0.55))
            scheduler_config = self.config.get('item_scheduler_item', {})
            platform_click(*c.get('items_storage', [0, 0]))
            time.sleep(0.55 + click_delay)
            platform_click(*c.get('items_tab', [0, 0]))
            time.sleep(0.33 + click_delay)
            platform_click(*c.get('items_bar', [0, 0]))
            time.sleep(0.33 + click_delay)
            item_name = scheduler_config.get('item_name', '')
            platform_key_press(item_name)
            time.sleep(0.55 + click_delay)
            platform_key_combo('{Enter}')
            time.sleep(0.43 + click_delay)
            platform_click(*c.get('item_first_slot', [0, 0]))
            time.sleep(0.33 + click_delay)
            platform_click(*c.get('item_value', [0, 0]))
            time.sleep(0.1 + click_delay)
            platform_click(*c.get('item_value', [0, 0]))
            time.sleep(0.33 + click_delay)
            quantity = scheduler_config.get('item_scheduler_quantity', '1')
            platform_key_combo(quantity)
            time.sleep(0.55 + click_delay)
            platform_key_combo('{Enter}')
            time.sleep(0.43 + click_delay)
            platform_click(*c.get('use_button', [0, 0]))
            time.sleep(0.78 + click_delay)
            platform_click(*c.get('items_bar', [0, 0]))
            time.sleep(0.33 + click_delay)
            platform_key_combo('{Enter}')
            time.sleep(0.55 + click_delay)
            platform_click(*c.get('items_storage', [0, 0]))
            return True
        except Exception as e:
            self.log_callback(f"Item scheduler error: {e}", logging.ERROR)
            return False

    def update_config(self, new_config):
        self.config = new_config

# ---------------------------- Main GUI Application ----------------------------
class App:
    def __init__(self):
        self.config = read_config()
        self.root = tb.Window(themename="solar")
        self.root.title("Elixir Macro")
        self.root.geometry("600x500")
        self.root.minsize(550, 450)
        self.root.resizable(True, True)

        self.log_text = None
        self.log_queue = []

        self.tracker_controller = TrackerController(self.config, self._log_gui)
        self.afk_controller = AntiAFKController(self.config, self._log_gui)
        self.action_controller = ActionController(self.config, self._log_gui)
        self.animation_running = False
        self._create_menu()
        self._create_notebook()
        self._create_statusbar()
        self._flush_logs()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_menu(self):
        menubar = tb.Menu(self.root)
        file_menu = tb.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Save Config", command=self._save_config)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)
        help_menu = tb.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)

    def _create_notebook(self):
        notebook = tb.Notebook(self.root, bootstyle="primary")
        notebook.pack(fill=BOTH, expand=YES, padx=5, pady=5)

        # Main tab
        self.main_frame = tb.Frame(notebook)
        notebook.add(self.main_frame, text="Main")
        self._build_main_tab()

        # Discord tab
        self.discord_frame = tb.Frame(notebook)
        notebook.add(self.discord_frame, text="Discord")
        self._build_discord_tab()

        # Settings tab
        self.settings_frame = tb.Frame(notebook)
        notebook.add(self.settings_frame, text="Settings")
        self._build_settings_tab()

        # Stats tab
        self.stats_frame = tb.Frame(notebook)
        notebook.add(self.stats_frame, text="Stats")
        self._build_stats_tab()

        # Crafting tab
        self.crafting_frame = tb.Frame(notebook)
        notebook.add(self.crafting_frame, text="Crafting")
        self._build_crafting_tab()

    def _build_main_tab(self):
        # Control buttons row
        btn_frame = tb.Frame(self.main_frame)
        btn_frame.pack(pady=10)
        self.start_btn = tb.Button(btn_frame, text="Start Tracking", command=self._start_tracking, bootstyle="success", width=14)
        self.start_btn.pack(side=LEFT, padx=5)
        self.stop_btn = tb.Button(btn_frame, text="Stop Tracking", command=self._stop_tracking, bootstyle="danger", width=14, state=DISABLED)
        self.stop_btn.pack(side=LEFT, padx=5)

        btn_frame2 = tb.Frame(self.main_frame)
        btn_frame2.pack(pady=5)
        self.afk_start_btn = tb.Button(btn_frame2, text="Start Anti-AFK", command=self._start_afk, bootstyle="success", width=14)
        self.afk_start_btn.pack(side=LEFT, padx=5)
        self.afk_stop_btn = tb.Button(btn_frame2, text="Stop Anti-AFK", command=self._stop_afk, bootstyle="danger", width=14, state=DISABLED)
        self.afk_stop_btn.pack(side=LEFT, padx=5)

        btn_frame3 = tb.Frame(self.main_frame)
        btn_frame3.pack(pady=5)
        self.auto_start_btn = tb.Button(btn_frame3, text="Start Auto Actions", command=self._start_auto, bootstyle="success", width=14)
        self.auto_start_btn.pack(side=LEFT, padx=5)
        self.auto_stop_btn = tb.Button(btn_frame3, text="Stop Auto Actions", command=self._stop_auto, bootstyle="danger", width=14, state=DISABLED)
        self.auto_stop_btn.pack(side=LEFT, padx=5)

        # Log display
        tb.Label(self.main_frame, text="Logs:", font=("Helvetica", 10, "bold")).pack(anchor=W, padx=10, pady=(10,0))
        log_frame = tb.Frame(self.main_frame)
        log_frame.pack(fill=BOTH, expand=YES, padx=10, pady=5)
        self.log_text = tb.Text(log_frame, wrap="word", state=DISABLED, font=("Courier", 9), height=12)
        scroll = tb.Scrollbar(log_frame, orient=VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side=LEFT, fill=BOTH, expand=YES)
        scroll.pack(side=RIGHT, fill=Y)
        tb.Button(self.main_frame, text="Clear Log", command=self._clear_log, bootstyle="secondary").pack(pady=5)

    def _build_discord_tab(self):
        webhook = self.config.get("discord", {}).get("webhook", {})
        self.webhook_enabled_var = tb.BooleanVar(value=webhook.get("enabled", "0") == "1")
        tb.Checkbutton(self.discord_frame, text="Enable Webhook", variable=self.webhook_enabled_var, bootstyle="round-toggle").pack(anchor=W, padx=15, pady=5)

        tb.Label(self.discord_frame, text="Webhook URL:").pack(anchor=W, padx=15)
        self.webhook_url_entry = tb.Entry(self.discord_frame, width=60)
        self.webhook_url_entry.insert(0, webhook.get("url", ""))
        self.webhook_url_entry.pack(anchor=W, padx=15, pady=2, fill=X)

        tb.Label(self.discord_frame, text="User ID to ping (optional):").pack(anchor=W, padx=15)
        self.ping_id_entry = tb.Entry(self.discord_frame, width=60)
        self.ping_id_entry.insert(0, webhook.get("ping_id", ""))
        self.ping_id_entry.pack(anchor=W, padx=15, pady=2, fill=X)

        tb.Label(self.discord_frame, text="Private Server Link (for biome alerts):").pack(anchor=W, padx=15)
        self.ps_link_entry = tb.Entry(self.discord_frame, width=60)
        self.ps_link_entry.insert(0, webhook.get("ps_link", ""))
        self.ps_link_entry.pack(anchor=W, padx=15, pady=2, fill=X)

        tb.Button(self.discord_frame, text="Test Webhook", command=self._test_webhook, bootstyle="info").pack(pady=10)

    def _build_settings_tab(self):
        # Biome alerts section (scrollable)
        tb.Label(self.settings_frame, text="Biome Alerts (enable which biomes to notify):", font=("Helvetica", 10, "bold")).pack(anchor=W, padx=10, pady=5)
        canvas = tb.Canvas(self.settings_frame, height=200)
        scrollbar = tb.Scrollbar(self.settings_frame, orient=VERTICAL, command=canvas.yview)
        scrollable_frame = tb.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=LEFT, fill=BOTH, expand=YES, padx=(10,0), pady=5)
        scrollbar.pack(side=RIGHT, fill=Y, padx=(0,10), pady=5)

        biome_names = list(self.config.get("biome_alerts", {}).keys())
        biome_names.sort()
        self.biome_vars = {}
        for name in biome_names:
            var = tb.BooleanVar(value=self.config["biome_alerts"].get(name, "0") == "1")
            cb = tb.Checkbutton(scrollable_frame, text=name, variable=var, bootstyle="round-toggle")
            cb.pack(anchor=W, padx=10, pady=1)
            self.biome_vars[name] = var

        # Other settings
        settings = self.config.get("settings", {})
        tb.Label(self.settings_frame, text="Other Settings:", font=("Helvetica", 10, "bold")).pack(anchor=W, padx=10, pady=(10,5))
        self.azerty_var = tb.BooleanVar(value=settings.get("azerty_mode", "0") == "1")
        tb.Checkbutton(self.settings_frame, text="AZERTY Mode (swap W<->Z, A<->Q)", variable=self.azerty_var, bootstyle="round-toggle").pack(anchor=W, padx=15, pady=2)
        self.vip_var = tb.BooleanVar(value=settings.get("vip_mode", "0") == "1")
        tb.Checkbutton(self.settings_frame, text="VIP Mode (walk speed +4%)", variable=self.vip_var, bootstyle="round-toggle").pack(anchor=W, padx=15, pady=2)
        self.vip_plus_var = tb.BooleanVar(value=settings.get("vip+_mode", "0") == "1")
        tb.Checkbutton(self.settings_frame, text="VIP+ Mode (walk speed normal)", variable=self.vip_plus_var, bootstyle="round-toggle").pack(anchor=W, padx=15, pady=2)
        tb.Label(self.settings_frame, text="Click Delay (seconds):").pack(anchor=W, padx=15, pady=(5,0))
        self.click_delay_var = tb.StringVar(value=settings.get("click_delay", "0.55"))
        tb.Spinbox(self.settings_frame, from_=0.1, to=2.0, increment=0.05, textvariable=self.click_delay_var, width=10, bootstyle="primary").pack(anchor=W, padx=15, pady=2)

        # Anti-AFK settings (moved here from its own tab)
        afk_cfg = self.config.get("anti-afk", {})
        tb.Label(self.settings_frame, text="Anti-AFK Settings:", font=("Helvetica", 10, "bold")).pack(anchor=W, padx=10, pady=(10,5))
        self.afk_enabled_var = tb.BooleanVar(value=afk_cfg.get("enabled", "0") == "1")
        tb.Checkbutton(self.settings_frame, text="Enable Anti-AFK", variable=self.afk_enabled_var, bootstyle="round-toggle").pack(anchor=W, padx=15, pady=2)
        tb.Label(self.settings_frame, text="Mode:").pack(anchor=W, padx=15)
        self.afk_mode_var = tb.StringVar(value=afk_cfg.get("mode", "Auto Click"))
        ttk.Combobox(self.settings_frame, textvariable=self.afk_mode_var, values=["Auto Click", "Random Jump", "Both"], state="readonly").pack(anchor=W, padx=15, pady=2, fill=X)
        tb.Label(self.settings_frame, text="Interval (seconds):").pack(anchor=W, padx=15)
        self.afk_interval_var = tb.StringVar(value=afk_cfg.get("interval_seconds", "30"))
        tb.Spinbox(self.settings_frame, from_=1, to=300, textvariable=self.afk_interval_var, width=10, bootstyle="primary").pack(anchor=W, padx=15, pady=2)

    def _build_stats_tab(self):
        """Create stats tab with colored biome names and animated GLITCHED."""
        self.stats_text = tb.Text(self.stats_frame, wrap="word", state=DISABLED,
                                  font=("Courier", 10), height=20)
        scroll = tb.Scrollbar(self.stats_frame, orient=VERTICAL,
                              command=self.stats_text.yview)
        self.stats_text.configure(yscrollcommand=scroll.set)
        self.stats_text.pack(side=LEFT, fill=BOTH, expand=YES, padx=10, pady=10)
        scroll.pack(side=RIGHT, fill=Y, padx=(0,10), pady=10)

        # Define colors for specific biomes
        self.biome_colors = {
            "RAINY": "#1E3A8A",
            "HELL": "#8B0000",
            "NULL": "#2C2C2C",
            "DREAMSPACE": "#FF69B4",
            "CORRUPTION": "#800080",
            "WINDY": "#ADD8E6",
            "NORMAL": "#FFFFFF",
            "SNOWY": "#F0FFFF",
            "HEAVEN": "#FFFFE0",
            "SAND STORM": "#EDC9AF",
            "EGGLAND": "#90EE90",
            "STARFALL": "#B0E0E6",
            "CYBERSPACE": "#00FFFF",
            "THE CITADEL OF ORDERS": "#D3D3D3",
        }
        # Register tags for each color
        for biome, col in self.biome_colors.items():
            self.stats_text.tag_config(f"color_{biome}", foreground=col)
        self.stats_text.tag_config("bold", font=("Courier", 10, "bold"))

        self._update_stats()
        self._animate_glitched()

    def _update_stats(self):
        """Update stats display with colored biome names (not overwriting GLITCHED line)."""
        if not hasattr(self, 'stats_text') or not self.stats_text:
            self.root.after(2000, self._update_stats)
            return

        tracker = self.tracker_controller.tracker
        self.stats_text.configure(state=NORMAL)
        self.stats_text.delete(1.0, END)

        if tracker and tracker._running:
            # Current biome
            current = tracker.current_biome or "Unknown"
            color_tag = f"color_{current.upper()}" if current.upper() in self.biome_colors else ""
            self.stats_text.insert(END, "Current Biome: ", ("bold",))
            if color_tag:
                self.stats_text.insert(END, f"{current}\n\n", (color_tag,))
            else:
                self.stats_text.insert(END, f"{current}\n\n")

            # Biome counts
            self.stats_text.insert(END, "Biome Counts:\n", ("bold",))
            for biome, count in sorted(tracker.biome_counts.items()):
                biome_upper = biome.upper()
                if biome_upper in self.biome_colors:
                    self.stats_text.insert(END, f"  {biome}: ", (f"color_{biome_upper}",))
                    self.stats_text.insert(END, f"{count}\n")
                else:
                    self.stats_text.insert(END, f"  {biome}: {count}\n")

            # Last sent aura/biome
            self.stats_text.insert(END, f"\nLast Sent Aura: {tracker.last_sent_aura or 'None'}\n", ("bold",))
            self.stats_text.insert(END, f"Last Sent Biome: {tracker.last_sent_biome or 'None'}\n")
        else:
            self.stats_text.insert(END, "Tracker not running. Start tracking to see stats.\n")

        self.stats_text.configure(state=DISABLED)
        self.root.after(2000, self._update_stats)

    def _animate_glitched(self):
        """Animate the GLITCHED biome entry with cycling colors and glitched text."""
        if not self.animation_running:
            return

        tracker = self.tracker_controller.tracker
        if tracker and tracker._running and "GLITCHED" in tracker.biome_counts and tracker.biome_counts["GLITCHED"] > 0:
            self.stats_text.configure(state=NORMAL)
            # Search for the line containing "GLITCHED:" (case-insensitive)
            start_pos = self.stats_text.search("GLITCHED:", "1.0", stopindex=END, nocase=True)
            if start_pos:
                line_end = self.stats_text.index(f"{start_pos}+1 lines linestart")
                self.stats_text.delete(start_pos, line_end)
                import random
                colors = ["#FF0000", "#0000FF", "#00FF00"]
                color_choice = random.choice(colors)
                glitched_variants = ["GLITCHED", "gLitcHEd", "G#*cHEd", "########",
                                     "G L I T C H", "Gʟɪᴛᴄʜᴇᴅ", "G̶L̶I̶T̶C̶H̶E̶D̶"]
                text_choice = random.choice(glitched_variants)
                count = tracker.biome_counts["GLITCHED"]
                self.stats_text.insert(start_pos, f"  {text_choice}: {count}\n", ("glitched_anim",))
                self.stats_text.tag_config("glitched_anim", foreground=color_choice, font=("Courier", 10, "bold"))
            self.stats_text.configure(state=DISABLED)

        self.root.after(300, self._animate_glitched)

    def _build_crafting_tab(self):
        # Potion crafting
        potion = self.config.get("potion_crafting", {})
        self.potion_enabled_var = tb.BooleanVar(value=potion.get("enabled", "0") == "1")
        tb.Checkbutton(self.crafting_frame, text="Enable Potion Crafting", variable=self.potion_enabled_var, bootstyle="round-toggle").pack(anchor=W, padx=15, pady=5)
        tb.Label(self.crafting_frame, text="Crafting Interval (minutes):").pack(anchor=W, padx=15)
        self.potion_interval_var = tb.StringVar(value=potion.get("crafting_interval", "30"))
        tb.Spinbox(self.crafting_frame, from_=5, to=120, textvariable=self.potion_interval_var, width=10, bootstyle="primary").pack(anchor=W, padx=15, pady=2)

        # Daily quests
        self.quests_enabled_var = tb.BooleanVar(value=self.config.get("claim_daily_quests", "0") == "1")
        tb.Checkbutton(self.crafting_frame, text="Claim Daily Quests every 30 minutes", variable=self.quests_enabled_var, bootstyle="round-toggle").pack(anchor=W, padx=15, pady=5)

        # Inventory screenshots
        inv_ss = self.config.get("invo_ss", {})
        self.inv_ss_enabled_var = tb.BooleanVar(value=inv_ss.get("enabled", "0") == "1")
        tb.Checkbutton(self.crafting_frame, text="Enable Inventory Screenshots", variable=self.inv_ss_enabled_var, bootstyle="round-toggle").pack(anchor=W, padx=15, pady=5)
        tb.Label(self.crafting_frame, text="Screenshot Interval (minutes):").pack(anchor=W, padx=15)
        self.inv_ss_interval_var = tb.StringVar(value=inv_ss.get("duration", "60"))
        tb.Spinbox(self.crafting_frame, from_=10, to=240, textvariable=self.inv_ss_interval_var, width=10, bootstyle="primary").pack(anchor=W, padx=15, pady=2)

        # Item scheduler
        sched = self.config.get("item_scheduler_item", {})
        self.sched_enabled_var = tb.BooleanVar(value=sched.get("enabled", "0") == "1")
        tb.Checkbutton(self.crafting_frame, text="Enable Item Scheduler", variable=self.sched_enabled_var, bootstyle="round-toggle").pack(anchor=W, padx=15, pady=5)
        tb.Label(self.crafting_frame, text="Item Name:").pack(anchor=W, padx=15)
        self.sched_item_name_entry = tb.Entry(self.crafting_frame, width=30)
        self.sched_item_name_entry.insert(0, sched.get("item_name", ""))
        self.sched_item_name_entry.pack(anchor=W, padx=15, pady=2)
        tb.Label(self.crafting_frame, text="Quantity:").pack(anchor=W, padx=15)
        self.sched_quantity_var = tb.StringVar(value=sched.get("item_scheduler_quantity", "1"))
        tb.Spinbox(self.crafting_frame, from_=1, to=999, textvariable=self.sched_quantity_var, width=10, bootstyle="primary").pack(anchor=W, padx=15, pady=2)
        tb.Label(self.crafting_frame, text="Interval (minutes):").pack(anchor=W, padx=15)
        self.sched_interval_var = tb.StringVar(value=sched.get("interval", "30"))
        tb.Spinbox(self.crafting_frame, from_=5, to=300, textvariable=self.sched_interval_var, width=10, bootstyle="primary").pack(anchor=W, padx=15, pady=2)
        self.sched_biome_only_var = tb.BooleanVar(value=sched.get("enable_only_if_biome", "0") == "1")
        tb.Checkbutton(self.crafting_frame, text="Run only when specific biome is active (not fully implemented)", variable=self.sched_biome_only_var, bootstyle="round-toggle").pack(anchor=W, padx=15, pady=2)

        # Note
        tb.Label(self.crafting_frame, text="Note: Place potion_path.py in 'paths' folder for crafting.", foreground="gray").pack(anchor=W, padx=15, pady=10)

    def _create_statusbar(self):
        self.statusbar = tb.Label(self.root, text="Ready", bootstyle="inverse", anchor=W)
        self.statusbar.pack(side=BOTTOM, fill=X)

    # ---------------------------- Logging ----------------------------
    def _log_gui(self, message, level=logging.INFO):
        self.log_queue.append((message, level))

    def _flush_logs(self):
        if self.log_text:
            for msg, level in self.log_queue:
                self.log_text.configure(state=NORMAL)
                timestamp = datetime.now().strftime("%H:%M:%S")
                if level >= logging.ERROR:
                    tag = "error"
                    self.log_text.tag_config("error", foreground="red")
                elif level >= logging.WARNING:
                    tag = "warning"
                    self.log_text.tag_config("warning", foreground="orange")
                else:
                    tag = None
                line = f"[{timestamp}] {msg}\n"
                self.log_text.insert(END, line, tag)
                self.log_text.see(END)
                self.log_text.configure(state=DISABLED)
            self.log_queue.clear()
        self.root.after(500, self._flush_logs)

    def _clear_log(self):
        if self.log_text:
            self.log_text.configure(state=NORMAL)
            self.log_text.delete(1.0, END)
            self.log_text.configure(state=DISABLED)

    # ---------------------------- Control Handlers ----------------------------
    def _start_tracking(self):
        self._save_config()
        self.tracker_controller.start()
        self.start_btn.configure(state=DISABLED)
        self.stop_btn.configure(state=NORMAL)
        self.statusbar.configure(text="Tracking active")

    def _stop_tracking(self):
        self.tracker_controller.stop()
        self.start_btn.configure(state=NORMAL)
        self.stop_btn.configure(state=DISABLED)
        self.statusbar.configure(text="Tracking stopped")

    def _start_afk(self):
        self._save_config()
        self.afk_controller.start()
        self.afk_start_btn.configure(state=DISABLED)
        self.afk_stop_btn.configure(state=NORMAL)
        self.statusbar.configure(text="Anti-AFK active")

    def _stop_afk(self):
        self.afk_controller.stop()
        self.afk_start_btn.configure(state=NORMAL)
        self.afk_stop_btn.configure(state=DISABLED)
        self.statusbar.configure(text="Anti-AFK stopped")

    def _start_auto(self):
        self._save_config()
        self.action_controller.start()
        self.auto_start_btn.configure(state=DISABLED)
        self.auto_stop_btn.configure(state=NORMAL)
        self.statusbar.configure(text="Auto actions active")

    def _stop_auto(self):
        self.action_controller.stop()
        self.auto_start_btn.configure(state=NORMAL)
        self.auto_stop_btn.configure(state=DISABLED)
        self.statusbar.configure(text="Auto actions stopped")

    def _save_config(self):
        # Webhook
        self.config["discord"]["webhook"]["enabled"] = "1" if self.webhook_enabled_var.get() else "0"
        self.config["discord"]["webhook"]["url"] = self.webhook_url_entry.get().strip()
        self.config["discord"]["webhook"]["ping_id"] = self.ping_id_entry.get().strip()
        self.config["discord"]["webhook"]["ps_link"] = self.ps_link_entry.get().strip()

        # Biome alerts
        for name, var in self.biome_vars.items():
            self.config["biome_alerts"][name] = "1" if var.get() else "0"

        # Settings
        self.config["settings"]["azerty_mode"] = "1" if self.azerty_var.get() else "0"
        self.config["settings"]["vip_mode"] = "1" if self.vip_var.get() else "0"
        self.config["settings"]["vip+_mode"] = "1" if self.vip_plus_var.get() else "0"
        self.config["settings"]["click_delay"] = self.click_delay_var.get().strip()

        # Anti-AFK
        self.config["anti-afk"]["enabled"] = "1" if self.afk_enabled_var.get() else "0"
        self.config["anti-afk"]["mode"] = self.afk_mode_var.get()
        self.config["anti-afk"]["interval_seconds"] = self.afk_interval_var.get().strip()

        # Crafting
        self.config["potion_crafting"]["enabled"] = "1" if self.potion_enabled_var.get() else "0"
        self.config["potion_crafting"]["crafting_interval"] = self.potion_interval_var.get().strip()
        self.config["claim_daily_quests"] = "1" if self.quests_enabled_var.get() else "0"
        self.config["invo_ss"]["enabled"] = "1" if self.inv_ss_enabled_var.get() else "0"
        self.config["invo_ss"]["duration"] = self.inv_ss_interval_var.get().strip()
        self.config["item_scheduler_item"]["enabled"] = "1" if self.sched_enabled_var.get() else "0"
        self.config["item_scheduler_item"]["item_name"] = self.sched_item_name_entry.get().strip()
        self.config["item_scheduler_item"]["item_scheduler_quantity"] = self.sched_quantity_var.get().strip()
        self.config["item_scheduler_item"]["interval"] = self.sched_interval_var.get().strip()
        self.config["item_scheduler_item"]["enable_only_if_biome"] = "1" if self.sched_biome_only_var.get() else "0"

        save_config(self.config)
        self.tracker_controller.update_config(self.config)
        self.afk_controller.update_config(self.config)
        self.action_controller.update_config(self.config)
        self.statusbar.configure(text="Configuration saved")

    def _test_webhook(self):
        url = self.webhook_url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Enter a webhook URL")
            return
        payload = {"content": "Test from Elixir Macro", "embeds": [{"title": "Test", "description": "Working!", "color": 0x00FF00}]}
        try:
            r = requests.post(url, json=payload, timeout=5)
            r.raise_for_status()
            messagebox.showinfo("Success", "Webhook test sent!")
        except Exception as e:
            messagebox.showerror("Webhook Error", str(e))

    def _show_about(self):
        messagebox.showinfo("About", f"Elixir Macro v{CURRENT_VERSION}\n\nComplete automation suite for Roblox.\n\nMade by spacedev0572")

    def _on_close(self):
        self._stop_tracking()
        self._stop_afk()
        self._stop_auto()
        self.root.destroy()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = App()
    app.run()