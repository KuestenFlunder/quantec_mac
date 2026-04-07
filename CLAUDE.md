# QUANTEC PRO Mac

## Projekt-Beschreibung

Neuimplementierung der QUANTEC PRO Radionics-Software als native Mac-Anwendung.
Originalquellcode nicht verfuegbar — basiert auf vollstaendigem Reverse Engineering der Windows-.NET-Anwendung.

QUANTEC PRO steuert ein USB-Hardwaregeraet (FTDI-Diode) und verwaltet Klienten, Behandlungsziele (Targets), Behandlungsblaetter (HealingSheets) und morphische Feld-Scans.

## Architektur

- **Frontend**: Electron + React + TypeScript + Vite
- **Backend**: Python (FastAPI), localhost:8000
- **Datenbank**: PostgreSQL 16 + pgvector (Docker)
  - `quantec_vector` (Port 5434): 117.030 esoterische Items, 256 Kategorien, pgvector Embeddings
  - `quantec_migration` (Port 5433): 861.088 raw_blocks, Transferschicht mit Rohdaten
- **Hardware**: FTDI FT232R (BitBang Mode) via pyftdi/python-ftd2xx
- **PDF**: WeasyPrint oder ReportLab

## Projektstruktur

```
backend/
  api/          # FastAPI Router (clients, targets, sheets, morphic, scan, send, schedule, reports)
  hardware/     # FTDI D2XX Wrapper, Diode-Steuerung, Signalqualitaet
  models/       # SQLAlchemy Models
  schemas/      # Pydantic Schemas
  services/     # Business Logic
  config.py     # Konfiguration
  database.py   # DB-Verbindung
  main.py       # FastAPI App Entry Point
frontend/
  src/           # React Components + TypeScript
  electron/      # Electron Main Process
  vite.config.ts
database/        # SQL Migrations, Seeds
docker-compose.yml
claudedocs/      # Reverse Engineering Dokumentation
  deobfuscated/  # Dekompilierte DLLs und C#-Code
```

## Kern-Workflow

```
Client anlegen -> Target erstellen -> HealingSheet erstellen
-> Morphische Felder scannen -> Items ins Sheet uebernehmen
-> Affirmation formulieren -> Sendeplan erstellen -> Bewellung starten
```

## Datenhierarchie

```
Client [1:n] -> Target [1:n] -> HealingSheet [1:n] -> HealingSheet-Item
                                                    -> Affirmation
                                                    -> Schedule [1:n] -> SendJob
```

## Wichtige Dokumentation

| Dokument | Pfad |
|----------|------|
| Funktionale Spezifikation | `claudedocs/QUANTEC_PRO_Funktionale_Spezifikation.md` |
| Hardware Reverse Engineering | `claudedocs/QUANTEC_Hardware_Reverse_Engineering.md` |
| Scan/Send Algorithmus | `claudedocs/QUANTEC_Scan_Send_Algorithmus.md` |
| Implementierungsplan | `claudedocs/QUANTEC_MAC_Implementierungsplan.md` |
| Migration Dokumentation | `claudedocs/QUANTEC_Migration_Dokumentation.md` |
| Setup-Anleitung | `claudedocs/QUANTEC_Setup_und_Gebrauchsanweisung.md` |
| Dekompilierter Hardware-Code | `claudedocs/deobfuscated/Hardware.decompiled.cs` |

## Konventionen

- Sprache: Deutsch (primaer), Englisch (sekundaer)
- Backend: Python, snake_case, FastAPI-Patterns
- Frontend: TypeScript, camelCase, React functional components
- Datenbank: PostgreSQL, snake_case Tabellen- und Spaltennamen
- Alle Umlaute in Dokumentation als ae/oe/ue (Kompatibilitaet)

## Docker

```bash
docker-compose up -d   # Startet PostgreSQL-Container
# quantec_vector:    localhost:5434
# quantec_migration: localhost:5433
```
