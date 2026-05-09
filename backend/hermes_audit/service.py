"""Application service for Hermes audit orchestration."""

from __future__ import annotations

from backend.hermes_audit.client import NousHermesClient
from backend.hermes_audit.models import HermesAuditReport, HermesAuditScope
from backend.hermes_audit.storage import HermesAuditStorage


class HermesAuditService:
    """Coordinates Hermes audit execution and persistence."""

    def __init__(self, *, client: NousHermesClient, storage: HermesAuditStorage) -> None:
        self.client = client
        self.storage = storage

    def audit(self, *, scope: HermesAuditScope, target: str, payload: dict) -> HermesAuditReport:
        report = self.client.audit(scope=scope, target=target, payload=payload)
        self.storage.save_report(report)
        return report
