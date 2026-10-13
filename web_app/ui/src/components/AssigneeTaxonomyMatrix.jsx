/**
 * AssigneeTaxonomyMatrix.jsx
 *
 * Shows Assignees and their presence across Taxonomy Nodes & filing years:
 * - Summary cards per Assignee showing patent counts, active years, and mapped taxonomy nodes
 * - Allows user to click an Assignee to inspect their exact taxonomy breakdown
 * - Fully modular, pure front-end client presentation
 */

import React, { useMemo, useState } from 'react';

const CARD_STYLE = {
  background: '#131d31',
  border: '1px solid #1e293b',
  borderRadius: 10,
  padding: '16px 20px',
  transition: 'border-color 0.2s, transform 0.15s',
  cursor: 'pointer',
};

export default function AssigneeTaxonomyMatrix({ patents, taxonomy, onSelectAssignee, selectedAssignee }) {
  const [filterQuery, setFilterQuery] = useState('');

  // 1. Build patent -> taxonomy nodes map
  const patentTaxMap = useMemo(() => {
    const map = {};
    patents.forEach(p => { map[p.patent_id] = []; });
    taxonomy.forEach(node => {
      const ids = node.supporting_patent_ids || [];
      ids.forEach(pid => {
        if (map[pid]) {
          map[pid].push(node.name);
        }
      });
    });
    return map;
  }, [patents, taxonomy]);

  // 2. Aggregate data by Assignee
  const assigneeStats = useMemo(() => {
    const stats = {};
    patents.forEach(p => {
      const assignee = p.assignee || 'Unknown';
      if (!stats[assignee]) {
        stats[assignee] = {
          name: assignee,
          patents: [],
          years: new Set(),
          taxonomyCounts: {},
        };
      }
      stats[assignee].patents.push(p);
      if (p.filing_date) {
        const y = String(p.filing_date).slice(0, 4);
        if (y && !isNaN(y)) stats[assignee].years.add(y);
      }
      const nodes = patentTaxMap[p.patent_id] || [];
      nodes.forEach(n => {
        stats[assignee].taxonomyCounts[n] = (stats[assignee].taxonomyCounts[n] || 0) + 1;
      });
    });

    return Object.values(stats)
      .map(s => ({
        ...s,
        yearsList: Array.from(s.years).sort(),
        topTaxonomies: Object.entries(s.taxonomyCounts)
          .sort((a, b) => b[1] - a[1]),
      }))
      .sort((a, b) => b.patents.length - a.patents.length);
  }, [patents, patentTaxMap]);

  // Filter assignees
  const filteredAssignees = useMemo(() => {
    if (!filterQuery.trim()) return assigneeStats;
    const q = filterQuery.toLowerCase();
    return assigneeStats.filter(a =>
      a.name.toLowerCase().includes(q) ||
      a.topTaxonomies.some(([taxName]) => taxName.toLowerCase().includes(q))
    );
  }, [assigneeStats, filterQuery]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14, flexWrap: 'wrap', gap: 10 }}>
        <p style={{ margin: 0, fontSize: 13, color: '#94a3b8' }}>
          Explore which taxonomy branches each assignee is active in. Click an assignee to filter the details below.
        </p>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            value={filterQuery}
            onChange={e => setFilterQuery(e.target.value)}
            placeholder="Filter assignee or taxonomy..."
            style={{
              padding: '6px 12px',
              borderRadius: 6,
              border: '1px solid #334155',
              background: '#1e293b',
              color: '#f1f5f9',
              fontSize: 12,
              outline: 'none',
              width: 220,
            }}
          />
          {selectedAssignee && (
            <button
              onClick={() => onSelectAssignee?.(null)}
              style={{
                background: '#334155',
                color: '#e2e8f0',
                border: 'none',
                borderRadius: 6,
                padding: '6px 10px',
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              Clear Filter ✕
            </button>
          )}
        </div>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
        gap: 14,
        maxHeight: 400,
        overflowY: 'auto',
        paddingRight: 4,
      }}>
        {filteredAssignees.map(a => {
          const isSelected = selectedAssignee === a.name;
          return (
            <div
              key={a.name}
              onClick={() => onSelectAssignee?.(isSelected ? null : a.name)}
              style={{
                ...CARD_STYLE,
                borderColor: isSelected ? '#6366f1' : '#1e293b',
                background: isSelected ? '#1e1b4b' : '#131d31',
                boxShadow: isSelected ? '0 0 0 1px #6366f1' : 'none',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                <span style={{ fontWeight: 700, color: '#f1f5f9', fontSize: 14, maxWidth: '75%' }}>
                  {a.name}
                </span>
                <span style={{
                  background: isSelected ? '#6366f1' : '#1e293b',
                  color: isSelected ? '#ffffff' : '#94a3b8',
                  padding: '2px 8px',
                  borderRadius: 12,
                  fontSize: 11,
                  fontWeight: 600,
                }}>
                  {a.patents.length} patent{a.patents.length > 1 ? 's' : ''}
                </span>
              </div>

              {/* Active years */}
              <div style={{ fontSize: 12, color: '#64748b', marginBottom: 10 }}>
                📅 Years: {a.yearsList.length > 0 ? a.yearsList.join(', ') : 'None'}
              </div>

              {/* Taxonomy node tags */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                {a.topTaxonomies.length === 0 ? (
                  <span style={{ color: '#475569', fontSize: 11 }}>No taxonomy mapping</span>
                ) : (
                  a.topTaxonomies.slice(0, 5).map(([taxName, count], idx) => (
                    <span
                      key={idx}
                      style={{
                        background: '#312e81',
                        color: '#c7d2fe',
                        padding: '2px 7px',
                        borderRadius: 6,
                        fontSize: 11,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 4,
                      }}
                    >
                      <span>{taxName}</span>
                      <strong style={{ color: '#818cf8', fontSize: 10 }}>({count})</strong>
                    </span>
                  ))
                )}
                {a.topTaxonomies.length > 5 && (
                  <span style={{ color: '#64748b', fontSize: 11, alignSelf: 'center' }}>
                    +{a.topTaxonomies.length - 5} more
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
