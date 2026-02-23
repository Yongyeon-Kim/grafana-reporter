from typing import Any, Dict

from clients.loki import format_loki_matrix_block, is_loki, summarize_loki_streams_by_count
from clients.prom import is_prometheus, summarize_matrix_result


def summarize_target_block(
    ds: Dict[str, Any],
    ds_id: int,
    legend: str,
    expr: str,
    start_epoch: int,
    end_epoch: int,
    step_sec: int,
    prom_query_range_fn,
    loki_query_range_fn,
) -> str:
    label = legend if legend else "(no legend)"

    # Prometheus
    if is_prometheus(ds):
        resp = prom_query_range_fn(ds_id, expr, start_epoch, end_epoch, step_sec)
        if resp.get("status") != "success":
            return f"  - `{label}`: 조회 실패"

        data = resp.get("data", {})
        rtype = data.get("resultType")
        if rtype != "matrix":
            if rtype == "vector":
                return f"  - `{label}`: resultType=vector (범위 결과 없음)"
            return f"  - `{label}`: 지원하지 않는 resultType: {rtype}"

        merged = summarize_matrix_result(resp)
        if not merged:
            return f"  - `{label}`: 데이터 없음"

        def fmt(x):
            return "n/a" if x is None else f"{x:.4g}"

        return f"  - `{label}` → avg **{fmt(merged['avg'])}**, p95 **{fmt(merged['p95'])}**, max **{fmt(merged['max'])}**"

    # Loki
    if is_loki(ds):
        resp = loki_query_range_fn(ds_id, expr, start_epoch, end_epoch, step_sec)
        if resp.get("status") != "success":
            return f"  - `{label}`: 조회 실패"

        data = resp.get("data", {})
        rtype = data.get("resultType")
        if rtype == "matrix":
            merged = summarize_matrix_result(resp)
            return format_loki_matrix_block(label, merged)
        if rtype == "streams":
            agg, err = summarize_loki_streams_by_count(
                expr, loki_query_range_fn, ds_id, start_epoch, end_epoch, step_sec
            )
            if err:
                return f"  - `{label}` (loki): {err}"

            def fmt(x):
                return "n/a" if x is None else f"{x:.4g}"

            return (
                f"  - `{label}` (loki) → total **{fmt(agg['total'])}**, "
                f"avg_rps **{fmt(agg['avg_rps'])}**, "
                f"max_{agg['bucket_range']} **{fmt(agg['max_bucket'])}**"
            )
        return f"  - `{label}`: 지원하지 않는 resultType: {rtype}"

    return f"  - `{label}`: 미지원 데이터소스 {ds.get('type')}"
