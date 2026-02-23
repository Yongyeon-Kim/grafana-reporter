import argparse
import logging
import re
from datetime import timedelta
from typing import Dict, List, Tuple

from clients.grafana_client import GrafanaClient
from clients.loki import is_loki
from services.dashboard import (
    extract_targets,
    flatten_panels,
    panel_datasource_resolver,
)
from services.reporter import post_mattermost, send_email
from services.summarizer import compute_total_for_target
from setting.config import AppConfig
from utils.timeutils import now_kst, step_for_range, to_epoch

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--range", choices=["7d", "24h", "1d"], required=True)
    return p.parse_args()


# ✅ 추가: compute_total_for_target 가 반환한 문자열에서 total 값만 추출
_TOTAL_RX = re.compile(r"total\s+\*\*([^*]+)\*\*", re.IGNORECASE)


def _parse_total_str(line: str) -> str | None:
    """
    '  - `legend` (loki) → total **123**' 형태에서 123만 추출.
    실패 시 None
    """
    if not line:
        return None
    m = _TOTAL_RX.search(line)
    return m.group(1).strip() if m else None


# ✅ 추가: 마크다운 테이블에서 안전하게 보이도록 간단 이스케이프
def _md_escape(s: str) -> str:
    return (s or "").replace("|", r"\|").replace("\n", " ")


def main():
    args = parse_args()
    cfg = AppConfig.load()  # env에서 URL, API KEY, 대시보드 UID, 웹훅
    gf = GrafanaClient(cfg.grafana_url, cfg.grafana_api_key)  # Grafana REST 호출용

    # 시간 범위 설정
    now = now_kst()
    if args.range in ("24h", "1d"):
        start = now - timedelta(days=1)
        range_label = "지난 24시간"
        step = 3600  # 1시간 - Interval
    else:
        start = now - timedelta(days=7)
        range_label = "지난 7일"
        step = 21600  # 6시간 - Interval

    start_epoch, end_epoch = to_epoch(start), to_epoch(now)
    step = step_for_range(end_epoch - start_epoch)

    # 대시보드에서 패널 추출
    dash = gf.get_dashboard_by_uid(cfg.grafana_dashboard_uid)
    panels = flatten_panels(dash)

    skipped: List[str] = []
    all_ds = gf.list_datasources()

    grouped: Dict[str, List[Tuple[str, str]]] = {}

    # 모든 패널 순회
    for p in panels:
        title = p.get("title") or "(제목 없음)"
        # 패널에 연결된 데이터소스 해석
        ds = panel_datasource_resolver(p, gf.get_datasource_by_uid, lambda: all_ds)

        if not ds or ds.get("id") is None:
            skipped.append(f"- `{title}` (데이터소스 없음)")
            continue

        # Loki 데이터소스가 아니면 건너뜀 (Prometheus 패널 제외)
        if not is_loki(ds):
            continue

        # 패널에 정의된 쿼리(target) 추출 (expr + legend)
        targets = extract_targets(p)
        if not targets:
            skipped.append(f"- `{title}` (쿼리 없음)")
            continue

        # 각 target 쿼리(expr) 순회
        for t in targets:
            expr = t["expr"]
            legend = t["legend"] or ""

            try:
                # Loki 쿼리를 실행해 total 합계 계산 (문자열)
                line = compute_total_for_target(
                    ds=ds,
                    ds_id=ds["id"],
                    legend=legend,
                    expr=expr,
                    start_epoch=start_epoch,
                    end_epoch=end_epoch,
                    step_sec=step,
                    # prom_query_range_fn=gf.prom_query_range,
                    loki_query_range_fn=gf.loki_query_range,
                )
                if not line:
                    continue

                # ✅ total **...** 파싱해서 테이블 행으로 적재
                total_str = _parse_total_str(line)
                if total_str is not None:
                    grouped.setdefault(title, []).append(
                        (_md_escape(legend or "(no legend)"), total_str)
                    )
                else:
                    # total 추출 실패한 경우 스킵 목록에 상세 기록
                    skipped.append(
                        f"- `{title}` / `{legend}`: total 파싱 실패 → {line}"
                    )

            except Exception as e:
                skipped.append(f"- `{title}` / `{legend}`: 오류 - {e}")

    # ✅ Mattermost 메시지 본문 구성
    lines: List[str] = []
    lines.append(
        f"**LLM Gateway Unified Monitoring 요약**  \n기간: {range_label} "
        f"({start.strftime('%Y-%m-%d %H:%M')} ~ {now.strftime('%Y-%m-%d %H:%M')} KST)"
    )
    lines.append("")

    if grouped:
        # 발견된 순서를 유지(파이썬 3.7+ dict는 삽입순서 유지)
        for panel_title, rows in grouped.items():
            if not rows:
                continue

            lines.append(f"**• {panel_title}**\n")
            lines.append("| 타겟(legend) | 합계 |")
            lines.append("|:--|--:|")
            for legend, total_str in rows:
                lines.append(f"| {legend} | {total_str} |")
            lines.append("")  # 섹션 간 공백
    else:
        lines.append("_표시할 데이터가 없습니다._")
        lines.append("")

    if skipped:
        lines.append(
            "<details><summary>건너뛴 항목</summary>\n\n"
            + "\n".join(skipped)
            + "\n\n</details>"
        )

    post_mattermost(cfg.mattermost_webhook, lines)

    # ✅ Email 전송
    if cfg.email_recipients:
        subject = f"Grafana 요약 리포트 ({range_label})"
        body_md = "\n".join(lines)
        send_email(
            host=cfg.smtp_host,
            port=cfg.smtp_port,
            user=cfg.smtp_user,
            password=cfg.smtp_password,
            recipients=cfg.email_recipients,
            subject=subject,
            body_md=body_md,
        )

    logger.info(f"[OK] Sent grouped tables for {len(grouped)} panels.")


if __name__ == "__main__":
    main()
