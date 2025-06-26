import cv2
import pytesseract
import pandas as pd
import difflib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
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

# Enhanced OCR Class
class FontAwareOCR:
    def __init__(self, font_path=None):
        self.font_path = font_path
        self.digit_templates_1080p = None
        self.digit_templates_1440p = None
        
    def generate_digit_templates(self, resolution_height):
        """Generate template images for digits 0-9 using the actual font"""
        font_size = 18 if resolution_height == 1080 else 24
        
        try:
            if self.font_path and os.path.exists(self.font_path):
                font = ImageFont.truetype(self.font_path, font_size)
            else:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()
            
        templates = {}
        
        for digit in '0123456789':
            img = Image.new('RGB', (50, 40), color='black')
            draw = ImageDraw.Draw(img)
            draw.text((10, 5), digit, fill='white', font=font)
            template = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            templates[digit] = template
            
        return templates

    def preprocess_1080p(self, image):
        """Optimized preprocessing for 1080p images"""
        # Upscale first to give OCR more pixels to work with
        height, width = image.shape[:2]
        upscaled = cv2.resize(image, (width * 2, height * 2), interpolation=cv2.INTER_CUBIC)
        
        # Convert to grayscale
        gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
        
        # Apply gentle denoising
        denoised = cv2.medianBlur(gray, 3)
        
        # Enhance contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        
        # Use adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Morphological operations to clean up text
        kernel = np.ones((2,2), np.uint8)
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return cleaned
    
    def preprocess_1440p(self, image):
        """Standard preprocessing for 1440p"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        return thresh

    def template_match_digits(self, image, templates):
        """Use template matching for better digit recognition"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        best_match = None
        best_score = 0
        
        for digit, template in templates.items():
            template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            
            # Try multiple scales
            for scale in [0.8, 1.0, 1.2]:
                scaled_template = cv2.resize(template_gray, None, fx=scale, fy=scale)
                
                if scaled_template.shape[0] > gray.shape[0] or scaled_template.shape[1] > gray.shape[1]:
                    continue
                    
                result = cv2.matchTemplate(gray, scaled_template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)
                
                if max_val > best_score:
                    best_score = max_val
                    best_match = digit
        
        return best_match if best_score > 0.6 else None

    def apply_1080p_fixes(self, text):
        """Enhanced character fixes for 1080p OCR artifacts"""
        fixes = {
            # Original fixes
            'T': '1', 'e': '4', 'a': '4', '?': '7', 'F': '7',
            # Enhanced fixes for 1080p
            'S': '5', 'g': '9', 'G': '6', 'b': '6', 'B': '8',
            'O': '0', 'o': '0', 'D': '0', 'Q': '0',
            'I': '1', 'l': '1', '|': '1', 'i': '1',
            'Z': '2', 'z': '2', 'R': '2',
            'E': '3', 'A': '4', 's': '5',
            'C': '6', 'c': '6', 'L': '7', 'P': '9'
        }
        
        result = ""
        for char in text:
            result += fixes.get(char, char)
        
        return result
    
    def extract_player_name(self, image, is_1080p):
        """Extract player names with language detection"""
        if is_1080p:
            processed = self.preprocess_1080p(image)
        else:
            processed = self.preprocess_1440p(image)
        
        # Multiple OCR attempts with different configs
        configs = [
            '--oem 3 --psm 8',  # Single word
            '--oem 3 --psm 7',  # Single text line
            '--oem 3 --psm 13'  # Raw line
        ]
        
        results = []
        for config in configs:
            try:
                text = pytesseract.image_to_string(processed, config=config, lang='eng').strip()
                if text and len(text) > 1:
                    results.append(text)
            except:
                continue
        
        # Return the most common result
        if results:
            return max(set(results), key=results.count)
        
        # Fallback to original method
        return extract_text(image, 'eng')
    
    def extract_number(self, image, is_1080p):
        """Extract numbers with template matching fallback"""
        
        # First try: Template matching for 1080p
        if is_1080p:
            if self.digit_templates_1080p is None:
                self.digit_templates_1080p = self.generate_digit_templates(1080)
            
            match_result = self.template_match_digits(image, self.digit_templates_1080p)
            if match_result is not None:
                return int(match_result)
        
        # Second try: Enhanced OCR
        if is_1080p:
            processed = self.preprocess_1080p(image)
        else:
            processed = self.preprocess_1440p(image)
        
        configs = [
            '--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789',
            '--oem 3 --psm 10 -c tessedit_char_whitelist=0123456789',
            '--oem 3 --psm 13 -c tessedit_char_whitelist=0123456789'
        ]
        
        for config in configs:
            try:
                text = pytesseract.image_to_string(processed, config=config).strip()
                
                # Apply character fixes
                if is_1080p:
                    text = self.apply_1080p_fixes(text)
                
                # Extract digits
                digits = ''.join(filter(str.isdigit, text))
                if digits:
                    return int(digits)
            except:
                continue
        
        # Fallback to original method
        try:
            text = extract_text(image)
            if is_1080p:
                text = self.apply_1080p_fixes(str(text))
            digits = ''.join(filter(str.isdigit, str(text)))
            return int(digits) if digits else 0
        except:
            return 0

