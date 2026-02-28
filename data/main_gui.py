import os, sys, json
import time
from time import sleep
from tkinter import messagebox, filedialog, ttk
import tkinter as tk
import sv_ttk
import discord_webhook
from data import config
import keyboard, mouse
from data import Tracker
from data import ocr_engine
import asyncio
import time
from PIL import Image, ImageGrab, ImageEnhance
import threading
from datetime import datetime, timedelta
import webbrowser
import pyautogui as auto
try:
    if sys.platform == "darwin":
        import mouse, keyboard
        from pynput.keyboard import Key
        print("macOS detected.. using mouse, keyboard imports.")
    else:
        try:
            from ahk import AHK
            ahk = AHK()
            print("Windows detected.. using AutoHotkey import.")
        except Exception as ahk_err:
            print(f"AHK init failed: {ahk_err}. Will use keyboard/mouse fallback.")
            ahk = None
except Exception as e:
    messagebox.showerror("Error", f"Error on loading basic imports: {str(e)}\n\nPlease redownload this software and try again.\nIf this continues, please report this to Golden (@spacedev0527).")
    sys.exit(1)

# Use enhanced OCR engine
perform_ocr = ocr_engine.perform_ocr
search_text_in_ocr = ocr_engine.search_text_in_ocr
check_ocr_text = ocr_engine.check_ocr_text
get_ocr_text = ocr_engine.get_ocr_text
ocr_text = None

def platform_click(x, y, button='left'):
    """Platform-specific click function"""
    if sys.platform == "win32":
        if ahk:
            ahk.click(x, y, coord_mode="Screen")
        else:
            mouse.move(x, y)
            mouse.click(button)
    elif sys.platform == "darwin":
        mouse.move(x, y)
        mouse.click(button)

def platform_key_press(key):
    """Platform-specific key press function"""
    if sys.platform == "win32":
        if ahk:
            ahk.send(key)
        else:
            keyboard.write(key)
    elif sys.platform == "darwin":
        keyboard.write(key)

def platform_key_combo(key):
    """Platform-specific key combination function"""
    if sys.platform == "win32":
        if ahk:
            ahk.send(key)
        else:
            keyboard.write(key)
    elif sys.platform == "darwin":
        try:
            if key == '{Enter}':
                keyboard.press(Key.enter)
                keyboard.release(Key.enter)
            else:
                keyboard.write(key)
        except NameError:
            keyboard.write(key)

