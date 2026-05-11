import cv2
import numpy as np
import dxcam
import mss
import pyautogui
import keyboard
import time
import threading
import sys
import json
import os
from dataclasses import dataclass, asdict
from typing import Optional, Tuple, List, Dict

# ===== DATA STRUCTURES =====
@dataclass
class CalibrationData:
    cast_button: Tuple[int, int] = (0, 0)
    bite_indicator: Tuple[int, int] = (0, 0)
    reel_region: Tuple[int, int, int, int] = (0, 0, 0, 0)  # left, top, width, height
    target_color_lower: Tuple[int, int, int] = (40, 100, 100)   # HSV
    target_color_upper: Tuple[int, int, int] = (80, 255, 255)
    bar_color_lower: Tuple[int, int, int] = (100, 150, 150)
    bar_color_upper: Tuple[int, int, int] = (130, 255, 255)
    completion_indicator: Tuple[int, int] = (0, 0)
    close_button: Tuple[int, int] = (0, 0)
    # Optional sell menu
    first_item: Tuple[int, int] = (0, 0)
    sell_button: Tuple[int, int] = (0, 0)
    confirm_button: Tuple[int, int] = (0, 0)
    # Bite colors (list of HSV ranges)
    bite_colors: List[Dict[str, Tuple[int, int, int]]] = None

    def __post_init__(self):
        if self.bite_colors is None:
            self.bite_colors = []

# Global instance
cal = CalibrationData()
CAL_FILE = "calibration.json"

# ===== CALIBRATION HELPER FUNCTIONS =====
def get_mouse_pos(prompt: str) -> Tuple[int, int]:
    """Wait for user to press 'c' and return current mouse position."""
    print(prompt)
    print("Move your mouse to the desired location and press 'c' to confirm.")
    while True:
        if keyboard.is_pressed('c'):
            x, y = pyautogui.position()
            print(f"Recorded: ({x}, {y})")
            time.sleep(0.3)  # debounce
            return x, y
        time.sleep(0.05)

def get_rectangle(prompt: str) -> Tuple[int, int, int, int]:
    """Get two mouse clicks to define a rectangle (left, top, width, height)."""
    print(prompt)
    print("Click the top-left corner, then click the bottom-right corner.")
    print("Press 'c' at each corner to confirm.")
    p1 = get_mouse_pos("Top-left corner: move mouse and press 'c'")
    p2 = get_mouse_pos("Bottom-right corner: move mouse and press 'c'")
    left = min(p1[0], p2[0])
    top = min(p1[1], p2[1])
    width = abs(p1[0] - p2[0])
    height = abs(p1[1] - p2[1])
    print(f"Region: left={left}, top={top}, width={width}, height={height}")
    return (left, top, width, height)

def capture_small_region(center: Tuple[int, int], size: int = 5) -> np.ndarray:
    """Capture a small square region around the given pixel."""
    x, y = center
    half = size // 2
    left = x - half
    top = y - half
    return capture_region((left, top, size, size))

def sample_color_range(center: Tuple[int, int], size: int = 5) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    """Sample the region around a click to get HSV min and max."""
    img = capture_small_region(center, size)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0].flatten()
    s = hsv[:, :, 1].flatten()
    v = hsv[:, :, 2].flatten()
    # Filter out outliers (e.g., use 10th and 90th percentiles to be robust)
    h_low, h_high = np.percentile(h, [10, 90])
    s_low, s_high = np.percentile(s, [10, 90])
    v_low, v_high = np.percentile(v, [10, 90])
    # Ensure integer and within [0,255]
    h_low, h_high = int(max(0, h_low)), int(min(179, h_high))
    s_low, s_high = int(max(0, s_low)), int(min(255, s_high))
    v_low, v_high = int(max(0, v_low)), int(min(255, v_high))
    return (h_low, s_low, v_low), (h_high, s_high, v_high)

