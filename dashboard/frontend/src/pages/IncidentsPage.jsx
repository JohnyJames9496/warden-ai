import { useState, useMemo, useEffect } from 'react';
import PageHeader from '../components/common/PageHeader';
import FilterTabs from '../components/common/FilterTabs';
import IncidentCard from '../components/incidents/IncidentCard';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const IncidentsPage = () => {
  const [activeTab, setActiveTab] = useState('all');
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchIncidents = async () => {
      try {
        const res = await fetch(`${API_URL}/api/v1/incidents`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const normalized = data.items.map((inc) => ({
          id: inc.id,
          service: inc.service,
          title: inc.title,
          namespace: `${inc.namespace} / ${inc.service}`,
          detail: inc.severity,
          status: inc.status,
          time: new Date(inc.created_at).toLocaleString(),
          category: statusToCategory(inc.status),
        }));
        setIncidents(normalized);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchIncidents();
    const interval = setInterval(fetchIncidents, 10000);
    return () => clearInterval(interval);
  }, []);

  const counts = useMemo(() => {
    const c = { all: 0, awaiting: 0, warning: 0, resolved: 0 };
    incidents.forEach((inc) => {
      c.all++;
      if (c[inc.category] != null) c[inc.category]++;
    });
    return c;
  }, [incidents]);

  const tabs = [
    { key: 'all', label: 'All', count: counts.all },
    { key: 'awaiting', label: 'Awaiting Approval', count: counts.awaiting },
    { key: 'warning', label: 'Warning', count: counts.warning },
    { key: 'resolved', label: 'Resolved', count: counts.resolved },
  ];

  const filteredIncidents = useMemo(() => {
    if (activeTab === 'all') return incidents;
    return incidents.filter((inc) => inc.category === activeTab);
  }, [activeTab, incidents]);

  return (
    <div>
      <PageHeader title="Incidents" subtitle="Detected anomalies across the cluster" />
      <FilterTabs tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} />

      {loading && (
        <div className="flex items-center justify-center py-16 text-sm text-slate-400">
          Loading incidents...
        </div>
      )}
      {error && (
        <div className="flex items-center justify-center py-16 text-sm text-red-400">
          Failed to load: {error}
        </div>
      )}
      {!loading && !error && (
        <div className="flex flex-col gap-3">
          {filteredIncidents.map((incident) => (
            <IncidentCard key={incident.id} incident={incident} />
          ))}
          {filteredIncidents.length === 0 && (
            <div className="flex items-center justify-center rounded-lg border border-dashed border-slate-700 py-16 text-sm text-slate-500">
              No incidents in this category
            </div>
          )}
        </div>
      )}
    </div>
  );
};

function statusToCategory(status) {
  switch (status) {
    case 'awaiting_approval': return 'awaiting';
    case 'active':
    case 'remediating': return 'warning';
    case 'resolved': return 'resolved';
    default: return 'warning';
  }
}

export default IncidentsPage;
