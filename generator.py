"""Synthetic gauge image generator for DialAgent (C056 OpenCV AI Competition).

Every image here is SYNTHETIC TEST DATA rendered by code, with exact
ground-truth values recorded alongside. Nothing here is a field
measurement, a photograph of a real gauge, or a claim about any real
installation.

Canonical gauge geometry (all coordinates in the 800x800 canonical frame):
  - canvas 800x800, dial centre (400, 400), face radius 300
  - value range 0..100, needle sweep -120 deg .. +120 deg
    (needle angle theta is measured clockwise from 12 o'clock)
  - 4 ArUco markers (DICT_4X4_50, ids 0..3, 90 px) at the plate corners
    (150,150), (650,150), (150,650), (650,650)

Variants:
  clean            straight render at a known value
  glare            bright white blob washed over the dial
  low_contrast     whole image blended toward grey
  tilt             strong perspective warp (markers still visible)
  partial_occlusion  one marker + a dial quadrant covered in black
  no_markers       dial rendered with no ArUco markers at all
  out_of_range     needle parked in the dead zone (straight down, 180 deg)
"""

import json
import math
import os

import cv2
import numpy as np

W, H = 800, 800
CX, CY = 400, 400
FACE_R = 300
NEEDLE_LEN = 250
FULL_RANGE = 100.0
MARKER_SIZE = 90
MARKER_CENTERS = [(150, 150), (650, 150), (150, 650), (650, 650)]
MARKER_IDS = [0, 1, 2, 3]
DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)


def value_to_theta(value):
    """Value 0..100 -> needle angle in degrees, clockwise from 12 o'clock."""
    return -120.0 + 2.4 * value


def theta_to_endpoint(theta_deg, length=NEEDLE_LEN):
    t = math.radians(theta_deg)
    return (int(round(CX + length * math.sin(t))),
            int(round(CY - length * math.cos(t))))


def _draw_dial(img, theta_deg):
    # plate
    img[:] = (255, 255, 255)
    # face
    cv2.circle(img, (CX, CY), FACE_R, (235, 235, 235), -1)
    cv2.circle(img, (CX, CY), FACE_R, (40, 40, 40), 2)
    # ticks: minor every 5 units, major every 25 units
    for v in range(0, 101, 5):
        th = math.radians(value_to_theta(v))
        major = (v % 25 == 0)
        r0 = 262 if major else 274
        r1 = 292
        p0 = (int(round(CX + r0 * math.sin(th))), int(round(CY - r0 * math.cos(th))))
        p1 = (int(round(CX + r1 * math.sin(th))), int(round(CY - r1 * math.cos(th))))
        cv2.line(img, p0, p1, (30, 30, 30), 3 if major else 1)
        if major:
            lr = 232
            lp = (int(round(CX + lr * math.sin(th))), int(round(CY - lr * math.cos(th))))
            cv2.putText(img, str(v), (lp[0] - 14, lp[1] + 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 30, 30), 2,
                        cv2.LINE_AA)
    # needle (pure red, no tail so the tip side is unambiguous)
    tip = theta_to_endpoint(theta_deg)
    cv2.line(img, (CX, CY), tip, (0, 0, 255), 5, cv2.LINE_AA)
    # hub
    cv2.circle(img, (CX, CY), 20, (40, 40, 40), -1)
    cv2.circle(img, (CX, CY), 7, (200, 200, 200), -1)
    return img


def _draw_markers(img):
    for mid, (mx, my) in zip(MARKER_IDS, MARKER_CENTERS):
        marker = cv2.aruco.generateImageMarker(DICT, mid, MARKER_SIZE)
        marker_bgr = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
        x0, y0 = mx - MARKER_SIZE // 2, my - MARKER_SIZE // 2
        img[y0:y0 + MARKER_SIZE, x0:x0 + MARKER_SIZE] = marker_bgr
    return img


def render(value=None, variant="clean"):
    """Render one fixture. value=None means 'no needle value' (unused)."""
    if variant == "out_of_range":
        theta = 180.0  # dead zone, straight down: outside the -120..+120 sweep
    else:
        theta = value_to_theta(value)
    img = np.zeros((H, W, 3), dtype=np.uint8)
    _draw_dial(img, theta)
    if variant != "no_markers":
        _draw_markers(img)

    if variant == "glare":
        overlay = img.copy()
        cv2.ellipse(overlay, (450, 480), (200, 130), 25, 0, 360,
                    (255, 255, 255), -1)
        cv2.ellipse(overlay, (520, 420), (90, 60), 0, 0, 360,
                    (255, 255, 255), -1)
        img = cv2.addWeighted(img, 0.25, overlay, 0.75, 0)
    elif variant == "low_contrast":
        img = cv2.addWeighted(img, 0.40, np.full_like(img, 180), 0.60, 0)
    elif variant == "tilt":
        src = np.float32([[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]])
        dst = np.float32([[120, 60], [700, 140], [640, 700], [60, 740]])
        m = cv2.getPerspectiveTransform(src, dst)
        img = cv2.warpPerspective(img, m, (W, H), borderValue=(255, 255, 255))
    elif variant == "partial_occlusion":
        # covers the bottom-right marker (id 3) and a dial quadrant
        cv2.rectangle(img, (560, 560), (W, H), (0, 0, 0), -1)
    return img


FIXTURES = [
    # (image_id, value, variant)
    ("clean_000", 0.0, "clean"),
    ("clean_025", 25.0, "clean"),
    ("clean_050", 50.0, "clean"),
    ("clean_075", 75.0, "clean"),
    ("clean_100", 100.0, "clean"),
    ("corrupt_glare", 50.0, "glare"),
    ("corrupt_lowcontrast", 50.0, "low_contrast"),
    ("corrupt_tilt", 50.0, "tilt"),
    ("corrupt_occlusion", 50.0, "partial_occlusion"),
    ("corrupt_nomarkers", 50.0, "no_markers"),
    ("corrupt_outofrange", None, "out_of_range"),
]


def generate_all(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    truth = []
    for image_id, value, variant in FIXTURES:
        img = render(value, variant)
        path = os.path.join(out_dir, image_id + ".png")
        cv2.imwrite(path, img)
        truth.append({
            "imageId": image_id,
            "groundTruthValue": value,
            "fullRange": FULL_RANGE,
            "tolerancePct": 5.0,
            "variant": variant,
            "label": "SYNTHETIC TEST DATA - rendered by generator.py, "
                     "not a field measurement",
        })
    with open(os.path.join(out_dir, "ground_truth.json"), "w") as f:
        json.dump(truth, f, indent=2)
    return truth


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    truth = generate_all(os.path.join(here, "fixtures"))
    for t in truth:
        print(t["imageId"], t["variant"], t["groundTruthValue"])
