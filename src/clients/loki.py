from typing import Any, Dict, Optional

from utils.timeutils import step_to_logql_range


def is_loki(ds: Dict[str, Any]) -> bool:
    return bool(ds) and (ds.get("type", "").lower() == "loki")


def summarize_loki_streams_by_count(
    expr: str,
    loki_query_range_fn,
    ds_id: int,
    start_epoch: int,
    end_epoch: int,
    step_sec: int,
) -> (Optional[Dict[str, Any]], Optional[str]):
    """
    streams 결과만 나오는 LogQL을 matrix로 변환:
      sum by () (count_over_time((<expr>)[STEP]))
    """
    win = step_to_logql_range(step_sec)
    wrapped = f"sum by () (count_over_time(({expr})[{win}]))"
    resp = loki_query_range_fn(ds_id, wrapped, start_epoch, end_epoch, step_sec)
    if resp.get("status") != "success":
        return None, "조회 실패"

    data = resp.get("data", {})
    if data.get("resultType") != "matrix":
        return None, f"예상 외 resultType: {data.get('resultType')}"

    result = data.get("result", [])
    if not result:
        return None, "데이터 없음"

    values = result[0].get("values", [])
    counts = []
    for ts, val in values:
        try:
            v = float(val)
        except Exception:
            v = 0.0
        counts.append(v)

    total = sum(counts)
    duration_sec = end_epoch - start_epoch
    avg_rps = (total / duration_sec) if duration_sec > 0 else None
    max_bucket = max(counts) if counts else None
    return {
        "total": total,
        "avg_rps": avg_rps,
        "max_bucket": max_bucket,
        "bucket_range": win,
    }, None


def format_loki_matrix_block(label: str, merged: Optional[Dict[str, Any]]) -> str:
    if not merged:
        return f"  - `{label}` (loki): 데이터 없음"

    def fmt(x):
        return "n/a" if x is None else f"{x:.4g}"

    return f"  - `{label}` (loki) → avg **{fmt(merged['avg'])}**, p95 **{fmt(merged['p95'])}**, max **{fmt(merged['max'])}**"
