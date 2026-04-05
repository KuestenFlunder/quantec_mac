import { useEffect, useState, useCallback } from 'react';
import type { MorphicCategoryInfo, MorphicTheme } from '../types';
import {
  fetchMorphicThemes,
  fetchMorphicCategories,
  getHardwareStatus,
  connectHardware,
  runFullScan,
  runItemScan,
  acceptScanResults,
} from '../api/client';

type ScanMode = 'full' | 'manual';

type ScanStep =
  | 'mode-select'
  | 'full-config'
  | 'manual-categories'
  | 'manual-params'
  | 'scanning'
  | 'results'
  | 'accepted';

interface FullScanStage1Item {
  category_id: number;
  category_name: string;
  theme_name: string | null;
  item_count: number;
  score: number;
}

interface ScanResultItem {
  item_id: number;
  category_id: number;
  category_name: string;
  text_primary: string | null;
  text_secondary: string | null;
  score: number;
}

/** Backend error response shape when scan/hardware calls fail. */
interface HardwareErrorResponse {
  error: string;
}

const DIODE_METHODS = [
  { value: 'selection', label: 'Selection (Standard)' },
  { value: 'quantec6', label: 'Quantec 6' },
  { value: 'quantec6random', label: 'Quantec 6 + Random' },
  { value: 'distribution', label: 'Distribution' },
  { value: 'remainder', label: 'Remainder' },
];

interface ScanViewProps {
  healingSheetId?: number;
}

