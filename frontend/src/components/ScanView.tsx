import { useEffect, useState, useRef, useCallback } from 'react';
import type { MorphicCategoryInfo, MorphicTheme, ScanResultItem, BackgroundTask } from '../types';
import {
  fetchMorphicThemes,
  fetchMorphicCategories,
  startScan,
  getTaskStatus,
  getScanResults,
  acceptScanResults,
  cancelTask,
} from '../api/client';

type ScanStep = 'categories' | 'params' | 'scanning' | 'results' | 'accepted';

const DIODE_TYPES = [
  { value: 'selection', label: 'Selection (Standard)' },
  { value: 'quantec6', label: 'Quantec 6' },
  { value: 'quantec6_with_random', label: 'Quantec 6 + Random' },
  { value: 'distribution', label: 'Distribution' },
  { value: 'remainder', label: 'Remainder' },
];

const STEP_LABELS = ['Kategorien', 'Parameter', 'Scan', 'Ergebnisse', 'Fertig'];

interface ScanViewProps {
  healingSheetId?: number;
}

export default function ScanView({ healingSheetId }: ScanViewProps) {
  const [step, setStep] = useState<ScanStep>('categories');
  const [themes, setThemes] = useState<MorphicTheme[]>([]);
  const [categories, setCategories] = useState<MorphicCategoryInfo[]>([]);
  const [selectedCatIds, setSelectedCatIds] = useState<Set<number>>(new Set());
  const [cycles, setCycles] = useState(88);
  const [diodeType, setDiodeType] = useState('selection');
  const [topN, setTopN] = useState(21);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [taskStatus, setTaskStatus] = useState<string>('');
  const [results, setResults] = useState<ScanResultItem[]>([]);
  const [selectedResultIds, setSelectedResultIds] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [acceptedCount, setAcceptedCount] = useState(0);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    loadCategories();
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  async function loadCategories() {
    setLoading(true);
    try {
      const [themeData, catData] = await Promise.all([
        fetchMorphicThemes(),
        fetchMorphicCategories(),
      ]);
      setThemes(themeData);
      setCategories(catData);
    } catch {
      setError('Kategorien konnten nicht geladen werden.');
    } finally {
      setLoading(false);
    }
  }

  function toggleCategory(catId: number) {
    setSelectedCatIds((prev) => {
      const next = new Set(prev);
      if (next.has(catId)) {
        next.delete(catId);
      } else {
        next.add(catId);
      }
      return next;
    });
  }

  function toggleResultItem(itemId: number) {
    setSelectedResultIds((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else {
        next.add(itemId);
      }
      return next;
    });
  }

  function selectAllResults() {
    setSelectedResultIds(new Set(results.map((r) => r.item_id)));
  }

  function deselectAllResults() {
    setSelectedResultIds(new Set());
  }

  const pollTask = useCallback(async (tid: string) => {
    try {
      const task: BackgroundTask = await getTaskStatus(tid);
      setProgress(task.progress ?? 0);
      setTaskStatus(task.status);

      if (task.status === 'completed') {
        if (pollingRef.current) clearInterval(pollingRef.current);
        const scanResults = await getScanResults(tid);
        setResults(scanResults.results);
        setSelectedResultIds(new Set(scanResults.results.map((r) => r.item_id)));
        setStep('results');
      } else if (task.status === 'failed') {
        if (pollingRef.current) clearInterval(pollingRef.current);
        setError(task.error ?? 'Scan fehlgeschlagen.');
        setStep('params');
      } else if (task.status === 'cancelled') {
        if (pollingRef.current) clearInterval(pollingRef.current);
        setStep('params');
      }
    } catch {
      // Polling-Fehler ignorieren, naechster Versuch kommt
    }
  }, []);

  async function handleStartScan() {
    setError(null);
    setStep('scanning');
    setProgress(0);
    setTaskStatus('starting');

    try {
      const task = await startScan({
        category_ids: Array.from(selectedCatIds),
        cycles,
        diode_type: diodeType,
        top_n: topN,
      });
      setTaskId(task.task_id);
      pollingRef.current = setInterval(() => pollTask(task.task_id), 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Scan konnte nicht gestartet werden.');
      setStep('params');
    }
  }

  async function handleCancelScan() {
    if (taskId) {
      try {
        await cancelTask(taskId);
      } catch {
        // Abbruch-Fehler ignorieren
      }
    }
    if (pollingRef.current) clearInterval(pollingRef.current);
    setStep('params');
  }

  async function handleAcceptResults() {
    if (!healingSheetId || selectedResultIds.size === 0) return;
    setError(null);
    try {
      const result = await acceptScanResults({
        healing_sheet_id: healingSheetId,
        item_ids: Array.from(selectedResultIds),
      });
      setAcceptedCount(result.added);
      setStep('accepted');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Uebernahme fehlgeschlagen.');
    }
  }

  function resetScan() {
    setStep('categories');
    setSelectedCatIds(new Set());
    setResults([]);
    setSelectedResultIds(new Set());
    setProgress(0);
    setTaskId(null);
    setError(null);
  }

  const stepIndex = ['categories', 'params', 'scanning', 'results', 'accepted'].indexOf(step);

  // Gruppiere Kategorien nach Theme
  const grouped = new Map<string, MorphicCategoryInfo[]>();
  for (const cat of categories) {
    const themeName = themes.find((t) => t.id === cat.theme_id)?.name ?? 'Sonstige';
    const existing = grouped.get(themeName);
    if (existing) {
      existing.push(cat);
    } else {
      grouped.set(themeName, [cat]);
    }
  }

  if (loading) {
    return <div className="loading-spinner" />;
  }

  return (
    <div>
      {/* Stepper */}
      <div className="stepper">
        {STEP_LABELS.map((label, idx) => (
          <div key={label} className="stepper-step">
            {idx > 0 && (
              <div className={`stepper-line${idx <= stepIndex ? ' completed' : ''}`} />
            )}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
              <div
                className={`stepper-dot${
                  idx === stepIndex ? ' active' : idx < stepIndex ? ' completed' : ''
                }`}
              >
                {idx < stepIndex ? '\u2713' : idx + 1}
              </div>
              <span
                className={`stepper-label${
                  idx === stepIndex ? ' active' : idx < stepIndex ? ' completed' : ''
                }`}
              >
                {label}
              </span>
            </div>
          </div>
        ))}
      </div>

      {error && (
        <div className="card" style={{ borderLeft: '3px solid var(--color-accent-red)', marginBottom: 16 }}>
          <p style={{ color: 'var(--color-accent-red)' }}>{error}</p>
        </div>
      )}

      {/* Schritt 1: Kategorie-Auswahl */}
      {step === 'categories' && (
        <div className="card">
          <div className="card-header">
            <h3>Kategorien auswaehlen</h3>
            <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text)', opacity: 0.6 }}>
              {selectedCatIds.size} ausgewaehlt (max. 21)
            </span>
          </div>
          {Array.from(grouped.entries()).map(([themeName, cats]) => (
            <div key={themeName} style={{ marginBottom: 16 }}>
              <div className="theme-group-header">{themeName}</div>
              <div className="checkbox-grid">
                {cats.map((cat) => (
                  <label
                    key={cat.id}
                    className={`checkbox-item${selectedCatIds.has(cat.id) ? ' selected' : ''}`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedCatIds.has(cat.id)}
                      onChange={() => toggleCategory(cat.id)}
                      disabled={!selectedCatIds.has(cat.id) && selectedCatIds.size >= 21}
                    />
                    <span style={{ flex: 1 }}>{cat.name}</span>
                    <span style={{ opacity: 0.4, fontSize: 'var(--font-size-sm)' }}>{cat.item_count}</span>
                  </label>
                ))}
              </div>
            </div>
          ))}
          <div className="form-actions">
            <button
              className="btn btn-primary"
              onClick={() => setStep('params')}
              disabled={selectedCatIds.size === 0}
              type="button"
            >
              Weiter
            </button>
          </div>
        </div>
      )}

      {/* Schritt 2: Scan-Parameter */}
      {step === 'params' && (
        <div className="card">
          <div className="card-header">
            <h3>Scan-Parameter</h3>
          </div>
          <div className="form-row-3">
            <div className="form-group">
              <label className="form-label">Zyklen</label>
              <input
                className="form-input"
                type="number"
                min={1}
                max={1000}
                value={cycles}
                onChange={(e) => setCycles(Number(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Diode-Typ</label>
              <select
                className="form-input"
                value={diodeType}
                onChange={(e) => setDiodeType(e.target.value)}
              >
                {DIODE_TYPES.map((dt) => (
                  <option key={dt.value} value={dt.value}>{dt.label}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Top-N Ergebnisse</label>
              <input
                className="form-input"
                type="number"
                min={1}
                max={500}
                value={topN}
                onChange={(e) => setTopN(Number(e.target.value))}
              />
            </div>
          </div>
          <div style={{ marginBottom: 16, padding: '12px 16px', background: 'var(--color-table-row-alt)', borderRadius: 'var(--radius-md)', fontSize: 'var(--font-size-sm)' }}>
            <strong>{selectedCatIds.size}</strong> Kategorien ausgewaehlt |{' '}
            <strong>{cycles}</strong> Zyklen |{' '}
            <strong>{DIODE_TYPES.find((d) => d.value === diodeType)?.label}</strong> |{' '}
            Top <strong>{topN}</strong>
          </div>
          <div className="form-actions">
            <button className="btn btn-secondary" onClick={() => setStep('categories')} type="button">
              Zurueck
            </button>
            <button className="btn btn-success btn-lg" onClick={handleStartScan} type="button">
              Scan starten
            </button>
          </div>
        </div>
      )}

      {/* Schritt 3: Scan laeuft */}
      {step === 'scanning' && (
        <div className="card" style={{ textAlign: 'center' }}>
          <div className="card-header" style={{ justifyContent: 'center' }}>
            <h3>Scan laeuft...</h3>
          </div>
          <div style={{ padding: '32px 0' }}>
            <div className="progress-bar progress-bar-lg" style={{ marginBottom: 16 }}>
              <div
                className="progress-bar-fill"
                style={{ width: `${Math.round(progress * 100)}%` }}
              />
            </div>
            <p style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600 }}>
              {Math.round(progress * 100)}%
            </p>
            <p style={{ fontSize: 'var(--font-size-sm)', opacity: 0.6, marginTop: 8 }}>
              Status: {taskStatus} | {selectedCatIds.size} Kategorien | {cycles} Zyklen
            </p>
          </div>
          <button className="btn btn-danger" onClick={handleCancelScan} type="button">
            Scan abbrechen
          </button>
        </div>
      )}

      {/* Schritt 4: Ergebnisse */}
      {step === 'results' && (
        <div className="card">
          <div className="card-header">
            <h3>Scan-Ergebnisse ({results.length})</h3>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-sm btn-secondary" onClick={selectAllResults} type="button">
                Alle
              </button>
              <button className="btn btn-sm btn-secondary" onClick={deselectAllResults} type="button">
                Keine
              </button>
            </div>
          </div>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: 40 }}></th>
                  <th>#</th>
                  <th>Text</th>
                  <th>Kategorie</th>
                  <th>Score</th>
                  <th>Qualitaet</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.item_id} onClick={() => toggleResultItem(r.item_id)}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedResultIds.has(r.item_id)}
                        onChange={() => toggleResultItem(r.item_id)}
                        style={{ accentColor: 'var(--color-primary)' }}
                      />
                    </td>
                    <td>{r.rank}</td>
                    <td style={{ fontWeight: 500 }}>{r.text_primary ?? '-'}</td>
                    <td>{r.category_name}</td>
                    <td>{r.score.toFixed(1)}</td>
                    <td>{r.quality_score?.toFixed(1) ?? '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="form-actions">
            <button className="btn btn-secondary" onClick={() => setStep('params')} type="button">
              Neuer Scan
            </button>
            {healingSheetId ? (
              <button
                className="btn btn-success"
                onClick={handleAcceptResults}
                disabled={selectedResultIds.size === 0}
                type="button"
              >
                {selectedResultIds.size} Items ins HealingSheet uebernehmen
              </button>
            ) : (
              <p style={{ fontSize: 'var(--font-size-sm)', opacity: 0.6, alignSelf: 'center' }}>
                Kein HealingSheet ausgewaehlt. Starten Sie den Scan ueber den HealingSheet-Editor.
              </p>
            )}
          </div>
        </div>
      )}

      {/* Schritt 5: Uebernommen */}
      {step === 'accepted' && (
        <div className="card" style={{ textAlign: 'center' }}>
          <div style={{ padding: '32px 0' }}>
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="var(--color-accent-green)"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{ width: 64, height: 64, marginBottom: 16 }}
            >
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
            <h3 style={{ color: 'var(--color-accent-green)', marginBottom: 8 }}>
              {acceptedCount} Items uebernommen
            </h3>
            <p style={{ opacity: 0.6 }}>
              Die ausgewaehlten Scan-Ergebnisse wurden erfolgreich ins HealingSheet eingefuegt.
            </p>
          </div>
          <button className="btn btn-primary" onClick={resetScan} type="button">
            Neuen Scan starten
          </button>
        </div>
      )}
    </div>
  );
}
