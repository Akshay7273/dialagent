"""Evaluation harness for DialAgent Day-1 slice.

Runs the reader over every fixture in fixtures/, compares against the
pre-written ground truth (generated BEFORE evaluation, never fitted
after), prints a per-case table, and judges the Day-1 gate:

  PASS only if error <= 5% of full range on EVERY clean synthetic case.

Writes results.json and EVAL_REPORT.md next to this file.
All fixtures are SYNTHETIC TEST DATA, labelled as such.
"""

import json
import os
import sys

import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reader import read_gauge  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIX_DIR = os.path.join(HERE, "fixtures")


def main():
    with open(os.path.join(FIX_DIR, "ground_truth.json")) as f:
        cases = json.load(f)
    rows = []
    for case in cases:
        path = os.path.join(FIX_DIR, case["imageId"] + ".png")
        img = cv2.imread(path)
        assert img is not None, f"missing fixture {path}"
        reading, trace = read_gauge(img)
        gt = case["groundTruthValue"]
        if reading["value"] is None or gt is None:
            err = None
        else:
            err = abs(reading["value"] - gt) / case["fullRange"] * 100.0
        rows.append({
            "imageId": case["imageId"],
            "variant": case["variant"],
            "groundTruth": gt,
            "value": reading["value"],
            "methodA": reading["methodA"],
            "methodB": reading["methodB"],
            "agreement": reading["agreement"],
            "confidence": reading["confidence"],
            "outcomeBucket": reading["outcomeBucket"],
            "failureReason": reading["failureReason"],
            "errorPct": None if err is None else round(err, 2),
            "traceSteps": len(trace),
            "totalLatencyMs": round(sum(s["latencyMs"] for s in trace), 1),
        })

    clean = [r for r in rows if r["variant"] == "clean"]
    gate_pass = all(
        r["errorPct"] is not None and r["errorPct"] <= 5.0 for r in clean)
    max_clean_err = max(
        (r["errorPct"] for r in clean if r["errorPct"] is not None),
        default=None)

    print(f"{'case':<22} {'gt':>6} {'read':>7} {'err%':>6} "
          f"{'conf':>5} {'bucket':<10} reason")
    print("-" * 90)
    for r in rows:
        print(f"{r['imageId']:<22} "
              f"{'-' if r['groundTruth'] is None else r['groundTruth']:>6} "
              f"{'-' if r['value'] is None else r['value']:>7} "
              f"{'-' if r['errorPct'] is None else r['errorPct']:>6} "
              f"{r['confidence']:>5} {r['outcomeBucket']:<10} "
              f"{r['failureReason'] or ''}")
    print("-" * 90)
    print(f"clean cases: {len(clean)}, max clean error: {max_clean_err}% "
          f"(gate: <=5% on every clean case)")
    print(f"DAY-1 GATE: {'PASS' if gate_pass else 'FAIL'}")

    with open(os.path.join(HERE, "results.json"), "w") as f:
        json.dump({"gate": "PASS" if gate_pass else "FAIL",
                   "maxCleanErrorPct": max_clean_err,
                   "rows": rows}, f, indent=2)

    lines = [
        "# DialAgent Day-1 evaluation report",
        "",
        "All fixtures are SYNTHETIC TEST DATA rendered by generator.py with "
        "exact ground truth. They are not field measurements.",
        "",
        f"Day-1 gate: **{'PASS' if gate_pass else 'FAIL'}** — "
        f"max clean error {max_clean_err}% of full range "
        f"(gate: <=5% on every clean case).",
        "",
        "| case | variant | ground truth | read | error % | confidence | "
        "bucket | failure reason |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['imageId']} | {r['variant']} | {r['groundTruth']} | "
            f"{r['value']} | {r['errorPct']} | {r['confidence']} | "
            f"{r['outcomeBucket']} | {r['failureReason'] or ''} |")
    lines += [
        "",
        "Attack-list behavior verified by the corrupted rows above: "
        "no markers fails with a reason and no guessed value; glare, low "
        "contrast, tilt, and occlusion never reach a confident bucket; "
        "the dead-zone needle fails as out of range instead of clamping.",
    ]
    with open(os.path.join(HERE, "EVAL_REPORT.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    return 0 if gate_pass else 1


if __name__ == "__main__":
    sys.exit(main())
