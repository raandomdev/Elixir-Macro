import os
import re
import json
import requests
import time
import logging
import asyncio
from pathlib import Path
import discord_webhook as discord
from datetime import datetime
from data import config as ok
ok.config_data = ok.read_config()

class BiomeTracker:
    def __init__(self):
        self.biomes = self._load_biome_data()
        self.auras = self._load_aura_data()
        #self.merchant = self._load_merchant_data()
        self.is_merchant = False
        self.merchant_name = ""
        self.current_biome = None
        self.biome_counts = {b["name"]: 0 for b in self.biomes.values()}
        self.config = self._load_config()
        self.webhook_url = ok.config_data['discord']['webhook']['url']
        self.private_server_link = ok.config_data['discord']['webhook']['ps_link']
        self.biome_alerts = self.config.get("biome_alerts", {})
        self.user_id = ok.config_data['discord']['webhook']['ping_id']
        self.last_aura = None
        self.last_processed_position = 0
        self.last_sent_biome = None
        self.last_sent_aura = None
        self.create_log_file()
        self.multi_instance = True if ok.config_data['settings']['multi_instance'] == '1' else False
        # control flag for asynchronous monitoring loop
        self._running = False

    def create_log_file(self):
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%m-%d-%Y %H-%M-%S")
        log_filename = log_dir / f"{timestamp} biome_tracker.log"

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(log_filename), logging.StreamHandler()],
            force=True,
        )

    def _load_config(self):
        try:
            with open(f"{ok.parent_path()}\\config.json") as f:
                config = json.load(f)
                for biome in self._load_biome_data():
                    if biome not in config.get("biome_alerts", {}):
                        config["biome_alerts"][biome] = False
                return config
        except Exception as e:
            logging.error(f"Config load error: {str(e)}")
            return {}

    def _load_biome_data(self):
        try:
            response = requests.get("https://raw.githubusercontent.com/vexsyx/OysterDetector/refs/heads/main/data/biome-data.json")
            response.raise_for_status()
            biome_list = response.json()
            logging.info(f"Loaded biome data from {response.url}")
            return {biome["name"]: biome for biome in biome_list}
        except Exception as e:
            logging.error(f"Failed to load biome data: {str(e)}")
            return {}

    def _load_aura_data(self):
        try:
            response = requests.get("https://raw.githubusercontent.com/vexsyx/OysterDetector/refs/heads/main/data/aura-data.json")
            response.raise_for_status()
            aura_list = response.json()
            logging.info(f"Loaded aura data from {response.url}")
            return {aura["identifier"]: aura for aura in aura_list}
        except Exception as e:
            logging.error(f"Failed to load aura data: {str(e)}")
            return {}

    #def _load_merchant_data(self):
    #    try:
    #        response = requests.get("https://raw.githubusercontent.com/Goldfish-cool/Goldens-Macro/refs/heads/data/merchant-data.json")
    #        response.raise_for_status()
    #        merchant_list = response.json()
    #        logging.info(f"Merchant data loaded from {response.url}")
    #        return {merchant["identifier"]: merchant for merchant in merchant_list}
    #    except Exception as e:
    #        logging.error(f"Failed to load merchant data: {str(e)}")
    #        return {}

    async def monitor_logs(self):
        """Begin monitoring the Roblox log files until stopped via `stop_monitoring`.
        This method is intended to be scheduled as an asyncio task (``create_task``)
        by the caller. It will exit its loop when ``self._running`` becomes False.
        """
        self._running = True
        log_dir = Path(os.getenv("LOCALAPPDATA")) / "Roblox" / "logs"

        latest_log = max(log_dir.glob("*.log"), key=os.path.getmtime, default=None)
        if latest_log:
            self.last_processed_position = latest_log.stat().st_size
        else:
            self.last_processed_position = 0

        while self._running:
            try:
                latest_log = max(
                    log_dir.glob("*.log"), key=os.path.getmtime, default=None
                )
                if not latest_log:
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
                logging.error(f"Log monitoring error: {str(e)}")
                await asyncio.sleep(5)

    async def _process_log_entry(self, line):
        try:
            if ok.config_data["biome_detection"]["enabled"] == "1":
                self._detect_biome_change(line)
            elif ok.config_data["enabled_dectection"] == "1":
                self._check_aura_equipped(line)
            else:
                return
        except Exception as e:
            logging.error(f"Log processing error: {str(e)}")

    def _detect_biome_change(self, line):
        if "[BloxstrapRPC]" not in line:
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
            logging.error(f"Biome detection error: {str(e)}")

    def _handle_new_biome(self, biome_name):
        try:
            self.current_biome = biome_name
            self.biome_counts[biome_name] += 1
            logging.info(f"Biome detected: {biome_name}")

            if biome_name != self.last_sent_biome:
                biome_data = self.biomes[biome_name]

                if biome_name in ["GLITCHED", "DREAMSPACE"]:
                    self._send_webhook(
                        title=f"Biome Detected",
                        description=f"# - {biome_name}",
                        color=int(biome_data["visuals"]["primary_hex"], 16),
                        thumbnail=biome_data["visuals"]["preview_image"],
                        urgent=True,
                        is_aura=False,
                    )
                else:
                    if ok.config_data['biome_alerts'][biome_name] == "1":
                        self._send_webhook(
                            title=f"Biome Detected",
                            description=f"# - {biome_name}",
                            color=int(biome_data["visuals"]["primary_hex"], 16),
                            thumbnail=biome_data["visuals"]["preview_image"],
                            urgent=False,
                            is_aura=False,
                        )

                self.last_sent_biome = biome_name

        except KeyError:
            logging.warning(f"Received unknown biome: {biome_name}")
        except Exception as e:
            logging.error(f"Biome handling error: {str(e)}")

    def _check_aura_equipped(self, line):
        if "[BloxstrapRPC]" not in line:
            return

        try:
            json_str = line.split("[BloxstrapRPC] ")[1]
            data = json.loads(json_str)
            state = data.get("data", {}).get("state", "")

            match = re.search(r'Equipped "(.*?)"', state)
            if match and (aura_name := match.group(1)) in self.auras:
                self._process_aura(aura_name)
        except (IndexError, json.JSONDecodeError):
            pass
        except Exception as e:
            logging.error(f"Aura check error: {str(e)}")

    def _process_aura(self, aura_name):
        try:
            aura = self.auras[aura_name]
            aura_data = aura["properties"]
            visuals = aura.get("visuals", {})
            thumbnail = visuals.get("preview_image")

            base_chance = aura_data["base_chance"]
            rarity = base_chance
            obtained_biome = None

            biome_amplifier = aura_data.get("biome_amplifier", ["None", 1])
            
            if biome_amplifier[0] != "None" and (
                self.current_biome == biome_amplifier[0] 
                or self.current_biome == "GLITCHED"
            ):
                rarity /= biome_amplifier[1]
                obtained_biome = self.current_biome

            rarity = int(rarity)

            if aura_data.get("rank") == "challenged":
                color = 0x808080      # Grey (challenged)
            else:
                if rarity <= 999:
                    color = 0xFFFFFF  # White (basic)
                elif rarity <= 9999:
                    color = 0xFFC0CB  # Very light pink (epic)
                elif rarity <= 99998:
                    color = 0xFFA500  # Orangeish/brown (unique)
                elif rarity <= 999999:
                    color = 0xFFFF00  # Yellow (legendary)
                elif rarity <= 9999999:
                    color = 0xFF1493  # Pink (mythic)
                elif rarity <= 99999998:
                    color = 0x00008B  # Darkish blue (exalted)
                elif rarity <= 999999999:
                    color = 0x8B0000  # Blood red (glorious)
                else:
                    color = 0x00FFFF  # Cyan (transcendent)

            fields = []
            if base_chance == 0:
                rarity_str = "Unobtainable"
            else:
                rarity_str = f"1 in {rarity:,}"
            fields.append({"name": "Rarity", "value": rarity_str, "inline": True})
            
            if obtained_biome:
                fields.append({"name": "Obtained From", "value": obtained_biome, "inline": True})

            logging.info(f"Aura equipped: {aura_name} (1 in {rarity:,})")

            if aura_name != self.last_sent_aura:
                self._send_webhook(
                    title=f"**Aura Detection**",
                    description=f"## {time.strftime('[%I:%M:%S %p]')} \n ## > Aura found/last equipped: {aura_name}",
                    color=color,
                    thumbnail=thumbnail,
                    is_aura=True,
                    fields=fields,
                    ended=False
                )
                self.last_sent_aura = aura_name

        except KeyError as e:
            logging.warning(f"Missing aura property: {str(e)}")
        except ZeroDivisionError:
            logging.error("Invalid biome amplifier value (division by zero)")
        except Exception as e:
            logging.error(f"Aura processing error: {str(e)}")

    def _detect_joined(self, line):
        # checks if friends or anyone has joined the server - ty hsm
        if "[ExpChat/mountClientApp (Trace)]" not in line:
            return
        
        try:
            json_str = line.split("[ExpChat/mountClientApp (Trace)] ")[1]
            match = re.search(r'- Player added: *?(\w+)', json_str)
            if match and (player_name := match.group(1)):
                self._process_player(player_name)

        except (IndexError, json.JSONDecodeError):
            logging.warning("Failed to parse joined player information.")
        except Exception as e:
            logging.error(f"Joined check error: {str(e)}")

    def _process_player(self, player_name):
        self._send_webhook(
            title="**Joined Detection!**",
            description=f"Player {player_name} has joined the experience.",
            color=0xFFFFFF,
            thumbnail=None,
            urgent=False,
            is_aura=True,
            fields=None
        )

    def _send_webhook(
        self, title, description, color, thumbnail=None, urgent=False, is_aura=False, fields=None):
        if not self.webhook_url:
            logging.error(f"Please specify a Webhook URL in the config")
            return

        try:
            current_time = datetime.now().isoformat()

            embed = {
                "title": title,
                "description": description,
                "color": color,
                "timestamp": current_time,
                "footer": {"text": "Goldens Sol's Macro", "icon_url": "https://goldfish-cool.github.io/Goldens-Macro/golden_pfp.png"},
            }

            if fields is not None:
                embed["fields"] = fields
            else:
                if not is_aura:
                    ps_link = self.private_server_link
                    if not ps_link or ps_link.strip() == "":
                        ps_link = "(lol get a load of this guy fr fr)."
                    embed["fields"] = [{"name": "Private Server Link", "value": ps_link}]

            if thumbnail:
                embed["thumbnail"] = {"url": thumbnail}

            payload = {
                "content": ("@everyone " if urgent else "") + (f"<@{self.user_id}> " if is_aura else ""),
                "embeds": [embed]
}
            #logging.info(f"Attempting to send webhook: {payload}")

            async def send():
                try:
                    response = await asyncio.to_thread(
                        requests.post, self.webhook_url, json=payload, timeout=5
                    )
                    if response.status_code == 429:
                        retry_after = response.json().get("retry_after", 5)
                        logging.warning(f"Rate limited - retrying in {retry_after}s")
                        await asyncio.sleep(retry_after)
                        await send()
                    response.raise_for_status()
                except Exception as e:
                    logging.error(f"Webhook failed: {str(e)}")

            asyncio.create_task(send())
        except Exception as e:
            logging.error(f"Webhook creation error: {str(e)}")

    def stop_monitoring(self):
        """Signal the log-monitoring loop started by :meth:`monitor_logs` to exit."""
        self._running = False

    def update_biome_counts(self):
        biomes = {
            "NORMAL": 0,
            "WINDY": 0, 
            "SNOWY": 0, 
            "RAINY": 0,
            "HELL": 0, 
            "SAND STORM": 0,
            "NULL": 0, 
            "STARFALL": 0, 
            "CORRUPTION": 0, 
            "GLITCHED": 0,
            "DREAMSPACE": 0
        }
        return biomes
    
    def log(self, message): 
        try:
            logging.info(msg=message)
        except Exception as e:
            print(f"Error with logging: {e}")
