import ctypes
import json
import os
import sys
from tkinter import messagebox, StringVar
from PIL import Image, ImageDraw

import requests


with open("path.txt", "r") as file:
    config_path = os.path.join(file.read(), "config.json")
config_data = None

def show_error(message):
    """Cross-platform error dialog."""
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.MessageBoxW(0, message, "Error", 0)
        except:
            messagebox.showerror("Error", message)
    else:
        messagebox.showerror("Error", message)

def get_current_version():
    return read_config()["current_version"]

def read_config(key=""):
    # try:
    with open(config_path) as config_file:
        config_data = config_file.read()
        config_data = json.loads(config_data)
        if len(config_data) == 0:
            show_error("CONFIG DATA NOT FOUND")
            exit(1)
        if not key == "":
            return config_data[key]
        return config_data
    # except:
    #     show_error("CONFIG DATA ERROR!")

def save_config(config_data_p):
    global config_data
    with open(config_path, 'w') as config_file:
        json.dump(config_data_p, config_file, indent=4)
    config_data = read_config()

def iterate_generate_list(json_object, var_list):
    for i in range(len(json_object)):
        if type(json_object[i]) == dict:
            var_list[i] = {}
            iterate_generate_dict(json_object[i], var_list[i])
        elif type(json_object[i]) == list:
            var_list[i] = []
            iterate_generate_list(json_object[i], var_list[i])
        else:
            var_list.append(StringVar(value=json_object[i]))

def iterate_generate_dict(json_object, var_list):
    for key in json_object:
        if type(json_object[key]) == dict:
            var_list[key] = {}
            iterate_generate_dict(json_object[key], var_list[key])
        elif type(json_object[key]) == list:
            var_list[key] = []
            iterate_generate_list(json_object[key], var_list[key])
        else:
            var_list[key] = StringVar(value=json_object[key])

def generate_tk_list():
    config_data = read_config()
    tk_var_list = {}
    iterate_generate_dict(config_data, tk_var_list)
    return tk_var_list

def iterate_save_dict(json_object, var_list):
    for key in json_object:
        if type(var_list[key]) == dict:
            iterate_save_dict(json_object[key], var_list[key])
        elif type(var_list[key]) == list:
            iterate_save_list(json_object[key], var_list[key])
        elif type(var_list[key]) == str:
            json_object[key] = var_list[key]
        else:
            json_object[key] = var_list[key].get()

def iterate_save_list(json_object, var_list):
    for i in range(len(var_list)):
        if type(var_list[i]) == dict:
            iterate_save_dict(json_object[i], var_list[i])
        elif type(var_list[i]) == list:
            iterate_save_list(json_object[i], var_list[i])
        else:
            json_object[i] = var_list[i].get()

def save_tk_list(tk_var_list):
    config_data = read_config()
    iterate_save_dict(config_data, tk_var_list)
    save_config(config_data)

def parent_path():
    with open("path.txt", "r") as file:
        return file.read()

def round_corners(im, rad):
    circle = Image.new('L', (rad * 2, rad * 2), 0)
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, rad * 2 - 1, rad * 2 - 1), fill=255)
    alpha = Image.new('L', im.size, 255)
    w, h = im.size
    alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
    alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
    alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
    alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))
    im.putalpha(alpha)
    return im

def theme_path():
    if "paths" not in config_data or "theme" not in config_data["paths"]:
        return os.path.join(parent_path(), "data", "themes", "solar.json")
    if "/" in config_data["paths"]["theme"] or "\\" in config_data["paths"]["theme"]:
        return config_data["paths"]["theme"]
    else:
        theme_name = config_data["paths"]["theme"]
        if theme_name in config_data.get("themes", {}):
            return os.path.join(parent_path(), config_data["themes"][theme_name])
        return os.path.join(parent_path(), "data", "themes", f"{theme_name.lower()}.json")

def read_theme(key=""):
    with open(theme_path()) as theme_file:
        theme_data = json.load(theme_file)
        if len(theme_data) == 0:
            show_error("THEME FILE NOT FOUND")
            exit(1)
        if not key == "":
            return theme_data[key]
        return theme_data

def read_json(path, key=""):
    full_path = os.path.join(parent_path(), path)
    with open(full_path) as file:
        data = json.load(file)
        if len(data) == 0:
            show_error("JSON FILE NOT FOUND")
            exit(1)
        if not key == "":
            return data[key]
        return data

def save_theme_path(path):
    config_data = read_config()
    config_data["theme_path"] = path
    save_config(config_data)

def convert_to_ahk():
    pass

config_data = read_config()
