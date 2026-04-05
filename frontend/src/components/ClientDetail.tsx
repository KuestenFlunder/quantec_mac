import { useEffect, useState } from 'react';
import type { Client, ClientCreate, Target } from '../types';
import { createClient, updateClient, fetchTargets } from '../api/client';

interface ClientDetailProps {
  client: Client | null;
  onSaved: () => void;
  onCancel: () => void;
  onSelectTarget: (target: Target) => void;
}

const EMPTY_FORM: ClientCreate = {
  first_name: '',
  last_name: '',
  title: null,
  salutation: null,
  letter_salutation: null,
  email: null,
  phone_home: null,
  phone_business: null,
  phone_mobile: null,
  address_street: null,
  address_zip: null,
  address_city: null,
  address_country: null,
  date_of_birth: null,
  gender: null,
  notes: null,
  active: true,
};

export default function ClientDetail({ client, onSaved, onCancel, onSelectTarget }: ClientDetailProps) {
  const [form, setForm] = useState<ClientCreate>(EMPTY_FORM);
  const [targets, setTargets] = useState<Target[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isNew = client === null;

  useEffect(() => {
    if (client) {
      setForm({
        first_name: client.first_name,
        last_name: client.last_name,
        title: client.title,
        salutation: client.salutation,
        letter_salutation: client.letter_salutation,
        email: client.email,
        phone_home: client.phone_home,
        phone_business: client.phone_business,
        phone_mobile: client.phone_mobile,
        address_street: client.address_street,
        address_zip: client.address_zip,
        address_city: client.address_city,
        address_country: client.address_country,
        date_of_birth: client.date_of_birth,
        gender: client.gender,
        notes: client.notes,
        active: client.active,
      });
      loadTargets(client.id);
    } else {
      setForm(EMPTY_FORM);
      setTargets([]);
    }
  }, [client]);

  async function loadTargets(clientId: number) {
    try {
      const data = await fetchTargets(clientId);
      setTargets(data);
    } catch {
      // Targets koennen spaeter geladen werden
    }
  }

  function updateField(field: keyof ClientCreate, value: string | boolean | null) {
    setForm((prev) => ({ ...prev, [field]: value === '' ? null : value }));
  }

  async function handleSave() {
    if (!form.first_name.trim() || !form.last_name.trim()) {
      setError('Vor- und Nachname sind erforderlich.');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      if (isNew) {
        await createClient(form);
      } else {
        await updateClient(client.id, form);
      }
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div className="card">
        <div className="card-header">
          <h3>{isNew ? 'Neuer Klient' : `${form.first_name} ${form.last_name}`}</h3>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              checked={form.active ?? true}
              onChange={(e) => updateField('active', e.target.checked)}
            />
            Aktiv
          </label>
        </div>

        {error && (
          <p style={{ color: 'var(--color-accent-red)', marginBottom: 12 }}>{error}</p>
        )}

        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Anrede</label>
            <input
              className="form-input"
              value={form.salutation ?? ''}
              onChange={(e) => updateField('salutation', e.target.value)}
              placeholder="Herr / Frau"
            />
          </div>
          <div className="form-group">
            <label className="form-label">Titel</label>
            <input
              className="form-input"
              value={form.title ?? ''}
              onChange={(e) => updateField('title', e.target.value)}
              placeholder="Dr. / Prof."
            />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Vorname *</label>
            <input
              className="form-input"
              value={form.first_name}
              onChange={(e) => updateField('first_name', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Nachname *</label>
            <input
              className="form-input"
              value={form.last_name}
              onChange={(e) => updateField('last_name', e.target.value)}
            />
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Briefanrede</label>
          <input
            className="form-input"
            value={form.letter_salutation ?? ''}
            onChange={(e) => updateField('letter_salutation', e.target.value)}
            placeholder="Sehr geehrter Herr..."
          />
        </div>

        <div className="form-row">
          <div className="form-group">
            <label className="form-label">E-Mail</label>
            <input
              className="form-input"
              type="email"
              value={form.email ?? ''}
              onChange={(e) => updateField('email', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Geschlecht</label>
            <select
              className="form-input"
              value={form.gender ?? ''}
              onChange={(e) => updateField('gender', e.target.value)}
            >
              <option value="">-</option>
              <option value="male">Maennlich</option>
              <option value="female">Weiblich</option>
              <option value="other">Divers</option>
            </select>
          </div>
        </div>

        <div className="form-row-3">
          <div className="form-group">
            <label className="form-label">Telefon (Privat)</label>
            <input
              className="form-input"
              value={form.phone_home ?? ''}
              onChange={(e) => updateField('phone_home', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Telefon (Geschaeftlich)</label>
            <input
              className="form-input"
              value={form.phone_business ?? ''}
              onChange={(e) => updateField('phone_business', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Mobiltelefon</label>
            <input
              className="form-input"
              value={form.phone_mobile ?? ''}
              onChange={(e) => updateField('phone_mobile', e.target.value)}
            />
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Strasse</label>
          <input
            className="form-input"
            value={form.address_street ?? ''}
            onChange={(e) => updateField('address_street', e.target.value)}
          />
        </div>

        <div className="form-row-3">
          <div className="form-group">
            <label className="form-label">PLZ</label>
            <input
              className="form-input"
              value={form.address_zip ?? ''}
              onChange={(e) => updateField('address_zip', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Stadt</label>
            <input
              className="form-input"
              value={form.address_city ?? ''}
              onChange={(e) => updateField('address_city', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Land</label>
            <input
              className="form-input"
              value={form.address_country ?? ''}
              onChange={(e) => updateField('address_country', e.target.value)}
            />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Geburtsdatum</label>
            <input
              className="form-input"
              type="date"
              value={form.date_of_birth ?? ''}
              onChange={(e) => updateField('date_of_birth', e.target.value)}
            />
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Notizen</label>
          <textarea
            className="form-input"
            rows={3}
            value={form.notes ?? ''}
            onChange={(e) => updateField('notes', e.target.value)}
          />
        </div>

        <div className="form-actions">
          <button className="btn btn-primary" onClick={handleSave} disabled={saving} type="button">
            {saving ? 'Speichert...' : 'Speichern'}
          </button>
          <button className="btn btn-secondary" onClick={onCancel} type="button">
            Abbrechen
          </button>
        </div>
      </div>

      {!isNew && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="card-header">
            <h3>Zielobjekte ({targets.length})</h3>
            <button className="btn btn-primary" onClick={() => onSelectTarget(null as unknown as Target)} type="button">
              + Neues Zielobjekt
            </button>
          </div>
          {targets.length > 0 ? (
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Typ</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {targets.map((t) => (
                    <tr key={t.id} onClick={() => onSelectTarget(t)}>
                      <td>{t.name}</td>
                      <td>{t.target_type ?? '-'}</td>
                      <td>
                        <span className={`badge ${t.active ? 'badge-active' : 'badge-inactive'}`}>
                          {t.active ? 'Aktiv' : 'Inaktiv'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p style={{ padding: '16px', color: 'var(--color-text-secondary)', textAlign: 'center' }}>
              Noch keine Zielobjekte. Erstellen Sie ein neues Zielobjekt fuer diesen Klienten.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