def calibrate():
    """Interactive calibration: click on screen elements and set color ranges."""
    print("\n=== CALIBRATION MODE ===")
    print("You will be asked to click on various parts of the screen.")
    print("Use 'c' to confirm the mouse position when prompted.")
    print("Press Ctrl+C at any time to abort calibration.\n")

    # 1. Cast button
    cal.cast_button = get_mouse_pos("Place mouse over the CAST button and press 'c'")

    # 2. Bite indicator (multiple colors)
    print("\nNow we will record colors that appear when a fish bites.")
    print("You need to see the bite notification and click on its colored area.")
    print("We will record up to 4 colors (red, green, grey, blue).")
    cal.bite_colors = []
    colors_seen = set()
    while len(cal.bite_colors) < 4:
        print(f"\nColor {len(cal.bite_colors)+1}:")
        pos = get_mouse_pos("Move mouse over the bite notification (colored part) and press 'c'")
        lower, upper = sample_color_range(pos)
        # Avoid duplicate ranges
        key = (lower, upper)
        if key not in colors_seen:
            colors_seen.add(key)
            cal.bite_colors.append({"lower": lower, "upper": upper})
            print(f"Recorded range: H={lower[0]}-{upper[0]}, S={lower[1]}-{upper[1]}, V={lower[2]}-{upper[2]}")
        else:
            print("Duplicate color ignored. Try a different bite color.")
        # Ask if they want to stop early
        if len(cal.bite_colors) < 4:
            ans = input("Record another color? (y/n): ").strip().lower()
            if ans != 'y':
                break
    if not cal.bite_colors:
        print("Warning: No bite colors recorded. Macro may not detect bites.")
        # Provide default ranges for common colors
        cal.bite_colors = [
            {"lower": (0, 100, 100), "upper": (10, 255, 255)},   # red
            {"lower": (40, 100, 100), "upper": (80, 255, 255)},   # green
            {"lower": (0, 0, 100), "upper": (180, 50, 255)},      # grey
            {"lower": (100, 100, 100), "upper": (130, 255, 255)}  # blue
        ]
        print("Using default bite color ranges.")

    # 3. Reel region (rectangle where the minigame appears)
    cal.reel_region = get_rectangle("Define the RECTANGLE where the reeling minigame appears.\nMake sure it includes the green zone and the blue bar.")

    # 4. Green zone color (target area)
    pos = get_mouse_pos("Move mouse over the GREEN zone in the minigame and press 'c'")
    lower, upper = sample_color_range(pos)
    cal.target_color_lower = lower
    cal.target_color_upper = upper
    print(f"Green zone range: {lower} to {upper}")

    # 5. Blue bar color
    pos = get_mouse_pos("Move mouse over the BLUE bar (the one you control) and press 'c'")
    lower, upper = sample_color_range(pos)
    cal.bar_color_lower = lower
    cal.bar_color_upper = upper
    print(f"Blue bar range: {lower} to {upper}")

    # 6. Completion indicator (white bar full)
    pos = get_mouse_pos("When the white bar is FULL (fish caught), click on the white area and press 'c'")
    lower, upper = sample_color_range(pos)
    cal.completion_indicator = pos
    # Store the color range for completion (usually white)
    # We'll reuse target_color_lower/upper for completion check? Better store separate.
    # For simplicity, we'll just check the pixel's color against a white range.
    # We'll add a field for completion_color later. For now, use a default white range.
    # Let's create a new field:
    cal.completion_color_lower = (0, 0, 200)   # very light/white
    cal.completion_color_upper = (180, 50, 255)
    print("Completion indicator set.")

    # 7. Close button (after catch)
    cal.close_button = get_mouse_pos("Move mouse over the 'Close' button on the catch screen and press 'c'")

    # 8. Optional sell menu
    ans = input("\nDo you want to configure auto-sell? (y/n): ").strip().lower()
    if ans == 'y':
        cal.first_item = get_mouse_pos("Move mouse over the first item in your inventory and press 'c'")
        cal.sell_button = get_mouse_pos("Move mouse over the 'Sell' button and press 'c'")
        cal.confirm_button = get_mouse_pos("Move mouse over the confirmation button and press 'c'")
    else:
        cal.first_item = (0, 0)
        cal.sell_button = (0, 0)
        cal.confirm_button = (0, 0)

    # Save calibration to file
    with open(CAL_FILE, 'w') as f:
        json.dump(asdict(cal), f, indent=4)
    print(f"\nCalibration saved to {CAL_FILE}. You can edit it manually if needed.")
    print("Calibration complete.\n")

def load_calibration():
    """Load calibration data from file, or run calibration if not found."""
    global cal
    if os.path.exists(CAL_FILE):
        with open(CAL_FILE, 'r') as f:
            data = json.load(f)
        # Convert lists back to tuples
        for k, v in data.items():
            if isinstance(v, list):
                if k == 'bite_colors':
                    # bite_colors is list of dicts with lower/upper lists
                    cal.bite_colors = v
                else:
                    # Convert list to tuple if length indicates coordinate
                    if len(v) == 2 and isinstance(v[0], int):
                        setattr(cal, k, tuple(v))
                    elif len(v) == 4 and isinstance(v[0], int):
                        setattr(cal, k, tuple(v))
                    else:
                        setattr(cal, k, v)
            else:
                setattr(cal, k, v)
        print("Calibration loaded.")
    else:
        print("No calibration file found. Starting calibration...")
        calibrate()
        # After calibration, reload to ensure all fields are set
        load_calibration()