DEFAULT_FONT = "Segoe UI"
DEFAULT_FONT_BOLD = "Segoe UI Semibold"
MAX_WIDTH = 1000

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
        self.coord_vars = {}
        self.config_key = config_key
        self.begin_x = None
        self.begin_y = None
        self.end_x = None
        self.end_y = None
        self.tk_var_list = config.generate_tk_list()
        self.main_loop = MainLoop()
        self.tab_control = ttk.Notebook(master=self)
        self.tab_control.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.main_tab = ttk.Frame(self.tab_control)
        self.discord_tab = ttk.Frame(self.tab_control)
        self.crafting_tab = ttk.Frame(self.tab_control)
        self.settings_tab = ttk.Frame(self.tab_control)
        self.merchant_tab = ttk.Frame(self.tab_control)
        self.extras_tab = ttk.Frame(self.tab_control)
        self.credits_tab = ttk.Frame(self.tab_control)

        self.tab_control.add(self.main_tab, text="Main")
        self.tab_control.add(self.discord_tab, text="Discord")
        self.tab_control.add(self.crafting_tab, text="Crafting")
        self.tab_control.add(self.settings_tab, text="Settings")
        self.tab_control.add(self.merchant_tab, text="Merchant")
        self.tab_control.add(self.extras_tab, text="Extras")
        self.tab_control.add(self.credits_tab, text="Credits")

        #self.tab_control.select("Credits")
        self.tab_control.grid(padx=10)

        buttons_frame = ttk.Frame(master=self)
        buttons_frame.grid(row=1, column=0, pady=(5, 8), padx=6, sticky="s")

        start_button = ttk.Button(master=buttons_frame, text="Start - F1", command=self.start, width=15)
        start_button.grid(row=0, column=0, padx=4, pady=4)
        
        stop_button = ttk.Button(master=buttons_frame, text="Stop - F2", command=self.stop, width=15)
        stop_button.grid(row=0, column=1, padx=4, pady=4)
        
        restart_button = ttk.Button(master=buttons_frame, text="Restart - F3", command=self.restart, width=15)
        restart_button.grid(row=0, column=2, padx=4, pady=4)

        keyboard.add_hotkey("F1", self.start)
        keyboard.add_hotkey("F2", self.stop)
        keyboard.add_hotkey("F3", self.restart)

        self.setup_main_tab()
        self.setup_discord_tab()
        self.setup_crafting_tab()
        self.setup_settings_tab()
        self.setup_merchant_tab()
        self.setup_extras_tab()
        self.setup_credits_tab()
    
    def setup_main_tab(self):
        miscalance_frame = ttk.LabelFrame(master=self.main_tab)
        miscalance_frame.grid(row=0, column=0, sticky="w", padx=(1, 1))
        
        miscalance_title = ttk.Label(master=miscalance_frame, text="Miscellaneous", font=("Segoe UI Semibold", 20, "bold"))
        miscalance_title.grid(row=0, column=0)
        
        obby = ttk.Checkbutton(master=miscalance_frame, text="Do Obby (30% Luck Boost Every 2 Mins)", 
                              variable=self.tk_var_list['obby']['enabled'],
                              command=self.save_config)
        obby.grid(row=2, column=0, padx=5, pady=5, sticky="w")
        
        chalice = ttk.Checkbutton(master=miscalance_frame, text="Auto Chalice", 
                                variable=self.tk_var_list['chalice']['enabled'], state="disabled",
                                command=self.save_config)
        chalice.grid(row=3, column=0, padx=5, pady=5, sticky="w")

        auto_equip_title = ttk.Label(master=miscalance_frame, text="Auto Equip", font=("Segoe UI Semibold", 20, "bold"))
        auto_equip_title.grid(row=0, column=1)
        
        enable_auto_equip = ttk.Checkbutton(master=miscalance_frame, text="Enable Auto Equip", 
                                          variable=self.tk_var_list['auto_equip']['enabled'],
                                          command=self.save_config)
        enable_auto_equip.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        auto_equip_gui = ttk.Button(master=miscalance_frame, text="Configure Search", width=25, 
                                  command=self.auto_equip_window)
        auto_equip_gui.grid(column=1, row=3, padx=5, pady=5)
        
        paths_frame = ttk.LabelFrame(master=self.main_tab)
        paths_frame.grid(row=1, column=0, sticky="w", padx=(1, 1))
        enable_collect_items = ttk.Checkbutton(master=paths_frame, text="Enable Item Collection", 
                                             variable=self.tk_var_list['item_collecting']['enabled'],
                                             command=self.save_config)
        enable_collect_items.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        assign_clicks = ttk.Button(master=paths_frame, text="Assign Clicks", 
                                 command=self.assign_clicks_gui)
        assign_clicks.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        pathin_ui = ttk.Button(master=paths_frame, text="Paths",
                                  command=self.pathing_ui)
        pathin_ui.grid(row=0, column=2, sticky="w", padx=5, pady=5)

    def setup_discord_tab(self):
        def test_webhook():
            if 'discord.com' in config.config_data["discord"]["webhook"]["url"] and 'https://' in config.config_data["discord"]["webhook"]["url"]:
                webhook = discord_webhook.DiscordWebhook(url=config.config_data["discord"]["webhook"]["url"])
                embed = discord_webhook.DiscordEmbed(
                    title="Webhook Test!",
                    description="This webhook is now correctly configured to Elixir Macro!"
                )
                embed.set_color(0x00ff00)
                webhook.add_embed(embed)
                webhook.execute()
        webhook_frame = ttk.Frame(master=self.discord_tab)
        webhook_frame.grid(row=0, column=0, sticky="news", padx=5, pady=5)
        
        webhook_title = ttk.Label(master=webhook_frame, text="Webhook", 
                                font=("Segoe UI Semibold", 20, "bold"))
        webhook_title.grid(row=0, column=0, padx=5, pady=5)
        
        webhook_enable = ttk.Checkbutton(master=webhook_frame, text="Enable Webhook", 
                                       variable=self.tk_var_list['discord']['webhook']['enabled'],
                                       command=self.save_config)
        webhook_enable.grid(row=0, column=1, padx=5, pady=2, sticky="w")
        
        webhook_test = ttk.Button(master=webhook_frame, text="Test Webhook", command=test_webhook)
        webhook_test.grid(row=6, column=2, padx=5, pady=2, sticky="w")

        webhook_url_label = ttk.Label(master=webhook_frame, text="Webhook URL")
        webhook_url_label.grid(row=2, column=0, padx=5, pady=2, sticky="w")
        
        webhook_url = ttk.Entry(master=webhook_frame, width=30,
                              textvariable=self.tk_var_list['discord']['webhook']['url'])
        webhook_url.grid(row=2, column=1, padx=5, pady=2)
        webhook_url.bind("<FocusOut>", lambda e: self.save_config())
        
        ping_id_label = ttk.Label(master=webhook_frame, text="User/Role ID to ping")
        ping_id_label.grid(row=4, column=0, padx=5, pady=2, sticky="w")
        
        ping_id = ttk.Entry(master=webhook_frame, width=30,
                          textvariable=self.tk_var_list['discord']['webhook']['ping_id'])
        ping_id.grid(row=4, column=1, padx=5, pady=2)
        ping_id.bind("<FocusOut>", lambda e: self.save_config())

        ps_link = ttk.Label(master=webhook_frame, text="Private Server Link:")
        ps_link.grid(row=5, column=0, padx=5, pady=2, sticky="w")
        
        ps_link_entry = ttk.Entry(master=webhook_frame, width=30,
                                textvariable=self.tk_var_list['discord']['webhook']['ps_link'])
        ps_link_entry.grid(row=5, column=1, padx=5, pady=2)
        
        inventory_shots = ttk.Checkbutton(master=webhook_frame, text="Inventory Screenshots", 
                                        variable=self.tk_var_list['invo_ss']['enabled'],
                                        command=self.save_config)
        inventory_shots.grid(row=6, column=0, padx=5, pady=5, sticky="w")
        
        duration = ttk.Label(master=webhook_frame, text="Duration:")
        duration.grid(row=6, column=1, padx=5, pady=5, sticky="w")
        
        inventory_shots_entry = ttk.Entry(master=webhook_frame, 
                                        textvariable=self.tk_var_list['invo_ss']['duration'], 
                                        width=6)
        inventory_shots_entry.grid(row=6, column=1, padx=5, pady=2)

    def setup_crafting_tab(self):
        crafting_frame = ttk.Frame(master=self.crafting_tab)
        crafting_frame.grid(row=0, column=0, sticky="n", padx=(1, 1))
        
        crafting_title = ttk.Label(master=crafting_frame, text="Potion Crafting", 
                                 font=("Segoe UI Semibold", 20, "bold"))
        crafting_title.grid(row=0, column=1, columnspan=4)
        
        crafting_enabled = ttk.Checkbutton(master=crafting_frame, text="Enable Potion Crafting", 
                                         variable=self.tk_var_list['potion_crafting']['enabled'],
                                         command=self.save_config)
        crafting_enabled.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        potion_list = ['None', 'Fortune', 'Speed Potion', 'Lucky Potion', 'Heavenly', 'Godly', 'Potion of bound']

        option1_var = self.tk_var_list['potion_crafting']['item_1']
        option2_var = self.tk_var_list['potion_crafting']['item_2']
        option3_var = self.tk_var_list['potion_crafting']['item_3']

        option1 = ttk.OptionMenu(crafting_frame, option1_var, potion_list[0], *potion_list)
        option1.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        
        option2 = ttk.OptionMenu(crafting_frame, option2_var, potion_list[0], *potion_list)
        option2.grid(row=4, column=1, padx=5, pady=5, sticky="w")
        
        option3 = ttk.OptionMenu(crafting_frame, option3_var, potion_list[0], *potion_list)
        option3.grid(row=5, column=1, padx=5, pady=5, sticky="w")

        option1_check = ttk.Checkbutton(master=crafting_frame, text="Craft Potion 1", 
                                      variable=self.tk_var_list['potion_crafting']['craft_potion_1'],
                                      command=self.save_config)
        option1_check.grid(row=3, column=2, padx=5, pady=5, sticky="w")
        
        option2_check = ttk.Checkbutton(master=crafting_frame, text="Craft Potion 2", 
                                      variable=self.tk_var_list['potion_crafting']['craft_potion_2'],
                                      command=self.save_config)
        option2_check.grid(row=4, column=2, padx=5, pady=5, sticky="w")
        
        option3_check = ttk.Checkbutton(master=crafting_frame, text="Craft Potion 3", 
                                      variable=self.tk_var_list['potion_crafting']['craft_potion_3'],
                                      command=self.save_config)
        option3_check.grid(row=5, column=2, padx=5, pady=5, sticky="w")
        
        auto_add = ttk.Checkbutton(master=crafting_frame, text="Auto Add Swicher", 
                                 variable=self.tk_var_list['potion_crafting']['temporary_auto_add'],
                                      command=self.save_config)
        auto_add.grid(row=2, column=2, padx=5, pady=5, sticky="w")
        
        potion_crafting = ttk.Checkbutton(master=crafting_frame, text="Potion Crafting", 
                                         variable=self.tk_var_list['potion_crafting']['potion_crafting'],
                                         command=self.save_config)
        potion_crafting.grid(row=2, column=3, padx=5, pady=5, sticky="w")

        crafting_clicks = ttk.Button(master=crafting_frame, text="Assign Crafting", 
                                   command=self.crafting_clicks)
        crafting_clicks.grid(row=2, column=4, padx=5, pady=5, sticky="w")
        
        crafting_interval = ttk.Label(master=crafting_frame, text="Auto add potion (every loop):")
        crafting_interval.grid(row=3, column=3, padx=5, pady=5, sticky="w")
        
        crafting_entry = ttk.Entry(master=crafting_frame, 
                                 textvariable=self.tk_var_list['potion_crafting']['current_temporary_auto_add'], 
                                 width=12)
        crafting_entry.grid(row=3, column=4, padx=5, pady=2, sticky="w")
        
        crafting_interval_time = ttk.Label(master=crafting_frame, text="Crafting interval (minutes):")
        crafting_interval_time.grid(row=4, column=3, padx=5, pady=2, sticky="w")
        
        interval_entry = ttk.Entry(master=crafting_frame, 
                                 textvariable=self.tk_var_list['potion_crafting']['crafting_interval'], 
                                 width=6)
        interval_entry.grid(row=4, column=4, padx=5, pady=2, sticky="w")

    def setup_settings_tab(self):
        settings_frame = ttk.LabelFrame(master=self.settings_tab)
        settings_frame.grid(row=0, column=0, sticky="n", padx=(1, 1))
        
        settings_title = ttk.Label(master=settings_frame, text="General", 
                                 font=("Segoe UI Semibold", 20, "bold"))
        settings_title.grid(row=0, column=0)
        
        vip_settings = ttk.Checkbutton(master=settings_frame, text="VIP Game Pass", 
                                     variable=self.tk_var_list['settings']['vip_mode'],
                                      command=self.save_config)
        vip_settings.grid(row=2, column=0, padx=5, pady=5, sticky="w")
        
        vip_mode = ttk.Checkbutton(master=settings_frame, text="VIP+ Mode", 
                                 variable=self.tk_var_list['settings']['vip+_mode'],
                                      command=self.save_config)
        vip_mode.grid(row=3, column=0, padx=5, pady=5, sticky="w")
        
        azerty_layout = ttk.Checkbutton(master=settings_frame, text="Azerty Keyboard Layout", 
                                      variable=self.tk_var_list['settings']['azerty_mode'],
                                      command=self.save_config)
        azerty_layout.grid(row=4, column=0, padx=5, pady=5, sticky="w")

        player_joined = ttk.Checkbutton(master=settings_frame, text="Alert when players join",
                                        variable=self.tk_var_list['settings']['join_server'],
                                        command=self.save_config)
        player_joined.grid(row=5, column=0, padx=5, pady=5, sticky="w")
        
        reset_check = ttk.Checkbutton(master=settings_frame, text="Reset and Align", 
                                    variable=self.tk_var_list['settings']['reset'],
                                      command=self.save_config)
        reset_check.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        claim_quest = ttk.Checkbutton(master=settings_frame, text="Claim Quests (30 minutes)", 
                                    variable=self.tk_var_list['claim_daily_quests'],
                                      command=self.save_config)
        claim_quest.grid(row=3, column=1, padx=5, pady=5, sticky="w")

    def setup_merchant_tab(self):
        merchant_frame = ttk.LabelFrame(master=self.merchant_tab, text="Mari")
        merchant_frame.grid(row=0, column=0, sticky="w", padx=(1, 1))

        mari_settings = ttk.Button(state="disabled", master=merchant_frame, text="Mari Settings", command=self.open_mari_settings).grid(row=2, column=3, padx=5, pady=5, sticky="w")
        ping_mari = ttk.Checkbutton(state="disabled", master=merchant_frame, text="Ping if Mari? (User Ping Id/Role Ping ID: &roleid):", 
                                   variable=self.tk_var_list['mari']['ping_enabled'],
                                   command=self.save_config,
                                   onvalue='1', offvalue='0').grid(row=2, column=1, padx=5, pady=5, sticky="w")
        mari_ping_entry = ttk.Entry(state="disabled", master=merchant_frame, textvariable=self.tk_var_list['mari']['ping_id'], width=6).grid(row=2, column=2, padx=5, pady=5, sticky="w")
        
        jester_frame = ttk.LabelFrame(master=self.merchant_tab, text="Jester")
        jester_frame.grid(row=1, column=0, sticky="n", padx=(1, 1))
        ping_jester = ttk.Checkbutton(state="disabled", master=jester_frame, text="Ping if Jester? (User Ping Id/Role Ping ID: &roleid):",
                                      variable=self.tk_var_list['jester']['ping_enabled'],
                                      command=self.save_config,
                                      onvalue='1', offvalue='0').grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ping_jester_entry = ttk.Entry(state="disabled", master=jester_frame, textvariable=self.tk_var_list['jester']['ping_id'], width=6).grid(row=2, column=2, padx=5, pady=5, sticky="w")
        jester_settings = ttk.Button(state="disabled", master=jester_frame, text="Jester Settings", command=self.open_jester_settings).grid(row=2, column=3, padx=5, pady=5, sticky="w")

        merchant_wh_frame = ttk.LabelFrame(master=self.merchant_tab, text="Merchant")
        merchant_wh_frame.grid(row=2, column=0, sticky="w", padx=(1, 1))

        merchant_webhook = ttk.Checkbutton(state="disabled", master=merchant_wh_frame, text="Enable Merchant Teleporter", 
                                           variable=self.tk_var_list['settings']['merchant']['enabled'],
                                           command=self.save_config, 
                                           onvalue='1', offvalue='0').grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        duration_label = ttk.Label(master=merchant_wh_frame, text="Duration:").grid(row=2, column=2, padx=5, pady=5, sticky="w")
        merchant_time = ttk.Entry(state="disabled", master=merchant_wh_frame, textvariable=self.tk_var_list['settings']['merchant']['duration'], 
                                  width=6)
        merchant_time.grid(row=2, column=3, padx=5, pady=5, sticky="w")
        merchant_time.bind("<FocusOut>", lambda e: self.save_config())

        merchant_calibration_button = ttk.Button(state="disabled", master=merchant_wh_frame, text="Merchant Calibration", command=self.open_merchant_calibration).grid(row=3, column=1, padx=5, pady=5, sticky="w")

    def setup_extras_tab(self):
        items_stuff = ttk.Frame(master=self.extras_tab)
        items_stuff.grid(row=0, column=0, sticky="n", padx=(5, 0))
        
        items_title = ttk.Label(master=items_stuff, text="Item Scheduler", 
                              font=("Segoe UI Semibold", 20, "bold"))
        items_title.grid(row=0, padx=5)
        
        enable_items = ttk.Checkbutton(master=items_stuff, text="Enable Item Scheduler", 
                                      variable=self.tk_var_list['item_scheduler_item']['enabled'],
                                      command=self.save_config)
        enable_items.grid(row=2, column=0, padx=5, pady=5, sticky="w")
        
        scheduler_items_list = ['None', 'Merchant Tracker', 'Fortune I', 'Fortune II', 'Fortune III', 
                              'Speed Potion I', 'Speed Potion II', 'Speed Potion III', 'Lucky Potion I', 
                              'Lucky Potion II', 'Lucky Potion III', 'Heavenly I', 'Heavenly II', 'Warp Potion']
        
        #scheduler_var = self.tk_var_list['item_scheduler_item']['item_name']
        #scheduler_items = ttk.OptionMenu(items_stuff, scheduler_var, scheduler_items_list[0], 
        #                               *scheduler_items_list)
        #scheduler_items.grid(row=3, column=0, padx=5, pady=5, sticky="w")
        scheduler_items = ttk.Entry(master=items_stuff, textvariable=self.tk_var_list['item_scheduler_item']['item_name'], width=20)
        scheduler_items.grid(row=3, column=0, padx=5, pady=5, sticky="w")
        quanity_text = ttk.Label(master=items_stuff, text="Quantity:", justify="left")
        quanity_text.grid(row=4, column=0, padx=5, pady=5, sticky="w")
        
        quanity = ttk.Entry(master=items_stuff, width=6,    
                          textvariable=self.tk_var_list['item_scheduler_item']['item_scheduler_quantity'])
        quanity.grid(row=4, column=1, padx=5, pady=2, sticky="w")

        item_scheduler_time = ttk.Label(master=items_stuff, text="Item Interval:")
        item_scheduler_time.grid(row=5, column=0, padx=5, pady=5, sticky="w")

        item_scheduler_time_entry = ttk.Entry(master=items_stuff, width=6, 
                          textvariable=self.tk_var_list['item_scheduler_item']['interval'])
        item_scheduler_time_entry.grid(row=5, column=1, padx=5, pady=2, sticky="w")

        biome_config = ttk.Frame(master=self.extras_tab)
        biome_config.grid(row=0, column=2, sticky="n", padx=(5, 0))
        
        biome_title = ttk.Label(master=biome_config, text="Detection", 
                              font=("Segoe UI Semibold", 20, "bold"))
        biome_title.grid(row=0, column=0)
        
        enable_biome = ttk.Checkbutton(master=biome_config, text="Enable Biome Detection", 
                                     variable=self.tk_var_list['biome_detection']['enabled'],
                                      command=self.save_config)
        enable_biome.grid(row=2, column=0, padx=5, pady=5, sticky="w")
        enable_detection = ttk.Checkbutton(master=biome_config, text="Enable Aura Detection", 
                                         variable=self.tk_var_list['enabled_dectection'],
                                      command=self.save_config)
        enable_detection.grid(row=3, column=0, padx=5, pady=5, sticky="w")
        
        pings_aura = ttk.Label(master=biome_config, text="Ping Min:", justify="left")
        pings_aura.grid(row=4, column=0, padx=5, pady=5, sticky="w")
        
        min_entry = ttk.Entry(master=biome_config, 
                            textvariable=self.tk_var_list['send_min'], width=8)
        min_entry.grid(row=4, column=1, padx=5, pady=2, sticky="w")
        
        pings_max = ttk.Label(master=biome_config, text="Ping Max:", justify="left")
        pings_max.grid(row=5, column=0, padx=5, pady=5, sticky="w")
        
        max_entry = ttk.Entry(master=biome_config, 
                            textvariable=self.tk_var_list['send_max'], width=8)
        max_entry.grid(row=5, column=1, padx=5, pady=2, sticky="w")

        config_biomes = ttk.Button(master=biome_config, text="Configure Biomes",
                              command=self.set_biome_region)
        config_biomes.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        #themes_frame = ttk.Frame(master=self.extras_tab)
        #themes_frame.grid(row=0, column=1, sticky="nw", padx=(5, 0))
        
        #themes_title = ttk.Label(master=themes_frame, text="Themes", 
        #                       font=("Segoe UI Semibold", 20, "bold"))
        #themes_title.grid(row=0, columnspan=2)

        #available_themes = self.style.theme_names()
        #current_theme = self.style.theme_use()
        
        #change_themes = ttk.Combobox(themes_frame, values=available_themes, state="readonly")
        #change_themes.grid(row=2, padx=5, pady=5, sticky="w", columnspan=2)
        #change_themes.set(current_theme)
        #change_themes.bind('<<ComboboxSelected>>', lambda e: self.change_theme(change_themes.get()))

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
""" 
        credits_label = ttk.Label(master=credits_frame, text=credits_text, font=(("Segoe UI", 10)))
        credits_label.grid(row=1, column=1, rowspan=2, padx=56, pady=(17, 30), sticky="n")

        join_server = ttk.Label(master=credits_frame, text="Join the Server!", 
                              font=("Segoe UI", 14, "underline"), cursor="hand2")
        join_server.grid(row=2, column=0, padx=6, pady=(0, 6))
        join_server.bind("<Button-1>", lambda event: webbrowser.open('https://discord.gg/JsMM299RF7'))
    
    #def change_theme(self, theme_name):
    #    try:
    #        self.style.theme_use(theme_name)
    #        config.config_data['theme'] = theme_name
    #        config.save_config(config.config_data)
    #    except Exception as e:
    #        self.show_message("Theme Error", f"Failed to change theme: {str(e)}", error=True)

    def start(self):
        config.save_tk_list(self.tk_var_list)
        config.save_config(config.config_data)
        self.iconify()
        # Start the multiprocessing method
        self.main_loop.start()
    
    def stop(self):
        config.save_tk_list(self.tk_var_list)
        config.save_config(config.config_data)
        self.deiconify()
        self.main_loop.stop()
        self.lift()
    def restart(self):
        os.execv(sys.executable, ['python', f'"{sys.argv[0]}"'])

    def show_message(self, title="", message="", error=False):
        if error:
            messagebox.showerror(title=title, message=message)
        else:
            messagebox.showinfo(title=title, message=message)

    def open_mari_settings(self):
        self.mari_window = tk.Toplevel()
        self.mari_window.title("Mari Settings")
        self.mari_window.resizable(False, False)
        self.mari_window.attributes('-topmost', True)

        mari_items = [
            "Void Coin",
            "Lucky Penny",
            "Mixed Potion",
            "Lucky Potion",
            "Lucky Potion L",
            "Lucky Potion XL",
            "Speed Potion",
            "Speed Potion L",
            "Speed Potion XL",
            "Gear A",
            "Gear B"
        ]
        numbers = ["1","2","3","4","5","6","7","8","9","10","11"]
        for i, mari_stuff in enumerate(mari_items, start=1):
            if mari_stuff not in self.tk_var_list['mari']['settings']:
                self.tk_var_list['mari']['settings'][mari_stuff] = tk.StringVar(value="0")
            ttk.Checkbutton(master=self.mari_window, text=mari_stuff,
                            variable=self.tk_var_list['mari']['settings'][mari_stuff],
                            command=self.save_config,
                            onvalue='1', offvalue='0').grid(row=i, column=0, padx=5, pady=5, sticky="w")
            
        for i, num in enumerate(numbers, start=1):
            if num not in self.tk_var_list['mari']['settings']:
                self.tk_var_list['mari']['settings'][num] = tk.StringVar(value="0")
            entry = ttk.Entry(master=self.mari_window, textvariable=self.tk_var_list['mari']['settings'][num],
                      width=4)
            entry.grid(row=i, column=1, padx=5, pady=5, sticky="w")
            entry.bind("<FocusOut>", lambda e: self.save_config())
        
    def open_jester_settings(self):
        self.jester_window = tk.Toplevel()
        self.jester_window.title("Jester Settings")
        self.jester_window.resizable(False, False)
        self.jester_window.attributes('-topmost', True) 

        jester_items = [
            "Oblivion Potion",
            "Heavenly Potion",
            "Rune of Everything",
            "Rune of Dust",
            "Rune of Nothing",
            "Rune Of Corruption",
            "Rune Of Hell",
            "Rune of Galaxy",
            "Rune of Rainstorm",
            "Rune of Frost",
            "Rune of Wind",
            "Strange Potion",
            "Lucky Potion",
            "Stella's Candle",
            "Merchant Tracker",
            "Random Potion Sack"
        ]

        for i, jester_settings in enumerate(jester_items, start=1):
            if jester_settings not in self.tk_var_list['jester']['settings']:
                self.tk_var_list['jester']['settings'][jester_settings] = tk.StringVar(value="0")
            ttk.Checkbutton(master=self.jester_window, text=jester_settings,
                            variable=self.tk_var_list['jester']['settings'][jester_settings],
                            command=self.save_config,
                            onvalue='1', offvalue='0').grid(row=i, column=0, padx=5, pady=5, sticky="w")
        
        numbers = ["1","2","3","4","5","6","7","8","9","10","11","12","13","14","15","16"]

        for i, num in enumerate(numbers, start=1):
            if num not in self.tk_var_list['jester']['settings']:
                self.tk_var_list['jester']['settings'][num] = tk.StringVar(value="0")
            entry = ttk.Entry(master=self.jester_window, textvariable=self.tk_var_list['jester']['settings'][num],
                      width=4)
            entry.grid(row=i, column=1, padx=5, pady=5, sticky="w")
            entry.bind("<FocusOut>", lambda e: self.save_config())

    def open_merchant_calibration(self):
        self.merchant_window = tk.Toplevel()
        self.merchant_window.title("Merchant Calibration")
        self.merchant_window.resizable(False, False)
        
        merchant_cali = [
            ("Merchant Open Button", "merchant_open_button"),
            ("Merchant Dialogue Box", "merchant_dialog"),
            ("Amount Button Entry", "merchant_amount_button"),
            ("Purchase Button", "merchant_purchase_button"),
            ("First Item Slot", "merchant_1_slot_button"),
            ("Merchant Name OCR", "merchant_name_ocr"),
            ("Item Name OCR", "merchant_item_name_ocr")
        ]

        for i, (label_text, config_key) in enumerate(merchant_cali, start=1):
            if "ocr" in label_text.lower():
                label = ttk.Label(master=self.merchant_window, text=f"{label_text} (X, Y, W, H):")
                label.grid(row=i, column=0, padx=5, pady=5, sticky="w")

                x_entry = ttk.Entry(master=self.merchant_window, textvariable=self.tk_var_list['clicks'][config_key][0], width=6)
                x_entry.grid(row=i, column=1, padx=5, pady=5)
                
                y_entry = ttk.Entry(master=self.merchant_window, textvariable=self.tk_var_list['clicks'][config_key][1], width=6)
                y_entry.grid(row=i, column=2, padx=5, pady=5)
                
                w_entry = ttk.Entry(master=self.merchant_window, textvariable=self.tk_var_list['clicks'][config_key][2], width=6)
                w_entry.grid(row=i, column=3, padx=5, pady=5)
                
                h_entry = ttk.Entry(master=self.merchant_window, textvariable=self.tk_var_list['clicks'][config_key][3], width=6)
                h_entry.grid(row=i, column=4, padx=5, pady=5)

                merchant_select_button = ttk.Button(master=self.merchant_window, text="Assign Click! (Drag your mouse)",
                                    command=lambda k=config_key, x=x_entry, y=y_entry, w=w_entry, h=h_entry: 
                                    self.start_capture_thread(k, x, y, w, h))
            else:
                label = ttk.Label(master=self.merchant_window, text=f"{label_text} (X, Y):")
                label.grid(row=i, column=0, padx=5, pady=5, sticky="w")

                x_entry = ttk.Entry(master=self.merchant_window, textvariable=self.tk_var_list['clicks'][config_key][0], width=6)
                x_entry.grid(row=i, column=1, padx=5, pady=5)
                
                y_entry = ttk.Entry(master=self.merchant_window, textvariable=self.tk_var_list['clicks'][config_key][1], width=6)
                y_entry.grid(row=i, column=2, padx=5, pady=5)

                merchant_select_button = ttk.Button(master=self.merchant_window, text="Assign Click!",
                                                    command=lambda k=config_key, x=x_entry, y=y_entry: 
                                    self.start_capture_thread(k, x, y))
                
            merchant_select_button.grid(row=i, column=5, padx=5, pady=5)

        save_button = ttk.Button(master=self.merchant_window, text="Save Calibration", 
                                command=lambda: self.save_window_settings(self.merchant_window))
        save_button.grid(row=len(merchant_cali) + 1, column=0, columnspan=6, pady=10)

    def auto_equip_window(self):
        self.auto_equip_window = tk.Toplevel()
        self.auto_equip_window.title("Auto Equip")
        self.auto_equip_window.geometry("250x140")
        self.auto_equip_window.resizable(False, False)
        self.auto_equip_window.attributes("-topmost", True)
        frame = ttk.Frame(master=self.auto_equip_window)
        frame.grid(row=0, column=0, sticky="n", padx=(1, 1))
        ttk.Label(master=frame, text="Enter aura name to be used for search.\nThe first result will be equipped so be specific.").grid(row=0, column=0, columnspan=2, padx=5, pady=5)
        aura_entry = ttk.Entry(master=frame, textvariable=self.tk_var_list['auto_equip']['aura'])
        aura_entry.grid(row=1, column=0, columnspan=2, padx=5, pady=5)

        special_checkbox = ttk.Checkbutton(master=frame, text="Search in Special Auras", variable=self.tk_var_list['auto_equip']['special_aura'], command=self.save_config, onvalue="1", offvalue="0")
        special_checkbox.grid()

        # submit 
        submit_button = ttk.Button(master=frame, text="Submit", command=lambda: self.save_window_settings(self.auto_equip_window))
        submit_button.grid(pady=5)

    def assign_clicks_gui(self):
        self.assign_clicks_gui = tk.Toplevel()
        self.assign_clicks_gui.title("Assign Clicks")
        self.assign_clicks_gui.resizable(False, False)
        self.assign_clicks_gui.attributes("-topmost", True)

        tabview = ttk.Notebook(master=self.assign_clicks_gui)
        tabview.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.assign_clicks_gui.grid_rowconfigure(0, weight=1)
        self.assign_clicks_gui.grid_columnconfigure(0, weight=1)

        aura_tab = ttk.Frame(tabview)
        collection_tab = ttk.Frame(tabview)
        items_tab = ttk.Frame(tabview)
        quest_tab = ttk.Frame(tabview)

        tabview.add(aura_tab, text="Auras Storage")
        tabview.add(collection_tab, text="Collection Menu")
        tabview.add(items_tab, text="Items Menu")
        tabview.add(quest_tab, text="Quest Menu")

        aura_tab.grid_rowconfigure(0, weight=1)
        collection_tab.grid_rowconfigure(0, weight=1)
        items_tab.grid_rowconfigure(0, weight=1)
        quest_tab.grid_rowconfigure(0, weight=1)

        aura_settings = [
            ("Aura Storage:", "aura_storage"),
            ("Regular Aura Tab:", "regular_tab"),
            ("Special Aura Tab:", "special_tab"),
            ("Aura Search Bar:", "search_bar"),
            ("First Aura Slot:", "aura_first_slot"),
            ("Equip Button:", "equip_button")
        ]

        collection_settings = [
            ("Collection Menu:", "collection_menu"),
            ("Exit Collection:", "exit_collection")
        ]

        items_settings = [
            ("Items Storage:", "items_storage"),
            ("Items Tab:", "items_tab"),
            ("Items Search Bar:", "items_bar"),
            ("Items First Slot:", "item_first_slot"),
            ("Quantity Bar:", "item_value"),
            ("Use Button:", "use_button")
        ]

        quest_settings = [
            ("Quest Menu:", "quest_menu"),
            ("First Slot:", "first_slot"),
            ("Second Slot:", "second_slot"),
            ("Third Slot:", "third_slot"),
            ("Claim Button:", "claim_button")
        ]

        def create_click_fields(parent, settings):
            for i, (label_text, config_key) in enumerate(settings):
                ttk.Label(parent, text=label_text).grid(row=i, column=0, padx=5, pady=2, sticky="w")
                
                x_entry = ttk.Entry(parent, width=6, 
                    textvariable=self.tk_var_list['clicks'][config_key][0])
                x_entry.grid(row=i, column=1, padx=5, pady=2)
                
                y_entry = ttk.Entry(parent, width=6, 
                    textvariable=self.tk_var_list['clicks'][config_key][1])
                y_entry.grid(row=i, column=2, padx=5, pady=2)
                
                ttk.Button(parent, text="Assign Click!", 
                    command=lambda k=config_key, x=x_entry, y=y_entry: 
                    self.start_capture_thread(k, x, y)).grid(row=i, column=3, padx=5, pady=2)

        create_click_fields(aura_tab, aura_settings)
        create_click_fields(collection_tab, collection_settings)
        create_click_fields(items_tab, items_settings)
        create_click_fields(quest_tab, quest_settings)

        ttk.Button(master=aura_tab, text="Save Calibration", 
                  command=lambda: self.save_window_settings(self.assign_clicks_gui)
                  ).grid(row=7, column=1, padx=5, pady=2)
                  
    def crafting_clicks(self):
        self.crafting_clicks = tk.Toplevel()
        self.crafting_clicks.title("Crafting")
        self.crafting_clicks.attributes("-topmost", True)
        self.crafting_clicks.resizable(False, False)
        
        crafting_frame = ttk.Frame(master=self.crafting_clicks)
        crafting_frame.pack(fill="both", expand=True)

        crafting_settings = [
            ("First Potion Slot:", "first_potion_slot"),
            ("Second Potion Slot:", "second_potion_slot"),
            ("Third Potion Slot:", "third_potion_slot"),
            ("Potion Tab Craft", "potion_tab"),
            ("Item Tab Craft", "item_tab"),
            ("Open Recipe Book", "open_recipe"),
            ("Add button 1", "add_button_1"),
            ("Add button 2", "add_button_2"),
            ("Add button 3", "add_button_3"),
            ("Add button 4", "add_button_4"),
            ("Craft button", "craft_button"),
            ("Potion Search bar:", "potion_search_bar"),
            ("Auto Add button", "auto_add_button")
        ]

        for i, (label_text, config_key) in enumerate(crafting_settings, start=1):
            ttk.Label(master=crafting_frame, text=label_text).grid(row=i, column=0, padx=5, pady=2, sticky="w")

            x_entry = ttk.Entry(master=crafting_frame, textvariable=self.tk_var_list['clicks'][config_key][0], width=6)
            x_entry.grid(row=i, column=1, padx=5, pady=2)

            y_entry = ttk.Entry(master=crafting_frame, textvariable=self.tk_var_list['clicks'][config_key][1], width=6)
            y_entry.grid(row=i, column=2, padx=5, pady=2)

            ttk.Button(master=crafting_frame, text="Assign Click!", command=lambda key=config_key, x=x_entry, y=y_entry: self.start_capture_thread(key, x, y)).grid(row=i, column=3, padx=5, pady=2)

    def pathing_ui(self):
        self.path_window = tk.Toplevel()
        self.path_window.title("Paths Window")
        self.path_window.attributes("-topmost", True)
        self.path_window.resizable(False, False)
        obby_and_chalice_frame = ttk.Labelframe(master=self.path_window, text="Paths")
        obby_and_chalice_frame.pack(fill="both", expand=True)

        for i in range(8):
            ttk.Checkbutton(master=obby_and_chalice_frame, text=str(i+1), width=4,
                          variable=self.tk_var_list['item_collecting'][f'spot{i+1}'], 
                          command=self.save_config,
                          onvalue='1', offvalue='0').grid(row=i, column=0, sticky='e')
        

    def save_window_settings(self, window):
        config.save_tk_list(self.tk_var_list)
        config.save_config(config.config_data)
        window.destroy()

    def save_config(self):
        config.save_config(config.config_data)
        config.save_tk_list(self.tk_var_list)
    def start_capture_thread(self, config_key, x_entry, y_entry, w_entry=None, h_entry=None):
        self.snipping_window = tk.Toplevel()
        self.snipping_window.attributes("-fullscreen", True)
        self.snipping_window.attributes("-alpha", 0.3)
        self.snipping_window.config(cursor="cross")
        self.canvas = tk.Canvas(self.snipping_window, bg="lightblue", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.x_entry = x_entry
        self.y_entry = y_entry
        self.w_entry = w_entry
        self.h_entry = h_entry
        self.config_key = config_key

        self.snipping_window.bind("<Button-1>", self.on_click)
        self.snipping_window.bind("<B1-Motion>", self.mouse_drag)
        self.snipping_window.bind("<ButtonRelease-1>", self.mouse_release)
        
        self.snipping_window.protocol("WM_DELETE_WINDOW", self.on_window_close)

    def on_window_close(self):
        """Handle window closing"""
        if hasattr(self, 'snipping_window'):
            self.snipping_window.destroy()

    def on_click(self, event):
        try:
            self.begin_x = event.x
            self.begin_y = event.y
            
            if hasattr(self, 'canvas'):
                self.canvas.delete("selection_rect")
        except Exception as e:
            print(f"Error in on_click: {e}")

    def mouse_drag(self, event):
        try:
            self.end_x, self.end_y = event.x, event.y

            if hasattr(self, 'canvas'):
                self.canvas.delete("selection_rect")
                self.canvas.create_rectangle(self.begin_x, self.begin_y, self.end_x, self.end_y,
                                          outline="white", width=2, tag="selection_rect")
            
            if hasattr(self, 'x_entry') and self.x_entry.winfo_exists():
                self.x_entry.delete(0, 'end')
                self.x_entry.insert(0, str(self.end_x))
            
            if hasattr(self, 'y_entry') and self.y_entry.winfo_exists():
                self.y_entry.delete(0, 'end')
                self.y_entry.insert(0, str(self.end_y))

            # Calculate and update width and height
            width = abs(self.end_x - self.begin_x)
            height = abs(self.end_y - self.begin_y)
            
            if hasattr(self, 'w_entry') and self.w_entry and self.w_entry.winfo_exists():
                self.w_entry.delete(0, 'end')
                self.w_entry.insert(0, str(width))
            
            if hasattr(self, 'h_entry') and self.h_entry and self.h_entry.winfo_exists():
                self.h_entry.delete(0, 'end')
                self.h_entry.insert(0, str(height))

        except Exception as e:
            print(f"Error in mouse_drag: {e}")

    def mouse_release(self, event):
        try:
            self.end_x = event.x
            self.end_y = event.y

            if hasattr(self, 'x_entry') and self.x_entry.winfo_exists():
                self.x_entry.delete(0, 'end')
                self.x_entry.insert(0, str(self.end_x))
            
            if hasattr(self, 'y_entry') and self.y_entry.winfo_exists():
                self.y_entry.delete(0, 'end')
                self.y_entry.insert(0, str(self.end_y))

            # Calculate final width and height
            width = abs(self.end_x - self.begin_x)
            height = abs(self.end_y - self.begin_y)
            
            if hasattr(self, 'w_entry') and self.w_entry and self.w_entry.winfo_exists():
                self.w_entry.delete(0, 'end')
                self.w_entry.insert(0, str(width))
            
            if hasattr(self, 'h_entry') and self.h_entry and self.h_entry.winfo_exists():
                self.h_entry.delete(0, 'end')
                self.h_entry.insert(0, str(height))

            if hasattr(self, 'config_key'):
                config_key = self.config_key.lower().replace('x', '').replace('y', '')
                config.config_data['clicks'][config_key] = [self.end_x, self.end_y, width, height]
                config.save_config(config.config_data)
            
            if hasattr(self, 'snipping_window'):
                self.snipping_window.destroy()
        except Exception as e:
            print(f"Error in on_mouse_release: {e}")
            if hasattr(self, 'snipping_window'):
                self.snipping_window.destroy()
        
    def set_biome_region(self):
        self.biome_window = tk.Toplevel()
        self.biome_window.title("Select Biomes")
        self.biome_window.geometry("300x400")
        self.biome_window.resizable(False, False)
        self.biome_window.attributes("-topmost", True)
    
        biomes = ["NORMAL", "WINDY", "RAINY", "SNOWY", "SAND STORM", "HELL", "STARFALL", "CORRUPTION", "NULL", "GLITCHED", "DREAMSPACE"]
        for i, biome in enumerate(biomes):
            state = "disabled" if biome in ["GLITCHED", "DREAMSPACE"] else "normal"
            if biome not in self.tk_var_list['biome_alerts']:
                self.tk_var_list['biome_alerts'][biome] = tk.StringVar(value="0")
            ttk.Checkbutton(master=self.biome_window, text=biome, state=state, 
                       variable=self.tk_var_list['biome_alerts'][biome],
                       command=self.save_config, 
                       onvalue="1", offvalue="0").grid(row=i, column=0, padx=5, pady=5, sticky="w")
            
aura_storage = config.config_data['clicks']['aura_storage']
regular_tab = config.config_data['clicks']['regular_tab']
special_tab = config.config_data['clicks']['special_tab']
search_bar = config.config_data['clicks']['search_bar']
aura_first_slot = config.config_data['clicks']['aura_first_slot']
equip_button = config.config_data['clicks']['equip_button']
collection_menu = config.config_data['clicks']['collection_menu']
exit_collection = config.config_data['clicks']['exit_collection']
items_storage = config.config_data['clicks']['items_storage']
items_tab = config.config_data['clicks']['items_tab']
items_bar = config.config_data['clicks']['items_bar']
item_value = config.config_data['clicks']['item_first_slot']
quanity_bar = config.config_data['clicks']['item_value']
use_button = config.config_data['clicks']['use_button']

quest_menu = config.config_data['clicks']['quest_menu']
daily_tab = config.config_data['clicks']['daily_tab']
first_slot = config.config_data['clicks']['first_slot']
second_slot = config.config_data['clicks']['second_slot']
third_slot = config.config_data['clicks']['third_slot']
claim_button = config.config_data['clicks']['claim_button']
merchant_name_ocr = config.config_data['clicks']['merchant_name_ocr']
merchant_open_button = config.config_data['clicks']['merchant_open_button']
merchant_dialog = config.config_data['clicks']['merchant_dialog']
merchant_item_name_ocr = config.config_data['clicks']['merchant_item_name_ocr']
merchant_amount_button = config.config_data['clicks']['merchant_amount_button']
merchant_purchase_button = config.config_data['clicks']['merchant_purchase_button']
merchant_1_slot_button = config.config_data['clicks']['merchant_1_slot_button']
last_log_position = 0
monitoring_active = False
monitoring_thread = None
lock = threading.Lock()


azerty_replace_dict = {"w":"z", "a":"q"}
def get_action(file):
    with open("path.txt") as path_file:
        with open(f'{path_file.read()}\\paths\\{file}.py') as file:
            return file.read()
    
def walk_time_conversion(d):
    if config.config_data["settings"]["vip+_mode"] == "1":
        return d
    elif config.config_data["settings"]["vip_mode"] == "1":
        return d * 1.04
    else:
        return d * 1.3

def walk_sleep(d):
    sleep(walk_time_conversion(d))

def walk_send(k, t):
    if config.config_data["settings"]["azerty_mode"] == "1" and k in azerty_replace_dict:
        k = azerty_replace_dict[k]
    
    if t == True:
        keyboard.on_press(k)
    else:
        keyboard.on_release(k)

running = False
initialiazed = False
main_process = None

class MainLoop:
    def __init__(self):
        self.config_data = config.read_config()
        self.macro_started = False
        self.has_discord_enabled = False
        self.discord_webhook = self.config_data["discord"]["webhook"]["url"]
        self.running = threading.Event()
        self.thread = None
        # Tracker instance for biome/aura monitoring
        try:
            self.tracker = Tracker.Tracker()
        except Exception:
            # fallback if import style differs
            self.tracker = Tracker()
        self.last_quest = datetime.min
        self.last_item = datetime.min
        self.last_potion = datetime.min
        self.last_merchant = datetime.min
        self.last_potion_3 = datetime.min
        self.last_ss = datetime.min
        self.last_item_scheduler = datetime.min
    def start(self):
        try:
            if self.config_data["discord"]["webhook"]["enabled"] == "1":
                webhook = discord_webhook.DiscordWebhook(url=self.discord_webhook)
                embed = discord_webhook.DiscordEmbed(title="Macro Started", description=f"{time.strftime('[%I:%M:%S %p]')}: Macro started.\n\n**Current Version:** {config.get_current_version()}\n**Support server:** https://discord.gg/JsMM299RF7")
                embed.set_footer(text=f"Elixir Macro | {config.get_current_version()}")
                embed.set_color(0x64ff5e)
                webhook.add_embed(embed)
                webhook.execute()
            print("Starting Macro!")
            self.running.set()
            self.thread = threading.Thread(target=self.loop_process, daemon=True)
            self.thread.start()
            # start tracker monitoring alongside macro
            try:
                self.tracker.start_monitoring()
            except Exception as e:
                print(f"Failed to start tracker monitoring: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Error on starting the macro. {e}")
    def stop(self):
        if self.config_data["discord"]["webhook"]["enabled"] == "1":
            webhook = discord_webhook.DiscordWebhook(url=self.discord_webhook)
            embed = discord_webhook.DiscordEmbed(title="Macro Stopped", description=f"{time.strftime('[%I:%M:%S %p]')}: Macro stopped.\n\n**Current Version:** {config.get_current_version()}\n**Support server:** https://discord.gg/JsMM299RF7")
            embed.set_footer(text=f"Elixir Macro | {config.get_current_version()}", icon_url="https://goldfish-cool.github.io/Goldens-Macro/golden_pfp.png")
            embed.set_color(0xff0000)
            webhook.add_embed(embed)
            webhook.execute()

        print("Stopping the whole process...")
        self.running.clear()

        # stop tracker monitoring if running
        try:
            if hasattr(self, 'tracker') and self.tracker:
                self.tracker.stop_monitoring()
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
        print("Starting biome detection (OCR + webhook)...")
        try:
            # Use OCR functions instead of the Tracker monitoring loop
            from data import Tracker as tracker_module

            # Get configured biome region: [x, y, w, h]
            region = config.config_data['clicks']['biome_region'] if 'biome_region' in config.config_data['clicks'] else [0, 0, 0, 0]
            x, y, w, h = map(int, region)
            x2, y2 = x + w, y + h

            # Try a direct OCR on the captured region first
            try:
                image = tracker_module.ImageGrab.grab(bbox=(x, y, x2, y2))
                ocr_text = tracker_module.perform_ocr(image) or ""
            except Exception as e:
                print(f"OCR capture error: {e}")
                ocr_text = ""

            ocr_text = (ocr_text or "").lower()

            biomes = [
                "normal", "windy", "rainy", "snowy", "sand storm",
                "hell", "starfall", "corruption", "null", "glitched", "dreamspace"
            ]

            detected = None
            # Search for known biome keywords in the OCR result
            for b in biomes:
                if b in ocr_text:
                    detected = b
                    break

            # If not found yet, fall back to the module helper which captures and searches
            if not detected:
                for b in biomes:
                    try:
                        if tracker_module.check_ocr_text(x, y, x2, y2, b):
                            detected = b
                            break
                    except Exception as e:
                        print(f"check_ocr_text error for {b}: {e}")
                        continue

            if detected:
                print(f"Detected biome: {detected.upper()}")
                # avoid spamming: only notify when biome changes
                last = getattr(tracker_module, 'last_biome', None)
                if last != detected:
                    # update last_biome and send webhook
                    try:
                        tracker_module.last_biome = detected
                    except Exception:
                        pass
                    desc = f"Detected biome: {detected.upper()} ({time.strftime('%I:%M:%S %p')})"
                    try:
                        # green-ish color for biome notifications
                        self.send_webhook("Biome Change", desc, 0x64ff5e)
                    except Exception as e:
                        print(f"Failed to send webhook: {e}")
                else:
                    print("Same biome as last detection; no webhook sent.")
            else:
                print("No biome detected in the selected region.")

        except Exception as e:
            print(f"Biome detection error: {e}")
            try:
                self.send_webhook("Biome Detection Error", str(e), 0xff0000, urgent=True)
            except Exception:
                pass

    def loop_process(self):
        print("Starting main loop process...")
        while self.running.is_set():
            try:
                if not self.running.is_set():
                    break
                if config.config_data['settings']['reset'] == "1":
                    if sys.platform == "win32":
                        self.activate_window(titles="Roblox")
                    # On macOS, window activation is not yet implemented
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
                messagebox.showerror(f"Error in main loop:", f"{str(e)}")
                if not self.running.is_set():
                    break
                time.sleep(5)
        print("Main loop process stopped")

    def auto_equip(self):
        if config.config_data['auto_equip']['enabled'] == "1":
            try:
                time.sleep(1.3)
                platform_click(aura_storage[0], aura_storage[1])
                time.sleep(0.55)
                if config.config_data['auto_equip']['special_aura'] == "0":
                    platform_click(regular_tab[0], regular_tab[1])
                    time.sleep(0.55)
                else:
                    platform_click(special_tab[0], special_tab[1])
                    time.sleep(0.55)
                platform_click(search_bar[0], search_bar[1])
                time.sleep(0.55)
                platform_key_press(config.config_data['auto_equip']['aura'])
                time.sleep(0.3)
                platform_key_combo('{Enter}')
                time.sleep(0.55)
                platform_click(aura_first_slot[0], aura_first_slot[1])
                time.sleep(0.55)
                platform_click(equip_button[0], equip_button[1])
                time.sleep(0.2)
                platform_click(search_bar[0], search_bar[1])
                time.sleep(0.3)
                platform_key_combo('{Enter}')
                platform_click(aura_storage[0], aura_storage[1])
                time.sleep(0.4)

            except Exception as e:
                messagebox.showerror("Auto Equip Error", str(e))
        else:
            return None
    def align_cam(self):
        if config.config_data["settings"]["reset"] == "1":
            try:
                platform_click(collection_menu[0], collection_menu[1])
                time.sleep(1)
                platform_click(exit_collection[0], exit_collection[1])
                time.sleep(1)
                
                if sys.platform == "win32":
                    if ahk:
                        ahk.mouse_drag(x=exit_collection[0], y=exit_collection[1], from_position=(exit_collection[0], exit_collection[1]), button='right', coord_mode="Screen", send_mode="Input")
                elif sys.platform == "darwin":
                    mouse.move(exit_collection[0], exit_collection[1])
                    mouse.press(Button.right)
                    mouse.move(exit_collection[0], exit_collection[1] + 50)
                    mouse.release(Button.right)
            except Exception as e:
                messagebox.showerror("Error", "Error on aligning camera")
        self.reset()
    def reset(self):
        if config.config_data['settings']['reset'] == "1":
            platform_key_combo('esc')
            sleep(0.33)
            platform_key_combo("r")
            sleep(0.55)
            platform_key_combo('{Enter}')

    def collect(self):
        for i in range(6):
            platform_key_combo("e")
            sleep(0.1)
            platform_key_combo("f")

    def do_obby(self):
        if config.config_data['obby']['enabled'] == "1":
            try:
                exec(f'{get_action("obby_path")}')
            except Exception as e:
                messagebox.showerror("Obby Error", f"{str(e)}")

    def do_crafting(self):
        if config.config_data['potion_crafting']['enabled'] == "1":
            try:
                exec(f'{get_action("potion_path")}')
            except Exception as e:
                messagebox.showerror("Crafting Error", f"{str(e)}")
        else:
            return None
    
    def crafting(self):
        try:
            search_potion = config.config_data['clicks']['potion_search_bar']
            first_slot = config.config_data['clicks']['first_potion_slot']
            second_slot = config.config_data['clicks']['second_potion_slot']
            third_slot = config.config_data['clicks']['third_potion_slot']
            open_recipe_book = config.config_data['clicks']['open_recipe']
            potion_tab = config.config_data['clicks']['potion_tab']
            item_tab = config.config_data["clicks"]["item_tab"]
            add_button_1 = config.config_data['clicks']['add_button_1']
            add_button_2 = config.config_data['clicks']['add_button_2']
            add_button_3 = config.config_data['clicks']['add_button_3']
            add_button_4 = config.config_data['clicks']['add_button_4']
            craft_button = config.config_data['clicks']['craft_button']
            auto_add_button = config.config_data['clicks']['auto_add_button']
            if config.config_data["potion_crafting"]["potion_crafting"] == "1":
                def potion_craft_one():
                    if config.config_data['potion_crafting']['item_1'] in ["Fortune", "Speed Potion", "Lucky Potion", "Heavenly", "Godly", "Potion of bound"]:
                        platform_click(potion_tab[0], potion_tab[1])
                        sleep(0.55)
                        platform_click(search_potion[0], search_potion[1])
                        sleep(0.55)
                        platform_key_combo(config.config_data['potion_crafting']['item_1'])
                        sleep(0.78)
                        platform_click(first_slot[0], first_slot[1])
                        sleep(0.55)
                        platform_click(open_recipe_book[0], open_recipe_book[1])
                        sleep(1)
                        platform_click(add_button_1[0], add_button_1[1])
                        sleep(0.38)
                        platform_click(add_button_2[0], add_button_2[1])
                        sleep(0.38)
                        platform_click(add_button_3[0], add_button_3[1])
                        sleep(0.30)
                        platform_click(add_button_4[0], add_button_4[1])
                        sleep(0.38)
                        platform_click(craft_button[0], craft_button[1])
                        sleep(1)

                def potion_craft_two():
                    if config.config_data['potion_crafting']['item_2'] in ["Fortune", "Speed Potion", "Lucky Potion", "Heavenly", "Godly", "Potion of bound"]:
                        platform_click(search_potion[0], search_potion[1])
                        sleep(0.55)
                        platform_key_combo(config.config_data['potion_crafting']['item_2'])
                        sleep(0.78)
                        platform_click(second_slot[0], second_slot[1])
                        sleep(0.55)
                        platform_click(open_recipe_book[0], open_recipe_book[1])
                        sleep(1)
                        platform_click(add_button_1[0], add_button_1[1])
                        sleep(0.38)
                        platform_click(add_button_2[0], add_button_2[1])
                        sleep(0.38)
                        platform_click(add_button_3[0], add_button_3[1])
                        sleep(0.30)
                        platform_click(add_button_4[0], add_button_4[1])
                        sleep(0.38)
                        platform_click(craft_button[0], craft_button[1])
                        sleep(0.78)

                def potion_craft_three():
                    if config.config_data['potion_crafting']['item_3'] in ["Fortune", "Speed Potion", "Lucky Potion", "Heavenly", "Godly", "Potion of bound"]:
                        platform_click(search_potion[0], search_potion[1])
                        sleep(0.55)
                        platform_key_combo(config.config_data['potion_crafting']['item_3'])
                        sleep(0.78)
                        platform_click(third_slot[0], third_slot[1])
                        sleep(0.55)
                        platform_click(open_recipe_book[0], open_recipe_book[1])
                        sleep(1)
                        platform_click(add_button_1[0], add_button_1[1])
                        sleep(0.38)
                        platform_click(add_button_2[0], add_button_2[1])
                        sleep(0.38)
                        platform_click(add_button_3[0], add_button_3[1])
                        sleep(0.30)
                        platform_click(add_button_4[0], add_button_4[1])
                        sleep(0.38)
                        platform_click(craft_button[0], craft_button[1])
                        sleep(0.78)

                def auto_add_potion():
                    platform_click(search_potion[0], search_potion[1])
                    sleep(0.78)
                    platform_key_combo(config.config_data['potion_crafting']['current_temporary_auto_add'])
                    sleep(0.78)
                    platform_key_combo('{Enter}')
                    sleep(0.48)
                    platform_click(first_slot[0], first_slot[1])
                    sleep(0.38)
                    platform_click(auto_add_button[0], auto_add_button[1])
                    sleep(0.38)
                    platform_key_combo('f')

                if config.config_data['potion_crafting']['craft_potion_1'] == "1":
                    potion_craft_one()

                if config.config_data['potion_crafting']['craft_potion_2'] == "1":
                    potion_craft_two()

                if config.config_data['potion_crafting']['craft_potion_3'] == "1":
                    potion_craft_three()

                if config.config_data['potion_crafting']['temporary_auto_add'] == "1":
                    auto_add_potion()

            elif config.config_data["Potion_crafting"] == "0":
                def potion_craft_one():
                    if config.config_data['potion_crafting']['item_1'] in ["Fortune", "Speed Potion", "Lucky Potion", "Heavenly", "Godly", "Potion of bound"]:
                        platform_click(item_tab[0], item_tab[1])
                        sleep(0.55)
                        platform_click(search_potion[0], search_potion[1])
                        sleep(0.55)
                        platform_key_combo(config.config_data['potion_crafting']['item_1'])
                        sleep(0.78)
                        platform_click(first_slot[0], first_slot[1])
                        sleep(0.55)
                        platform_click(open_recipe_book[0], open_recipe_book[1])
                        sleep(1)
                        platform_click(add_button_1[0], add_button_1[1])
                        sleep(0.38)
                        platform_click(add_button_2[0], add_button_2[1])
                        sleep(0.38)
                        platform_click(add_button_3[0], add_button_3[1])
                        sleep(0.30)
                        platform_click(add_button_4[0], add_button_4[1])
                        sleep(0.38)
                        platform_click(craft_button[0], craft_button[1])
                        sleep(0.78)

                def potion_craft_two():
                    if config.config_data['potion_crafting']['item_2'] in ["Fortune", "Speed Potion", "Lucky Potion", "Heavenly", "Godly", "Potion of bound"]:
                        platform_click(search_potion[0], search_potion[1])
                        sleep(0.55)
                        platform_key_combo(config.config_data['potion_crafting']['item_2'])
                        sleep(0.78)
                        platform_click(second_slot[0], second_slot[1])
                        sleep(0.55)
                        platform_click(open_recipe_book[0], open_recipe_book[1])
                        sleep(1)
                        platform_click(add_button_1[0], add_button_1[1])
                        sleep(0.38)
                        platform_click(add_button_2[0], add_button_2[1])
                        sleep(0.38)
                        platform_click(add_button_3[0], add_button_3[1])
                        sleep(0.30)
                        platform_click(add_button_4[0], add_button_4[1])
                        sleep(0.38)
                        platform_click(craft_button[0], craft_button[1])
                        sleep(0.78)

                def potion_craft_three():
                    if config.config_data['potion_crafting']['item_3'] in ["Fortune", "Speed Potion", "Lucky Potion", "Heavenly", "Godly", "Potion of bound"]:
                        platform_click(search_potion[0], search_potion[1])
                        sleep(0.55)
                        platform_key_combo(config.config_data['potion_crafting']['item_3'])
                        sleep(0.78)
                        platform_click(third_slot[0], third_slot[1])
                        sleep(0.55)
                        platform_click(open_recipe_book[0], open_recipe_book[1])
                        sleep(1)
                        platform_click(add_button_1[0], add_button_1[1])
                        sleep(0.38)
                        platform_click(add_button_2[0], add_button_2[1])
                        sleep(0.38)
                        platform_click(add_button_3[0], add_button_3[1])
                        sleep(0.30)
                        platform_click(add_button_4[0], add_button_4[1])
                        sleep(0.38)
                        platform_click(craft_button[0], craft_button[1])
                        sleep(0.78)

                def auto_add_potion():
                    platform_click(search_potion[0], search_potion[1])
                    sleep(0.78)
                    platform_key_combo(config.config_data['potion_crafting']['current_temporary_auto_add'])
                    sleep(0.78)
                    platform_key_combo('{Enter}')
                    sleep(0.48)
                    platform_click(first_slot[0], first_slot[1])
                    sleep(0.38)
                    platform_click(auto_add_button[0], auto_add_button[1])
                    sleep(0.38)
                    platform_key_combo('f')

                if config.config_data['potion_crafting']['craft_potion_1'] == "1":
                    potion_craft_one()

                if config.config_data['potion_crafting']['craft_potion_2'] == "1":
                    potion_craft_two()

                if config.config_data['potion_crafting']['craft_potion_3'] == "1":
                    potion_craft_three()

                if config.config_data['potion_crafting']['temporary_auto_add'] == "1":
                    auto_add_potion()

            self.reset()

        except Exception as e:
            messagebox.showerror("Crafting", str(e))

    def chalice(self):
        return None

    def claim_quests(self):
        if config.config_data['claim_daily_quests'] == "1":
            try:
                platform_click(quest_menu[0], quest_menu[1])
                sleep(0.55)
                platform_click(first_slot[0], first_slot[1])
                sleep(0.38)
                platform_click(claim_button[0], claim_button[1])
                sleep(0.38)
                platform_click(second_slot[0], second_slot[1])
                sleep(0.38)
                platform_click(claim_button[0], claim_button[1])
                sleep(0.38)
                platform_click(third_slot[0], third_slot[1])
                sleep(0.38)
                platform_click(claim_button[0], claim_button[1])
                sleep(0.28)
                platform_click(quest_menu[0], quest_menu[1])
            except Exception as e:
                messagebox.showerror("Quest Error", f"{str(e)}")
    
    def item_collecting(self):
        if config.config_data['item_collecting']['enabled'] == "1":
            try:
                exec(f'{get_action("item_collect")}')
            except Exception as e:
                messagebox.showerror("Item Collecting Error", str(e))
        else:
            return None

    def item_scheduler(self):
        if config.config_data['item_scheduler_item']['enabled'] == "1":
            try:
                platform_click(items_storage[0], items_storage[1])
                sleep(0.55)
                platform_click(items_tab[0], items_tab[1])
                sleep(0.33)
                platform_click(items_bar[0], items_bar[1])
                sleep(0.33)
                platform_key_combo(config.config_data['item_scheduler_item']["item_name"])
                sleep(0.55)
                platform_key_combo('{Enter}')
                sleep(0.43)
                platform_click(item_value[0], item_value[1])
                sleep(0.33)
                platform_click(quanity_bar[0], quanity_bar[1])
                sleep(0.1)
                platform_click(quanity_bar[0], quanity_bar[1])
                sleep(0.33)
                platform_key_combo(config.config_data['item_scheduler_item']["item_scheduler_quantity"])
                sleep(0.55)
                platform_key_combo('{Enter}')
                sleep(0.43)
                platform_click(use_button[0], use_button[1])
                sleep(0.78)
                platform_click(items_storage[0], items_storage[1])
            except Exception as e:
                messagebox.showerror("Schelduer Error", str(e))
        else:
            return None

    def inventory_screenshots(self):
        if config.config_data['invo_ss']['enabled'] == "1":
            try:
                sleep(0.39)
                platform_click(aura_storage[0], aura_storage[1])
                sleep(0.55)
                platform_click(regular_tab[0], regular_tab[1])
                sleep(0.55)
                
                screen_shot_dir = os.path.join(os.getcwd(), "images")
                os.makedirs(screen_shot_dir, exist_ok=True)
                
                screen_shot = auto.screenshot()
                screenshot_path = os.path.join(screen_shot_dir, "inventory_screenshots.png")
                screen_shot.save(screenshot_path)
                
                if 'discord.com' in self.discord_webhook and 'https://' in self.discord_webhook:
                    webhook = discord_webhook.DiscordWebhook(url=self.discord_webhook)
                    discord_embed = discord_webhook.DiscordEmbed(
                        title="**Aura Screenshot!**",
                        description=""
                    )
                    if os.path.exists(screenshot_path):
                        with open(screenshot_path, 'rb') as f:
                            webhook.add_file(file=f.read(), filename="inventory_screenshots.png")
                        discord_embed.set_image(url="attachment://inventory_screenshots.png")
                    webhook.add_embed(discord_embed)
                    webhook.execute()

                sleep(0.55)
                platform_click(aura_storage[0], aura_storage[1])
                sleep(0.55)
                platform_click(items_storage[0], items_storage[1])
                sleep(0.55)
                platform_click(items_tab[0], items_tab[1])
                sleep(0.33)

                screen_shot_items = auto.screenshot()
                items_screenshot_path = os.path.join(screen_shot_dir, "item_screenshots.png")
                screen_shot_items.save(items_screenshot_path)

                if 'discord.com' in self.discord_webhook and 'https://' in self.discord_webhook:
                    webhook = discord_webhook.DiscordWebhook(url=self.discord_webhook)
                    discord_embed = discord_webhook.DiscordEmbed(
                        title="**Item screenshot!**",
                        description=""
                    )
                    if os.path.exists(items_screenshot_path):
                        with open(items_screenshot_path, 'rb') as f:
                            webhook.add_file(file=f.read(), filename="item_screenshots.png")
                        discord_embed.set_image(url="attachment://item_screenshots.png")
                    webhook.add_embed(discord_embed)
                    webhook.execute()
                    
                platform_click(items_storage[0], items_storage[1])
            except Exception as e:
                messagebox.showerror("Inventory Screenshots", f"{str(e)}")

    def auto_loop_stuff(self):
        if config.config_data['potion_crafting']['enabled'] == "1":
            get_crafting = True
        else:
            get_crafting = False

        try:
            crafting_interval = int(config.config_data['potion_crafting']['crafting_interval'])
            interval = timedelta(minutes=crafting_interval)
        except (ValueError, TypeError):
            interval = timedelta(minutes=20)
            
        if get_crafting and datetime.now() - self.last_potion >= interval:
            self.do_crafting()
            self.last_potion = datetime.now()

        if config.config_data['claim_daily_quests'] == "1":
            get_quest = True
        else:
            get_quest = False
        try:
            quest_interval = 30
            quest = timedelta(minutes=30)
        except (ValueError, TypeError):
            quest = timedelta(minutes=30)

        if get_quest and datetime.now() - self.last_quest >= quest:
            self.claim_quests()
            self.last_quest = datetime.now()

        if config.config_data['invo_ss']['enabled'] == "1":
            get_ss = True
        else:
            get_ss = False

        try:
            ss_interval = int(config.config_data['invo_ss']['duration'])
            ss_timedelta = timedelta(minutes=ss_interval)
        except (ValueError, TypeError):
            ss_timedelta = timedelta(minutes=60)
        
        if get_ss and datetime.now() - self.last_ss >= ss_timedelta:
            self.inventory_screenshots()
            self.last_ss = datetime.now()

        if config.config_data['settings']['merchant']['enabled'] == "1":
            get_merchant = True
        else:
            get_merchant = False

        if config.config_data["item_scheduler_item"]["enabled"] == "1":
            get_item_scheduler = True
        else:
            get_item_scheduler = False

        try:
            item_scheduler_interval = int(config.config_data['item_scheduler_item']['interval'])
            item_scheduler_time = timedelta(minutes=item_scheduler_interval)
        except (ValueError, TypeError):
            item_scheduler_time = timedelta(minutes=20)
            self.send_webhook(
                "Configuration Warning",
                f"Invalid item scheduler interval in config. Defaulting to 20 minutes.\nPlease fix this ASAP before the Item {config.config_data['item_scheduler_item']['item_name']}, will be used every 20 Minutes.",
                0xffff00
            )

        if get_item_scheduler and datetime.now() - self.last_item_scheduler >= item_scheduler_time:
            self.item_scheduler()
            self.last_item_scheduler = datetime.now()

        #try:
        #    merchant_duration = int(config.config_data['settings']['merchant']['duration'])
        #    merchant_time = timedelta(minutes=merchant_duration)
        #except (ValueError, TypeError):
        #    merchant_time = timedelta(minutes=15)

        #if get_merchant and datetime.now() - self.last_merchant >= merchant_time:
        #    await asyncio.sleep(0.75)
        #    await self.merchant_teleport()
        #    self.last_merchant = datetime.now()

    def send_webhook(self, title, description, color, urgent=False):
            try:
                
                if self.config_data["discord"]["webhook"]["enabled"] == "1":
                    self.has_discord_enabled = True
                else:
                    return

                if self.has_discord_enabled:
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
                messagebox.showerror("Error", f"There was a problem sending webhook. Please try again. {e}")
    
    def activate_window(self, titles=""):
        """Windows-only function to activate a window by title."""
        if sys.platform != "win32":
            print(f"Window activation not implemented for {sys.platform}")
            return
        try:
            import pywinctl as pwc
        except ImportError:
            messagebox.showerror(title="Import Error", message=f"Failed to activate: {titles}")
            return

        windows = pwc.getAllTitles()
        the_window = titles
        if the_window not in windows:
            messagebox.showerror(title="Error", message=f"No window found with title: {titles}")
        else:
            for window in windows:
                if titles in window:
                    pwc.getWindowsWithTitle(window)[0].activate()
                    break
            else:
                messagebox.showerror(title="Error", message=f"No window found with title containing {titles}")


