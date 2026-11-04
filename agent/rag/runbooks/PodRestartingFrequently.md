# PodRestartingFrequently Runbook

## Symptoms
Pod restart count exceeds 5 in a rolling window. Pod may appear Running between crashes
but is in a soft crash loop — not yet in CrashLoopBackOff backoff state.

## Common Causes
1. Memory leak — pod grows until OOMKilled, restarts, repeats
2. Liveness probe too aggressive — killing healthy pods before they finish startup
3. Application bug causing periodic panics or unhandled exceptions
4. External dependency flapping — connection reset causing the app to exit

## Recommended Actions
- If OOMKilled in restart history: rollout_restart the deployment
- If multiple pods restarting: rollout_restart the deployment
- If single pod restarting, rest of deployment healthy: restart_pod
- If cause unknown and restarts accelerating: escalate

## Do NOT
- Ignore frequent restarts — they will escalate to CrashLoopBackOff
- Use restart_pod for OOMKilled — the pod will hit the memory limit again immediately