# ===== SCREEN CAPTURE SETUP =====
camera = None
sct = None
try:
    camera = dxcam.create()
except Exception as e:
    print(f"dxcam failed: {e}, falling back to MSS")
    sct = mss.mss()

def capture_region(region: Tuple[int, int, int, int]) -> np.ndarray:
    """Capture a region of the screen. Returns BGR image (cv2 format)."""
    left, top, width, height = region
    if camera is not None:
        frame = camera.grab(region=(left, top, left+width, top+height))
        if frame is not None:
            return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    # Fallback to MSS
    monitor = {"left": left, "top": top, "width": width, "height": height}
    img = sct.grab(monitor)
    return np.array(img)[:, :, :3]

def pixel_matches_any_color(pixel: Tuple[int, int], color_ranges: List[Dict]) -> bool:
    """Check if the pixel matches any of the given HSV ranges."""
    region = (pixel[0], pixel[1], 1, 1)
    img = capture_region(region)
    if img.size == 0:
        return False
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[0, 0]
    for cr in color_ranges:
        lower = cr['lower']
        upper = cr['upper']
        if (lower[0] <= h <= upper[0] and
            lower[1] <= s <= upper[1] and
            lower[2] <= v <= upper[2]):
            return True
    return False

def find_blue_bar_position(reel_img: np.ndarray) -> Optional[int]:
    """Find the x-coordinate of the blue bar inside the reel region."""
    hsv = cv2.cvtColor(reel_img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, cal.bar_color_lower, cal.bar_color_upper)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    largest = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest)
    return x + w // 2

def is_within_green_zone(bar_x: int, reel_img: np.ndarray) -> bool:
    """Check if the bar's x lies within the green target zone."""
    hsv = cv2.cvtColor(reel_img, cv2.COLOR_BGR2HSV)
    green_mask = cv2.inRange(hsv, cal.target_color_lower, cal.target_color_upper)
    col_sum = np.sum(green_mask, axis=0)
    green_cols = np.where(col_sum > 0)[0]
    if len(green_cols) == 0:
        return False
    left = green_cols[0]
    right = green_cols[-1]
    return left <= bar_x <= right

def click_mouse(x: int, y: int, button: str = 'left'):
    pyautogui.click(x, y, button=button)

def reel_until_catch():
    global fishing_active
    while fishing_active:
        img = capture_region(cal.reel_region)
        bar_x = find_blue_bar_position(img)
        if bar_x is not None:
            if is_within_green_zone(bar_x, img):
                pyautogui.click(button='left')
            else:
                pyautogui.click(button='left')
        else:
            pyautogui.click(button='left')

        # Check completion indicator
        if pixel_matches_any_color(cal.completion_indicator, [{"lower": cal.completion_color_lower, "upper": cal.completion_color_upper}]):
            fishing_active = False
            time.sleep(0.5)
            click_mouse(*cal.close_button)
            break

        time.sleep(0.02)

def auto_sell():
    if cal.first_item == (0,0):
        return
    click_mouse(*cal.first_item)
    time.sleep(0.2)
    click_mouse(*cal.sell_button)
    time.sleep(0.2)
    click_mouse(*cal.confirm_button)
    time.sleep(0.5)

def fishing_loop():
    global fishing_active, running
    while running:
        # Cast
        click_mouse(*cal.cast_button)
        time.sleep(0.5)

        # Wait for bite
        bite_detected = False
        start_time = time.time()
        while not bite_detected and running:
            if pixel_matches_any_color(cal.bite_indicator, cal.bite_colors):
                bite_detected = True
                break
            if time.time() - start_time > 15:
                break
            time.sleep(0.1)

        if not bite_detected:
            continue

        # Reel
        fishing_active = True
        reel_until_catch()

        # Sell
        auto_sell()

        time.sleep(1)

def hotkey_listener():
    global running
    keyboard.add_hotkey('f1', lambda: setattr(sys.modules[__name__], 'running', True))
    keyboard.add_hotkey('f2', lambda: setattr(sys.modules[__name__], 'running', False))
    keyboard.wait()

if __name__ == "__main__":
    # Load calibration first
    load_calibration()

    # Global flags
    running = True
    fishing_active = False

    print("\nSol's RNG Fishing Macro with Calibration")
    print("Press F1 to start, F2 to stop.")
    print("Make sure you are standing next to water with the cast button visible.")

    listener_thread = threading.Thread(target=hotkey_listener, daemon=True)
    listener_thread.start()

    while True:
        if running:
            print("Macro started.")
            fishing_loop()
        else:
            print("Macro paused. Press F1 to resume.")
            time.sleep(1)