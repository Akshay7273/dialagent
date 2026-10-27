# DialAgent (C056 OpenCV AI Competition 2026) — Day-1 slice

An agentic vision inspector that reads analog gauges from images.

## How it works (frozen agent loop, same steps every run)

1. `detect_markers` — cv2.aruco.ArucoDetector finds the 4 plate markers.
2. `estimate_homography` — cv2.findHomography with USAC_MAGSAC maps the
   detected marker corners to the canonical face.
3. `rectify_face` — cv2.warpPerspective to the canonical 800x800 view.
4. `quality_checks` — glare / low-contrast / occlusion / perspective
   flags measured on the rectified dial.
5. `method_a_warppolar` — cv2.warpPolar unwraps the red needle mask;
   the angular peak is the needle angle.
6. `method_b_pca` — cv2.PCACompute on the same needle pixels, an
   independent second read.
7. `agreement_check` + `range_check` + `bucket_decision` — the two reads
   must agree within 5 deg, the needle must be inside the calibrated
   sweep, and the outcome bucket is confident / uncertain / failed.

Every reading carries its full trace with per-tool-call latency.

## Attack-list behavior (never silently wrong)

- No markers: failed `no_markers_detected`, no guessed value.
- Homography reprojection RMS over 3 px: failed `bad_homography`.
- Needle outside the calibrated sweep: failed `needle_out_of_range`,
  never clamped to the range ends.
- Glare, low contrast, occlusion, strong perspective, partial markers,
  or dual-method disagreement: confidence capped, outcome uncertain at
  best, reason named in the trace.

## Fixtures: synthetic test data only

Everything in `fixtures/` is rendered by `generator.py` with exact
ground truth recorded in `ground_truth.json` before evaluation. These
are not field measurements and are never claimed as such.

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python generator.py   # render fixtures
.venv/bin/python evaluate.py    # eval table + Day-1 gate verdict
.venv/bin/uvicorn app:app --port 8000   # web endpoint + trace panel
```

## Day-1 gate result

See EVAL_REPORT.md. Gate: PASS only if error is within 5% of full
range on EVERY clean synthetic case.
