
import cv2
import pytesseract
import pandas as pd
import tkinter as tk
import difflib
from PIL import Image, ImageTk
from langdetect import detect

DEFAULT_RESOLUTION = (2560, 1440)
NUM_ROWS = 10

COLUMNS_2560 = {
    'Player': (474, 852),
    'ACS': (987, 1037),
    'K': (1149, 1190),
    'D': (1220, 1251),
    'A': (1288, 1318),
    'ECON': (1407, 1445),
    'FIRST BLOODS': (1618, 1648),
    'PLANTS': (1823, 1842),
    'DEFUSES': (2027, 2047)
}

ROW_HEIGHT_2560 = 32
ROW_SPACING_2560 = 69.7
SCOREBOARD_ORIGIN_2560 = (445, 475)
TEMPLATE_BBOX = (1180, 428, 1209, 439)
MAP_NAMES = ["ASCENT", "BIND", "PEARL", "SPLIT", "LOTUS", "HAVEN", "ICEBOX", "SUNSET", "BREEZE", "CORRODE"]
MAP_NAME_BOX = (167, 175, 251, 187)
TEAM1_ROUNDS_BOX = (970, 120, 1080, 205)
TEAM2_ROUNDS_BOX = (1400, 120, 1525, 205)

def auto_scale(value, original, actual):
    return value * actual / original

def crop_box(img, x1, y1, x2, y2):
    return img[int(y1):int(y2), int(x1):int(x2)]

def color_extract_text(image, color='green'):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    if color == 'green':
        lower = (40, 40, 40)
        upper = (90, 255, 255)
        mask = cv2.inRange(hsv, lower, upper)
    elif color == 'red':
        lower1 = (0, 50, 50)
        upper1 = (10, 255, 255)
        lower2 = (160, 50, 50)
        upper2 = (180, 255, 255)
        mask1 = cv2.inRange(hsv, lower1, upper1)
        mask2 = cv2.inRange(hsv, lower2, upper2)
        mask = cv2.bitwise_or(mask1, mask2)
    else:
        return extract_text(image)
    result = cv2.bitwise_and(image, image, mask=mask)
    gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    config = '--oem 3 --psm 7'
    return pytesseract.image_to_string(thresh, config=config, lang='eng').strip()

def extract_text(image, lang='eng', adaptive=False, retries=True):
    def preprocess_standard(img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        return thresh

    def preprocess_adaptive(img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )

    def preprocess_robust(img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.medianBlur(gray, 3)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return thresh

    config = '--oem 3 --psm 7'

    try:
        if adaptive:
            thresh = preprocess_adaptive(image)
        else:
            thresh = preprocess_standard(image)

        text = pytesseract.image_to_string(thresh, config=config, lang=lang).strip()

        # Retry with robust preprocessing if empty or garbage
        if retries and (not text or text.strip() in ['0', '', '\x0c']):
            robust_thresh = preprocess_robust(image)
            retry_text = pytesseract.image_to_string(robust_thresh, config=config, lang=lang).strip()
            if retry_text and retry_text != text:
                text = retry_text

    except Exception:
        text = ''

    return text

def extract_map_name(region):
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    text = pytesseract.image_to_string(thresh, config="--psm 7")
    text = text.strip().upper().replace('\n', '').replace('\x0c', '')
    print("Cleaned OCR result:", repr(text))
    closest = difflib.get_close_matches(text, MAP_NAMES, n=1, cutoff=0.4)
    return closest[0] if closest else "Unknown"

def clean_round_score(text):
    fixes = {'(': '1', '{': '1', '|': '4', 'l': '1', 'I': '1', 'o': '0', 'O': '0', '“': '1', '"': '1'}
    cleaned = ''.join(fixes.get(c, c) for c in text)
    digits = ''.join(filter(str.isdigit, cleaned))
    return int(digits) if digits else -1

def detect_language(text):
    try:
        return detect(text)
    except:
        return 'unknown'

def extract_scoreboard(image_path, debug_output_path=None):
    import os
    exec(open(__file__.replace("extract_scoreboard_patched.py", "extract_scoreboard-body.py")).read())

def show_debug_window(image_path):
    window = tk.Tk()
    window.title("Scoreboard Debug Output")
    img = Image.open(image_path)
    tk_img = ImageTk.PhotoImage(img)
    label = tk.Label(window, image=tk_img)
    label.pack()
    window.mainloop()

if __name__ == "__main__":
    import sys
    import json
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No image path provided"}))
        sys.exit(1)
    image_path = sys.argv[1]
    debug_path = sys.argv[2] if len(sys.argv) >= 3 else "debug_output.jpg"
    try:
        map_name, t1, t2, winner, df = extract_scoreboard(image_path, debug_path)
        print(json.dumps({
            "map": map_name,
            "team1_rounds": t1,
            "team2_rounds": t2,
            "winner": winner,
            "players": df.to_dict(orient="records")
        }, ensure_ascii=False, indent=2))
        show_debug_window(debug_path)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
