import os
import sys
from dataclasses import dataclass


def env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        print(f"[ERR] env {name} is required.", file=sys.stderr)
        sys.exit(1)
    return v.strip()


@dataclass(frozen=True)
class AppConfig:
    grafana_url: str
    grafana_api_key: str
    grafana_dashboard_uid: str
    mattermost_webhook: str

    # Email settings
    smtp_host: str | None
    smtp_port: int
    smtp_user: str | None
    smtp_password: str | None
    email_recipients: list[str]

    @staticmethod
    def load() -> "AppConfig":
        url = env("GRAFANA_URL").rstrip("/")
        recipients = os.getenv("EMAIL_RECIPIENTS")
        return AppConfig(
            grafana_url=url,
            grafana_api_key=env("GRAFANA_API_KEY"),
            grafana_dashboard_uid=env("GRAFANA_DASHBOARD_UID"),
            mattermost_webhook=env("MATTERMOST_WEBHOOK"),
            # Email settings
            smtp_host=os.getenv("SMTP_HOST"),
            smtp_port=int(os.getenv("SMTP_PORT") or 587),
            smtp_user=os.getenv("SMTP_USER"),
            smtp_password=os.getenv("SMTP_PASSWORD"),
            email_recipients=[r.strip() for r in (recipients or "").split(",") if r],
        )
