#!/usr/bin/env bash

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

LOG_DIR="logs/table"
mkdir -p "${LOG_DIR}"

ABSOLUTE_RANGE=${1:-24h}
TS="$(date +%Y%m%d_%H%M%S)"

LOG_FILE="${LOG_DIR}/report_${ABSOLUTE_RANGE}_${TS}.log"

(cd src && python3 -m report_table \
                    --range "${ABSOLUTE_RANGE}") \
                    >> "${LOG_FILE}" 2>&1

echo "[OK] Started background job."
echo "[OK] Logging to ${LOG_FILE}"