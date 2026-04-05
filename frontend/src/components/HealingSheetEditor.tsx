import { useEffect, useState } from 'react';
import type { HealingSheet, HealingSheetItem, HealingSheetUpdate } from '../types';
import { fetchSheets, createSheet, fetchSheetItems, updateSheet, deleteSheet, deleteSheetItem } from '../api/client';

interface HealingSheetEditorProps {
  targetId: number;
  onBack?: () => void;
  onOpenMorphicBrowser: (sheetId: number) => void;
  onStartScan?: (sheetId: number) => void;
}

export default function HealingSheetEditor({ targetId, onBack, onOpenMorphicBrowser, onStartScan }: HealingSheetEditorProps) {
  const [sheets, setSheets] = useState<HealingSheet[]>([]);
  const [selectedSheet, setSelectedSheet] = useState<HealingSheet | null>(null);
  const [items, setItems] = useState<HealingSheetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [editForm, setEditForm] = useState<HealingSheetUpdate>({});
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    loadSheets();
  }, [targetId]);

  async function loadSheets() {
    setLoading(true);
    try {
      const data = await fetchSheets(targetId);
      setSheets(data);
      if (data.length > 0 && data[0]) {
        selectSheet(data[0]);
      } else {
        setSelectedSheet(null);
        setItems([]);
      }
    } catch {
      // Fehlerbehandlung
    } finally {
      setLoading(false);
    }
  }

  async function selectSheet(sheet: HealingSheet) {
    setSelectedSheet(sheet);
    setEditForm({
      name: sheet.name,
      send_type: sheet.send_type,
      expiry_date: sheet.expiry_date,
      active: sheet.active,
    });
    try {
      const itemData = await fetchSheetItems(sheet.id);
      setItems(itemData);
    } catch {
      setItems([]);
    }
  }

  async function handleCreateSheet() {
    setCreating(true);
    try {
      const sheetName = `Sheet ${sheets.length + 1}`;
      const newSheet = await createSheet(targetId, { name: sheetName, active: true });
      await loadSheets();
      selectSheet(newSheet);
    } catch {
      // Fehlerbehandlung
    } finally {
      setCreating(false);
    }
  }

  async function handleSaveSheet() {
    if (!selectedSheet) return;
    try {
      await updateSheet(selectedSheet.id, editForm);
      await loadSheets();
    } catch {
      // Fehlerbehandlung
    }
  }

  async function handleDeleteSheet() {
    if (!selectedSheet) return;
    if (!confirm(`Sheet "${selectedSheet.name}" wirklich loeschen?`)) return;
    try {
      await deleteSheet(selectedSheet.id);
      setSelectedSheet(null);
      setItems([]);
      await loadSheets();
    } catch {
      // Fehlerbehandlung
    }
  }

  async function handleDeleteItem(itemId: number) {
    if (!selectedSheet) return;
    try {
      await deleteSheetItem(selectedSheet.id, itemId);
      setItems((prev) => prev.filter((i) => i.id !== itemId));
    } catch {
      // Fehlerbehandlung
    }
  }

  function handleStartScan() {
    if (!selectedSheet || !onStartScan) return;
    onStartScan(selectedSheet.id);
  }

  if (loading) {
    return <div className="loading-spinner" />;
  }

  return (
    <div>
      {onBack && (
        <div style={{ marginBottom: 'var(--spacing-md)' }}>
          <button className="btn btn-secondary btn-sm" onClick={onBack} type="button">
            ← Zurueck zum Zielobjekt
          </button>
        </div>
      )}

      <div className="split-pane">
        <div className="split-pane-left">
          <div style={{
            padding: 'var(--spacing-md)',
            borderBottom: '1px solid var(--color-border)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <strong style={{ fontSize: 'var(--font-size-sm)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
              Healing Sheets
            </strong>
            <button
              className="btn btn-primary btn-sm"
              onClick={handleCreateSheet}
              disabled={creating}
              type="button"
            >
              {creating ? '...' : '+ Neu'}
            </button>
          </div>
          {sheets.length === 0 ? (
            <div className="empty-state" style={{ padding: 'var(--spacing-lg)' }}>
              <p>Keine Sheets vorhanden.</p>
              <p style={{ marginTop: 8, fontSize: '0.9em', opacity: 0.6 }}>
                Erstellen Sie ein neues Healing Sheet.
              </p>
            </div>
          ) : (
            sheets.map((sheet) => (
              <div
                key={sheet.id}
                className={`list-item${selectedSheet?.id === sheet.id ? ' active' : ''}`}
                onClick={() => selectSheet(sheet)}
              >
                <div style={{ fontWeight: 500 }}>{sheet.name}</div>
                <div style={{ fontSize: 'var(--font-size-sm)', opacity: 0.6 }}>
                  {sheet.send_type ?? 'Standard'} | {sheet.active ? 'Aktiv' : 'Inaktiv'}
                </div>
              </div>
            ))
          )}
        </div>

        <div className="split-pane-right">
          {selectedSheet ? (
            <>
              <div style={{ marginBottom: 'var(--spacing-lg)' }}>
                <div className="form-row-3">
                  <div className="form-group">
                    <label className="form-label">Name</label>
                    <input
                      className="form-input"
                      value={editForm.name ?? ''}
                      onChange={(e) => setEditForm((p) => ({ ...p, name: e.target.value }))}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Sende-Typ</label>
                    <select
                      className="form-input"
                      value={editForm.send_type ?? ''}
                      onChange={(e) => setEditForm((p) => ({ ...p, send_type: e.target.value || null }))}
                    >
                      <option value="">Standard</option>
                      <option value="continuous">Kontinuierlich</option>
                      <option value="interval">Intervall</option>
                      <option value="single">Einmalig</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Ablaufdatum</label>
                    <input
                      className="form-input"
                      type="date"
                      value={editForm.expiry_date ?? ''}
                      onChange={(e) => setEditForm((p) => ({ ...p, expiry_date: e.target.value || null }))}
                    />
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 'var(--spacing-md)', flexWrap: 'wrap' }}>
                  <button className="btn btn-primary btn-sm" onClick={handleSaveSheet} type="button">
                    Sheet speichern
                  </button>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => onOpenMorphicBrowser(selectedSheet.id)}
                    type="button"
                  >
                    + Item aus Morphischen Feldern
                  </button>
                  <button className="btn btn-success btn-sm" onClick={handleStartScan} type="button">
                    Scan starten
                  </button>
                  <button className="btn btn-danger btn-sm" onClick={handleDeleteSheet} type="button">
                    Sheet loeschen
                  </button>
                </div>
              </div>

              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Text</th>
                      <th>Potenz</th>
                      <th>Intensitaet</th>
                      <th>QRS</th>
                      <th>Farbe</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.length === 0 ? (
                      <tr>
                        <td colSpan={7} style={{ textAlign: 'center', opacity: 0.5 }}>
                          Keine Items. Fuegen Sie Items aus den Morphischen Feldern hinzu oder starten Sie einen Scan.
                        </td>
                      </tr>
                    ) : (
                      items.map((item, idx) => (
                        <tr key={item.id}>
                          <td>{idx + 1}</td>
                          <td>{item.text ?? '-'}</td>
                          <td>
                            {item.potency_kind && item.potency_value
                              ? `${item.potency_kind} ${item.potency_value}`
                              : '-'}
                          </td>
                          <td>{item.potency_intensity?.toFixed(1) ?? '-'}</td>
                          <td>{item.qrs_factor?.toFixed(2) ?? '-'}</td>
                          <td>
                            {item.color ? (
                              <span
                                style={{
                                  display: 'inline-block',
                                  width: 16,
                                  height: 16,
                                  borderRadius: 3,
                                  background: item.color,
                                  border: '1px solid var(--color-border)',
                                }}
                              />
                            ) : (
                              '-'
                            )}
                          </td>
                          <td>
                            <button
                              className="btn btn-danger btn-sm"
                              onClick={() => handleDeleteItem(item.id)}
                              type="button"
                            >
                              X
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div className="empty-state">
              {sheets.length === 0
                ? 'Erstellen Sie ein Healing Sheet ueber den "+ Neu" Button.'
                : 'Waehlen Sie ein Healing Sheet aus der Liste.'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
