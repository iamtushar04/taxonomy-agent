/**
 * TechnologyTrendChart.jsx
 *
 * Visualizes Technology / Taxonomy Evolution by Filing Year:
 * - X-Axis: Filing Year
 * - Y-Axis: Patent Count mapped to each Technology node
 * - Stacked / Grouped Bars for top taxonomy nodes
 * - Allows selecting Level 1 (Macro Themes) or Level 2 (Specific Categories)
 */

import React, { useMemo, useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from 'recharts';

const TOP_N_TECH = 8;
const TECH_COLORS = [
  '#38bdf8', '#818cf8', '#34d399', '#fbbf24',
  '#f43f5e', '#c084fc', '#2dd4bf', '#fb923c',
  '#e879f9', '#a3e635'
];

/**
 * Builds chart data:
 * [{ year: "2020", "Temperature Control": 3, "Aerosol Generation": 1, ... }]
 */
function buildTechTrendData(patents, taxonomy, selectedLevel) {
  // 1. Filter nodes by level if specified, or pick non-root nodes
  const filteredNodes = taxonomy.filter(n => {
    if (selectedLevel === 'ALL') return n.level > 0;
    return n.level === Number(selectedLevel);
  });

  // 2. Count patents per tech node across all years to pick top N
  const nodeTotalCounts = {};
  filteredNodes.forEach(n => {
    nodeTotalCounts[n.name] = (n.supporting_patent_ids || []).length;
  });

  const topNodes = Object.entries(nodeTotalCounts)
    .filter(([_, count]) => count > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, TOP_N_TECH)
    .map(([name]) => name);

  // 3. Build map: patent_id -> filing_year
  const patentYearMap = {};
  patents.forEach(p => {
    if (p.filing_date) {
      const y = String(p.filing_date).slice(0, 4);
      if (y && !isNaN(y)) patentYearMap[p.patent_id] = y;
    }
  });

  // 4. Aggregate: Year -> { year, [techNode]: count, _patents: { [techNode]: [patent_id, ...] } }
  const yearMap = {};
  filteredNodes.forEach(node => {
    if (!topNodes.includes(node.name)) return;
    const pids = node.supporting_patent_ids || [];
    pids.forEach(pid => {
      const year = patentYearMap[pid];
      if (!year) return;
      if (!yearMap[year]) yearMap[year] = { year, _patents: {} };
      yearMap[year][node.name] = (yearMap[year][node.name] || 0) + 1;
      if (!yearMap[year]._patents[node.name]) yearMap[year]._patents[node.name] = [];
      if (!yearMap[year]._patents[node.name].includes(pid)) {
        yearMap[year]._patents[node.name].push(pid);
      }
    });
  });

  return {
    data: Object.values(yearMap).sort((a, b) => a.year - b.year),
    topNodes
  };
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const rawData = payload[0]?.payload || {};
  const patentsByTech = rawData._patents || {};

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
        const pids = patentsByTech[entry.dataKey] || [];
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

export default function TechnologyTrendChart({ patents, taxonomy, onSelectTechNode }) {
  const [levelFilter, setLevelFilter] = useState('ALL');

  const { data, topNodes } = useMemo(
    () => buildTechTrendData(patents, taxonomy, levelFilter),
    [patents, taxonomy, levelFilter]
  );

  return (
    <div>
      {/* Controls row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontSize: 13, color: '#94a3b8' }}>
          Shows how filing volumes in key technology branches evolve over time.
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, color: '#64748b' }}>Taxonomy Depth:</span>
          <select
            value={levelFilter}
            onChange={e => setLevelFilter(e.target.value)}
            style={{
              padding: '5px 10px',
              borderRadius: 6,
              border: '1px solid #334155',
              background: '#1e293b',
              color: '#cbd5e1',
              fontSize: 12,
              outline: 'none',
            }}
          >
            <option value="ALL">All Levels</option>
            <option value="1">Level 1 (Themes)</option>
            <option value="2">Level 2 (Categories)</option>
            <option value="3">Level 3 (Sub-Tech)</option>
          </select>
        </div>
      </div>

      {data.length === 0 ? (
        <div style={{ color: '#64748b', textAlign: 'center', padding: 40, fontSize: 13 }}>
          No filing date information mapped to technology nodes.
        </div>
      ) : (
        <div style={{ width: '100%', minWidth: 0, height: 360 }}>
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
                label={{ value: 'Patents Mapped', angle: -90, position: 'insideLeft', fill: '#64748b' }}
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
                  <span
                    onClick={() => onSelectTechNode?.(value)}
                    style={{ color: '#cbd5e1', cursor: 'pointer' }}
                    title={`Click to filter by ${value}`}
                  >
                    {value.length > 25 ? value.slice(0, 25) + '…' : value}
                  </span>
                )}
              />
              {topNodes.map((techName, i) => (
                <Bar
                  key={techName}
                  dataKey={techName}
                  stackId="tech"
                  fill={TECH_COLORS[i % TECH_COLORS.length]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
