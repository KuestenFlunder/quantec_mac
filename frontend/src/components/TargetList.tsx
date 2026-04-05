import { useEffect, useState } from 'react';
import type { Target, Client } from '../types';
import { fetchClients, fetchTargets } from '../api/client';

interface TargetListProps {
  onSelectTarget: (target: Target, client: Client) => void;
}

export default function TargetList({ onSelectTarget }: TargetListProps) {
  const [clients, setClients] = useState<Client[]>([]);
  const [targets, setTargets] = useState<Map<number, Target[]>>(new Map());
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const clientList = await fetchClients();
      setClients(clientList);
      const targetMap = new Map<number, Target[]>();
      const results = await Promise.all(
        clientList.map((c) => fetchTargets(c.id).then((t) => ({ clientId: c.id, targets: t })))
      );
      for (const r of results) {
        targetMap.set(r.clientId, r.targets);
      }
      setTargets(targetMap);
    } catch {
      // Fehlerbehandlung
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return <div className="loading-spinner" />;
  }

  const allTargets = clients.flatMap((client) => {
    const clientTargets = targets.get(client.id) ?? [];
    return clientTargets.map((t) => ({ target: t, client }));
  });

  const filtered = allTargets.filter(({ target, client }) => {
    const term = search.toLowerCase();
    return (
      target.name.toLowerCase().includes(term) ||
      client.last_name.toLowerCase().includes(term) ||
      client.first_name.toLowerCase().includes(term)
    );
  });

  return (
    <div>
      <div className="toolbar">
        <input
          type="text"
          className="form-input search-input"
          placeholder="Zielobjekte suchen..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {filtered.length === 0 ? (
        <div className="empty-state">
          <p>Keine Zielobjekte gefunden.</p>
          <p style={{ marginTop: 8, fontSize: '0.9em', color: 'var(--color-text-secondary)' }}>
            Zielobjekte werden ueber die Klienten-Ansicht angelegt: Klient auswaehlen → "Neues Zielobjekt"
          </p>
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Typ</th>
                <th>Klient</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(({ target, client }) => (
                <tr key={target.id} onClick={() => onSelectTarget(target, client)}>
                  <td>{target.name}</td>
                  <td>{target.target_type ?? '-'}</td>
                  <td>{client.first_name} {client.last_name}</td>
                  <td>
                    <span className={`badge ${target.active ? 'badge-active' : 'badge-inactive'}`}>
                      {target.active ? 'Aktiv' : 'Inaktiv'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
