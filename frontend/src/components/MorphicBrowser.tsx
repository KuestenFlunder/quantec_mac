import { useEffect, useState } from 'react';
import type { MorphicCategoryInfo, MorphicItem } from '../types';
import { fetchMorphicCategories, fetchMorphicItems, searchMorphicItems } from '../api/client';

interface MorphicBrowserProps {
  onSelectItem?: (item: MorphicItem) => void;
}

export default function MorphicBrowser({ onSelectItem }: MorphicBrowserProps) {
  const [categories, setCategories] = useState<MorphicCategoryInfo[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<MorphicCategoryInfo | null>(null);
  const [items, setItems] = useState<MorphicItem[]>([]);
  const [search, setSearch] = useState('');
  const [searchMode, setSearchMode] = useState<'fulltext' | 'semantic'>('fulltext');
  const [loading, setLoading] = useState(true);
  const [searchResults, setSearchResults] = useState<MorphicItem[] | null>(null);

  useEffect(() => {
    loadCategories();
  }, []);

  async function loadCategories() {
    setLoading(true);
    try {
      const data = await fetchMorphicCategories();
      setCategories(data);
    } catch {
      // Fehlerbehandlung
    } finally {
      setLoading(false);
    }
  }

  async function selectCategory(cat: MorphicCategoryInfo) {
    setSelectedCategory(cat);
    setSearchResults(null);
    try {
      const data = await fetchMorphicItems(cat.id);
      setItems(data);
    } catch {
      setItems([]);
    }
  }

  async function handleSearch() {
    if (!search.trim()) {
      setSearchResults(null);
      return;
    }
    try {
      const results = await searchMorphicItems(search, searchMode);
      setSearchResults(results);
    } catch {
      setSearchResults([]);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') {
      handleSearch();
    }
  }

  if (loading) {
    return <div className="loading-spinner" />;
  }

  const displayItems = searchResults ?? items;

  // Gruppiere Kategorien nach Theme
  const grouped = new Map<string, MorphicCategoryInfo[]>();
  for (const cat of categories) {
    const theme = cat.theme_name ?? 'Sonstige';
    const existing = grouped.get(theme);
    if (existing) {
      existing.push(cat);
    } else {
      grouped.set(theme, [cat]);
    }
  }

  return (
    <div className="split-pane" style={{ height: '100%' }}>
      <div className="split-pane-left">
        <div style={{ padding: 'var(--spacing-md)', borderBottom: '1px solid var(--color-border)' }}>
          <strong style={{ fontSize: 'var(--font-size-sm)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Kategorien ({categories.length})
          </strong>
        </div>
        <div style={{ overflowY: 'auto', flex: 1 }}>
          {Array.from(grouped.entries()).map(([theme, cats]) => (
            <div key={theme}>
              <div
                style={{
                  padding: 'var(--spacing-sm) var(--spacing-lg)',
                  fontSize: 'var(--font-size-sm)',
                  fontWeight: 600,
                  color: 'var(--color-primary)',
                  background: 'var(--color-table-row-alt)',
                  textTransform: 'uppercase',
                  letterSpacing: 0.3,
                }}
              >
                {theme}
              </div>
              {cats.map((cat) => (
                <div
                  key={cat.id}
                  className={`list-item${selectedCategory?.id === cat.id ? ' active' : ''}`}
                  onClick={() => selectCategory(cat)}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>{cat.name}</span>
                    <span
                      style={{
                        fontSize: 'var(--font-size-sm)',
                        opacity: 0.5,
                        background: 'var(--color-background)',
                        padding: '1px 6px',
                        borderRadius: 8,
                      }}
                    >
                      {cat.item_count}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      <div className="split-pane-right">
        <div className="toolbar">
          <input
            type="text"
            className="form-input search-input"
            placeholder="Morphische Felder durchsuchen..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <div style={{ display: 'flex', gap: 'var(--spacing-xs)' }}>
            <button
              className={`btn btn-sm ${searchMode === 'fulltext' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setSearchMode('fulltext')}
              type="button"
            >
              Volltext
            </button>
            <button
              className={`btn btn-sm ${searchMode === 'semantic' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setSearchMode('semantic')}
              type="button"
            >
              Semantisch
            </button>
          </div>
          <button className="btn btn-primary btn-sm" onClick={handleSearch} type="button">
            Suchen
          </button>
        </div>

        {searchResults !== null && (
          <div style={{ marginBottom: 'var(--spacing-md)', fontSize: 'var(--font-size-sm)', opacity: 0.6 }}>
            {searchResults.length} Ergebnis{searchResults.length !== 1 ? 'se' : ''} fuer &quot;{search}&quot;
            <button
              style={{ marginLeft: 8, background: 'none', border: 'none', color: 'var(--color-primary)', cursor: 'pointer' }}
              onClick={() => { setSearchResults(null); setSearch(''); }}
              type="button"
            >
              Zuruecksetzen
            </button>
          </div>
        )}

        {displayItems.length === 0 ? (
          <div className="empty-state">
            {searchResults !== null
              ? 'Keine Ergebnisse gefunden.'
              : selectedCategory
                ? 'Keine Items in dieser Kategorie.'
                : 'Waehlen Sie eine Kategorie aus der Liste.'}
          </div>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Text</th>
                  <th>Beschreibung</th>
                  {onSelectItem && <th></th>}
                </tr>
              </thead>
              <tbody>
                {displayItems.map((item) => (
                  <tr key={item.id} onClick={() => onSelectItem?.(item)}>
                    <td style={{ fontWeight: 500 }}>{item.text_primary ?? '-'}</td>
                    <td style={{ opacity: 0.7 }}>{item.text_secondary ?? '-'}</td>
                    {onSelectItem && (
                      <td>
                        <button className="btn btn-primary btn-sm" type="button">
                          Hinzufuegen
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
