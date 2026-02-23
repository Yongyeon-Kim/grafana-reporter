from typing import Any, Dict, Optional

from clients.loki import is_loki
from clients.prom import is_prometheus
from utils.timeutils import step_to_logql_range


def _sum_values_from_matrix(resp: Dict[str, Any]) -> float:
    """matrix 결과의 모든 시계열 샘플 값을 합산"""
    total = 0.0
    for s in resp.get("data", {}).get("result", []):
        # 각 시계열 안의 values = [(timestamp, value), ...]
        for ts, val in s.get("values", []):
            try:
                total += float(val) # 숫자로 변환 후 합계
            except Exception:
                continue
    return total


def _expr_looks_like_rate(expr: str) -> bool:
    """쿼리식이 rate/irate/increase/sum_over_time 계열인지 판별"""
    e = expr.replace(" ", "").lower()
    return (
        ("rate(" in e)
        or ("irate(" in e)
        or ("increase(" in e)
        or ("sum_over_time(" in e)
    )


def _prom_total_via_wrapper(
    expr: str,
    prom_query_range_fn,
    ds_id: int,
    start_epoch: int,
    end_epoch: int,
    step_sec: int,
) -> Optional[float]:
    """
    1) sum_over_time((<expr>)[STEP]) 로 감싸서 non-overlap 버킷 합계를 만든 뒤 합산.
       - <expr>가 rate()/increase() 등 insta​nt vector여도 동작
       - STEP=쿼리 step과 동일 → 겹치지 않는 버킷
    실패 시 None 반환.
    """
    win = step_to_logql_range(step_sec)
    wrapped = f"sum_over_time(( {expr} )[{win}])"
    try:
        resp = prom_query_range_fn(ds_id, wrapped, start_epoch, end_epoch, step_sec)
        if resp.get("status") != "success":
            return None
        if resp.get("data", {}).get("resultType") != "matrix":
            return None
        return _sum_values_from_matrix(resp)
    except Exception:
        return None


def _prom_total_fallback(
    expr: str, resp: Dict[str, Any], step_sec: int
) -> Optional[float]:
    """
    fallback: matrix 값을 그대로 합산(=버킷 합)
    - 만약 expr가 rate()/irate() 라면 '값*step'로 적분 후 합산
    - 이미 increase()/sum_over_time() 결과면 값 자체가 버킷 카운트이므로 그대로 합산
    """
    result = resp.get("data", {}).get("result", [])
    if not result:
        return 0.0

    looks_rate = _expr_looks_like_rate(expr)
    total = 0.0
    for s in result:
        for ts, val in s.get("values", []):
            try:
                v = float(val)
            except Exception:
                continue
            if looks_rate and (
                "rate(" in expr.replace(" ", "").lower()
                or "irate(" in expr.replace(" ", "").lower()
            ):
                total += v * step_sec  # rate → 적분
            else:
                total += v  # increase()/sum_over_time() 또는 이미 카운트 버킷
    return total


def compute_total_for_target(
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

    # --- Prometheus ---
    if is_prometheus(ds):
        # 1) 래퍼로 비겹치는 버킷 합 구하기 시도
        wrapped_total = _prom_total_via_wrapper(
            expr, prom_query_range_fn, ds_id, start_epoch, end_epoch, step_sec
        )
        if wrapped_total is not None:
            return f"  - `{label}` → total **{wrapped_total:.4g}**"

        # 2) 실패 시 원 쿼리로 range 실행 후 합계 추정
        try:
            resp = prom_query_range_fn(ds_id, expr, start_epoch, end_epoch, step_sec)
            if resp.get("status") != "success":
                return f"  - `{label}`: 조회 실패"
            if resp.get("data", {}).get("resultType") != "matrix":
                return f"  - `{label}`: 지원하지 않는 resultType: {resp.get('data', {}).get('resultType')}"
            total = _prom_total_fallback(expr, resp, step_sec)
            return f"  - `{label}` → total **{(total or 0.0):.4g}**"
        except Exception as e:
            return f"  - `{label}`: 오류 - {e}"

    # --- Loki ---
    if is_loki(ds):
        try:
            # 1) 그대로 실행
            resp = loki_query_range_fn(ds_id, expr, start_epoch, end_epoch, step_sec)
            if resp.get("status") != "success":
                return f"  - `{label}`: 조회 실패"
            rtype = resp.get("data", {}).get("resultType")

            if rtype == "matrix":
                # 이미 숫자 시계열(카운트/비율 등)이면 합계
                total = _sum_values_from_matrix(resp)
                return f"  - `{label}` (loki) → total **{total:.4g}**"

            if rtype == "streams":
                # streams면 count_over_time로 버킷 카운트화(비겹침) 후 합계
                win = step_to_logql_range(step_sec)
                wrapped = f"sum by () (count_over_time(({expr})[{win}]))"
                r2 = loki_query_range_fn(
                    ds_id, wrapped, start_epoch, end_epoch, step_sec
                )
                if r2.get("status") != "success":
                    return f"  - `{label}` (loki): 조회 실패"
                if r2.get("data", {}).get("resultType") != "matrix":
                    return f"  - `{label}` (loki): 예상 외 resultType: {r2.get('data', {}).get('resultType')}"
                total = _sum_values_from_matrix(r2)
                return f"  - `{label}` (loki) → total **{total:.4g}**"

            return f"  - `{label}`: 지원하지 않는 resultType: {rtype}"

        except Exception as e:
            return f"  - `{label}`: 오류 - {e}"

    return f"  - `{label}`: 미지원 데이터소스 {ds.get('type')}"
