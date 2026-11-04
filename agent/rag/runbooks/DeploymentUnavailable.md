# DeploymentUnavailable Runbook

## Symptoms
Deployment has fewer available replicas than desired. Alert fires when available < desired
for more than 2 minutes.

## Common Causes
1. Pod crash loop — OOMKilled or CrashLoopBackOff preventing replicas from becoming ready
2. Image pull failure — wrong tag, registry unreachable, or missing pull secret
3. Bad rollout — new version failing readiness probe
4. Node pressure — no schedulable nodes available for pending pods

## Recommended Actions
- If pods show CrashLoopBackOff or OOMKilled: rollout_restart the deployment
- If image pull failure: escalate — automated restart will not fix a missing image
- If recent deployment caused the regression: rollout_restart to trigger re-evaluation
- If node pressure: escalate — pod-level actions will not help

## Do NOT
- Use restart_pod — the deployment controller will reschedule it anyway
- Ignore — a deployment with 0 available replicas means the service is down
