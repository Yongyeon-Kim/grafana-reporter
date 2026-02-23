import requests
from typing import Any, Dict, Optional

class GrafanaClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ---- Dashboards ----
    def get_dashboard_by_uid(self, uid: str) -> Dict[str, Any]:
        r = requests.get(f"{self.base_url}/api/dashboards/uid/{uid}", headers=self.headers, timeout=30)
        r.raise_for_status()
        return r.json()["dashboard"]

    # ---- Datasources ----
    def get_datasource_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        r = requests.get(f"{self.base_url}/api/datasources/uid/{uid}", headers=self.headers, timeout=30)
        if r.status_code != 200:
            return None
        return r.json()

    def list_datasources(self) -> Dict[str, Any]:
        r = requests.get(f"{self.base_url}/api/datasources", headers=self.headers, timeout=30)
        r.raise_for_status()
        return r.json()

    # ---- Proxy calls ----
    def prom_query_range(self, ds_id: int, expr: str, start_epoch: int, end_epoch: int, step_sec: int) -> Dict[str, Any]:
        r = requests.get(
            f"{self.base_url}/api/datasources/proxy/{ds_id}/api/v1/query_range",
            headers=self.headers,
            params={"query": expr, "start": start_epoch, "end": end_epoch, "step": step_sec},
            timeout=60
        )
        r.raise_for_status()
        return r.json()

    def loki_query_range(self, ds_id: int, query: str, start_epoch: int, end_epoch: int, step_sec: int) -> Dict[str, Any]:
        r = requests.get(
            f"{self.base_url}/api/datasources/proxy/{ds_id}/loki/api/v1/query_range",
            headers=self.headers,
            params={"query": query, "start": start_epoch*1000000000, "end": end_epoch*1000000000, "step": step_sec},
            timeout=90
        )
        r.raise_for_status()
        return r.json()
