import pyautogui
import keyboard
import pyperclip
import time

frozen = False
saved_color = None

print("Move your mouse to detect colors.")
print("Hold CTRL to freeze and copy the color. Press ESC to quit.")

while True:
    # Exit
    if keyboard.is_pressed("esc"):
        print("Exiting...")
        break

    # Get mouse position
    x, y = pyautogui.position()

    # Get pixel color
    r, g, b = pyautogui.pixel(x, y)
    current_color = f"RGB({r}, {g}, {b})  HEX: #{r:02X}{g:02X}{b:02X}"

    # If CTRL is pressed → freeze + copy
    if keyboard.is_pressed("ctrl"):
        if not frozen:
            frozen = True
            saved_color = current_color
            pyperclip.copy(saved_color)
            print(f"\nCopied: {saved_color}")
    else:
        frozen = False

    # Display color
    if frozen:
        print(f"\rFrozen: {saved_color}        ", end="")
    else:
        print(f"\rLive: {current_color}        ", end="")

    time.sleep(0.05)