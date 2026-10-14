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

export default function PatentTaxonomyTable({
  patents,
  taxonomy,
  selectedAssignee,
  onSelectAssignee,
  selectedTechNode,
  onSelectTechNode
}) {
  const [search, setSearch] = useState('');
  const [selectedYear, setSelectedYear] = useState('ALL');
  const [activePatentModal, setActivePatentModal] = useState(null);
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

  // Extract unique taxonomy node names
  const availableTechNodes = useMemo(() => {
    return taxonomy
      .filter(n => n.level > 0)
      .map(n => n.name)
      .sort();
  }, [taxonomy]);

  const filtered = useMemo(() => {
    return patents.filter(p => {
      // 1. Assignee filter
      if (selectedAssignee && p.assignee !== selectedAssignee) return false;

      // 2. Year filter
      if (selectedYear !== 'ALL') {
        const y = p.filing_date ? String(p.filing_date).slice(0, 4) : '';
        if (y !== selectedYear) return false;
      }

      // 3. Technology / Taxonomy Node filter
      if (selectedTechNode) {
        const nodes = patentTaxMap[p.patent_id] || [];
        if (!nodes.includes(selectedTechNode)) return false;
      }

      // 4. Full search query
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
  }, [patents, search, selectedAssignee, selectedYear, selectedTechNode, patentTaxMap]);

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

        <select
          value={selectedTechNode || 'ALL'}
          onChange={e => onSelectTechNode?.(e.target.value === 'ALL' ? null : e.target.value)}
          style={{
            padding: '9px 12px',
            borderRadius: 8,
            border: '1px solid #334155',
            background: '#1e293b',
            color: selectedTechNode ? '#38bdf8' : '#cbd5e1',
            fontSize: 13,
            outline: 'none',
            fontWeight: selectedTechNode ? 600 : 400,
            maxWidth: 220,
          }}
        >
          <option value="ALL">All Technologies ({availableTechNodes.length})</option>
          {availableTechNodes.map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>

        {(selectedAssignee || selectedTechNode || selectedYear !== 'ALL' || search) && (
          <button
            onClick={() => {
              onSelectAssignee?.(null);
              onSelectTechNode?.(null);
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
                <tr key={p.patent_id} style={{ transition: 'background 0.15s', cursor: 'pointer' }}
                  onClick={() => setActivePatentModal(p)}
                  onMouseEnter={e => e.currentTarget.style.background = '#1e293b'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  title="Click to view full patent details, abstract, and taxonomy alignment"
                >
                  <td style={{ ...TD_STYLE, fontFamily: 'monospace', color: '#6366f1', fontWeight: 600 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span>📄</span>
                      <span style={{ textDecoration: 'underline' }}>{p.patent_id}</span>
                    </div>
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
        Showing {filtered.length} of {patents.length} patents (click any row for full patent details)
      </div>

      {/* Patent Detail Modal */}
      {activePatentModal && (
        <div 
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.75)',
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
            backdropFilter: 'blur(4px)'
          }}
          onClick={() => setActivePatentModal(null)}
        >
          <div 
            style={{
              background: '#0f172a',
              border: '1px solid #334155',
              borderRadius: 16,
              maxWidth: 720,
              width: '100%',
              maxHeight: '85vh',
              overflowY: 'auto',
              padding: 24,
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
              color: '#f8fafc'
            }}
            onClick={e => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid #334155', paddingBottom: 16, marginBottom: 16 }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ background: '#312e81', color: '#a5b4fc', padding: '3px 8px', borderRadius: 6, fontSize: 13, fontFamily: 'monospace', fontWeight: 700 }}>
                    {activePatentModal.patent_id}
                  </span>
                  <span style={{ fontSize: 12, color: '#94a3b8' }}>
                    Filed: {activePatentModal.filing_date ? String(activePatentModal.filing_date).slice(0, 10) : 'N/A'}
                  </span>
                </div>
                <h3 style={{ fontSize: 17, fontWeight: 700, marginTop: 10, marginBottom: 4, color: '#f1f5f9', lineHeight: 1.4 }}>
                  {activePatentModal.title || 'No Title Available'}
                </h3>
                <div style={{ fontSize: 13, color: '#38bdf8' }}>
                  Assignee: {activePatentModal.assignee || 'Unknown'}
                </div>
              </div>
              <button 
                onClick={() => setActivePatentModal(null)}
                style={{
                  background: '#1e293b',
                  border: '1px solid #475569',
                  color: '#cbd5e1',
                  borderRadius: 8,
                  padding: '6px 12px',
                  cursor: 'pointer',
                  fontSize: 14,
                  fontWeight: 'bold'
                }}
              >
                ✕ Close
              </button>
            </div>

            {/* Aligned Taxonomy Categories */}
            <div style={{ marginBottom: 18 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginBottom: 8 }}>
                Aligned Taxonomy Categories ({patentTaxMap[activePatentModal.patent_id]?.length || 0})
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {(patentTaxMap[activePatentModal.patent_id] || []).map((tName, i) => (
                  <span key={i} style={{
                    background: '#1e1b4b',
                    border: '1px solid #4338ca',
                    color: '#c7d2fe',
                    padding: '4px 10px',
                    borderRadius: 99,
                    fontSize: 12,
                    fontWeight: 600
                  }}>
                    {tName}
                  </span>
                ))}
              </div>
            </div>

            {/* AI Summary / Abstract */}
            {activePatentModal.summary && (
              <div style={{ marginBottom: 18, background: '#1e293b', padding: 14, borderRadius: 10, border: '1px solid #334155' }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#38bdf8', marginBottom: 6 }}>
                  ✨ Technical Summary
                </div>
                <div style={{ fontSize: 13, color: '#cbd5e1', lineHeight: 1.5 }}>
                  {activePatentModal.summary}
                </div>
              </div>
            )}

            {/* Full Text / Claims Snippet */}
            {activePatentModal.full_text && (
              <div style={{ marginTop: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginBottom: 8 }}>
                  Patent Specification & Claims Preview
                </div>
                <div style={{
                  background: '#090d16',
                  padding: 14,
                  borderRadius: 10,
                  border: '1px solid #1e293b',
                  fontSize: 12,
                  color: '#94a3b8',
                  lineHeight: 1.6,
                  maxHeight: 240,
                  overflowY: 'auto',
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'monospace'
                }}>
                  {activePatentModal.full_text}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
