import logging
from pathlib import Path
from .store import get_client, get_runbook_collection

log = logging.getLogger("warden.rag")


def ingest_runbooks():
    client = get_client()
    col = get_runbook_collection(client)
    runbook_dir = Path(__file__).parent / "runbooks"

    ingested = 0
    for f in runbook_dir.glob("*.md"):
        text = f.read_text()
        alert_name = f.stem
        col.upsert(
            ids=[alert_name],
            documents=[text],
            metadatas=[{"alert": alert_name}],
        )
        log.info("ingested runbook: %s", alert_name)
        ingested += 1

    count = col.count()
    log.info("runbook collection size after ingest: %d", count)

    if count == 0:
        raise RuntimeError("runbook ingest produced empty collection — aborting startup")

    log.info("ingest complete: %d files ingested, %d total in collection", ingested, count)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ingest_runbooks()
