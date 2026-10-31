#!/bin/bash

echo "Starting Warden..."

# Kill any existing processes
pkill -f "uvicorn main:api" 2>/dev/null
pkill -f "uvicorn backend.main:app" 2>/dev/null
pkill -f "uvicorn main:app" 2>/dev/null
pkill -f "vite" 2>/dev/null
docker stop opa 2>/dev/null && docker rm opa 2>/dev/null

sleep 2

# Start OPA
echo "[1/5] Starting OPA..."
docker run -d --name opa -p 8181:8181 \
  -v /home/ec2-user/warden-ai/policies:/policies \
  openpolicyagent/opa:latest run --server \
  --addr 0.0.0.0:8181 \
  /policies/remediation.rego

# Start dashboard backend
echo "[2/5] Starting dashboard backend..."
cd /home/ec2-user/warden-ai/dashboard/backend
uv run uvicorn backend.main:app --port 8000 &

sleep 2

# Start agent
echo "[3/5] Starting agent..."
cd /home/ec2-user/warden-ai/agent
uv run uvicorn main:api --port 8001 &

sleep 2

# Start detector receiver
echo "[4/5] Starting detector receiver..."
cd /home/ec2-user/warden-ai/detector/receiver
uv run uvicorn main:app --port 8002 &

sleep 2

# Start frontend
echo "[5/5] Starting frontend..."
cd /home/ec2-user/warden-ai/dashboard/frontend
npm run dev &

echo ""
echo "All services started:"
echo "  Dashboard frontend  → http://localhost:5173"
echo "  Dashboard backend   → http://localhost:8000"
echo "  Agent               → http://localhost:8001"
echo "  Detector receiver   → http://localhost:8002"
echo "  OPA                 → http://localhost:8181"
echo ""
echo "Press Ctrl+C to stop all services"

wait
