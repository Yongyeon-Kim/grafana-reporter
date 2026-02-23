import math
from typing import Any, Dict, List, Optional, Tuple


def is_prometheus(ds: Dict[str, Any]) -> bool:
    return bool(ds) and (ds.get("type", "").lower() == "prometheus")


def p95(values: List[float]) -> Optional[float]:
    if not values:
        return None
    arr = sorted(values)
    idx = int(math.ceil(0.95 * len(arr))) - 1
    idx = max(0, min(idx, len(arr) - 1))
    return arr[idx]


def summarize_series(samples: List[Tuple[int, float]]) -> Dict[str, Optional[float]]:
    vals = [
        v
        for _, v in samples
        if v is not None and not math.isnan(v) and not math.isinf(v)
    ]
    if not vals:
        return {"avg": None, "p95": None, "max": None}
    return {"avg": sum(vals) / len(vals), "p95": p95(vals), "max": max(vals)}


def summarize_matrix_result(
    resp: Dict[str, Any],
) -> Optional[Dict[str, Optional[float]]]:
    series = resp.get("data", {}).get("result", [])
    if not series:
        return None
    series_summaries = []
    for s in series:
        samples = []
        for ts, val in s.get("values", []):
            try:
                v = float(val)
            except Exception:
                v = None
            samples.append((int(float(ts)), v))
        series_summaries.append(summarize_series(samples))

    def safe_mean(xs):
        xs = [x for x in xs if x is not None]
        return sum(xs) / len(xs) if xs else None

    merged = {
        "avg": safe_mean([s["avg"] for s in series_summaries]),
        "p95": safe_mean([s["p95"] for s in series_summaries]),
        "max": max(
            [s["max"] for s in series_summaries if s["max"] is not None], default=None
        ),
    }
    return merged
