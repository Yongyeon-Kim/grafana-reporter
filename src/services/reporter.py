import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

import markdown
import requests

logger = logging.getLogger(__name__)


def send_email(
    host: str,
    port: int,
    user: str | None,
    password: str | None,
    recipients: list[str],
    subject: str,
    body_md: str,
) -> None:
    """
    SMTP를 통해 이메일 전송.
    """
    if not all([host, recipients]):
        logger.warning("[EMAIL SKIP] SMTP_HOST or EMAIL_RECIPIENTS is not configured.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = user or "noreply@localhost"
    msg["To"] = ", ".join(recipients)

    # HTML 본문 생성
    html_body = markdown.markdown(body_md, extensions=["tables"])
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(host, port) as server:
            if user and password:
                server.starttls()
                server.login(user, password)
            server.sendmail(msg["From"], recipients, msg.as_string())
            logger.info(f"[EMAIL OK] Sent to {', '.join(recipients)}")
    except Exception as e:
        logger.exception(f"[EMAIL ERROR] {e}")
        raise


def post_mattermost(webhook: str, lines: List[str]) -> None:
    """
    Mattermost Webhook으로 메시지 전송.
    """
    if not webhook:
        logger.error("[MATTERMOST ERROR] Webhook URL is not configured.")
        return

    payload = {
        "username": "Grafana Reporter",
        "icon_url": "https://grafana.com/static/assets/img/fav32.png",
        "text": "\n".join(lines),
    }
    logger.info(f"[MATTERMOST POST] url={webhook}")
    logger.info(f"[MATTERMOST PAYLOAD] {payload}")

    try:
        r = requests.post(webhook, json=payload, timeout=30)
        r.raise_for_status()
        logger.info(f"[MATTERMOST STATUS] {r.status_code}")
    except Exception as e:
        logger.exception(f"[MATTERMOST ERROR] {e}")
        raise
