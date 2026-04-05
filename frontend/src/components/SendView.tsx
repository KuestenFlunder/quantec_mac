import { useEffect, useState, useRef, useCallback } from 'react';
import type { HealingSheet, HealingSheetItem, BackgroundTask } from '../types';
import {
  fetchAllSheets,
  fetchSheetItems,
  startDirectSend,
  getTaskStatus,
} from '../api/client';

type SendState = 'idle' | 'sending' | 'completed' | 'error';

export default function SendView() {
  const [sheets, setSheets] = useState<HealingSheet[]>([]);
  const [selectedSheetId, setSelectedSheetId] = useState<number | null>(null);
  const [items, setItems] = useState<HealingSheetItem[]>([]);
  const [duration, setDuration] = useState(120);
  const [sendState, setSendState] = useState<SendState>('idle');
  const [taskId, setTaskId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [countdown, setCountdown] = useState(0);
  const [currentItemIdx, setCurrentItemIdx] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const itemCycleRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    loadSheets();
    return () => {
      clearAllTimers();
    };
  }, []);

  function clearAllTimers() {
    if (pollingRef.current) clearInterval(pollingRef.current);
    if (countdownRef.current) clearInterval(countdownRef.current);
    if (itemCycleRef.current) clearInterval(itemCycleRef.current);
  }

  async function loadSheets() {
    setLoading(true);
    try {
      const data = await fetchAllSheets();
      setSheets(data.filter((s) => s.active));
    } catch {
      setError('HealingSheets konnten nicht geladen werden.');
    } finally {
      setLoading(false);
    }
  }

  async function handleSheetSelect(sheetId: number) {
    setSelectedSheetId(sheetId);
    try {
      const itemData = await fetchSheetItems(sheetId);
      setItems(itemData);
    } catch {
      setItems([]);
    }
  }

  const pollTask = useCallback(async (tid: string) => {
    try {
      const task: BackgroundTask = await getTaskStatus(tid);
      setProgress(task.progress ?? 0);

      if (task.status === 'completed') {
        clearAllTimers();
        setSendState('completed');
        setCountdown(0);
      } else if (task.status === 'failed') {
        clearAllTimers();
        setSendState('error');
        setError(task.error ?? 'Senden fehlgeschlagen.');
      }
    } catch {
      // Polling-Fehler ignorieren
    }
  }, []);

  async function handleStartSend() {
    if (selectedSheetId === null) return;
    setError(null);
    setSendState('sending');
    setCountdown(duration);
    setCurrentItemIdx(0);

    // Countdown starten
    countdownRef.current = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) return 0;
        return prev - 1;
      });
    }, 1000);

    // Item-Wechsel fuer Overlay-Text
    if (items.length > 0) {
      itemCycleRef.current = setInterval(() => {
        setCurrentItemIdx((prev) => (prev + 1) % items.length);
      }, 6000);
    }

    try {
      const task = await startDirectSend(selectedSheetId, { duration });
      setTaskId(task.task_id);
      pollingRef.current = setInterval(() => pollTask(task.task_id), 2000);
    } catch (err) {
      clearAllTimers();
      setSendState('error');
      setError(err instanceof Error ? err.message : 'Senden konnte nicht gestartet werden.');
    }
  }

  function handleStopSend() {
    if (taskId) {
      // Fire-and-forget cancel
      fetch(`http://localhost:8000/api/scan/tasks/${taskId}/cancel`, { method: 'POST' }).catch(() => {});
    }
    clearAllTimers();
    setSendState('idle');
    setCountdown(0);
    setProgress(0);
  }

  function handleReset() {
    setSendState('idle');
    setCountdown(0);
    setProgress(0);
    setError(null);
    setTaskId(null);
  }

  function formatTime(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }

  const currentItem = items[currentItemIdx];
  const selectedSheet = sheets.find((s) => s.id === selectedSheetId);

  if (loading) {
    return <div className="loading-spinner" />;
  }

  return (
    <div className="send-container">
      {/* Sheet-Auswahl */}
      <div style={{ width: '100%', maxWidth: 600 }}>
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">HealingSheet</label>
            <select
              className="form-input"
              value={selectedSheetId ?? ''}
              onChange={(e) => {
                const val = e.target.value;
                if (val) handleSheetSelect(Number(val));
              }}
              disabled={sendState === 'sending'}
            >
              <option value="">-- Sheet auswaehlen --</option>
              {sheets.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.send_type ?? 'Standard'})
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Sendedauer (Sekunden)</label>
            <input
              className="form-input"
              type="number"
              min={10}
              max={3600}
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              disabled={sendState === 'sending'}
            />
          </div>
        </div>
      </div>

      {/* Animations-Bereich */}
      <div className="send-animation">
        <div className="send-animation-bg" />

        {/* Scrollende Items */}
        <div className="send-items-scroller">
          <div
            className="send-items-track"
            style={{
              animationPlayState: sendState === 'sending' ? 'running' : 'paused',
            }}
          >
            {items.length > 0
              ? [...items, ...items].map((item, idx) => (
                  <div key={idx} className="send-item-text">
                    {item.text ?? `Item ${item.sort_index}`}
                  </div>
                ))
              : (
                <div style={{ padding: 24, textAlign: 'center', color: 'var(--color-primary-light)', opacity: 0.4 }}>
                  {selectedSheetId ? 'Keine Items im Sheet.' : 'Waehlen Sie ein HealingSheet aus.'}
                </div>
              )
            }
          </div>
        </div>

        {/* Overlay-Text mit Fade */}
        {sendState === 'sending' && currentItem && (
          <div
            key={currentItemIdx}
            className="send-overlay-text"
          >
            {currentItem.text ?? `Item ${currentItem.sort_index}`}
          </div>
        )}

        {/* Idle/Completed Overlay */}
        {sendState === 'idle' && (
          <div style={{
            position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexDirection: 'column', gap: 8,
          }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="var(--color-primary-light)" strokeWidth="1.5" style={{ width: 48, height: 48, opacity: 0.5 }}>
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
            <span style={{ color: 'var(--color-primary-light)', opacity: 0.6 }}>Bereit zum Senden</span>
          </div>
        )}

        {sendState === 'completed' && (
          <div style={{
            position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexDirection: 'column', gap: 8,
          }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="var(--color-accent-green)" strokeWidth="2" style={{ width: 64, height: 64 }}>
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
            <span style={{ color: 'var(--color-accent-green)', fontSize: 'var(--font-size-lg)', fontWeight: 600 }}>
              Bewellung abgeschlossen
            </span>
          </div>
        )}
      </div>

      {/* Countdown */}
      {sendState === 'sending' && (
        <div style={{ textAlign: 'center' }}>
          <div className="send-countdown">{formatTime(countdown)}</div>
          <div className="send-countdown-label">Verbleibend</div>
          <div className="progress-bar" style={{ width: 300, margin: '12px auto 0' }}>
            <div
              className="progress-bar-fill"
              style={{ width: `${Math.round(progress * 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <p style={{ color: 'var(--color-accent-red)', textAlign: 'center' }}>{error}</p>
      )}

      {/* Controls */}
      <div className="send-controls" style={{ justifyContent: 'center' }}>
        <div
          className={`send-status-dot${sendState === 'sending' ? ' active' : ''}`}
        />
        <span style={{ fontSize: 'var(--font-size-sm)', opacity: 0.6, minWidth: 100 }}>
          {sendState === 'idle' && 'Bereit'}
          {sendState === 'sending' && 'Sendet...'}
          {sendState === 'completed' && 'Abgeschlossen'}
          {sendState === 'error' && 'Fehler'}
        </span>

        {sendState === 'idle' && (
          <button
            className="btn btn-success btn-lg"
            onClick={handleStartSend}
            disabled={selectedSheetId === null || items.length === 0}
            type="button"
          >
            Senden starten
          </button>
        )}

        {sendState === 'sending' && (
          <button className="btn btn-danger btn-lg" onClick={handleStopSend} type="button">
            Stoppen
          </button>
        )}

        {(sendState === 'completed' || sendState === 'error') && (
          <button className="btn btn-primary btn-lg" onClick={handleReset} type="button">
            Zuruecksetzen
          </button>
        )}
      </div>

      {/* Sheet-Info */}
      {selectedSheet && (
        <div style={{
          fontSize: 'var(--font-size-sm)', opacity: 0.5, textAlign: 'center',
        }}>
          {selectedSheet.name} | {items.length} Items | {selectedSheet.send_type ?? 'Standard'}
        </div>
      )}
    </div>
  );
}