# Original functions (kept for compatibility)
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
    fixes = {
        '(': '1', '{': '1', '|': '4', 'l': '1', 'I': '1', 'o': '0', 'O': '0', '"': '1', '"': '1'
    }
    cleaned = ''.join(fixes.get(c, c) for c in text)
    digits = ''.join(filter(str.isdigit, cleaned))
    return int(digits) if digits else -1

def detect_language(text):
    try:
        return detect(text)
    except:
        return 'unknown'

def extract_scoreboard(image_path, font_path=None):
    """Enhanced scoreboard extraction with font-aware OCR"""
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("Could not load image")

    img_h, img_w = img.shape[:2]
    is_1080p = img_w == 1920 and img_h == 1080

    # Initialize enhanced OCR
    if font_path is None:
        # Try to find font in common locations
        possible_fonts = [
            "valorant_font.ttf",
            "fonts/valorant_font.ttf", 
            "assets/valorant_font.ttf",
            "public/valorant_font.ttf"
        ]
        for font in possible_fonts:
            if os.path.exists(font):
                font_path = font
                break
    
    ocr_engine = FontAwareOCR(font_path)

    # Use appropriate coordinate system
    if is_1080p:
        origin = SCOREBOARD_ORIGIN_1920
        columns = COLUMNS_1920
        row_height = auto_scale(ROW_HEIGHT_2560, DEFAULT_RESOLUTION[1], img_h)
        row_spacing = auto_scale(ROW_SPACING_2560, DEFAULT_RESOLUTION[1], img_h)
    else:
        origin = SCOREBOARD_ORIGIN_2560
        columns = {
            k: (auto_scale(x1, DEFAULT_RESOLUTION[0], img_w),
                auto_scale(x2, DEFAULT_RESOLUTION[0], img_w))
            for k, (x1, x2) in COLUMNS_2560.items()
        }
        row_height = auto_scale(ROW_HEIGHT_2560, DEFAULT_RESOLUTION[1], img_h)
        row_spacing = auto_scale(ROW_SPACING_2560, DEFAULT_RESOLUTION[1], img_h)

    col_min_x = min(c[0] for c in columns.values())
    col_max_x = max(c[1] for c in columns.values())
    scoreboard_width = col_max_x - col_min_x

    bbox_x1, bbox_y1 = origin
    bbox_x2 = bbox_x1 + scoreboard_width
    bbox_y2 = bbox_y1 + row_spacing * NUM_ROWS

    # Scale map and team boxes
    def scale_box(box):
        x1, y1, x2, y2 = box
        return (
            auto_scale(x1, DEFAULT_RESOLUTION[0], img_w),
            auto_scale(y1, DEFAULT_RESOLUTION[1], img_h),
            auto_scale(x2, DEFAULT_RESOLUTION[0], img_w),
            auto_scale(y2, DEFAULT_RESOLUTION[1], img_h)
        )

    map_box = scale_box(MAP_NAME_BOX)
    team1_box = scale_box(TEAM1_ROUNDS_BOX)
    team2_box = scale_box(TEAM2_ROUNDS_BOX)

    # Extract metadata
    map_name = extract_map_name(crop_box(img, *map_box))
    
    try:
        t1_raw = color_extract_text(crop_box(img, *team1_box), color='green')
        t1_score = clean_round_score(t1_raw)
    except:
        t1_score = -1

    try:
        t2_raw = color_extract_text(crop_box(img, *team2_box), color='red')
        t2_score = clean_round_score(t2_raw)
    except:
        t2_score = -1

    winner = "Team 1" if t1_score > t2_score else "Team 2" if t2_score > t1_score else "Draw"

    # Extract scoreboard data with enhanced OCR
    player_data = []
    for i in range(NUM_ROWS):
        row_top = bbox_y1 + int(i * row_spacing)
        row_info = {}
        
        for col_name, (col_x1, col_x2) in columns.items():
            crop_x1 = bbox_x1 + (col_x1 - col_min_x)
            crop_x2 = bbox_x1 + (col_x2 - col_min_x)
            cell = img[row_top:row_top + row_height, crop_x1:crop_x2]

            if col_name == 'Player':
                # Use enhanced player name extraction
                text = ocr_engine.extract_player_name(cell, is_1080p)
                
                # Fallback to language detection if needed
                if not text or len(text) < 2:
                    primary_text = extract_text(cell, lang='eng')
                    lang_detected = detect_language(primary_text)
                    if lang_detected == 'ar':
                        text = extract_text(cell, lang='ara', adaptive=True)
                    elif lang_detected == 'ja':
                        text = extract_text(cell, lang='jpn', adaptive=True)
                    else:
                        text = primary_text
            else:
                # Use enhanced number extraction
                text = ocr_engine.extract_number(cell, is_1080p)

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
    font_path = sys.argv[2] if len(sys.argv) >= 3 else None

    try:
        map_name, t1, t2, winner, df = extract_scoreboard(image_path, font_path)
        print(json.dumps({
            "map": map_name,
            "team1_rounds": t1,
            "team2_rounds": t2,
            "winner": winner,
            "players": df.to_dict(orient="records")
        }, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
