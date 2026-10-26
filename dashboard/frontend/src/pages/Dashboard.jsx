import { useEffect, useState } from 'react';
import Header from '../components/Header';
import StatCard from '../components/StatCard';
import SentinelScoreCard from '../components/SentinelScoreCard';
import RemediationActionsList from '../components/RemediationActionsList';
import LiveIncidentFeed from '../components/LiveIncidentFeed';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function Dashboard() {
  const [overview, setOverview] = useState(null);
  const [incidents, setIncidents] = useState([]);

  useEffect(() => {
    fetch(`${API_URL}/api/v1/overview`)
      .then((r) => r.json())
      .then(setOverview)
      .catch(console.error);

    fetch(`${API_URL}/api/v1/incidents?limit=5`)
      .then((r) => r.json())
      .then((d) => setIncidents(d.items || []))
      .catch(console.error);

    const interval = setInterval(() => {
      fetch(`${API_URL}/api/v1/incidents?limit=5`)
        .then((r) => r.json())
        .then((d) => setIncidents(d.items || []))
        .catch(console.error);
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const liveIncidents = incidents.map((inc) => ({
    id: inc.id,
    title: `${inc.service} — ${inc.title}`,
    subtitle: `namespace: ${inc.namespace} · ${inc.status}`,
    status: inc.status,
    time: new Date(inc.created_at).toLocaleString(),
  }));

  return (
    <div className="bg-slate-950">
      <Header />
      <div className="flex flex-col items-stretch gap-3 p-4 lg:flex-row">
        <SentinelScoreCard score={86} maxScore={100} nodesLabel="Nodes 5/5" podsLabel="Pods 42/45" />
        <div className="flex min-w-0 flex-1 flex-col gap-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              value={overview?.active_incidents ?? '—'}
              label="Active incidents"
              subtext={overview ? `${overview.active_incidents} active` : 'loading...'}
              accentColor="red"
              subtextColor="red"
            />
            <StatCard
              value={overview?.resolved_today ?? '—'}
              label="Auto-resolved today"
              subtext={overview ? `${overview.auto_remediated_today} auto-remediated` : 'loading...'}
              accentColor="green"
              subtextColor="green"
            />
            <StatCard
              value={overview?.avg_remediation_time ?? '—'}
              label="Avg. time to remediate"
              subtext="steady"
              accentColor="white"
            />
            <StatCard
              value={overview?.actions_last_24h ?? '—'}
              label="Actions taken (24h)"
              subtext={overview ? `${overview.rollbacks_today ?? 0} rollbacks` : 'loading...'}
              accentColor="white"
              subtextColor="green"
            />
          </div>
          <RemediationActionsList actions={[]} />
        </div>
      </div>
      <div className="px-4 pb-4">
        <LiveIncidentFeed incidents={liveIncidents} />
      </div>
    </div>
  );
}

export default Dashboard;
