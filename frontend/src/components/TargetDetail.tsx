import { useEffect, useState, useRef } from 'react';
import type { Target, TargetCreate, HealingSheet } from '../types';
import { createTarget, updateTarget, fetchSheets, createSheet } from '../api/client';

interface TargetDetailProps {
  target: Target | null;
  clientId: number;
  onSaved: () => void;
  onCancel: () => void;
  onOpenSheets?: (targetId: number) => void;
}

const EMPTY_FORM: TargetCreate = {
  name: '',
  target_type: 'person',
  gender: null,
  date_of_birth: null,
  notes: null,
  active: true,
};

export default function TargetDetail({ target, clientId, onSaved, onCancel, onOpenSheets }: TargetDetailProps) {
  const [form, setForm] = useState<TargetCreate>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [photo1Preview, setPhoto1Preview] = useState<string | null>(null);
  const [photo2Preview, setPhoto2Preview] = useState<string | null>(null);
  const [_photo1File, setPhoto1File] = useState<File | null>(null);
  const [_photo2File, setPhoto2File] = useState<File | null>(null);
  const photo1Ref = useRef<HTMLInputElement>(null);
  const photo2Ref = useRef<HTMLInputElement>(null);

  const [sheets, setSheets] = useState<HealingSheet[]>([]);
  const [sheetsLoading, setSheetsLoading] = useState(false);
  const [creatingSheet, setCreatingSheet] = useState(false);

  const isNew = target === null;

  useEffect(() => {
    if (target) {
      setForm({
        name: target.name,
        target_type: target.target_type,
        gender: target.gender,
        date_of_birth: target.date_of_birth,
        notes: target.notes,
        active: target.active,
      });
      setPhoto1Preview(null);
      setPhoto2Preview(null);
      loadSheets(target.id);
    } else {
      setForm(EMPTY_FORM);
      setPhoto1Preview(null);
      setPhoto2Preview(null);
      setSheets([]);
    }
  }, [target]);

  async function loadSheets(targetId: number) {
    setSheetsLoading(true);
    try {
      const data = await fetchSheets(targetId);
      setSheets(data);
    } catch {
      // Sheets koennen spaeter geladen werden
    } finally {
      setSheetsLoading(false);
    }
  }

  function updateField(field: keyof TargetCreate, value: string | boolean | null) {
    setForm((prev) => ({ ...prev, [field]: value === '' ? null : value }));
  }

  function handlePhotoChange(photoNum: 1 | 2, e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) processFile(photoNum, file);
  }

  function removePhoto(photoNum: 1 | 2) {
    if (photoNum === 1) {
      setPhoto1Preview(null);
      setPhoto1File(null);
      if (photo1Ref.current) photo1Ref.current.value = '';
    } else {
      setPhoto2Preview(null);
      setPhoto2File(null);
      if (photo2Ref.current) photo2Ref.current.value = '';
    }
  }

  function processFile(photoNum: 1 | 2, file: File) {
    if (!file.type.startsWith('image/')) {
      setError('Bitte waehlen Sie eine Bilddatei (JPG, PNG).');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError('Bild darf maximal 10 MB gross sein.');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      if (photoNum === 1) {
        setPhoto1Preview(reader.result as string);
        setPhoto1File(file);
      } else {
        setPhoto2Preview(reader.result as string);
        setPhoto2File(file);
      }
    };
    reader.readAsDataURL(file);
    setError(null);
  }

  function handleDrop(photoNum: 1 | 2, e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    const file = e.dataTransfer.files?.[0];
    if (file) processFile(photoNum, file);
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
  }

  async function handleSave() {
    if (!form.name?.trim()) {
      setError('Name ist erforderlich.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (isNew) {
        await createTarget(clientId, form);
      } else {
        await updateTarget(target.id, form);
      }
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  }

  async function handleCreateSheet() {
    if (!target) return;
    setCreatingSheet(true);
    try {
      const sheetName = `Sheet ${sheets.length + 1}`;
      await createSheet(target.id, { name: sheetName, active: true });
      await loadSheets(target.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Fehler beim Erstellen');
    } finally {
      setCreatingSheet(false);
    }
  }

  return (
    <div>
      <div className="card">
        <div className="card-header">
          <h3>{isNew ? 'Neues Zielobjekt' : `Zielobjekt: ${target?.name}`}</h3>
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
            <label className="form-label">Name *</label>
            <input
              className="form-input"
              value={form.name ?? ''}
              onChange={(e) => updateField('name', e.target.value)}
              placeholder="Name des Zielobjekts"
            />
          </div>
          <div className="form-group">
            <label className="form-label">Typ</label>
            <select
              className="form-input"
              value={form.target_type ?? ''}
              onChange={(e) => updateField('target_type', e.target.value)}
            >
              <option value="">-</option>
              <option value="person">Person</option>
              <option value="animal">Tier</option>
              <option value="plant">Pflanze</option>
              <option value="object">Objekt</option>
              <option value="location">Ort</option>
            </select>
          </div>
        </div>

        <div className="form-row">
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

        {/* Foto-Upload Bereich */}
        <div className="form-row" style={{ gap: 24 }}>
          <div className="form-group" style={{ flex: 1 }}>
            <span className="form-label">Zielbild 1 (Hauptbild)</span>
            <div
              onDrop={(e) => handleDrop(1, e)}
              onDragOver={handleDragOver}
              style={{
                border: '2px dashed var(--color-primary-light)',
                borderRadius: 8,
                padding: 16,
                textAlign: 'center',
                backgroundColor: 'var(--color-bg-tertiary)',
                minHeight: 160,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {photo1Preview ? (
                <>
                  <img src={photo1Preview} alt="Zielbild 1"
                    style={{ maxWidth: '100%', maxHeight: 200, borderRadius: 4, objectFit: 'contain' }} />
                  <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                    <label htmlFor="photo1-input" className="btn btn-secondary" style={{ fontSize: '0.8em', cursor: 'pointer' }}>
                      Aendern
                    </label>
                    <button className="btn btn-secondary" style={{ fontSize: '0.8em' }}
                      onClick={() => removePhoto(1)} type="button">Entfernen</button>
                  </div>
                </>
              ) : (
                <label htmlFor="photo1-input" style={{
                  cursor: 'pointer', padding: 16, display: 'flex', flexDirection: 'column',
                  alignItems: 'center', width: '100%',
                }}>
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary-light)" strokeWidth="1.5">
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <circle cx="8.5" cy="8.5" r="1.5" />
                    <path d="M21 15l-5-5L5 21" />
                  </svg>
                  <span style={{ marginTop: 8, color: 'var(--color-text-secondary)', fontSize: '0.9em' }}>
                    Klicken oder Bild hierher ziehen
                  </span>
                  <span style={{ color: 'var(--color-text-secondary)', fontSize: '0.75em' }}>
                    JPG, PNG (max. 10 MB)
                  </span>
                </label>
              )}
              <input id="photo1-input" ref={photo1Ref} type="file" accept="image/*"
                style={{ display: 'none' }} onChange={(e) => handlePhotoChange(1, e)} />
            </div>
          </div>

          <div className="form-group" style={{ flex: 1 }}>
            <span className="form-label">Zielbild 2 (optional)</span>
            <div
              onDrop={(e) => handleDrop(2, e)}
              onDragOver={handleDragOver}
              style={{
                border: '2px dashed var(--color-primary-light)',
                borderRadius: 8,
                padding: 16,
                textAlign: 'center',
                backgroundColor: 'var(--color-bg-tertiary)',
                minHeight: 160,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {photo2Preview ? (
                <>
                  <img src={photo2Preview} alt="Zielbild 2"
                    style={{ maxWidth: '100%', maxHeight: 200, borderRadius: 4, objectFit: 'contain' }} />
                  <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                    <label htmlFor="photo2-input" className="btn btn-secondary" style={{ fontSize: '0.8em', cursor: 'pointer' }}>
                      Aendern
                    </label>
                    <button className="btn btn-secondary" style={{ fontSize: '0.8em' }}
                      onClick={() => removePhoto(2)} type="button">Entfernen</button>
                  </div>
                </>
              ) : (
                <label htmlFor="photo2-input" style={{
                  cursor: 'pointer', padding: 16, display: 'flex', flexDirection: 'column',
                  alignItems: 'center', width: '100%',
                }}>
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary-light)" strokeWidth="1.5">
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <circle cx="8.5" cy="8.5" r="1.5" />
                    <path d="M21 15l-5-5L5 21" />
                  </svg>
                  <span style={{ marginTop: 8, color: 'var(--color-text-secondary)', fontSize: '0.9em' }}>
                    Klicken oder Bild hierher ziehen
                  </span>
                  <span style={{ color: 'var(--color-text-secondary)', fontSize: '0.75em' }}>
                    JPG, PNG (max. 10 MB)
                  </span>
                </label>
              )}
              <input id="photo2-input" ref={photo2Ref} type="file" accept="image/*"
                style={{ display: 'none' }} onChange={(e) => handlePhotoChange(2, e)} />
            </div>
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Notizen</label>
          <textarea
            className="form-input"
            rows={3}
            value={form.notes ?? ''}
            onChange={(e) => updateField('notes', e.target.value)}
            placeholder="Behandlungsziel, Hinweise..."
          />
        </div>

        <div className="form-actions">
          <button className="btn btn-primary" onClick={handleSave} disabled={saving} type="button">
            {saving ? 'Speichert...' : isNew ? 'Zielobjekt anlegen' : 'Speichern'}
          </button>
          <button className="btn btn-secondary" onClick={onCancel} type="button">
            Zurueck zum Klienten
          </button>
        </div>
      </div>

      {/* Healing Sheets Sektion - nur bei bestehendem Zielobjekt */}
      {!isNew && target && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="card-header">
            <h3>Healing Sheets ({sheets.length})</h3>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                className="btn btn-primary"
                onClick={handleCreateSheet}
                disabled={creatingSheet}
                type="button"
              >
                {creatingSheet ? 'Erstellt...' : '+ Neues Sheet'}
              </button>
              {sheets.length > 0 && onOpenSheets && (
                <button
                  className="btn btn-secondary"
                  onClick={() => onOpenSheets(target.id)}
                  type="button"
                >
                  Sheet-Editor oeffnen
                </button>
              )}
            </div>
          </div>
          {sheetsLoading ? (
            <div className="loading-spinner" />
          ) : sheets.length > 0 ? (
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Sende-Typ</th>
                    <th>Ablaufdatum</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {sheets.map((sheet) => (
                    <tr key={sheet.id}>
                      <td>{sheet.name}</td>
                      <td>{sheet.send_type ?? 'Standard'}</td>
                      <td>{sheet.expiry_date ?? '-'}</td>
                      <td>
                        <span className={`badge ${sheet.active ? 'badge-active' : 'badge-inactive'}`}>
                          {sheet.active ? 'Aktiv' : 'Inaktiv'}
                        </span>
                      </td>
                      <td>
                        {onOpenSheets && (
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => onOpenSheets(target.id)}
                            type="button"
                          >
                            Bearbeiten
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p style={{ padding: '16px', color: 'var(--color-text-secondary)', textAlign: 'center' }}>
              Noch keine Healing Sheets. Erstellen Sie ein neues Sheet fuer dieses Zielobjekt.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
