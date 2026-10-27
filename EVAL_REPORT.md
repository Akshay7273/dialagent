# DialAgent Day-1 evaluation report

All fixtures are SYNTHETIC TEST DATA rendered by generator.py with exact ground truth. They are not field measurements.

Day-1 gate: **PASS** — max clean error 0.0% of full range (gate: <=5% on every clean case).

| case | variant | ground truth | read | error % | confidence | bucket | failure reason |
|---|---|---|---|---|---|---|---|
| clean_000 | clean | 0.0 | 0.0 | 0.0 | 1.0 | confident |  |
| clean_025 | clean | 25.0 | 25.0 | 0.0 | 1.0 | confident |  |
| clean_050 | clean | 50.0 | 50.0 | 0.0 | 1.0 | confident |  |
| clean_075 | clean | 75.0 | 75.0 | 0.0 | 1.0 | confident |  |
| clean_100 | clean | 100.0 | 100.0 | 0.0 | 1.0 | confident |  |
| corrupt_glare | glare | 50.0 | 50.0 | 0.0 | 0.5 | uncertain |  |
| corrupt_lowcontrast | low_contrast | 50.0 | None | None | 0.0 | failed | bad_homography |
| corrupt_tilt | tilt | 50.0 | 50.0 | 0.0 | 0.7 | uncertain |  |
| corrupt_occlusion | partial_occlusion | 50.0 | 50.0 | 0.0 | 0.55 | uncertain |  |
| corrupt_nomarkers | no_markers | 50.0 | None | None | 0.0 | failed | no_markers_detected |
| corrupt_outofrange | out_of_range | None | None | None | 0.0 | failed | needle_out_of_range |

Attack-list behavior verified by the corrupted rows above: no markers fails with a reason and no guessed value; glare, low contrast, tilt, and occlusion never reach a confident bucket; the dead-zone needle fails as out of range instead of clamping.
