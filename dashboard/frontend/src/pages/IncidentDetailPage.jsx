import { useState, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import IncidentStatusBadge from '../components/incidents/IncidentStatusBadge';

const API_URL = import.meta.env.VITE_API_URL || '';

const IncidentDetailPage = () => {
  const { id } = useParams();
  const [incident, setIncident] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState(null);
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const fetchIncident = async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/incidents/${id}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setIncident(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncident();
  }, [id]);

  const handleApprove = async () => {
    setActionLoading(true);
    setActionMsg(null);
    try {
      const res = await fetch(`${API_URL}/api/v1/incidents/${id}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ actioned_by: 'dashboard-user' }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      setActionMsg({ type: 'success', text: 'Approved — incident resolved.' });
      await fetchIncident();
    } catch (err) {
      setActionMsg({ type: 'error', text: err.message });
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    setActionLoading(true);
    setActionMsg(null);
    try {
      const res = await fetch(`${API_URL}/api/v1/incidents/${id}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ actioned_by: 'dashboard-user', reason: 'Rejected from dashboard' }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      setActionMsg({ type: 'success', text: 'Rejected — incident closed.' });
      await fetchIncident();
    } catch (err) {
      setActionMsg({ type: 'error', text: err.message });
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) return <div className="p-8 text-slate-400">Loading incident...</div>;
  if (error) return <div className="p-8 text-red-400">Error: {error}</div>;
  if (!incident) return null;

  const latestDecision = incident.agent_decisions?.[incident.agent_decisions.length - 1];
  const latestPolicy = incident.policy_checks?.[incident.policy_checks.length - 1];
  const latestApproval = incident.approval_requests?.[incident.approval_requests.length - 1];
  const isPendingApproval = latestApproval?.status === 'pending';

  return (
    <div className="space-y-6 p-4">
      {/* Header */}
      <div>
        <Link to="/incidents" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-white mb-2">
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to incidents
        </Link>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-bold text-white">
              {incident.service}
              <span className="font-normal text-slate-400"> — </span>
              {incident.title}
            </h1>
            <p className="mt-1 font-mono text-xs text-slate-400">
              {incident.namespace} · incident #{incident.id}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <IncidentStatusBadge status={incident.status} />
            <span className="font-mono text-sm text-slate-500">
              {currentTime.toLocaleTimeString('en-GB')}
            </span>
          </div>
        </div>
      </div>

      {/* Agent Decision */}
      {latestDecision && (
        <div className="rounded-lg border border-slate-700 bg-slate-900 p-4 space-y-2">
          <h2 className="text-sm font-semibold text-white">Agent Decision</h2>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="text-slate-400">Proposed Action</div>
            <div className="text-white font-mono">{latestDecision.proposed_action}</div>
            <div className="text-slate-400">Target</div>
            <div className="text-white font-mono">{latestDecision.target || '—'}</div>
            <div className="text-slate-400">Confidence</div>
            <div className="text-white">{(latestDecision.confidence * 100).toFixed(0)}%</div>
          </div>
          {latestDecision.reasoning_trace?.[0]?.output && (
            <p className="text-xs text-slate-400 mt-2 border-t border-slate-700 pt-2">
              {latestDecision.reasoning_trace[0].output}
            </p>
          )}
        </div>
      )}

      {/* Policy Check */}
      {latestPolicy && (
        <div className="rounded-lg border border-slate-700 bg-slate-900 p-4 space-y-2">
          <h2 className="text-sm font-semibold text-white">OPA Policy Check</h2>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="text-slate-400">Verdict</div>
            <div className={latestPolicy.verdict === 'approved' ? 'text-green-400' : 'text-red-400'}>
              {latestPolicy.verdict}
            </div>
            <div className="text-slate-400">Reason</div>
            <div className="text-white">{latestPolicy.reason}</div>
          </div>
        </div>
      )}

      {/* Approval Action */}
      {isPendingApproval && (
        <div className="rounded-lg border border-yellow-600 bg-slate-900 p-4 space-y-3">
          <h2 className="text-sm font-semibold text-yellow-400">Human Approval Required</h2>
          <p className="text-xs text-slate-400">
            OPA flagged this action as high-risk. A human must approve before execution.
          </p>
          {actionMsg && (
            <p className={`text-xs ${actionMsg.type === 'error' ? 'text-red-400' : 'text-green-400'}`}>
              {actionMsg.text}
            </p>
          )}
          <div className="flex gap-3">
            <button
              onClick={handleApprove}
              disabled={actionLoading}
              className="px-4 py-2 rounded bg-green-600 hover:bg-green-500 text-white text-sm font-medium disabled:opacity-50"
            >
              {actionLoading ? 'Processing...' : 'Approve'}
            </button>
            <button
              onClick={handleReject}
              disabled={actionLoading}
              className="px-4 py-2 rounded bg-red-700 hover:bg-red-600 text-white text-sm font-medium disabled:opacity-50"
            >
              {actionLoading ? 'Processing...' : 'Reject'}
            </button>
          </div>
        </div>
      )}

      {/* Audit Log */}
      {incident.audit_log?.length > 0 && (
        <div className="rounded-lg border border-slate-700 bg-slate-900 p-4 space-y-2">
          <h2 className="text-sm font-semibold text-white">Audit Log</h2>
          <div className="space-y-2">
            {incident.audit_log.map((entry, i) => (
              <div key={i} className="flex gap-3 text-xs">
                <span className="text-slate-500 font-mono whitespace-nowrap">
                  {new Date(entry.created_at).toLocaleTimeString()}
                </span>
                <span className="text-slate-400">{entry.actor}</span>
                <span className="text-white">{entry.action}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default IncidentDetailPage;
