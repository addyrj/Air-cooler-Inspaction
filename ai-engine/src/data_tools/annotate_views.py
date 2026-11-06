"""
Draw colored class-wise bounding boxes on the 3 cooler views
and save annotated images to data/annotated/.

Run:
    python src/data_tools/annotate_views.py
"""
import cv2
import numpy as np
from pathlib import Path

ROOT   = Path(__file__).parents[3]
SRC    = ROOT / "data" / "reviewed" / "good"
OUT    = ROOT / "data" / "annotated"
OUT.mkdir(parents=True, exist_ok=True)

# BGR color per category
COLORS = {
    "body":       (60,  60, 200),   # dark red  — structural body/chassis
    "label":      (0,  200,  80),   # green     — text labels / stickers
    "mechanical": (220, 80,   0),   # blue-ish  — fan, motor hub
    "control":    (0,  210, 210),   # yellow    — knobs, control panel
    "electrical": (200, 180,  0),   # cyan      — electric cable, wiring
    "water":      (200,  0, 180),   # magenta   — water components
    "fastener":   (0,  130, 255),   # orange    — screws
    "protection": (180, 180, 180),  # gray      — corrugation, protectors
}

FONT      = cv2.FONT_HERSHEY_SIMPLEX
THICKNESS = 2
FONT_SCALE = 0.52


def box(img, x1, y1, x2, y2, label, category):
    color = COLORS[category]
    cv2.rectangle(img, (x1, y1), (x2, y2), color, THICKNESS)
    # Label background
    (tw, th), _ = cv2.getTextSize(label, FONT, FONT_SCALE, 1)
    lx, ly = x1, max(y1 - 4, th + 4)
    cv2.rectangle(img, (lx, ly - th - 4), (lx + tw + 6, ly + 2), color, -1)
    cv2.putText(img, label, (lx + 3, ly - 1), FONT, FONT_SCALE, (255, 255, 255), 1, cv2.LINE_AA)


# ─── FRONT VIEW ─────────────────────────────────────────────────────────────
def annotate_front(src_name: str):
    img = cv2.imread(str(SRC / src_name))
    # Controls / top panel
    box(img,   0,   0, 960, 168, "control_panel",      "control")
    box(img,  18,  95, 175, 162, "brand_name (Brize)",  "label")
    box(img, 685,  95, 948, 162, "model_name (Glacier 110)", "label")
    box(img, 583,  42, 950,  92, "mobile_number",       "label")
    box(img, 118,  42, 580,  90, "tagline",             "label")
    box(img, 228,  62, 380, 162, "pump_knob",           "control")
    box(img, 508,  62, 655, 162, "speed_knob",          "control")
    # Mechanical
    box(img,  55, 155, 906, 822, "fan_grill",           "mechanical")
    box(img, 135, 185, 878, 812, "fan_assembly",        "mechanical")
    box(img, 410, 425, 575, 592, "motor_hub",           "mechanical")
    # Body / tank
    box(img,  28, 808, 940,1085, "lower_tank",          "body")
    box(img, 374, 917, 496,1079, "water_level_indicator","water")
    box(img,  28, 798, 940, 820, "upper-lower tank joint","body")
    # Wheels
    box(img,  58,1092, 192,1252, "caster_wheel",        "mechanical")
    box(img, 768,1092, 908,1252, "caster_wheel",        "mechanical")
    out = OUT / f"annotated_FRONT_{src_name}"
    cv2.imwrite(str(out), img)
    print(f"Saved: {out.name}")
    return out


# ─── SIDE VIEW ─────────────────────────────────────────────────────────────
def annotate_side(src_name: str):
    img = cv2.imread(str(SRC / src_name))
    # Labels / stickers
    box(img, 268, 162, 423, 318, "sticker (ISI)",       "label")
    box(img, 447, 128, 782, 232, "sticker (barcode)",   "label")
    # Electrical
    box(img, 305, 288, 520, 888, "electric_cable",      "electrical")
    # Water
    box(img, 408, 626, 792, 748, "water_inlet_label",   "water")
    box(img, 268, 748, 672, 800, "overflow_marking",    "water")
    # Body
    box(img,  28,   8, 940, 762, "cooler_body",         "body")
    box(img,  22, 755, 945, 935, "lower_tank",          "body")
    box(img,   0, 738, 960, 812, "tank joint/gap",      "body")
    # Wheels
    box(img, 228, 935, 912,1048, "caster_wheels",       "mechanical")
    out = OUT / f"annotated_SIDE_{src_name}"
    cv2.imwrite(str(out), img)
    print(f"Saved: {out.name}")
    return out


# ─── INTERNAL (BACK) VIEW ───────────────────────────────────────────────────
def annotate_internal(src_name: str):
    img = cv2.imread(str(SRC / src_name))
    # Body frame
    box(img,  28,  12, 938, 628, "cooler_body (internal)",  "body")
    # Mechanical
    box(img, 105,  98, 742, 638, "fan_frame",           "mechanical")
    box(img, 148, 138, 728, 612, "fan_assembly",        "mechanical")
    box(img, 345, 272, 532, 460, "motor_hub",           "mechanical")
    # Electrical
    box(img,  85,  98, 555, 388, "electric_wiring",     "electrical")
    box(img, 365, 302, 515, 388, "green_wire",          "electrical")
    box(img, 102, 128, 362, 355, "corrugated_sleeve",   "protection")
    # Water
    box(img, 522, 315, 608, 618, "water_pipe",          "water")
    # Tank & wheels
    box(img,  22, 618, 942, 855, "lower_tank",          "body")
    box(img, 118, 862, 302, 968, "caster_wheel",        "mechanical")
    out = OUT / f"annotated_INTERNAL_{src_name}"
    cv2.imwrite(str(out), img)
    print(f"Saved: {out.name}")
    return out


if __name__ == "__main__":
    annotate_front("WhatsApp_Image_2026-10-28_at_18.39.08.jpeg")
    annotate_side("WhatsApp_Image_2026-10-28_at_18.39.02.jpeg")
    annotate_internal("WhatsApp_Image_2026-10-28_at_18.39.39.jpeg")
    print(f"\nAll annotated images saved to: {OUT}")
