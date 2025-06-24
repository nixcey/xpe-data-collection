import cv2
import pytesseract
import pandas as pd
import tkinter as tk
import difflib
from PIL import Image, ImageTk
from langdetect import detect
import os

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

COLUMNS_1920 = {
    'Player': (353, 620),
    'ACS': (738, 768),
    'K': (863, 883),
    'D': (913, 933),
    'A': (963, 983),
    'ECON': (1055, 1085),
    'FIRST BLOODS': (1213, 1233),
    'PLANTS': (1363, 1383),
    'DEFUSES': (1520, 1535)
}

ROW_HEIGHT_2560 = 32
ROW_SPACING_2560 = 69.7
SCOREBOARD_ORIGIN_2560 = (445, 475)
SCOREBOARD_ORIGIN_1920 = (334, 358)
TEMPLATE_BBOX_2560 = (1180, 428, 1209, 439)
TEMPLATE_BBOX_1920 = (884, 320, 908, 330)

MAP_NAMES = ["ASCENT", "BIND", "PEARL", "SPLIT", "LOTUS", "HAVEN", "ICEBOX", "SUNSET", "BREEZE", "CORRODE"]
MAP_NAME_BOX = (167, 175, 251, 187)
TEAM1_ROUNDS_BOX = (970, 120, 1080, 205)
TEAM2_ROUNDS_BOX = (1400, 120, 1525, 205)

DEBUG_FOLDER = "debug_cells"
os.makedirs(DEBUG_FOLDER, exist_ok=True)

def auto_scale(value, original, actual):
    return int(value * actual / original)

def crop_box(img, x1, y1, x2, y2):
    return img[y1:y2, x1:x2]

def color_extract_text(image, color='green'):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    if color == 'green':
        lower = (40, 40, 40)
        upper = (90, 255, 255)
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

    if color != 'red':
        mask = cv2.inRange(hsv, lower, upper)

    result = cv2.bitwise_and(image, image, mask=mask)
    gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    config = '--oem 3 --psm 7'
    return pytesseract.image_to_string(thresh, config=config, lang='eng').strip()

def extract_text(image, lang='eng', adaptive=False):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if adaptive:
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY, 11, 2)
    else:
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    config = '--oem 3 --psm 7'
    return pytesseract.image_to_string(thresh, config=config, lang=lang).strip()

def extract_map_name(region):
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    text = pytesseract.image_to_string(thresh, config="--psm 7")
    text = text.strip().upper().replace('\n', '').replace('\x0c', '')
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

def extract_scoreboard(image_path):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("Could not load image")

    img_h, img_w = img.shape[:2]
    is_1080p = img_w == 1920 and img_h == 1080

    origin = SCOREBOARD_ORIGIN_1920 if is_1080p else SCOREBOARD_ORIGIN_2560
    row_height = ROW_HEIGHT_2560 if not is_1080p else auto_scale(ROW_HEIGHT_2560, DEFAULT_RESOLUTION[1], img_h)
    row_spacing = ROW_SPACING_2560 if not is_1080p else auto_scale(ROW_SPACING_2560, DEFAULT_RESOLUTION[1], img_h)

    columns = COLUMNS_1920 if is_1080p else {
        k: (auto_scale(x1, DEFAULT_RESOLUTION[0], img_w),
            auto_scale(x2, DEFAULT_RESOLUTION[0], img_w))
        for k, (x1, x2) in COLUMNS_2560.items()
    }

    col_min_x = min(c[0] for c in columns.values())
    col_max_x = max(c[1] for c in columns.values())
    scoreboard_width = col_max_x - col_min_x
    bbox_x1, bbox_y1 = origin
    bbox_x2 = bbox_x1 + scoreboard_width
    bbox_y2 = bbox_y1 + row_spacing * NUM_ROWS

    map_box = [auto_scale(x, DEFAULT_RESOLUTION[0 if i % 2 == 0 else 1], img_w if i % 2 == 0 else img_h) for i, x in enumerate(MAP_NAME_BOX)]
    t1_box = [auto_scale(x, DEFAULT_RESOLUTION[0 if i % 2 == 0 else 1], img_w if i % 2 == 0 else img_h) for i, x in enumerate(TEAM1_ROUNDS_BOX)]
    t2_box = [auto_scale(x, DEFAULT_RESOLUTION[0 if i % 2 == 0 else 1], img_w if i % 2 == 0 else img_h) for i, x in enumerate(TEAM2_ROUNDS_BOX)]

    map_name = extract_map_name(crop_box(img, *map_box))
    t1_score = clean_round_score(color_extract_text(crop_box(img, *t1_box), 'green'))
    t2_score = clean_round_score(color_extract_text(crop_box(img, *t2_box), 'red'))
    winner = "Team 1" if t1_score > t2_score else "Team 2" if t2_score > t1_score else "Draw"

    player_data = []
    for i in range(NUM_ROWS):
        row_top = bbox_y1 + int(i * row_spacing)
        row_info = {}
        for col_name, (col_x1, col_x2) in columns.items():
            crop_x1 = bbox_x1 + (col_x1 - col_min_x)
            crop_x2 = bbox_x1 + (col_x2 - col_min_x)
            cell = img[row_top:row_top + row_height, crop_x1:crop_x2]

            debug_path = os.path.join(DEBUG_FOLDER, f"row{i}_{col_name}.png")
            cv2.imwrite(debug_path, cell)

            if col_name == 'Player':
                primary_text = extract_text(cell, lang='eng')
                lang_detected = detect_language(primary_text)
                if lang_detected == 'ar':
                    text = extract_text(cell, lang='ara', adaptive=True)
                elif lang_detected == 'ja':
                    text = extract_text(cell, lang='jpn', adaptive=True)
                else:
                    text = primary_text
            else:
                text = extract_text(cell)
                if is_1080p:
                    fixes = {'T': '1', 'e': '4', 'a': '4', '?': '7', 'F': '7'}
                    print(text)
                    text = ''.join(fixes.get(c, c) for c in text)
                    print(text)
                try:
                    text = int(''.join(filter(str.isdigit, text)))
                except:
                    text = "Unknown"

            row_info[col_name] = text
        player_data.append(row_info)

    return map_name, t1_score, t2_score, winner, pd.DataFrame(player_data)

if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print(json.dumps({"error": "No image path provided"}))
        sys.exit(1)

    image_path = sys.argv[1]

    try:
        map_name, t1, t2, winner, df = extract_scoreboard(image_path)
        print(json.dumps({
            "map": map_name,
            "team1_rounds": t1,
            "team2_rounds": t2,
            "winner": winner,
            "players": df.to_dict(orient="records")
        }, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
