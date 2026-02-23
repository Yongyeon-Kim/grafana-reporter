import logging
from typing import Any, Dict

from clients.loki import is_loki
from utils.timeutils import step_to_logql_range

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def _sum_values_from_matrix(resp: Dict[str, Any]) -> float:
    """
    Loki range API resultType == "matrix" → 모든 values를 합산
    """
    total = 0.0
    results = resp.get("data", {}).get("result", [])
    logger.info(f"[MATRIX RESULT COUNT] {len(results)} series")

    for s in results:
        values = s.get("values", [])
        logger.info(f"[SERIES LENGTH] {len(values)} samples")
        for ts, val in values:
            try:
                v = float(val)
                total += v
            except Exception:
                logger.info(f"[SKIP VALUE] {val}")
                continue
    logger.info(f"[MATRIX TOTAL] {total}")
    return total


def compute_total_for_target(
    ds: Dict[str, Any],
    ds_id: int,
    legend: str,
    expr: str,
    start_epoch: int,
    end_epoch: int,
    step_sec: int,
    # prom_query_range_fn,
    loki_query_range_fn,
) -> str:
    label = legend if legend else "(no legend)"

    # --- Loki ---
    if is_loki(ds):
        try:
            logger.info(f"[TARGET START] legend={label}, expr={expr}")

            # 1) 그대로 실행
            resp = loki_query_range_fn(ds_id, expr, start_epoch, end_epoch, step_sec)
            logger.info(f"[RAW RESPONSE STATUS] {resp.get('status')}")
            if resp.get("status") != "success":
                return f"  - `{label}`: 조회 실패"

            rtype = resp.get("data", {}).get("resultType")
            logger.info(f"[RESULT TYPE] {rtype}")

            # (A) 이미 숫자 시계열(예: count_over_time, rate, sum 등) → 단순 합계
            if rtype == "matrix":
                total = _sum_values_from_matrix(resp)
                return f"  - `{label}` → total **{total:.4g}**"

            # (B) 로그 라인 스트림 → count_over_time으로 '버킷 카운트' 시계열로 변환 후 합계
            if rtype == "streams":
                win = step_to_logql_range(step_sec)

                # sum by () 로 라벨 제거(단일 시계열로 합산)
                wrapped = f"sum by () (count_over_time(({expr})[{win}]))"
                logger.info(f"[WRAPPED EXPR] {wrapped}")

                # 변환된 쿼리 실행
                r2 = loki_query_range_fn(
                    ds_id, wrapped, start_epoch, end_epoch, step_sec
                )
                logger.info(f"[WRAPPED RESPONSE STATUS] {r2.get('status')}")
                if r2.get("status") != "success":
                    return f"  - `{label}`: 조회 실패"
                if r2.get("data", {}).get("resultType") != "matrix":
                    return f"  - `{label}`: 예상 외 resultType: {r2.get('data', {}).get('resultType')}"
                total = _sum_values_from_matrix(r2)
                logger.info(f"[STREAMS TOTAL AFTER COUNT] {total}")
                return f"  - `{label}` → total **{total:.4g}**"

            return f"  - `{label}`: 지원하지 않는 resultType: {rtype}"

        except Exception as e:
            logger.exception(f"[ERROR] {e}")
            return f"  - `{label}`: 오류 - {e}"

    return f"  - `{label}`: 미지원 데이터소스 {ds.get('type')}"
