"""DialAgent reader: ArUco + USAC homography + warpPolar needle read,
plus an independent PCA needle read, agreement check, confidence, and
one outcome bucket per reading. Every reading carries its trace.

Geometry contract (same as generator.py):
  canonical frame 800x800, dial centre (400, 400), face radius 300
  value 0..100 <-> needle angle theta -120..+120 deg (clockwise from up)
  4 ArUco markers DICT_4X4_50 ids 0..3 at (150,150), (650,150),
  (150,650), (650,650), size 90 px

Attack-list rules (never violated):
  - 0 markers            -> failed "no_markers_detected", no guessed value
  - <3 markers           -> failed "insufficient_markers"
  - homography RMS > 3px -> failed "bad_homography"
  - needle in the dead zone (outside -120..+120 by more than 3 deg of
    measurement tolerance) -> failed "needle_out_of_range", never clamped
  - glare / low contrast / occlusion / strong perspective / partial
    markers / dual-method disagreement -> confidence capped, outcome
    "uncertain" at best, and the trace names the reason
  - a reading without a trace is not a reading: trace is always present
"""

import math
import time

import cv2
import numpy as np

W, H = 800, 800
CX, CY = 400, 400
FACE_R = 300
FULL_RANGE = 100.0
MARKER_SIZE = 90
MARKER_CENTERS = {0: (150, 150), 1: (650, 150), 2: (150, 650), 3: (650, 650)}
DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

# thresholds (fixed before evaluation, not fitted after)
HOMOGRAPHY_RMS_FAIL = 3.0      # px
PERSPECTIVE_RESIDUAL_FLAG = 8.0  # px vs best similarity fit
GLARE_SAT_FRAC_FLAG = 0.05     # fraction of dial pixels with all ch > 250
LOW_CONTRAST_STD_FLAG = 25.0   # grey std inside dial
OCCLUSION_BLACK_FRAC_FLAG = 0.08  # fraction of dial pixels with all ch < 40
NEEDLE_MIN_PIXELS = 200
AGREE_TOL_DEG = 5.0
OUT_OF_RANGE_TOL_DEG = 3.0     # measurement tolerance at the sweep ends

# constant per-pixel grids for the canonical frame (built once, not per read)
_YY, _XX = np.mgrid[0:H, 0:W]
_DIAL_MASK = (_XX - CX) ** 2 + (_YY - CY) ** 2 <= FACE_R ** 2
_RADIUS = np.sqrt((_XX - CX) ** 2 + (_YY - CY) ** 2)


def _trace_step(trace, name, tool, t0, output):
    trace.append({
        "step": name,
        "tool": tool,
        "latencyMs": round((time.perf_counter() - t0) * 1000, 1),
        "output": output,
    })


def _canonical_corners(mid):
    mx, my = MARKER_CENTERS[mid]
    s = MARKER_SIZE // 2
    return [(mx - s, my - s), (mx + s, my - s),
            (mx + s, my + s), (mx - s, my + s)]


def _similarity_residual(src_pts, dst_pts):
    """RMS residual (px) between the detected points and the best
    similarity (rotation + uniform scale + translation, no shear) fit
    of the same point pairs, via cv2.estimateAffinePartial2D. Large
    residual = the view is strongly perspective, not just rotated or
    scaled, so rectification is doing heavy work."""
    src = np.asarray(src_pts, dtype=np.float64)
    dst = np.asarray(dst_pts, dtype=np.float64)
    mat, _ = cv2.estimateAffinePartial2D(src, dst)
    if mat is None:
        return float("inf")
    pred = (mat[:, :2] @ src.T).T + mat[:, 2]
    return float(np.sqrt(((pred - dst) ** 2).sum(1).mean()))


def _theta_to_value(theta):
    return (theta + 120.0) / 2.4


def _direction_to_theta(dx, dy):
    """Image-space direction -> needle angle deg clockwise from up."""
    return math.degrees(math.atan2(dx, -dy))


def _wrap_deg(a):
    return (a + 180.0) % 360.0 - 180.0


