/**
 * PatentTaxonomyTable.jsx
 *
 * Table showing: Patent Number | Title | Assignee | Filing Date | Taxonomy Nodes
 *
 * Accepts:
 *   - patents: array from /api/analytics (id, title, assignee, filing_date)
 *   - taxonomy: array from /api/taxonomy (name, supporting_patent_ids, level)
 */

import React, { useMemo, useState } from 'react';

function buildPatentTaxonomyMap(patents, taxonomy) {
  // Build a map: patent_id → list of taxonomy node names (leaf + parent)
  const map = {};
  patents.forEach(p => { map[p.patent_id] = []; });

  taxonomy.forEach(node => {
    const ids = node.supporting_patent_ids || [];
    ids.forEach(pid => {
      if (map[pid] !== undefined) {
        map[pid].push(node.name);
      }
    });
  });
  return map;
}

const TD_STYLE = {
  padding: '10px 14px',
  borderBottom: '1px solid #1e293b',
  color: '#e2e8f0',
  fontSize: 13,
  verticalAlign: 'top',
};

const TH_STYLE = {
  padding: '10px 14px',
  background: '#0f172a',
  color: '#6366f1',
  fontSize: 12,
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  textAlign: 'left',
  position: 'sticky',
  top: 0,
  zIndex: 1,
};

export default function PatentTaxonomyTable({ patents, taxonomy, selectedAssignee, onSelectAssignee }) {
  const [search, setSearch] = useState('');
  const [selectedYear, setSelectedYear] = useState('ALL');
  const patentTaxMap = useMemo(() => buildPatentTaxonomyMap(patents, taxonomy), [patents, taxonomy]);

  // Extract unique years
  const availableYears = useMemo(() => {
    const years = new Set();
    patents.forEach(p => {
      if (p.filing_date) {
        const y = String(p.filing_date).slice(0, 4);
        if (y && !isNaN(y)) years.add(y);
      }
    });
    return Array.from(years).sort().reverse();
  }, [patents]);

  // Extract unique assignees
  const availableAssignees = useMemo(() => {
    const set = new Set();
    patents.forEach(p => { if (p.assignee) set.add(p.assignee); });
    return Array.from(set).sort();
  }, [patents]);

  const filtered = useMemo(() => {
    return patents.filter(p => {
      // 1. Assignee filter (from props or selection)
      if (selectedAssignee && p.assignee !== selectedAssignee) return false;

      // 2. Year filter
      if (selectedYear !== 'ALL') {
        const y = p.filing_date ? String(p.filing_date).slice(0, 4) : '';
        if (y !== selectedYear) return false;
      }

      // 3. Search query
      if (search.trim()) {
        const q = search.toLowerCase();
        const matchesQuery = (
          p.patent_id.toLowerCase().includes(q) ||
          (p.title || '').toLowerCase().includes(q) ||
          (p.assignee || '').toLowerCase().includes(q) ||
          (patentTaxMap[p.patent_id] || []).some(n => n.toLowerCase().includes(q))
        );
        if (!matchesQuery) return false;
      }

      return true;
    });
  }, [patents, search, selectedAssignee, selectedYear, patentTaxMap]);

  return (
    <div>
      {/* Filter controls */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="🔍  Search by patent #, title, assignee, taxonomy..."
          style={{
            flex: '1 1 240px',
            padding: '9px 14px',
            borderRadius: 8,
            border: '1px solid #334155',
            background: '#1e293b',
            color: '#f1f5f9',
            fontSize: 13,
            outline: 'none',
          }}
        />

        <select
          value={selectedAssignee || 'ALL'}
          onChange={e => onSelectAssignee?.(e.target.value === 'ALL' ? null : e.target.value)}
          style={{
            padding: '9px 12px',
            borderRadius: 8,
            border: '1px solid #334155',
            background: '#1e293b',
            color: selectedAssignee ? '#818cf8' : '#cbd5e1',
            fontSize: 13,
            outline: 'none',
            fontWeight: selectedAssignee ? 600 : 400,
            maxWidth: 220,
          }}
        >
          <option value="ALL">All Assignees ({availableAssignees.length})</option>
          {availableAssignees.map(a => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>

        <select
          value={selectedYear}
          onChange={e => setSelectedYear(e.target.value)}
          style={{
            padding: '9px 12px',
            borderRadius: 8,
            border: '1px solid #334155',
            background: '#1e293b',
            color: selectedYear !== 'ALL' ? '#818cf8' : '#cbd5e1',
            fontSize: 13,
            outline: 'none',
            fontWeight: selectedYear !== 'ALL' ? 600 : 400,
          }}
        >
          <option value="ALL">All Filing Years</option>
          {availableYears.map(y => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>

        {(selectedAssignee || selectedYear !== 'ALL' || search) && (
          <button
            onClick={() => {
              onSelectAssignee?.(null);
              setSelectedYear('ALL');
              setSearch('');
            }}
            style={{
              padding: '9px 12px',
              borderRadius: 8,
              border: 'none',
              background: '#334155',
              color: '#e2e8f0',
              fontSize: 12,
              cursor: 'pointer',
            }}
          >
            Reset Filters ✕
          </button>
        )}
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto', overflowY: 'auto', maxHeight: 420, borderRadius: 10, border: '1px solid #1e293b' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 700 }}>
          <thead>
            <tr>
              <th style={{ ...TH_STYLE, width: 130 }}>Patent #</th>
              <th style={{ ...TH_STYLE, minWidth: 200 }}>Title</th>
              <th style={{ ...TH_STYLE, width: 160 }}>Assignee</th>
              <th style={{ ...TH_STYLE, width: 110 }}>Filing Date</th>
              <th style={{ ...TH_STYLE, minWidth: 200 }}>Taxonomy Nodes</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ ...TD_STYLE, textAlign: 'center', color: '#64748b', padding: 32 }}>
                  No results found.
                </td>
              </tr>
            ) : (
              filtered.map(p => (
                <tr key={p.patent_id} style={{ transition: 'background 0.15s' }}
                  onMouseEnter={e => e.currentTarget.style.background = '#1e293b'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <td style={{ ...TD_STYLE, fontFamily: 'monospace', color: '#6366f1', fontWeight: 600 }}>
                    {p.patent_id}
                  </td>
                  <td style={{ ...TD_STYLE }}>{p.title || '—'}</td>
                  <td style={{ ...TD_STYLE, color: '#94a3b8' }}>{p.assignee || '—'}</td>
                  <td style={{ ...TD_STYLE, color: '#94a3b8', whiteSpace: 'nowrap' }}>
                    {p.filing_date ? String(p.filing_date).slice(0, 10) : '—'}
                  </td>
                  <td style={{ ...TD_STYLE }}>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                      {(patentTaxMap[p.patent_id] || []).length === 0 ? (
                        <span style={{ color: '#475569', fontSize: 12 }}>No match</span>
                      ) : (
                        patentTaxMap[p.patent_id].map((name, i) => (
                          <span key={i} style={{
                            background: '#312e81',
                            color: '#a5b4fc',
                            padding: '2px 8px',
                            borderRadius: 99,
                            fontSize: 11,
                            fontWeight: 500,
                          }}>
                            {name}
                          </span>
                        ))
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div style={{ marginTop: 8, color: '#475569', fontSize: 12, textAlign: 'right' }}>
        Showing {filtered.length} of {patents.length} patents
      </div>
    </div>
  );
}
