import os
import subprocess
import sys
import json
import pathlib
import threading
from tkinter import messagebox

sys.dont_write_bytecode = True
sys.path.append(pathlib.Path(__file__).parent.resolve())

 
def create_main_gui(gui):
    gui.mainloop()
    
def set_path():
    try:
        if getattr(sys, 'frozen', False):
            application_path = pathlib.Path(sys.executable).parent.resolve()
            if "_MEIPASS" in str(application_path) or "_temp_" in str(application_path):
                application_path = pathlib.Path(os.path.expanduser("~")).joinpath("Documents").joinpath("Goldens_Macro")
                os.makedirs(application_path, exist_ok=True)
        else:
            application_path = pathlib.Path(__file__).parent.resolve()
            
        with open("path.txt", "w") as file:
            file.write(str(application_path))
    except Exception as e:
        error_message = f"Error on trying to set the path: {str(e)}"
        messagebox.showerror("Error", error_message)

def main():
    set_path()
    
    from data import main_gui
    gui = main_gui.App()
    create_main_gui(gui)

    
if __name__ == "__main__":
    main()
