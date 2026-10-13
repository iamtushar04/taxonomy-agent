/**
 * AssigneeTechHeatmap.jsx
 *
 * Competitive Intelligence Heatmap:
 * - Rows: Assignees (Competitors)
 * - Columns: Key Technology / Taxonomy Categories
 * - Cells: Patent volume density (heat intensity)
 * - Highlights competitor strength, overlaps, and white spaces
 * - Clicking any cell filters the dashboard to that specific (Assignee, Tech) intersection
 */

import React, { useMemo } from 'react';

const TH_STYLE = {
  padding: '10px 12px',
  background: '#0f172a',
  color: '#6366f1',
  fontSize: 12,
  fontWeight: 700,
  textAlign: 'center',
  position: 'sticky',
  top: 0,
  zIndex: 2,
  borderBottom: '1px solid #334155',
  whiteSpace: 'nowrap',
};

const ROW_HEADER_STYLE = {
  padding: '10px 14px',
  background: '#131d31',
  color: '#f1f5f9',
  fontSize: 13,
  fontWeight: 600,
  textAlign: 'left',
  position: 'sticky',
  left: 0,
  zIndex: 1,
  borderRight: '1px solid #1e293b',
  borderBottom: '1px solid #1e293b',
  whiteSpace: 'nowrap',
};

// Generates an indigo/cyan heat gradient based on relative density
function getHeatColor(count, maxCount) {
  if (!count || count === 0) return { bg: 'transparent', text: '#475569' };
  const ratio = Math.min(count / (maxCount || 1), 1);
  if (ratio > 0.7) return { bg: '#4f46e5', text: '#ffffff' };     // High density
  if (ratio > 0.4) return { bg: '#4338ca', text: '#e0e7ff' };     // Medium-high
  if (ratio > 0.2) return { bg: '#312e81', text: '#c7d2fe' };     // Medium
  return { bg: '#1e1b4b', text: '#a5b4fc' };                      // Emerging / 1 patent
}

