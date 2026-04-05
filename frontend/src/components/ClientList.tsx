import { useEffect, useState } from 'react';
import type { Client } from '../types';
import { fetchClients } from '../api/client';

interface ClientListProps {
  onSelectClient: (client: Client) => void;
  onNewClient: () => void;
}

export default function ClientList({ onSelectClient, onNewClient }: ClientListProps) {
  const [clients, setClients] = useState<Client[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadClients();
  }, []);

  async function loadClients() {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchClients();
      setClients(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Fehler beim Laden');
    } finally {
      setLoading(false);
    }
  }

  const filtered = clients.filter((c) => {
    const term = search.toLowerCase();
    return (
      c.first_name.toLowerCase().includes(term) ||
      c.last_name.toLowerCase().includes(term) ||
      (c.address_city ?? '').toLowerCase().includes(term) ||
      (c.phone_home ?? '').includes(term) ||
      (c.phone_mobile ?? '').includes(term)
    );
  });

  if (loading) {
    return <div className="loading-spinner" />;
  }

  if (error) {
    return (
      <div className="card">
        <p style={{ color: 'var(--color-accent-red)' }}>Fehler: {error}</p>
        <button className="btn btn-secondary" onClick={loadClients} type="button" style={{ marginTop: 12 }}>
          Erneut versuchen
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="toolbar">
        <input
          type="text"
          className="form-input search-input"
          placeholder="Klienten suchen..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button className="btn btn-primary" onClick={onNewClient} type="button">
          + Neuer Klient
        </button>
      </div>

      {filtered.length === 0 ? (
        <div className="empty-state">
          {search ? 'Keine Klienten gefunden.' : 'Noch keine Klienten vorhanden.'}
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Vorname</th>
                <th>Nachname</th>
                <th>Stadt</th>
                <th>Telefon</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((client) => (
                <tr key={client.id} onClick={() => onSelectClient(client)}>
                  <td>{client.first_name}</td>
                  <td>{client.last_name}</td>
                  <td>{client.address_city ?? '-'}</td>
                  <td>{client.phone_mobile ?? client.phone_home ?? '-'}</td>
                  <td>
                    <span className={`badge ${client.active ? 'badge-active' : 'badge-inactive'}`}>
                      {client.active ? 'Aktiv' : 'Inaktiv'}
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
