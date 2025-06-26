import cv2

DEFAULT_RESOLUTION = (2560, 1440)
NUM_ROWS = 10

COLUMNS_2560 = {
    'Player': (474, 780),
    'ACS': (915, 957),
    'K': (1077, 1118),
    'D': (1148, 1179),
    'A': (1216, 1246),
    'ECON': (1330, 1373),
    'FIRST BLOODS': (1546, 1576),
    'PLANTS': (1745, 1770),
    'DEFUSES': (1950, 1975)
}

ROW_HEIGHT_2560 = 30       # Visible height of each row
ROW_SPACING_2560 = 69      # Distance from top of one row to top of the next
SCOREBOARD_ORIGIN_2560 = (517, 480)
TEMPLATE_BBOX = (1180, 428, 1209, 439)

def auto_scale(value, original, actual):
    return int(value * actual / original)

def draw_debug_boxes(image_path, output_path):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("Could not load image")

    img_h, img_w = img.shape[:2]

    # Scale dimensions
    origin_x = auto_scale(SCOREBOARD_ORIGIN_2560[0], DEFAULT_RESOLUTION[0], img_w)
    origin_y = auto_scale(SCOREBOARD_ORIGIN_2560[1], DEFAULT_RESOLUTION[1], img_h)
    row_height = auto_scale(ROW_HEIGHT_2560, DEFAULT_RESOLUTION[1], img_h)
    row_spacing = auto_scale(ROW_SPACING_2560, DEFAULT_RESOLUTION[1], img_h)

    scaled_columns = {
        name: (
            auto_scale(x1, DEFAULT_RESOLUTION[0], img_w),
            auto_scale(x2, DEFAULT_RESOLUTION[0], img_w)
        )
        for name, (x1, x2) in COLUMNS_2560.items()
    }

    col_min_x = min(c[0] for c in scaled_columns.values())
    col_max_x = max(c[1] for c in scaled_columns.values())
    scoreboard_width = col_max_x - col_min_x
    scoreboard_height = row_spacing * NUM_ROWS

    # Bounding box
    bbox_x1 = origin_x
    bbox_y1 = origin_y
    bbox_x2 = origin_x + scoreboard_width
    bbox_y2 = origin_y + scoreboard_height - auto_scale(45, DEFAULT_RESOLUTION[1], img_h)

    debug_img = img.copy()

    # Draw scoreboard bbox (red)
    cv2.rectangle(debug_img, (bbox_x1, bbox_y1), (bbox_x2, bbox_y2), (0, 0, 255), 3)

    # Draw template bbox (green)
    template_x1 = auto_scale(TEMPLATE_BBOX[0], DEFAULT_RESOLUTION[0], img_w)
    template_y1 = auto_scale(TEMPLATE_BBOX[1], DEFAULT_RESOLUTION[1], img_h)
    template_x2 = auto_scale(TEMPLATE_BBOX[2], DEFAULT_RESOLUTION[0], img_w)
    template_y2 = auto_scale(TEMPLATE_BBOX[3], DEFAULT_RESOLUTION[1], img_h)
    cv2.rectangle(debug_img, (template_x1, template_y1), (template_x2, template_y2), (0, 255, 0), 3)

    # Draw columns (yellow)
    for name, (col_x1, col_x2) in scaled_columns.items():
        x1 = bbox_x1 + (col_x1 - col_min_x)
        x2 = bbox_x1 + (col_x2 - col_min_x)
        cv2.rectangle(debug_img, (x1, bbox_y1), (x2, bbox_y2), (0, 255, 255), 2)
        cv2.putText(debug_img, name, (x1 + 3, bbox_y1 + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    # Draw rows (cyan)
    for i in range(NUM_ROWS):
        y_top = bbox_y1 + i * row_spacing
        y_bottom = y_top + row_height
        cv2.rectangle(debug_img, (bbox_x1, y_top), (bbox_x2, y_bottom), (255, 255, 0), 1)
        cv2.putText(debug_img, f"Row {i}", (bbox_x1 + 5, y_top + 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

    # Save result
    cv2.imwrite(output_path, debug_img)
    print(f"Debug image saved to {output_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python debug_draw.py <input_image> <output_image>")
        sys.exit(1)

    draw_debug_boxes(sys.argv[1], sys.argv[2])
