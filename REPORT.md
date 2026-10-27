# TECHNICAL REPORT DRAFT: DialAgent (C056 OpenCV AI Competition 2026)

Status: FINAL, verified 2026-10-27. Public repo:
https://github.com/Akshay7273/dialagent. Demo video:
https://www.youtube.com/watch?v=wniI0_Q8bFY (Unlisted, 3:38, uploaded
2026-10-27, processing and checks clean). Live endpoint:
http://47.128.224.162:8000/ (EC2 t3.micro, kept alive through Nov 9,
publicly confirmed from an independent phone browser 2026-10-27). All
numbers verified against results.json (gate PASS, max clean error
0.0%). Anything marked pending is not done yet and must not be claimed
as done.

## 1. Problem
Analog gauges are read by eye in plants, labs, and old infrastructure.
A confident wrong reading is worse than an admitted failure, so the
system must refuse to guess and must show its work.

## 2. Approach: a frozen agent loop
The same steps run in the same order on every image, and every reading
carries its trace with per tool call latency:

1. detect_markers: cv2.aruco.ArucoDetector finds the 4 plate markers.
2. estimate_homography: cv2.findHomography with USAC_MAGSAC maps
   detected marker corners to the canonical face.
3. rectify_face: cv2.warpPerspective to the canonical 800x800 view.
4. quality_checks: glare, low contrast, occlusion, and perspective
   flags measured on the rectified dial.
5. method_a_warppolar: cv2.warpPolar unwraps the needle mask; the
   angular peak is the needle angle.
6. method_b_pca: cv2.PCACompute on the same needle pixels, an
   independent second read.
7. agreement_check, range_check, bucket_decision: the two reads must
   agree within 5 degrees, the needle must sit inside the calibrated
   sweep, and the outcome bucket is confident, uncertain, or failed.

## 3. Why two methods
One method can be wrong quietly. Two independent reads that must agree
turn a silent error into a visible disagreement, which caps confidence
and names both reads in the trace.

## 4. Evaluation: synthetic fixtures with exact ground truth
All fixtures are rendered by generator.py with ground truth recorded
before evaluation. They are synthetic test data, not field
measurements, and are labelled as such.

| case | variant | ground truth | read | error pct | confidence | bucket |
|---|---|---|---|---|---|---|
| clean_000 | clean | 0.0 | 0.0 | 0.0 | 1.0 | confident |
| clean_025 | clean | 25.0 | 25.0 | 0.0 | 1.0 | confident |
| clean_050 | clean | 50.0 | 50.0 | 0.0 | 1.0 | confident |
| clean_075 | clean | 75.0 | 75.0 | 0.0 | 1.0 | confident |
| clean_100 | clean | 100.0 | 100.0 | 0.0 | 1.0 | confident |
| corrupt_glare | glare | 50.0 | 50.0 | 0.0 | 0.5 | uncertain |
| corrupt_lowcontrast | low_contrast | 50.0 | none | n/a | 0.0 | failed (bad_homography) |
| corrupt_tilt | tilt | 50.0 | 50.0 | 0.0 | 0.7 | uncertain |
| corrupt_occlusion | partial_occlusion | 50.0 | 50.0 | 0.0 | 0.55 | uncertain |
| corrupt_nomarkers | no_markers | 50.0 | none | n/a | 0.0 | failed (no_markers_detected) |
| corrupt_outofrange | out_of_range | n/a | none | n/a | 0.0 | failed (needle_out_of_range) |

Day-1 gate verdict: PASS. Max clean error 0.0 percent of full range
(gate: within 5 percent on every clean case). No fallback triggered.

## 5. Attack list behavior, verified
No markers: failed with reason, no guessed value. Needle outside the
calibrated sweep: failed, never clamped to the range ends. Glare, tilt,
and occlusion: at most uncertain, never a confident wrong number. Dual
method disagreement beyond tolerance: confidence capped and both reads
named in the trace (rule implemented and trace tested; no current
fixture triggers it, which is stated here, not hidden).

## 6. Limitations, stated plainly
- Fixtures are synthetic only. A real photo demo is pending.
- Low contrast fails loudly on homography quality (reprojection RMS
  37.6 px against a 3 px gate) instead of reading uncertain. This is
  spec compliant loud failure, but a pre homography contrast check
  would be a better behavior and is a known improvement.
- The endpoint has been smoke tested locally and is now hosted on AWS
  EC2 (t3.micro), kept alive through Nov 9.
- The demo video is recorded (Unlisted, 3:38, link in the header). The
  COOL benchmark is a Day-3 stretch only and is not part of the current
  build.

## 7. Architecture
FastAPI backend, static frontend, no exotic stack. OpenCV 5 does the
vision work. AWS hosts the endpoint (meaningful AWS component, per the
rules). No model call sits in the vision path; the math is
deterministic OpenCV.

## 8. Reproducibility
Public repo: https://github.com/Akshay7273/dialagent (public, main
branch). From the repo: create the venv, install requirements.txt, run
generator.py to render fixtures, run evaluate.py for the table and the
gate verdict, run uvicorn app:app for the endpoint and trace panel.
Deploy method (EC2 free tier, user-data script) is in the repo under
deploy/. Demo video: https://www.youtube.com/watch?v=wniI0_Q8bFY.
Live endpoint: http://47.128.224.162:8000/.
