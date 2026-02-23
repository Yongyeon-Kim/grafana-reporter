import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def flatten_panels(dashboard: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    대시보드 JSON 구조 안의 패널들을 flatten 해서 리스트로 반환.
    - row 패널 안의 panels도 재귀적으로 펼침.
    """
    out: List[Dict[str, Any]] = []

    def walk(panels):
        for p in panels:
            if p.get("type") == "row" and p.get("panels"):
                logger.info(f"[FLATTEN ROW] 포함된 패널 수={len(p['panels'])}")
                walk(p["panels"])
            else:
                logger.info(f"[ADD PANEL] title={p.get('title')}, type={p.get('type')}")
                out.append(p)

    panels = dashboard.get("panels", [])
    logger.info(f"[DASHBOARD PANELS] count={len(panels)}")
    walk(panels)
    logger.info(f"[FLATTEN RESULT] 총 패널 수={len(out)}")
    return out


def panel_datasource_resolver(
    panel: Dict[str, Any], get_ds_by_uid, list_ds
) -> Dict[str, Any] | None:
    """
    패널에 연결된 데이터소스를 찾아 반환.
    - dict(uid) 타입이면 get_ds_by_uid 사용
    - str 타입이면 list_ds() 안에서 name으로 검색
    """
    ds = panel.get("datasource")
    if not ds:
        logger.info(f"[DATASOURCE RESOLVE] panel '{panel.get('title')}' → 없음")
        return None

    if isinstance(ds, dict) and "uid" in ds:
        resolved = get_ds_by_uid(ds["uid"])
        logger.info(f"[DATASOURCE RESOLVE] uid={ds['uid']} → {resolved}")
        return resolved

    if isinstance(ds, str):
        for item in list_ds():
            if item.get("name") == ds:
                logger.info(f"[DATASOURCE RESOLVE] name={ds} → {item}")
                return item
    logger.info(
        f"[DATASOURCE RESOLVE FAIL] panel '{panel.get('title')}' datasource={ds}"
    )
    return None


def extract_targets(panel: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    패널 안의 target(expr, legend)을 추출해서 리스트로 반환.
    """
    outs = []
    for t in panel.get("targets", []):
        expr = t.get("expr") or t.get("query") or t.get("expression")
        if expr:
            legend = t.get("legendFormat") or t.get("refId") or ""
            outs.append({"expr": expr, "legend": legend})
            logger.info(
                f"[EXTRACT TARGET] panel='{panel.get('title')}', expr={expr}, legend={legend}"
            )
    logger.info(
        f"[EXTRACT TARGETS DONE] panel='{panel.get('title')}', count={len(outs)}"
    )
    return outs