export default function ScanView({ healingSheetId }: ScanViewProps) {
  // -- Hardware status --
  const [hwConnected, setHwConnected] = useState(false);
  const [hwSignalQuality, setHwSignalQuality] = useState(0);
  const [hwChecking, setHwChecking] = useState(true);

  // -- Shared state --
  const [step, setStep] = useState<ScanStep>('mode-select');
  const [mode, setMode] = useState<ScanMode>('full');
  const [error, setError] = useState<string | null>(null);
  const [scanPhaseLabel, setScanPhaseLabel] = useState('');

  // -- Theme & category data --
  const [themes, setThemes] = useState<MorphicTheme[]>([]);
  const [categories, setCategories] = useState<MorphicCategoryInfo[]>([]);
  const [loadingData, setLoadingData] = useState(true);

  // -- Full scan config --
  const [selectedThemeId, setSelectedThemeId] = useState<number | undefined>(undefined);
  const [categoryCycles, setCategoryCycles] = useState(88);
  const [itemCycles, setItemCycles] = useState(88);
  const [topCategories, setTopCategories] = useState(5);
  const [topItems, setTopItems] = useState(21);
  const [method, setMethod] = useState('selection');

  // -- Manual scan config --
  const [selectedCatIds, setSelectedCatIds] = useState<Set<number>>(new Set());
  const [manualCycles, setManualCycles] = useState(88);
  const [manualTopN, setManualTopN] = useState(21);
  const [manualMethod, setManualMethod] = useState('selection');

  // -- Results --
  const [stage1Results, setStage1Results] = useState<FullScanStage1Item[]>([]);
  const [itemResults, setItemResults] = useState<ScanResultItem[]>([]);
  const [selectedResultIds, setSelectedResultIds] = useState<Set<number>>(new Set());
  const [resultSignalQuality, setResultSignalQuality] = useState(0);
  const [acceptedCount, setAcceptedCount] = useState(0);

  // -- Init: load hardware status + category data --
  useEffect(() => {
    checkHardwareStatus();
    loadCategoryData();
  }, []);

  const checkHardwareStatus = useCallback(async () => {
    setHwChecking(true);
    try {
      const status = await getHardwareStatus();
      setHwConnected(status.connected);
      setHwSignalQuality(status.signal_quality);
    } catch {
      setHwConnected(false);
      setHwSignalQuality(0);
    } finally {
      setHwChecking(false);
    }
  }, []);

  async function handleConnectHardware() {
    setError(null);
    try {
      const result = await connectHardware();
      setHwConnected(result.connected);
      if (!result.connected) {
        setError('Diode konnte nicht verbunden werden: ' + result.message);
      }
      await checkHardwareStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verbindung fehlgeschlagen.');
    }
  }

  async function loadCategoryData() {
    setLoadingData(true);
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
      setLoadingData(false);
    }
  }

  // -- Category toggle (manual mode) --
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

  // -- Result selection --
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
    setSelectedResultIds(new Set(itemResults.map((r) => r.item_id)));
  }

  function deselectAllResults() {
    setSelectedResultIds(new Set());
  }

  // -- Full scan --
  async function handleFullScan() {
    setError(null);
    setStep('scanning');
    setScanPhaseLabel('Stufe 1: Kategorien werden gescannt...');
    setStage1Results([]);
    setItemResults([]);

    try {
      const result = await runFullScan({
        theme_id: selectedThemeId,
        category_cycles: categoryCycles,
        item_cycles: itemCycles,
        top_categories: topCategories,
        top_items: topItems,
        method,
      });

      if ('error' in result) {
        setError((result as unknown as HardwareErrorResponse).error);
        setStep('full-config');
        return;
      }

      setScanPhaseLabel('Stufe 2: Items werden gescannt...');

      // Small delay so the user sees the phase change
      await new Promise((resolve) => setTimeout(resolve, 300));

      setStage1Results(result.stage1_categories);
      setItemResults(result.stage2_items);
      setResultSignalQuality(result.signal_quality);
      setSelectedResultIds(new Set(result.stage2_items.map((r) => r.item_id)));
      setStep('results');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Scan fehlgeschlagen.');
      setStep('full-config');
    }
  }

  // -- Manual scan --
  async function handleManualScan() {
    setError(null);
    setStep('scanning');
    setScanPhaseLabel('Items werden gescannt...');
    setStage1Results([]);
    setItemResults([]);

    try {
      const result = await runItemScan({
        category_ids: Array.from(selectedCatIds),
        cycles: manualCycles,
        top_n: manualTopN,
        method: manualMethod,
      });

      if ('error' in result) {
        setError((result as unknown as HardwareErrorResponse).error);
        setStep('manual-params');
        return;
      }

      setItemResults(result.results);
      setResultSignalQuality(result.signal_quality);
      setSelectedResultIds(new Set(result.results.map((r) => r.item_id)));
      setStep('results');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Scan fehlgeschlagen.');
      setStep('manual-params');
    }
  }

  // -- Accept results into HealingSheet --
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

  // -- Reset --
  function resetScan() {
    setStep('mode-select');
    setStage1Results([]);
    setItemResults([]);
    setSelectedResultIds(new Set());
    setSelectedCatIds(new Set());
    setError(null);
  }

  // -- Grouped categories for manual mode --
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

  if (loadingData) {
    return <div className="loading-spinner" />;
  }

  return (
    <div>
      {/* Hardware Status Bar */}
      <div
        className="card"
        style={{
          marginBottom: 16,
          padding: '12px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div
            style={{
              width: 12,
              height: 12,
              borderRadius: '50%',
              background: hwChecking
                ? 'var(--color-border)'
                : hwConnected
                  ? 'var(--color-accent-green)'
                  : 'var(--color-accent-red)',
              boxShadow: hwConnected && !hwChecking
                ? '0 0 8px var(--color-accent-green)'
                : 'none',
              animation: hwConnected && !hwChecking ? 'pulse 2s ease-in-out infinite' : 'none',
            }}
          />
          <span style={{ fontWeight: 500 }}>
            {hwChecking
              ? 'Diode wird geprueft...'
              : hwConnected
                ? 'Diode verbunden'
                : 'Diode nicht verbunden'}
          </span>
          {hwConnected && !hwChecking && (
            <span
              style={{
                fontSize: 'var(--font-size-sm)',
                opacity: 0.6,
                marginLeft: 8,
              }}
            >
              Signalqualitaet: {hwSignalQuality.toFixed(1)}%
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {!hwConnected && !hwChecking && (
            <button
              className="btn btn-primary btn-sm"
              onClick={handleConnectHardware}
              type="button"
            >
              Verbinden
            </button>
          )}
          <button
            className="btn btn-secondary btn-sm"
            onClick={checkHardwareStatus}
            disabled={hwChecking}
            type="button"
          >
            Status pruefen
          </button>
        </div>
      </div>

      {error && (
        <div
          className="card"
          style={{ borderLeft: '3px solid var(--color-accent-red)', marginBottom: 16 }}
        >
          <p style={{ color: 'var(--color-accent-red)' }}>{error}</p>
        </div>
      )}

      {/* Step: Mode Selection */}
      {step === 'mode-select' && (
        <div className="card">
          <div className="card-header">
            <h3>Scan-Modus waehlen</h3>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <button
              type="button"
              onClick={() => {
                setMode('full');
                setStep('full-config');
              }}
              style={{
                padding: 24,
                border: '2px solid var(--color-border)',
                borderRadius: 'var(--radius-lg)',
                background: 'var(--color-white)',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all var(--transition-fast)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--color-primary)';
                e.currentTarget.style.background = 'rgba(46, 117, 181, 0.05)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--color-border)';
                e.currentTarget.style.background = 'var(--color-white)';
              }}
            >
              <div style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600, marginBottom: 8, color: 'var(--color-primary-dark)' }}>
                Voll-Scan (automatisch)
              </div>
              <div style={{ fontSize: 'var(--font-size-sm)', opacity: 0.7, lineHeight: 1.5 }}>
                2-stufiger Scan: Zuerst werden die relevantesten Kategorien ermittelt, dann die
                besten Items innerhalb dieser Kategorien gescannt. Empfohlen fuer die meisten
                Anwendungsfaelle.
              </div>
            </button>
            <button
              type="button"
              onClick={() => {
                setMode('manual');
                setStep('manual-categories');
              }}
              style={{
                padding: 24,
                border: '2px solid var(--color-border)',
                borderRadius: 'var(--radius-lg)',
                background: 'var(--color-white)',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all var(--transition-fast)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--color-primary)';
                e.currentTarget.style.background = 'rgba(46, 117, 181, 0.05)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--color-border)';
                e.currentTarget.style.background = 'var(--color-white)';
              }}
            >
              <div style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600, marginBottom: 8, color: 'var(--color-primary-dark)' }}>
                Manueller Scan
              </div>
              <div style={{ fontSize: 'var(--font-size-sm)', opacity: 0.7, lineHeight: 1.5 }}>
                Waehlen Sie selbst die Kategorien aus, in denen gescannt werden soll. Ideal wenn
                Sie bereits wissen, welche Bereiche relevant sind.
              </div>
            </button>
          </div>
        </div>
      )}

      {/* Step: Full Scan Config */}
      {step === 'full-config' && (
        <div className="card">
          <div className="card-header">
            <h3>Voll-Scan konfigurieren</h3>
          </div>
          <div className="form-row-3">
            <div className="form-group">
              <label className="form-label">Theme (optional)</label>
              <select
                className="form-input"
                value={selectedThemeId ?? ''}
                onChange={(e) =>
                  setSelectedThemeId(e.target.value ? Number(e.target.value) : undefined)
                }
              >
                <option value="">Alle Themes</option>
                {themes.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Methode</label>
              <select
                className="form-input"
                value={method}
                onChange={(e) => setMethod(e.target.value)}
              >
                {DIODE_METHODS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Top Kategorien</label>
              <input
                className="form-input"
                type="number"
                min={1}
                max={50}
                value={topCategories}
                onChange={(e) => setTopCategories(Number(e.target.value))}
              />
            </div>
          </div>
          <div className="form-row-3">
            <div className="form-group">
              <label className="form-label">Kategorie-Zyklen</label>
              <input
                className="form-input"
                type="number"
                min={1}
                max={1000}
                value={categoryCycles}
                onChange={(e) => setCategoryCycles(Number(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Item-Zyklen</label>
              <input
                className="form-input"
                type="number"
                min={1}
                max={1000}
                value={itemCycles}
                onChange={(e) => setItemCycles(Number(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Top Items</label>
              <input
                className="form-input"
                type="number"
                min={1}
                max={500}
                value={topItems}
                onChange={(e) => setTopItems(Number(e.target.value))}
              />
            </div>
          </div>
          <div
            style={{
              marginBottom: 16,
              padding: '12px 16px',
              background: 'var(--color-table-row-alt)',
              borderRadius: 'var(--radius-md)',
              fontSize: 'var(--font-size-sm)',
            }}
          >
            <strong>{selectedThemeId ? themes.find((t) => t.id === selectedThemeId)?.name : 'Alle Themes'}</strong>
            {' | '}
            <strong>{categoryCycles}</strong> Kat.-Zyklen |{' '}
            <strong>{itemCycles}</strong> Item-Zyklen |{' '}
            Top <strong>{topCategories}</strong> Kategorien{' '}
            &rarr; Top <strong>{topItems}</strong> Items |{' '}
            <strong>{DIODE_METHODS.find((m) => m.value === method)?.label}</strong>
          </div>
          <div className="form-actions">
            <button
              className="btn btn-secondary"
              onClick={() => setStep('mode-select')}
              type="button"
            >
              Zurueck
            </button>
            <button
              className="btn btn-success btn-lg"
              onClick={handleFullScan}
              disabled={!hwConnected}
              type="button"
            >
              Voll-Scan starten
            </button>
          </div>
        </div>
      )}

      {/* Step: Manual - Category Selection */}
      {step === 'manual-categories' && (
        <div className="card">
          <div className="card-header">
            <h3>Kategorien auswaehlen</h3>
            <span
              style={{
                fontSize: 'var(--font-size-sm)',
                color: 'var(--color-text)',
                opacity: 0.6,
              }}
            >
              {selectedCatIds.size} ausgewaehlt
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
                    />
                    <span style={{ flex: 1 }}>{cat.name}</span>
                    <span style={{ opacity: 0.4, fontSize: 'var(--font-size-sm)' }}>
                      {cat.item_count}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          ))}
          <div className="form-actions">
            <button
              className="btn btn-secondary"
              onClick={() => setStep('mode-select')}
              type="button"
            >
              Zurueck
            </button>
            <button
              className="btn btn-primary"
              onClick={() => setStep('manual-params')}
              disabled={selectedCatIds.size === 0}
              type="button"
            >
              Weiter
            </button>
          </div>
        </div>
      )}

      {/* Step: Manual - Scan Parameters */}
      {step === 'manual-params' && (
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
                value={manualCycles}
                onChange={(e) => setManualCycles(Number(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Methode</label>
              <select
                className="form-input"
                value={manualMethod}
                onChange={(e) => setManualMethod(e.target.value)}
              >
                {DIODE_METHODS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
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
                value={manualTopN}
                onChange={(e) => setManualTopN(Number(e.target.value))}
              />
            </div>
          </div>
          <div
            style={{
              marginBottom: 16,
              padding: '12px 16px',
              background: 'var(--color-table-row-alt)',
              borderRadius: 'var(--radius-md)',
              fontSize: 'var(--font-size-sm)',
            }}
          >
            <strong>{selectedCatIds.size}</strong> Kategorien ausgewaehlt |{' '}
            <strong>{manualCycles}</strong> Zyklen |{' '}
            <strong>{DIODE_METHODS.find((m) => m.value === manualMethod)?.label}</strong> |{' '}
            Top <strong>{manualTopN}</strong>
          </div>
          <div className="form-actions">
            <button
              className="btn btn-secondary"
              onClick={() => setStep('manual-categories')}
              type="button"
            >
              Zurueck
            </button>
            <button
              className="btn btn-success btn-lg"
              onClick={handleManualScan}
              disabled={!hwConnected}
              type="button"
            >
              Scan starten
            </button>
          </div>
        </div>
      )}

      {/* Step: Scanning */}
      {step === 'scanning' && (
        <div className="card" style={{ textAlign: 'center' }}>
          <div className="card-header" style={{ justifyContent: 'center' }}>
            <h3>Scan laeuft...</h3>
          </div>
          <div style={{ padding: '48px 0' }}>
            {/* Pulsating dot */}
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: '50%',
                background: 'var(--color-primary)',
                margin: '0 auto 24px',
                animation: 'pulse 1.5s ease-in-out infinite',
                boxShadow: '0 0 24px rgba(46, 117, 181, 0.4)',
              }}
            />
            <p
              style={{
                fontSize: 'var(--font-size-lg)',
                fontWeight: 600,
                marginBottom: 12,
              }}
            >
              {scanPhaseLabel}
            </p>
            <p
              style={{
                fontSize: 'var(--font-size-sm)',
                opacity: 0.5,
              }}
            >
              Die Hardware-Diode wird abgefragt. Dies kann 10-30 Sekunden dauern.
            </p>
          </div>
        </div>
      )}

      {/* Step: Results */}
      {step === 'results' && (
        <div>
          {/* Stage 1: Category results (only for full scan) */}
          {mode === 'full' && stage1Results.length > 0 && (
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-header">
                <h3>Stufe 1: Ausgewaehlte Kategorien ({stage1Results.length})</h3>
                <span style={{ fontSize: 'var(--font-size-sm)', opacity: 0.6 }}>
                  Signalqualitaet: {resultSignalQuality.toFixed(1)}%
                </span>
              </div>
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Kategorie</th>
                      <th>Theme</th>
                      <th>Items</th>
                      <th>Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stage1Results.map((cat, idx) => (
                      <tr
                        key={cat.category_id}
                        style={
                          idx < 3
                            ? {
                                background:
                                  idx === 0
                                    ? 'rgba(1, 184, 148, 0.12)'
                                    : idx === 1
                                      ? 'rgba(1, 184, 148, 0.08)'
                                      : 'rgba(1, 184, 148, 0.04)',
                              }
                            : undefined
                        }
                      >
                        <td style={{ fontWeight: idx < 3 ? 700 : 400 }}>{idx + 1}</td>
                        <td style={{ fontWeight: 500 }}>{cat.category_name}</td>
                        <td>{cat.theme_name ?? '-'}</td>
                        <td>{cat.item_count}</td>
                        <td style={{ fontWeight: idx < 3 ? 600 : 400 }}>{cat.score}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Stage 2: Item results */}
          <div className="card">
            <div className="card-header">
              <h3>
                {mode === 'full' ? 'Stufe 2: ' : ''}Scan-Ergebnisse ({itemResults.length})
              </h3>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                {mode !== 'full' && (
                  <span style={{ fontSize: 'var(--font-size-sm)', opacity: 0.6, marginRight: 8 }}>
                    Signalqualitaet: {resultSignalQuality.toFixed(1)}%
                  </span>
                )}
                <button
                  className="btn btn-sm btn-secondary"
                  onClick={selectAllResults}
                  type="button"
                >
                  Alle
                </button>
                <button
                  className="btn btn-sm btn-secondary"
                  onClick={deselectAllResults}
                  type="button"
                >
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
                  </tr>
                </thead>
                <tbody>
                  {itemResults.map((r, idx) => (
                    <tr
                      key={r.item_id}
                      onClick={() => toggleResultItem(r.item_id)}
                      style={
                        idx < 3
                          ? {
                              background:
                                idx === 0
                                  ? 'rgba(1, 184, 148, 0.12)'
                                  : idx === 1
                                    ? 'rgba(1, 184, 148, 0.08)'
                                    : 'rgba(1, 184, 148, 0.04)',
                            }
                          : undefined
                      }
                    >
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedResultIds.has(r.item_id)}
                          onChange={() => toggleResultItem(r.item_id)}
                          style={{ accentColor: 'var(--color-primary)' }}
                        />
                      </td>
                      <td style={{ fontWeight: idx < 3 ? 700 : 400 }}>{idx + 1}</td>
                      <td style={{ fontWeight: 500 }}>
                        {r.text_primary ?? '-'}
                        {r.text_secondary && (
                          <span
                            style={{
                              display: 'block',
                              fontSize: 'var(--font-size-sm)',
                              opacity: 0.5,
                              marginTop: 2,
                            }}
                          >
                            {r.text_secondary}
                          </span>
                        )}
                      </td>
                      <td>{r.category_name}</td>
                      <td style={{ fontWeight: idx < 3 ? 600 : 400 }}>{r.score}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="form-actions">
              <button className="btn btn-secondary" onClick={resetScan} type="button">
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
                <p
                  style={{
                    fontSize: 'var(--font-size-sm)',
                    opacity: 0.6,
                    alignSelf: 'center',
                  }}
                >
                  Kein HealingSheet ausgewaehlt. Starten Sie den Scan ueber den
                  HealingSheet-Editor.
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Step: Accepted */}
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