export default function AssigneeTechHeatmap({
  patents,
  taxonomy,
  selectedAssignee,
  selectedTechNode,
  onSelectCell
}) {
  const { assignees, techNodes, matrix, maxCellVal } = useMemo(() => {
    // 1. Build patent -> taxonomy nodes
    const patentTechMap = {};
    patents.forEach(p => { patentTechMap[p.patent_id] = new Set(); });

    taxonomy.forEach(n => {
      // Pick Level 1 & Level 2 nodes for meaningful columns
      if (n.level === 0) return;
      (n.supporting_patent_ids || []).forEach(pid => {
        if (patentTechMap[pid]) patentTechMap[pid].add(n.name);
      });
    });

    // 2. Aggregate Assignee -> { total, techCounts: {} }
    const assigneeMap = {};
    const techFrequency = {};

    patents.forEach(p => {
      const a = p.assignee || 'Unknown';
      if (!assigneeMap[a]) assigneeMap[a] = { total: 0, techCounts: {} };
      assigneeMap[a].total += 1;

      const nodes = patentTechMap[p.patent_id] || new Set();
      nodes.forEach(tName => {
        techFrequency[tName] = (techFrequency[tName] || 0) + 1;
        assigneeMap[a].techCounts[tName] = (assigneeMap[a].techCounts[tName] || 0) + 1;
      });
    });

    // Top assignees (by patent count)
    const sortedAssignees = Object.entries(assigneeMap)
      .sort((a, b) => b[1].total - a[1].total)
      .slice(0, 10)
      .map(([name, data]) => ({ name, ...data }));

    // Top technologies (by patent count)
    const sortedTech = Object.entries(techFrequency)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([name]) => name);

    // Compute max cell count for heatmap color scaling
    let maxVal = 1;
    sortedAssignees.forEach(a => {
      sortedTech.forEach(t => {
        const val = a.techCounts[t] || 0;
        if (val > maxVal) maxVal = val;
      });
    });

    return {
      assignees: sortedAssignees,
      techNodes: sortedTech,
      matrix: assigneeMap,
      maxCellVal: maxVal
    };
  }, [patents, taxonomy]);

  if (assignees.length === 0 || techNodes.length === 0) {
    return (
      <div style={{ color: '#64748b', textAlign: 'center', padding: 30, fontSize: 13 }}>
        Not enough taxonomy or assignee data to build the competitive matrix.
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontSize: 13, color: '#94a3b8' }}>
          Competitive Matrix: Click any cell to see patents belonging to that Assignee & Technology.
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: '#64748b' }}>
          <span>Density:</span>
          <span style={{ background: '#1e1b4b', padding: '2px 6px', borderRadius: 4, color: '#a5b4fc' }}>Low</span>
          <span style={{ background: '#312e81', padding: '2px 6px', borderRadius: 4, color: '#c7d2fe' }}>Med</span>
          <span style={{ background: '#4f46e5', padding: '2px 6px', borderRadius: 4, color: '#ffffff' }}>High</span>
        </div>
      </div>

      <div style={{ overflowX: 'auto', overflowY: 'auto', maxHeight: 380, borderRadius: 10, border: '1px solid #1e293b' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 650 }}>
          <thead>
            <tr>
              <th style={{ ...TH_STYLE, textAlign: 'left', minWidth: 180, left: 0, zIndex: 3 }}>
                Assignee / Competitor
              </th>
              {techNodes.map(t => (
                <th
                  key={t}
                  style={{
                    ...TH_STYLE,
                    background: selectedTechNode === t ? '#312e81' : '#0f172a',
                    color: selectedTechNode === t ? '#ffffff' : '#6366f1',
                    cursor: 'pointer',
                  }}
                  title={`Filter by ${t}`}
                  onClick={() => onSelectCell?.(null, selectedTechNode === t ? null : t)}
                >
                  {t.length > 20 ? t.slice(0, 20) + '…' : t}
                </th>
              ))}
              <th style={{ ...TH_STYLE, width: 80 }}>Total</th>
            </tr>
          </thead>
          <tbody>
            {assignees.map(a => {
              const isAssigneeSelected = selectedAssignee === a.name;
              return (
                <tr key={a.name}>
                  {/* Row Header: Assignee name */}
                  <td
                    style={{
                      ...ROW_HEADER_STYLE,
                      background: isAssigneeSelected ? '#1e1b4b' : '#131d31',
                      color: isAssigneeSelected ? '#818cf8' : '#f1f5f9',
                      cursor: 'pointer',
                    }}
                    title={`Filter by ${a.name}`}
                    onClick={() => onSelectCell?.(isAssigneeSelected ? null : a.name, null)}
                  >
                    {a.name}
                  </td>

                  {/* Heatmap cells */}
                  {techNodes.map(t => {
                    const count = a.techCounts[t] || 0;
                    const heat = getHeatColor(count, maxCellVal);
                    const isCellActive = (selectedAssignee === a.name && selectedTechNode === t);

                    return (
                      <td
                        key={t}
                        onClick={() => {
                          if (count > 0) {
                            onSelectCell?.(
                              isCellActive ? null : a.name,
                              isCellActive ? null : t
                            );
                          }
                        }}
                        style={{
                          textAlign: 'center',
                          padding: '10px 8px',
                          borderBottom: '1px solid #1e293b',
                          borderRight: '1px solid #1e293b',
                          background: isCellActive ? '#6366f1' : heat.bg,
                          color: isCellActive ? '#ffffff' : heat.text,
                          fontWeight: count > 0 ? 700 : 400,
                          fontSize: 13,
                          cursor: count > 0 ? 'pointer' : 'default',
                          transition: 'all 0.15s ease',
                        }}
                        title={count > 0 ? `${a.name}: ${count} patent(s) in "${t}" (Click to view)` : 'No patents in this branch'}
                      >
                        {count > 0 ? count : '·'}
                      </td>
                    );
                  })}

                  {/* Row Total */}
                  <td style={{
                    textAlign: 'center',
                    padding: '10px 8px',
                    borderBottom: '1px solid #1e293b',
                    color: '#94a3b8',
                    fontSize: 12,
                    fontWeight: 700,
                    background: '#0b1120'
                  }}>
                    {a.total}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
