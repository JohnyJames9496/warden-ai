#!/bin/sh
set -e
echo "[warden] ingesting runbooks..."
python -c "
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s %(message)s')
from rag.ingest import ingest_runbooks
ingest_runbooks()
"
echo "[warden] starting agent..."
exec uvicorn main:api --host 0.0.0.0 --port 8001
