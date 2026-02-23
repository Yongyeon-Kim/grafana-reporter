#!/usr/bin/env bash

set -a
source .env
set +a

LOG_DIR="logs/text"
mkdir -p "${LOG_DIR}"

ABSOLUTE_RANGE=7d # 24h
TS="$(date +%Y%m%d_%H%M%S)"

LOG_FILE="${LOG_DIR}/report_${ABSOLUTE_RANGE}_${TS}.log"

(cd src && python3 -m report_text \
    --range "${ABSOLUTE_RANGE}") \
    >> "${LOG_FILE}" 2>&1 &

echo "[OK] Started background job."
echo "[OK] Logging to ${LOG_FILE}"

# # crontab -e
# # 매일 09:00 KST에 지난 24시간 보고
# 0 9 * * * /usr/bin/env bash -lc 'cd /opt/monitor && /usr/bin/python3 grafana_dash_pull_and_alert.py --range 24h'
# # 매주 월요일 09:30 KST에 지난 7일 보고
# 30 9 * * 1 /usr/bin/env bash -lc 'cd /opt/monitor && /usr/bin/python3 grafana_dash_pull_and_alert.py --range 7d'