def _red_mask(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    lo1, hi1 = np.array([0, 80, 80]), np.array([10, 255, 255])
    lo2, hi2 = np.array([170, 80, 80]), np.array([180, 255, 255])
    return cv2.inRange(hsv, lo1, hi1) | cv2.inRange(hsv, lo2, hi2)


def read_gauge(image_bgr):
    """Run the frozen agent loop on one image. Returns (reading, trace)."""
    trace = []
    reading = {
        "value": None, "unit": "percent of full range",
        "confidence": 0.0, "methodA": None, "methodB": None,
        "agreement": False, "outcomeBucket": "failed",
        "failureReason": None,
    }

    def fail(reason, note):
        t0 = time.perf_counter()
        reading["failureReason"] = reason
        _trace_step(trace, "bucket_decision", "rule_engine", t0,
                    f"failed: {reason} ({note})")
        return reading, trace

    # ---- step 1: marker detection -------------------------------------
    t0 = time.perf_counter()
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    detector = cv2.aruco.ArucoDetector(
        DICT, cv2.aruco.DetectorParameters())
    corners, ids, _ = detector.detectMarkers(gray)
    n_markers = 0 if ids is None else len(ids)
    _trace_step(trace, "detect_markers", "cv2.aruco.ArucoDetector", t0,
                f"markers found: {n_markers} "
                f"ids={sorted(ids.flatten().tolist()) if ids is not None else []}")
    if n_markers == 0:
        return fail("no_markers_detected",
                    "no ArUco markers visible; no value guessed")
    if n_markers < 3:
        return fail("insufficient_markers",
                    f"only {n_markers} marker(s); homography unreliable")

    src_pts, dst_pts = [], []
    for cs, mid in zip(corners, ids.flatten()):
        if int(mid) not in MARKER_CENTERS:
            continue
        src_pts.extend([tuple(map(float, c)) for c in cs[0]])
        dst_pts.extend([tuple(map(float, c)) for c in _canonical_corners(int(mid))])
    src_pts = np.array(src_pts, dtype=np.float64)
    dst_pts = np.array(dst_pts, dtype=np.float64)

    # ---- step 2: USAC homography --------------------------------------
    t0 = time.perf_counter()
    homography, _ = cv2.findHomography(
        src_pts, dst_pts, cv2.USAC_MAGSAC, 3.0)
    if homography is None or abs(np.linalg.det(homography[:2, :2])) < 1e-9:
        _trace_step(trace, "estimate_homography", "cv2.findHomography(USAC_MAGSAC)",
                    t0, "homography estimation failed (degenerate)")
        return fail("bad_homography", "homography degenerate")
    projected = cv2.perspectiveTransform(
        src_pts.reshape(-1, 1, 2), homography).reshape(-1, 2)
    rms = float(np.sqrt(((projected - dst_pts) ** 2).sum(1).mean()))
    _trace_step(trace, "estimate_homography", "cv2.findHomography(USAC_MAGSAC)",
                t0, f"reprojection RMS={rms:.2f}px over {len(src_pts)} corners")
    if rms > HOMOGRAPHY_RMS_FAIL:
        return fail("bad_homography", f"reprojection RMS {rms:.2f}px > 3px")

    # ---- step 3: rectify ----------------------------------------------
    t0 = time.perf_counter()
    rect = cv2.warpPerspective(image_bgr, homography, (W, H),
                               borderValue=(255, 255, 255))
    _trace_step(trace, "rectify_face", "cv2.warpPerspective", t0,
                "face warped to canonical 800x800 view")

    # ---- step 4: image-quality flags (on the rectified face) -----------
    t0 = time.perf_counter()
    dial_px = rect[_DIAL_MASK]
    sat_frac = float((np.all(dial_px >= 250, axis=1)).mean())
    black_frac = float((np.all(dial_px < 40, axis=1)).mean())
    grey_std = float(cv2.cvtColor(rect, cv2.COLOR_BGR2GRAY)[_DIAL_MASK].std())
    centers_img = [tuple(map(float, c)) for c in
                   [np.mean(cs[0], axis=0) for cs in corners]]
    centers_can = [MARKER_CENTERS[int(m)] for m in ids.flatten()]
    persp = _similarity_residual(centers_img, centers_can)
    flags = []
    if n_markers < 4:
        flags.append("partial_markers")
    if sat_frac > GLARE_SAT_FRAC_FLAG:
        flags.append("glare")
    if grey_std < LOW_CONTRAST_STD_FLAG:
        flags.append("low_contrast")
    if black_frac > OCCLUSION_BLACK_FRAC_FLAG:
        flags.append("occlusion")
    if persp > PERSPECTIVE_RESIDUAL_FLAG:
        flags.append("strong_perspective")
    _trace_step(trace, "quality_checks", "dial_region_metrics", t0,
                f"markers={n_markers} sat_frac={sat_frac:.3f} "
                f"black_frac={black_frac:.3f} grey_std={grey_std:.1f} "
                f"perspective_residual={persp:.1f}px flags={flags}")

    # ---- step 5: method A, warpPolar needle read -----------------------
    t0 = time.perf_counter()
    mask = _red_mask(rect)
    # keep the needle band only: radius 50..270 px from the centre
    band = mask.copy()
    band[(_RADIUS < 50) | (_RADIUS > 270)] = 0
    n_red = int((band > 0).sum())
    if n_red < NEEDLE_MIN_PIXELS:
        _trace_step(trace, "method_a_warppolar", "cv2.warpPolar", t0,
                    f"red needle pixels in band: {n_red} (too few)")
        return fail("needle_not_found", "needle mask too weak")
    # warpPolar rows = angle (0..360 over 300 rows), cols = radius
    polar = cv2.warpPolar(band, (360, 300), (CX, CY), 300,
                          cv2.WARP_POLAR_LINEAR)
    profile = polar[:, 60:324].sum(axis=1).astype(np.float64)
    # circular smoothing (5-tap) so a needle on the 0/360 seam stays one peak
    kernel = np.array([1.0, 2.0, 3.0, 2.0, 1.0])
    profile_s = np.convolve(
        np.concatenate([profile[-2:], profile, profile[:2]]),
        kernel, mode="valid") / kernel.sum()
    phi = float(np.argmax(profile_s)) / 300.0 * 360.0  # image polar angle
    # polar angle phi is atan2(dy, dx); needle angle theta is clockwise
    # from up, so theta = phi + 90 (verified: needle-up gives phi=270,
    # theta=0; needle-right gives phi=0, theta=90)
    theta_a = _wrap_deg(phi + 90.0)
    _trace_step(trace, "method_a_warppolar", "cv2.warpPolar", t0,
                f"polar peak phi={phi:.1f}deg -> theta_A={theta_a:.2f}deg "
                f"(red pixels={n_red})")

    # ---- step 6: method B, independent PCA needle read -----------------
    t0 = time.perf_counter()
    ys, xs = np.where(band > 0)
    pts = np.column_stack([xs, ys]).astype(np.float64)
    mean, eigvecs = cv2.PCACompute(pts, mean=None)
    axis = eigvecs[0]
    centroid = pts.mean(axis=0)
    to_centroid = centroid - np.array([CX, CY])
    if float(axis @ to_centroid) < 0:
        axis = -axis
    theta_b = _direction_to_theta(float(axis[0]), float(axis[1]))
    _trace_step(trace, "method_b_pca", "cv2.PCACompute", t0,
                f"principal axis=({axis[0]:.3f},{axis[1]:.3f}) "
                f"-> theta_B={theta_b:.2f}deg (pixels={len(pts)})")

    # ---- step 7: agreement + range -------------------------------------
    t0 = time.perf_counter()
    diff = abs(_wrap_deg(theta_a - theta_b))
    agreement = diff <= AGREE_TOL_DEG
    theta = theta_a  # method A is primary; B is the check
    _trace_step(trace, "agreement_check", "rule_engine", t0,
                f"theta_A={theta_a:.2f} theta_B={theta_b:.2f} "
                f"diff={diff:.2f}deg agreement={agreement}")
    if not (-120.0 - OUT_OF_RANGE_TOL_DEG <= theta <=
            120.0 + OUT_OF_RANGE_TOL_DEG):
        _trace_step(trace, "range_check", "rule_engine", t0,
                    f"theta={theta:.2f}deg outside sweep -120..+120 "
                    f"(dead zone); value NOT clamped")
        return fail("needle_out_of_range",
                    f"needle at {theta:.1f}deg is outside the calibrated sweep")

    # ---- step 8: confidence + bucket ------------------------------------
    t0 = time.perf_counter()
    conf = 1.0
    if "partial_markers" in flags:
        conf = min(conf, 0.55)
    if "glare" in flags or "low_contrast" in flags:
        conf = min(conf, 0.50)
    if "occlusion" in flags:
        conf = min(conf, 0.55)
    if "strong_perspective" in flags:
        conf = min(conf, 0.70)
    if not agreement:
        conf = min(conf, 0.50)
        flags.append("dual_method_disagreement")
    value = min(max(_theta_to_value(theta), 0.0), FULL_RANGE)
    value = round(value, 2)
    if conf >= 0.8 and agreement and not flags:
        bucket = "confident"
    else:
        bucket = "uncertain"
    reading.update({
        "value": value, "confidence": round(conf, 2),
        "methodA": round(_theta_to_value(theta_a), 2),
        "methodB": round(_theta_to_value(theta_b), 2),
        "agreement": agreement, "outcomeBucket": bucket,
        "failureReason": None,
    })
    _trace_step(trace, "bucket_decision", "rule_engine", t0,
                f"value={value} confidence={conf:.2f} bucket={bucket} "
                f"flags={flags}" + ("" if agreement else
                f" (methodA={reading['methodA']} methodB={reading['methodB']} disagree)"))
    return reading, trace
