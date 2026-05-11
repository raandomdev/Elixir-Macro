import asyncio
import json
import logging
import os
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import requests
import ttkbootstrap as tb
from tkinter import messagebox, filedialog, ttk
from ttkbootstrap.constants import *

try:
    import pyautogui
    PYAutoGUI_AVAILABLE = True
except ImportError:
    PYAutoGUI_AVAILABLE = False
    print("Warning: pyautogui not installed. Anti‑AFK will be disabled.")

CURRENT_VERSION = "1.2.1"

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
            "NORMAL": "0", "WINDY": "0", "RAINY": "0", "SNOWY": "0", "EGGLAND": "0", "SINGULARITY": "0",
            "SAND STORM": "0", "HELL": "0", "STARFALL": "0", "HEAVEN": "0",
            "CORRUPTION": "0", "NULL": "0", "GLITCHED": "0", "DREAMSPACE": "0",
            "CYBERSPACE": "0", "THE CITADEL OF ORDERS": "0"
        },
        "auto_equip": {
            "enabled": "0",
            "aura_name": "",
            "is_special": "0"
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

# ------------------------------------------------------------
#  BiomeTracker (fixed webhook)
# ------------------------------------------------------------
class BiomeTracker:
    def __init__(self, config, log_callback=None):
        self.config = config
        self.log_callback = log_callback
        self.biomes = self._load_biome_data()
        self.auras = self._load_aura_data()
        self.is_merchant = False
        self.merchant_name = ""
        self.current_biome = None
        self.biome_counts = {b.get("name", f"unknown_{i}"): 0 for i, b in enumerate(self.biomes.values())}
        self._update_webhook_settings()   # load from config
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
                "https://raw.githubusercontent.com/raandomdev/Elixir-Macro/refs/heads/ui/assets/biome-data.json",
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
                    self._log(f"Biome data missing for: {biome_name}", logging.WARNING)
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
        except Exception as e:
            self._log(f"Aura check error: {str(e)}", logging.ERROR)

    def _process_aura(self, aura_name):
        try:
            aura = self.auras.get(aura_name)
            if not aura:
                self._log(f"Aura data missing for: {aura_name}", logging.WARNING)
                return

            aura_data = aura.get("properties", {})
            visuals = aura.get("visuals", {})
            thumbnail = visuals.get("preview_image")

            base_chance = aura_data.get("base_chance", 0)
            rarity = base_chance
            obtained_biome = None

            biome_amplifier = aura_data.get("biome_amplifier", ["None", 1])
            if isinstance(biome_amplifier, list) and len(biome_amplifier) >= 2:
                if biome_amplifier[0] != "None" and (
                    self.current_biome == biome_amplifier[0]
                    or self.current_biome == "GLITCHED"
                ):
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

        except ZeroDivisionError:
            self._log("Invalid biome amplifier value (division by zero)", logging.ERROR)
        except Exception as e:
            self._log(f"Aura processing error: {str(e)}", logging.ERROR)

    # ----- FIXED WEBHOOK SENDING -----
    def _send_webhook(self, title, description, color, thumbnail=None, urgent=False, is_aura=False, fields=None):
        # Check if webhook is enabled and URL is set
        if not self.webhook_enabled:
            self._log("Webhook disabled in settings. Not sending.", logging.INFO)
            return
        if not self.webhook_url:
            self._log("Webhook URL is empty. Cannot send.", logging.WARNING)
            return

        try:
            current_time = datetime.now().isoformat()
            embed = {
                "title": title,
                "description": description,
                "color": color,
                "timestamp": current_time,
                "footer": {
                    "text": "Elixir Macro"#,
                    #"icon_url": "https://goldfish-cool.github.io/Goldens-Macro/golden_pfp.png"
                },
            }
            if fields is not None:
                embed["fields"] = fields
            else:
                if not is_aura:
                    ps_link = self.private_server_link if self.private_server_link and self.private_server_link.strip() else "(no private server link)"
                    embed["fields"] = [{"name": "Private Server Link", "value": ps_link}]

            if thumbnail:
                embed["thumbnail"] = {"url": thumbnail}

            content = ""
            if urgent:
                content += "@everyone "
            if is_aura and self.user_id and self.user_id.strip():
                content += f"<@{self.user_id}>"

            payload = {"content": content.strip(), "embeds": [embed]}

            # Send synchronously in a thread to avoid blocking the async loop
            threading.Thread(target=self._send_webhook_sync, args=(payload,), daemon=True).start()
        except Exception as e:
            self._log(f"Webhook creation error: {str(e)}", logging.ERROR)

    def _send_webhook_sync(self, payload):
        """Synchronous webhook sender (runs in a separate thread)."""
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            if response.status_code == 429:
                retry_after = response.json().get("retry_after", 5)
                self._log(f"Rate limited - retrying in {retry_after}s", logging.WARNING)
                time.sleep(retry_after)
                self._send_webhook_sync(payload)   # retry
            else:
                response.raise_for_status()
                self._log(f"Webhook sent successfully: {payload['embeds'][0]['title']}", logging.INFO)
        except Exception as e:
            self._log(f"Webhook failed: {str(e)}", logging.ERROR)

    def stop_monitoring(self):
        self._running = False

# ------------------------------------------------------------
#  TrackerController (updated config propagation)
# ------------------------------------------------------------
class TrackerController:
    def __init__(self, config, log_callback):
        self.tracker = None
        self.loop = None
        self.thread = None
        self._stop_event = threading.Event()
        self.config = config
        self.log_callback = log_callback

    def start(self):
        if self.tracker and self.tracker._running:
            return
        self._stop_event.clear()
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
        self._stop_event.set()

    def update_config(self, new_config):
        self.config = new_config
        if self.tracker:
            self.tracker.config = new_config
            self.tracker._update_webhook_settings()   # refresh webhook settings

# ------------------------------------------------------------
#  AntiAFKController (unchanged)
# ------------------------------------------------------------
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
            self.log_callback("Anti-AFK requires pyautogui. Install with: pip install pyautogui", logging.ERROR)
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
                    self.log_callback(f"Anti-AFK: Auto-click performed", logging.INFO)
                elif mode == "Random Jump":
                    pyautogui.press('space')
                    self.log_callback(f"Anti-AFK: Random jump performed", logging.INFO)
                elif mode == "Both":
                    pyautogui.click()
                    time.sleep(0.2)
                    pyautogui.press('space')
                    self.log_callback(f"Anti-AFK: Click + jump performed", logging.INFO)
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

class App:
    def __init__(self):
        self.config = read_config()
        self.root = tb.Window(themename="solar")
        self.root.title("Elixir Macro v1.1.3")
        self.root.geometry("630x315")
        #self.root.minsize(700, 550)
        self.root.resizable(True, True)

        self.log_text = None
        self.log_queue = []

        self.tracker_controller = TrackerController(self.config, self._log_gui)
        self.afk_controller = AntiAFKController(self.config, self._log_gui)

        self._create_menu()
        self._create_notebook()
        self._create_statusbar()

        # Systen buttons
        btn_frame = tb.Frame(self.root)
        start_button = tb.Button(btn_frame, text="Start Tracker", command=self._start_tracking, bootstyle="success")    
        stop_button = tb.Button(btn_frame, text="Stop Tracker", command=self._stop_tracking, bootstyle="danger")
        start_button.pack(side=LEFT, padx=10)
        stop_button.pack(side=LEFT, padx=10)

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
        notebook.pack(fill=BOTH, expand=YES, padx=8, pady=8)

        # General tab
        self.general_frame = tb.Frame(notebook)
        notebook.add(self.general_frame, text="Main")
        self._build_general_tab()

        # Webhook tab
        self.webhook_frame = tb.Frame(notebook)
        notebook.add(self.webhook_frame, text="Webhook")
        self._build_webhook_tab()

        # Biomes tab
        self.biome_frame = tb.Frame(notebook)
        notebook.add(self.biome_frame, text="Biome Alerts")
        self._build_biome_tab()

        # Anti-AFK tab
        self.afk_frame = tb.Frame(notebook)
        notebook.add(self.afk_frame, text="Credits")
        self._build_credits_tab()

        # Logs tab
        self.log_frame = tb.Frame(notebook)
        notebook.add(self.log_frame, text="Logs")
        self._build_log_tab()

    def _build_general_tab(self):
        # Enable Aura Detection
        self.aura_var = tb.BooleanVar(value=self.config.get("enable_aura_detection", "0") == "1")
        cb_aura = tb.Checkbutton(self.general_frame, text="Enable Aura Detection",
                                 variable=self.aura_var, bootstyle="round-toggle")
        cb_aura.pack(anchor=W, padx=15, pady=8)

        # Enable Biome Detection
        self.biome_detect_var = tb.BooleanVar(value=self.config.get("biome_detection", "0") == "1")
        cb_biome = tb.Checkbutton(self.general_frame, text="Enable Biome Detection",
                                  variable=self.biome_detect_var, bootstyle="round-toggle")
        cb_biome.pack(anchor=W, padx=15, pady=8)

        # Control buttons for tracker
        btn_frame = tb.Frame(self.general_frame)
        btn_frame.pack(pady=16)


    def _build_webhook_tab(self):
        webhook = self.config.get("discord", {}).get("webhook", {})
        # Enabled
        self.webhook_enabled_var = tb.BooleanVar(value=webhook.get("enabled", "0") == "1")
        cb_enable = tb.Checkbutton(self.webhook_frame, text="Enable Webhook",
                                   variable=self.webhook_enabled_var, bootstyle="round-toggle")
        cb_enable.pack(anchor=W, padx=15, pady=8)

        # URL
        tb.Label(self.webhook_frame, text="Webhook URL:").pack(anchor=W, padx=15)
        self.webhook_url_entry = tb.Entry(self.webhook_frame, width=60)
        self.webhook_url_entry.insert(0, webhook.get("url", ""))
        self.webhook_url_entry.pack(anchor=W, padx=15, pady=4, fill=X)

        # Ping ID
        tb.Label(self.webhook_frame, text="User ID to ping (optional):").pack(anchor=W, padx=15)
        self.ping_id_entry = tb.Entry(self.webhook_frame, width=60)
        self.ping_id_entry.insert(0, webhook.get("ping_id", ""))
        self.ping_id_entry.pack(anchor=W, padx=15, pady=4, fill=X)

        # Private server link
        tb.Label(self.webhook_frame, text="Private Server Link (for biome alerts):").pack(anchor=W, padx=15)
        self.ps_link_entry = tb.Entry(self.webhook_frame, width=60)
        self.ps_link_entry.insert(0, webhook.get("ps_link", ""))
        self.ps_link_entry.pack(anchor=W, padx=15, pady=4, fill=X)

        # Test button
        test_btn = tb.Button(self.webhook_frame, text="Test Webhook", command=self._test_webhook,
                             bootstyle="info")
        test_btn.pack(pady=8)

    def _build_biome_tab(self):
        canvas = tb.Canvas(self.biome_frame)
        scrollbar = tb.Scrollbar(self.biome_frame, orient=VERTICAL, command=canvas.yview)
        scrollable_frame = tb.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=LEFT, fill=BOTH, expand=YES, padx=(10, 0), pady=10)
        scrollbar.pack(side=RIGHT, fill=Y, padx=(0, 10), pady=10)

        biome_names = list(self.config.get("biome_alerts", {}).keys())
        biome_names.sort()
        self.biome_vars = {}
        for name in biome_names:
            var = tb.BooleanVar(value=self.config["biome_alerts"].get(name, "0") == "1")
            cb = tb.Checkbutton(scrollable_frame, text=name, variable=var, bootstyle="round-toggle")
            cb.pack(anchor=W, padx=20, pady=2)
            self.biome_vars[name] = var

    def _build_credits_tab(self):
        self.credits_frame = tb.Frame(self.afk_frame)
        self.credits_frame.pack(fill=BOTH, expand=YES, padx=15, pady=15)
        credits_text = (
            "Elixir Macro (macOS)\n\n" \
            "Made by Spacedev (spacedev0572)\n\n" \
            "Special thanks to:\n" \
            "@vamp (vamp12340) for making the new biome previews!\n")
        label = tb.Label(self.credits_frame, text=credits_text, justify=CENTER, font=("Segoe UI", 11))
        label.pack(expand=True)

    def _build_log_tab(self):
        frame = tb.Frame(self.log_frame)
        frame.pack(fill=BOTH, expand=YES)

        self.log_text = tb.Text(frame, wrap="word", state=DISABLED, font=("Courier", 10))
        scroll = tb.Scrollbar(frame, orient=VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side=LEFT, fill=BOTH, expand=YES)
        scroll.pack(side=RIGHT, fill=Y)

        clear_btn = tb.Button(self.log_frame, text="Clear Log", command=self._clear_log, bootstyle="secondary")
        clear_btn.pack(pady=6)

    def _create_statusbar(self):
        self.statusbar = tb.Label(self.root, text="Ready", bootstyle="inverse", anchor=W)
        self.statusbar.pack(side=BOTTOM, fill=X)

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

    # Tracker controls
    def _start_tracking(self):
        self._save_config()
        self.tracker_controller.start()
        #self.start_btn.configure(state=DISABLED)
        #self.stop_btn.configure(state=NORMAL)
        self.statusbar.configure(text="Tracking active")

    def _stop_tracking(self):
        self.tracker_controller.stop()
        #self.start_btn.configure(state=NORMAL)
        #self.stop_btn.configure(state=DISABLED)
        self.statusbar.configure(text="Tracking stopped")

    def _save_config(self):
        # General
        self.config["enable_aura_detection"] = "1" if self.aura_var.get() else "0"
        self.config["biome_detection"] = "1" if self.biome_detect_var.get() else "0"

        # Webhook
        webhook_enabled = "1" if self.webhook_enabled_var.get() else "0"
        if "discord" not in self.config:
            self.config["discord"] = {}
        if "webhook" not in self.config["discord"]:
            self.config["discord"]["webhook"] = {}
        self.config["discord"]["webhook"]["enabled"] = webhook_enabled
        self.config["discord"]["webhook"]["url"] = self.webhook_url_entry.get().strip()
        self.config["discord"]["webhook"]["ping_id"] = self.ping_id_entry.get().strip()
        self.config["discord"]["webhook"]["ps_link"] = self.ps_link_entry.get().strip()

        # Biome alerts
        for name, var in self.biome_vars.items():
            self.config["biome_alerts"][name] = "1" if var.get() else "0"

        save_config(self.config)

        # Update running controllers
        self.tracker_controller.update_config(self.config)
        self.statusbar.configure(text="Configuration saved")

    def _test_webhook(self):
        webhook_url = self.webhook_url_entry.get().strip()
        if not webhook_url:
            messagebox.showerror("Error", "Please enter a webhook URL")
            return
        payload = {
            "content": "Test message from Elixir Macro",
            "embeds": [{
                "title": "Test",
                "description": "If you see this, the webhook is working!",
                "color": 0x00FF00
            }]
        }
        try:
            response = requests.post(webhook_url, json=payload, timeout=5)
            response.raise_for_status()
            messagebox.showinfo("Success", "Webhook test sent successfully!")
        except Exception as e:
            messagebox.showerror("Webhook Error", f"Failed to send test: {e}")

    def _show_about(self):
        messagebox.showinfo("About",
                            f"Elixir Macro\nVersion {CURRENT_VERSION}\n\n"
                            "Biome/Aura tracker + Anti-AFK for Roblox.\n"
                            "Logs are saved in the 'logs' folder.\n"
                            "Settings are stored in ~/Library/Application Support/ElixirMacro/ (macOS).\n\n"
                            "Made by vexsyx")

    def _on_close(self):
        self._stop_tracking()
        #self._stop_afk()
        self.root.destroy()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = App()
    app.run()
