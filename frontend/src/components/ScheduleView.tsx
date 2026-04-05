import { useEffect, useState } from 'react';
import type { HealingSheet, Schedule, ScheduleCreate, SendJob } from '../types';
import {
  fetchAllSheets,
  updateSchedule,
  deleteSchedule,
  fetchScheduleJobs,
} from '../api/client';

type NewScheduleForm = ScheduleCreate & { healing_sheet_id?: number };

const API_BASE = 'http://localhost:8000/api';

const SCHEDULE_TYPES = [
  { value: 'direct', label: 'Direkt' },
  { value: 'interval', label: 'Intervall' },
  { value: 'random', label: 'Zufaellig' },
  { value: 'single', label: 'Einmalig' },
];

function getStatusBadgeClass(status: string): string {
  switch (status) {
    case 'active': return 'badge-active';
    case 'pending': return 'badge-pending';
    case 'running': return 'badge-running';
    case 'completed': return 'badge-active';
    case 'failed': return 'badge-inactive';
    default: return 'badge-pending';
  }
}

function formatDateTime(iso: string | null): string {
  if (!iso) return '-';
  const d = new Date(iso);
  return d.toLocaleString('de-DE', { dateStyle: 'medium', timeStyle: 'short' });
}

export default function ScheduleView() {
  const [sheets, setSheets] = useState<HealingSheet[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [selectedSchedule, setSelectedSchedule] = useState<Schedule | null>(null);
  const [jobs, setJobs] = useState<SendJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNewDialog, setShowNewDialog] = useState(false);
  const [newForm, setNewForm] = useState<NewScheduleForm>({
    schedule_type: 'direct',
    start_date: null,
    end_date: null,
    interval_duration: 3600,
    send_duration: 120,
    active: true,
    butler_active: false,
  });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const sheetData = await fetchAllSheets();
      setSheets(sheetData);

      // Schedules aus den Sheets laden: jedes Sheet hat Schedules referenziert
      // Da kein dedizierter list-all-schedules Endpoint existiert,
      // holen wir die Schedules ueber Sheets
      const allSchedules: Schedule[] = [];
      for (const sheet of sheetData) {
        try {
          const response = await fetch(`${API_BASE}/sheets/${sheet.id}/schedules`);
          if (response.ok) {
            const data = await response.json() as Schedule[];
            allSchedules.push(...data);
          }
        } catch {
          // Einzelne Fehler ignorieren
        }
      }
      setSchedules(allSchedules);
    } catch {
      setError('Daten konnten nicht geladen werden.');
    } finally {
      setLoading(false);
    }
  }

  async function selectSchedule(schedule: Schedule) {
    setSelectedSchedule(schedule);
    try {
      const jobData = await fetchScheduleJobs(schedule.id);
      setJobs(jobData);
    } catch {
      setJobs([]);
    }
  }

  async function handleToggleActive(schedule: Schedule) {
    try {
      await updateSchedule(schedule.id, { active: !schedule.active });
      await loadData();
    } catch {
      setError('Status konnte nicht geaendert werden.');
    }
  }

  async function handleDeleteSchedule(scheduleId: number) {
    try {
      await deleteSchedule(scheduleId);
      setSelectedSchedule(null);
      setJobs([]);
      await loadData();
    } catch {
      setError('Sendeplan konnte nicht geloescht werden.');
    }
  }

  async function handleCreateSchedule() {
    if (!newForm.healing_sheet_id) return;
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/sheets/${newForm.healing_sheet_id}/schedules`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          schedule_type: newForm.schedule_type,
          start_date: newForm.start_date,
          end_date: newForm.end_date,
          interval_duration: newForm.interval_duration,
          send_duration: newForm.send_duration,
          active: newForm.active,
          butler_active: newForm.butler_active,
        }),
      });
      if (!response.ok) throw new Error('Erstellung fehlgeschlagen');
      setShowNewDialog(false);
      setNewForm({
        schedule_type: 'direct',
        start_date: null,
        end_date: null,
        interval_duration: 3600,
        send_duration: 120,
        active: true,
        butler_active: false,
      });
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erstellung fehlgeschlagen.');
    }
  }

  function getSheetName(sheetId: number): string {
    return sheets.find((s) => s.id === sheetId)?.name ?? `Sheet #${sheetId}`;
  }

  if (loading) {
    return <div className="loading-spinner" />;
  }

  return (
    <div>
      {error && (
        <div className="card" style={{ borderLeft: '3px solid var(--color-accent-red)', marginBottom: 16 }}>
          <p style={{ color: 'var(--color-accent-red)' }}>{error}</p>
        </div>
      )}

      {/* Toolbar */}
      <div className="toolbar">
        <span style={{ flex: 1, fontSize: 'var(--font-size-sm)', opacity: 0.6 }}>
          {schedules.length} Sendeplaene
        </span>
        <button className="btn btn-primary" onClick={() => setShowNewDialog(true)} type="button">
          + Neuer Sendeplan
        </button>
      </div>

      {/* Schedule-Liste */}
      {schedules.length === 0 ? (
        <div className="empty-state">
          Noch keine Sendeplaene vorhanden. Erstellen Sie einen neuen Plan.
        </div>
      ) : (
        <div className="table-container" style={{ marginBottom: 16 }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>HealingSheet</th>
                <th>Typ</th>
                <th>Start</th>
                <th>Ende</th>
                <th>Intervall</th>
                <th>Sendedauer</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {schedules.map((s) => (
                <tr key={s.id} onClick={() => selectSchedule(s)}>
                  <td style={{ fontWeight: 500 }}>{getSheetName(s.healing_sheet_id)}</td>
                  <td>{SCHEDULE_TYPES.find((t) => t.value === s.schedule_type)?.label ?? s.schedule_type ?? '-'}</td>
                  <td>{formatDateTime(s.start_date)}</td>
                  <td>{formatDateTime(s.end_date)}</td>
                  <td>{s.interval_duration ? `${Math.round(s.interval_duration / 60)} Min.` : '-'}</td>
                  <td>{s.send_duration ? `${s.send_duration} Sek.` : '-'}</td>
                  <td>
                    <span className={`badge ${getStatusBadgeClass(s.active ? 'active' : 'pending')}`}>
                      {s.active ? 'Aktiv' : 'Inaktiv'}
                    </span>
                  </td>
                  <td style={{ display: 'flex', gap: 4 }}>
                    <button
                      className={`btn btn-sm ${s.active ? 'btn-secondary' : 'btn-success'}`}
                      onClick={(e) => { e.stopPropagation(); handleToggleActive(s); }}
                      type="button"
                    >
                      {s.active ? 'Pause' : 'Start'}
                    </button>
                    <button
                      className="btn btn-sm btn-danger"
                      onClick={(e) => { e.stopPropagation(); handleDeleteSchedule(s.id); }}
                      type="button"
                    >
                      X
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Sendejobs des ausgewaehlten Plans */}
      {selectedSchedule && (
        <div className="card">
          <div className="card-header">
            <h3>
              Sendejobs: {getSheetName(selectedSchedule.healing_sheet_id)}
            </h3>
            <span style={{ fontSize: 'var(--font-size-sm)', opacity: 0.6 }}>
              Plan #{selectedSchedule.id}
            </span>
          </div>
          {jobs.length === 0 ? (
            <div className="empty-state">Keine Sendejobs vorhanden.</div>
          ) : (
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Geplant</th>
                    <th>Start</th>
                    <th>Ende</th>
                    <th>Dauer</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((j) => (
                    <tr key={j.id}>
                      <td>{formatDateTime(j.scheduled_start)}</td>
                      <td>{formatDateTime(j.actual_start)}</td>
                      <td>{formatDateTime(j.actual_end)}</td>
                      <td>{j.duration ? `${j.duration} Sek.` : '-'}</td>
                      <td>
                        <span className={`badge ${getStatusBadgeClass(j.status)}`}>
                          {j.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Neuer Sendeplan Dialog */}
      {showNewDialog && (
        <div className="modal-overlay" onClick={() => setShowNewDialog(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Neuer Sendeplan</h3>
              <button className="modal-close" onClick={() => setShowNewDialog(false)} type="button">
                &times;
              </button>
            </div>

            <div className="form-group">
              <label className="form-label">HealingSheet *</label>
              <select
                className="form-input"
                value={newForm.healing_sheet_id ?? ''}
                onChange={(e) => setNewForm((p: NewScheduleForm) => ({ ...p, healing_sheet_id: Number(e.target.value) || undefined }))}
              >
                <option value="">-- Sheet auswaehlen --</option>
                {sheets.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Typ</label>
              <select
                className="form-input"
                value={newForm.schedule_type ?? 'direct'}
                onChange={(e) => setNewForm((p: NewScheduleForm) => ({ ...p, schedule_type: e.target.value }))}
              >
                {SCHEDULE_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Startdatum</label>
                <input
                  className="form-input"
                  type="datetime-local"
                  value={newForm.start_date ?? ''}
                  onChange={(e) => setNewForm((p: NewScheduleForm) => ({ ...p, start_date: e.target.value || null }))}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Enddatum</label>
                <input
                  className="form-input"
                  type="datetime-local"
                  value={newForm.end_date ?? ''}
                  onChange={(e) => setNewForm((p: NewScheduleForm) => ({ ...p, end_date: e.target.value || null }))}
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Intervall (Minuten)</label>
                <input
                  className="form-input"
                  type="number"
                  min={1}
                  value={Math.round((newForm.interval_duration ?? 3600) / 60)}
                  onChange={(e) => setNewForm((p: NewScheduleForm) => ({ ...p, interval_duration: Number(e.target.value) * 60 }))}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Sendedauer (Sekunden)</label>
                <input
                  className="form-input"
                  type="number"
                  min={10}
                  value={newForm.send_duration ?? 120}
                  onChange={(e) => setNewForm((p: NewScheduleForm) => ({ ...p, send_duration: Number(e.target.value) }))}
                />
              </div>
            </div>

            <div className="form-actions">
              <button className="btn btn-secondary" onClick={() => setShowNewDialog(false)} type="button">
                Abbrechen
              </button>
              <button
                className="btn btn-primary"
                onClick={handleCreateSchedule}
                disabled={!newForm.healing_sheet_id}
                type="button"
              >
                Sendeplan erstellen
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
