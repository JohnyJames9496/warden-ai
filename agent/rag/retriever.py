import logging
from .store import get_runbook_collection, get_incident_collection

log = logging.getLogger("warden.rag")


def get_runbook(alert_name: str, n_results: int = 1) -> str:
    try:
        col = get_runbook_collection()
        results = col.query(query_texts=[alert_name], n_results=n_results)
        docs = results.get("documents", [[]])[0]
        return "\n\n".join(docs) if docs else ""
    except Exception as exc:
        log.warning("runbook retrieval failed for '%s': %s", alert_name, exc)
        return ""


def get_similar_incidents(description: str, n_results: int = 3) -> str:
    col = get_incident_collection()
    try:
        results = col.query(query_texts=[description], n_results=n_results)
        docs = results.get("documents", [[]])[0]
        return "\n\n".join(docs) if docs else ""
    except Exception:
        return ""


def store_incident(incident_id: str, description: str, action: str, outcome: str):
    col = get_incident_collection()
    col.upsert(
        ids=[incident_id],
        documents=[f"Incident: {description}\nAction taken: {action}\nOutcome: {outcome}"],
        metadatas=[{"action": action}],
    )
