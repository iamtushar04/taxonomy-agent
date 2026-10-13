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

  // Build year → assignee count map
  const yearMap = {};
  patents.forEach(p => {
    if (!p.filing_date) return;
    const year = String(p.filing_date).slice(0, 4);
    if (!year || isNaN(year)) return;
    if (!yearMap[year]) yearMap[year] = { year };
    const assignee = topAssignees.includes(p.assignee) ? p.assignee : null;
    if (assignee) {
      yearMap[year][assignee] = (yearMap[year][assignee] || 0) + 1;
    }
  });

  return {
    data: Object.values(yearMap).sort((a, b) => a.year - b.year),
    topAssignees
  };
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: '#1e293b', border: '1px solid #334155',
      borderRadius: 8, padding: '10px 14px', color: '#f1f5f9'
    }}>
      <p style={{ margin: 0, fontWeight: 600, marginBottom: 6 }}>Year: {label}</p>
      {payload.map((entry, i) => (
        <p key={i} style={{ margin: '2px 0', color: entry.fill, fontSize: 13 }}>
          {entry.dataKey}: <strong>{entry.value}</strong>
        </p>
      ))}
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
    <div style={{ width: '100%', height: 380 }}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey="year"
            tick={{ fill: '#94a3b8', fontSize: 12 }}
            label={{ value: 'Filing Year', position: 'insideBottom', offset: -50, fill: '#64748b' }}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fill: '#94a3b8', fontSize: 12 }}
            label={{ value: 'Patent Count', angle: -90, position: 'insideLeft', fill: '#64748b' }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ paddingTop: 16, color: '#94a3b8', fontSize: 12 }}
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
