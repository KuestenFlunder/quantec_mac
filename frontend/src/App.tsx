import { useState } from 'react';
import type { NavSection, Client, Target } from './types';
import { fetchClient, fetchTarget } from './api/client';
import Sidebar from './components/Sidebar';
import ClientList from './components/ClientList';
import ClientDetail from './components/ClientDetail';
import TargetDetail from './components/TargetDetail';
import HealingSheetEditor from './components/HealingSheetEditor';
import MorphicBrowser from './components/MorphicBrowser';
import ScanView from './components/ScanView';
import SendView from './components/SendView';
import ScheduleView from './components/ScheduleView';
import ReportsView from './components/ReportsView';
import DatabaseView from './components/DatabaseView';
import SettingsView from './components/SettingsView';

const SECTION_TITLES: Record<NavSection, string> = {
  clients: 'Klienten',
  morphic: 'Morphische Felder',
  scanner: 'Scanner',
  send: 'Bewellung',
  schedule: 'Sendeplan',
  reports: 'Berichte',
  database: 'Datenbank',
  settings: 'Einstellungen',
};

type SubView =
  | { type: 'list' }
  | { type: 'client-detail'; client: Client | null }
  | { type: 'target-detail'; target: Target | null; clientId: number }
  | { type: 'sheet-editor'; targetId: number; clientId: number }
  | { type: 'morphic-picker'; sheetId: number; targetId: number; clientId: number }
  | { type: 'scan'; sheetId: number; targetId: number; clientId: number };

export default function App() {
  const [activeSection, setActiveSection] = useState<NavSection>('clients');
  const [subView, setSubView] = useState<SubView>({ type: 'list' });

  function navigateTo(section: NavSection) {
    setActiveSection(section);
    setSubView({ type: 'list' });
  }

  function getTitle(): string {
    switch (subView.type) {
      case 'client-detail':
        return subView.client
          ? `${subView.client.first_name} ${subView.client.last_name}`
          : 'Neuer Klient';
      case 'target-detail':
        return subView.target ? `Zielobjekt: ${subView.target.name}` : 'Neues Zielobjekt';
      case 'sheet-editor':
        return 'Healing Sheets';
      case 'morphic-picker':
        return 'Item auswaehlen';
      case 'scan':
        return 'Hardware-Scan';
      default:
        return SECTION_TITLES[activeSection];
    }
  }

  function renderContent() {
    switch (subView.type) {
      case 'client-detail':
        return (
          <ClientDetail
            client={subView.client}
            onSaved={() => setSubView({ type: 'list' })}
            onCancel={() => setSubView({ type: 'list' })}
            onSelectTarget={(target) => {
              const cId = subView.client?.id;
              if (cId) {
                setSubView({ type: 'target-detail', target: target?.id ? target : null, clientId: cId });
              }
            }}
          />
        );

      case 'target-detail': {
        const returnToClient = async () => {
          try {
            const client = await fetchClient(subView.clientId);
            setSubView({ type: 'client-detail', client });
          } catch {
            setSubView({ type: 'list' });
          }
        };
        return (
          <TargetDetail
            target={subView.target}
            clientId={subView.clientId}
            onSaved={returnToClient}
            onCancel={returnToClient}
            onOpenSheets={(targetId) =>
              setSubView({ type: 'sheet-editor', targetId, clientId: subView.clientId })
            }
          />
        );
      }

      case 'sheet-editor': {
        const returnToTarget = async () => {
          try {
            const target = await fetchTarget(subView.targetId);
            setSubView({ type: 'target-detail', target, clientId: subView.clientId });
          } catch {
            setSubView({ type: 'list' });
          }
        };
        return (
          <HealingSheetEditor
            targetId={subView.targetId}
            onBack={returnToTarget}
            onOpenMorphicBrowser={(sheetId) =>
              setSubView({
                type: 'morphic-picker',
                sheetId,
                targetId: subView.targetId,
                clientId: subView.clientId,
              })
            }
            onStartScan={(sheetId) =>
              setSubView({
                type: 'scan',
                sheetId,
                targetId: subView.targetId,
                clientId: subView.clientId,
              })
            }
          />
        );
      }

      case 'morphic-picker':
        return (
          <MorphicBrowser
            onSelectItem={() => {
              setSubView({
                type: 'sheet-editor',
                targetId: subView.targetId,
                clientId: subView.clientId,
              });
            }}
          />
        );

      case 'scan':
        return (
          <ScanView
            healingSheetId={subView.sheetId}
          />
        );

      default:
        break;
    }

    switch (activeSection) {
      case 'clients':
        return (
          <ClientList
            onSelectClient={(client) =>
              setSubView({ type: 'client-detail', client })
            }
            onNewClient={() =>
              setSubView({ type: 'client-detail', client: null })
            }
          />
        );

      case 'morphic':
        return <MorphicBrowser />;

      case 'scanner':
        return <ScanView />;

      case 'send':
        return <SendView />;

      case 'schedule':
        return <ScheduleView />;

      case 'reports':
        return <ReportsView />;

      case 'database':
        return <DatabaseView />;

      case 'settings':
        return <SettingsView />;
    }
  }

  return (
    <div className="app-layout">
      <Sidebar activeSection={activeSection} onNavigate={navigateTo} />
      <main className="app-content">
        <div className="content-header">
          <h1>{getTitle()}</h1>
        </div>
        <div className="content-body">{renderContent()}</div>
      </main>
    </div>
  );
}
