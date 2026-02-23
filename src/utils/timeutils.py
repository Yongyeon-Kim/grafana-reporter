# timeutils.py
import logging
from datetime import datetime, timedelta, timezone

# 로깅 설정
logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    """KST 기준 현재 시간을 반환"""
    now = datetime.now(KST)
    logger.info(f"[NOW KST] {now}")
    return now


def to_epoch(dt: datetime) -> int:
    """datetime → epoch 초 단위로 변환"""
    epoch = int(dt.timestamp())
    logger.info(f"[TO EPOCH] {dt} → {epoch}")
    return epoch


def step_for_range(seconds: int) -> int:
    """
    조회 기간(초 단위)에 따라 step 크기(버킷 간격)를 결정
    - 24h 이내: 300초(5m)
    - 3d 이내: 900초(15m)
    - 그 이상: 1800초(30m)
    """
    if seconds <= 24 * 3600:  # 24h
        step = 300  # 5m
    elif seconds <= 3 * 24 * 3600:  # 3d
        step = 900  # 15m
    else:
        step = 1800  # 30m

    logger.info(f"[STEP FOR RANGE] seconds={seconds}, step={step}")
    return step


def step_to_logql_range(step_sec: int) -> str:
    """
    step 값을 LogQL range 윈도 문자열로 변환
    ex) 300 → '5m', 900 → '15m', 3600 → '1h'
    """
    if step_sec % 3600 == 0:
        win = f"{step_sec // 3600}h"
    elif step_sec % 60 == 0:
        win = f"{step_sec // 60}m"
    else:
        win = f"{step_sec}s"

    logger.info(f"[STEP TO LOGQL RANGE] step_sec={step_sec}, window={win}")
    return win
