/**
 * AssigneeFilingChart.jsx
 *
 * Bar chart: Filing Year (X-axis) vs Patent Count (Y-axis), color-coded by Assignee.
 * Shows top-N assignees to avoid a cluttered legend.
 */

import React, { useMemo } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, Cell
} from 'recharts';

const TOP_N_ASSIGNEES = 10;
const COLORS = [
  '#6366f1', '#22d3ee', '#f59e0b', '#10b981',
  '#f43f5e', '#a78bfa', '#34d399', '#fb923c',
  '#38bdf8', '#e879f9'
];

/**
 * Transforms flat patent list into chart-ready data:
 *   [{ year: "2019", "Apple Inc.": 3, "Google LLC": 1, ... }, ...]
 */
function buildChartData(patents) {
  const assigneeCounts = {};
  patents.forEach(p => {
    const assignee = p.assignee || 'Unknown';
    assigneeCounts[assignee] = (assigneeCounts[assignee] || 0) + 1;
  });

  // Pick top N assignees by total patent count
  const topAssignees = Object.entries(assigneeCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, TOP_N_ASSIGNEES)
    .map(([name]) => name);

  // Build year → assignee count map and patent list
  const yearMap = {};
  patents.forEach(p => {
    if (!p.filing_date) return;
    const year = String(p.filing_date).slice(0, 4);
    if (!year || isNaN(year)) return;
    if (!yearMap[year]) yearMap[year] = { year, _patents: {} };
    const assignee = topAssignees.includes(p.assignee) ? p.assignee : null;
    if (assignee) {
      yearMap[year][assignee] = (yearMap[year][assignee] || 0) + 1;
      if (!yearMap[year]._patents[assignee]) yearMap[year]._patents[assignee] = [];
      if (!yearMap[year]._patents[assignee].includes(p.patent_id)) {
        yearMap[year]._patents[assignee].push(p.patent_id);
      }
    }
  });

  return {
    data: Object.values(yearMap).sort((a, b) => a.year - b.year),
    topAssignees
  };
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const rawData = payload[0]?.payload || {};
  const patentsByAssignee = rawData._patents || {};

  return (
    <div style={{
      background: '#0b1120',
      border: '1px solid #334155',
      borderRadius: 10,
      padding: '12px 16px',
      color: '#f1f5f9',
      boxShadow: '0 12px 30px rgba(0,0,0,0.85)',
      maxWidth: 360,
      position: 'relative',
      zIndex: 9999,
      pointerEvents: 'none',
    }}>
      <p style={{ margin: 0, fontWeight: 700, fontSize: 14, color: '#e2e8f0', marginBottom: 8, borderBottom: '1px solid #1e293b', paddingBottom: 4 }}>
        📅 Filing Year: {label}
      </p>
      {payload.map((entry, i) => {
        const pids = patentsByAssignee[entry.dataKey] || [];
        return (
          <div key={i} style={{ marginBottom: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
              <span style={{ color: entry.fill, fontWeight: 600, fontSize: 13 }}>
                ● {entry.dataKey}:
              </span>
              <strong style={{ color: '#fff', fontSize: 12 }}>
                {entry.value} patent{entry.value > 1 ? 's' : ''}
              </strong>
            </div>
            {pids.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4, paddingLeft: 12 }}>
                {pids.slice(0, 6).map((pid, idx) => (
                  <span
                    key={idx}
                    style={{
                      fontFamily: 'monospace',
                      fontSize: 11,
                      background: '#1e293b',
                      color: '#a5b4fc',
                      padding: '1px 6px',
                      borderRadius: 4,
                      border: '1px solid #334155',
                    }}
                  >
                    {pid}
                  </span>
                ))}
                {pids.length > 6 && (
                  <span style={{ fontSize: 10, color: '#64748b', alignSelf: 'center' }}>
                    +{pids.length - 6} more
                  </span>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default function AssigneeFilingChart({ patents }) {
  const { data, topAssignees } = useMemo(() => buildChartData(patents), [patents]);

  if (!data.length) {
    return (
      <div style={{ color: '#94a3b8', textAlign: 'center', padding: 40 }}>
        No filing date data available for these patents.
      </div>
    );
  }

  return (
    <div style={{ width: '100%', minWidth: 0, height: 380 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey="year"
            tick={{ fill: '#94a3b8', fontSize: 12 }}
            dy={6}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fill: '#94a3b8', fontSize: 12 }}
            label={{ value: 'Patent Count', angle: -90, position: 'insideLeft', fill: '#64748b' }}
          />
          <Tooltip
            content={<CustomTooltip />}
            cursor={false}
            wrapperStyle={{ zIndex: 99999, pointerEvents: 'none' }}
          />
          <Legend
            verticalAlign="top"
            wrapperStyle={{ paddingBottom: 16, color: '#94a3b8', fontSize: 12 }}
            formatter={(value) => (
              <span style={{ color: '#cbd5e1' }}>
                {value.length > 28 ? value.slice(0, 28) + '…' : value}
              </span>
            )}
          />
          {topAssignees.map((assignee, i) => (
            <Bar key={assignee} dataKey={assignee} stackId="a" fill={COLORS[i % COLORS.length]} radius={i === topAssignees.length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
