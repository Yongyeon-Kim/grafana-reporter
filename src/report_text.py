import argparse
import logging
from datetime import timedelta

from clients.grafana_client import GrafanaClient
from clients.loki import is_loki
from services.dashboard import (
    extract_targets,
    flatten_panels,
    panel_datasource_resolver,
)
from services.reporter import post_mattermost
from services.summarizer import compute_total_for_target
from setting.config import AppConfig
from utils.timeutils import now_kst, to_epoch

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--range", choices=["7d", "24h", "1d"], required=True)
    return p.parse_args()


def main():
    args = parse_args()
    cfg = AppConfig.load()  # env에서 URL, API KEY, 대시보드 UID, 웹훅
    gf = GrafanaClient(
        cfg.grafana_url, cfg.grafana_api_key
    )  # Grafana REST 호출용 클라이언트 생성

    # 시간 범위 설정
    now = now_kst()
    if args.range in ("24h", "1d"):
        start = now - timedelta(days=1)
        range_label = "지난 24시간"
    else:
        start = now - timedelta(days=7)
        range_label = "지난 7일"

    start_epoch, end_epoch = to_epoch(start), to_epoch(now)
    # step = step_for_range(end_epoch - start_epoch)
    step = 21600  # 6시간

    # 대시보드에서 패널 추출
    dash = gf.get_dashboard_by_uid(cfg.grafana_dashboard_uid)
    panels = flatten_panels(dash)

    lines = []
    lines.append(
        f"**LLM Gateway Unified Monitoring 요약**  \n기간: {range_label} ({start.strftime('%Y-%m-%d %H:%M')} ~ {now.strftime('%Y-%m-%d %H:%M')} KST)"
    )
    lines.append("")

    skipped = []
    counted = 0
    all_ds = gf.list_datasources()

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

        block = [f"**• {title}**"]
        any_series = False

        # 각 target 쿼리(expr) 순회
        for t in targets:
            expr = t["expr"]
            legend = t["legend"] or ""
            try:
                # Loki 쿼리를 실행해 total 합계 계산
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
                if line is None:
                    continue

                block.append(line)
                if "total **" in line:
                    any_series = True
            except Exception as e:
                block.append(f"  - `{legend}`: 오류 - {e}")

        if any_series:
            counted += 1
            lines.append("\n".join(block))
            lines.append("")

    if skipped:
        lines.append(
            "<details><summary>건너뛴 패널</summary>\n\n"
            + "\n".join(skipped)
            + "\n\n</details>"
        )

    post_mattermost(cfg.mattermost_webhook, lines)
    logger.info(f"[OK] Sent summary for {counted} panels.")


if __name__ == "__main__":
    main()
