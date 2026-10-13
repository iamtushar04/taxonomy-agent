/**
 * AnalyticsDashboard.jsx
 *
 * Main analytics panel — fetches patent metadata from /api/analytics/{run_id}
 * and renders the AssigneeFilingChart + PatentTaxonomyTable side by side.
 *
 * Props:
 *   - runId        (string)  — the current session run ID
 *   - taxonomy     (array)   — already-loaded taxonomy from the graph view
 *   - isPubmed     (boolean) — if true, show "not available" message
 */

import React, { useEffect, useState } from 'react';
import axiosClient from '../api/axiosClient';
import AssigneeFilingChart from './AssigneeFilingChart';
import TechnologyTrendChart from './TechnologyTrendChart';
import AssigneeTechHeatmap from './AssigneeTechHeatmap';
import PatentTaxonomyTable from './PatentTaxonomyTable';
import AssigneeTaxonomyMatrix from './AssigneeTaxonomyMatrix';

const PANEL_STYLE = {
  background: '#0f172a',
  border: '1px solid #1e293b',
  borderRadius: 12,
  padding: '20px 24px',
};

const SECTION_TITLE = {
  fontSize: 15,
  fontWeight: 700,
  color: '#e2e8f0',
  marginBottom: 14,
  display: 'flex',
  alignItems: 'center',
  gap: 8,
};

export default function AnalyticsDashboard({ runId, taxonomy, isPubmed }) {
  const [patents, setPatents] = useState(null); // null = loading, [] = empty, [...] = loaded
  const [error, setError] = useState(null);
  const [selectedAssignee, setSelectedAssignee] = useState(null);
  const [selectedTechNode, setSelectedTechNode] = useState(null);

  useEffect(() => {
    if (!runId || isPubmed) return;
    setPatents(null);
    setError(null);
    setSelectedAssignee(null);
    setSelectedTechNode(null);

    axiosClient.get(`/api/analytics/${runId}`)
      .then(res => setPatents(res.data.patents || []))
      .catch(err => {
        const msg = err.response?.data?.detail || 'Failed to load analytics data.';
        setError(msg);
      });
  }, [runId, isPubmed]);

  // ── Guard: PubMed run ─────────────────────────────────────────────────────
  if (isPubmed) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#64748b', flexDirection: 'column', gap: 12 }}>
        <span style={{ fontSize: 36 }}>📡</span>
        <p style={{ margin: 0, fontSize: 14 }}>Analytics are only available for patent sessions, not PubMed.</p>
      </div>
    );
  }

  // ── Guard: no session selected ────────────────────────────────────────────
  if (!runId) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#64748b', flexDirection: 'column', gap: 12 }}>
        <span style={{ fontSize: 36 }}>📊</span>
        <p style={{ margin: 0, fontSize: 14 }}>Select or run a session to see analytics.</p>
      </div>
    );
  }

  // ── Guard: loading ────────────────────────────────────────────────────────
  if (patents === null && !error) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#64748b', flexDirection: 'column', gap: 14 }}>
        <div className="spinner" style={{ width: 32, height: 32, border: '3px solid #334155', borderTop: '3px solid #6366f1', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
        <p style={{ margin: 0, fontSize: 14 }}>Loading analytics…</p>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  // ── Guard: error ──────────────────────────────────────────────────────────
  if (error) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#f87171', flexDirection: 'column', gap: 12 }}>
        <span style={{ fontSize: 36 }}>⚠️</span>
        <p style={{ margin: 0, fontSize: 14 }}>{error}</p>
      </div>
    );
  }

  // ── Summary stats ─────────────────────────────────────────────────────────
  const uniqueAssignees = new Set(patents.map(p => p.assignee).filter(Boolean)).size;
  const withDates = patents.filter(p => p.filing_date).length;

  return (
    <div style={{ padding: '20px 24px', overflowY: 'auto', minHeight: '100%', boxSizing: 'border-box' }}>

      {/* ── KPI strip ─────────────────────────────────────────────────── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: 16,
        marginBottom: 20,
      }}>
        {[
          { label: 'Total Patents', value: patents.length, icon: '📄' },
          { label: 'Unique Assignees', value: uniqueAssignees, icon: '🏢' },
          { label: 'Taxonomy Nodes', value: taxonomy.length, icon: '🌿' },
          { label: 'With Filing Date', value: withDates, icon: '📅' },
        ].map(({ label, value, icon }) => (
          <div key={label} style={{
            ...PANEL_STYLE,
            textAlign: 'center',
            padding: '14px 18px',
          }}>
            <div style={{ fontSize: 22 }}>{icon}</div>
            <div style={{ fontSize: 24, fontWeight: 800, color: '#6366f1', marginTop: 4 }}>{value}</div>
            <div style={{ fontSize: 11, color: '#64748b', marginTop: 2, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
          </div>
        ))}
      </div>

      {/* Active Filter Pill Bar (if any selection is active) */}
      {(selectedAssignee || selectedTechNode) && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          background: '#1e1b4b',
          border: '1px solid #4338ca',
          borderRadius: 8,
          padding: '10px 16px',
          marginBottom: 20,
        }}>
          <span style={{ fontSize: 13, color: '#c7d2fe', fontWeight: 600 }}>Active Filters:</span>
          {selectedAssignee && (
            <span style={{ background: '#6366f1', color: '#fff', padding: '3px 10px', borderRadius: 99, fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
              🏢 {selectedAssignee}
              <button
                onClick={() => setSelectedAssignee(null)}
                style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer', padding: 0 }}
              >✕</button>
            </span>
          )}
          {selectedTechNode && (
            <span style={{ background: '#0284c7', color: '#fff', padding: '3px 10px', borderRadius: 99, fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
              🔬 {selectedTechNode}
              <button
                onClick={() => setSelectedTechNode(null)}
                style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer', padding: 0 }}
              >✕</button>
            </span>
          )}
          <button
            onClick={() => { setSelectedAssignee(null); setSelectedTechNode(null); }}
            style={{
              marginLeft: 'auto',
              background: '#312e81',
              color: '#e0e7ff',
              border: 'none',
              borderRadius: 6,
              padding: '4px 10px',
              fontSize: 12,
              cursor: 'pointer',
            }}
          >
            Clear All ✕
          </button>
        </div>
      )}

      {/* ── 1. Assignee Filing Activity by Year (Filing Velocity) ─────── */}
      <div style={{ ...PANEL_STYLE, marginBottom: 20 }}>
        <div style={SECTION_TITLE}>
          <span>📊</span> Assignee Filing Activity by Year (Filing Velocity)
        </div>
        <AssigneeFilingChart patents={patents} />
      </div>

      {/* ── 2. Technology Growth by Year (Lifecycle Trends) ───────────── */}
      <div style={{ ...PANEL_STYLE, marginBottom: 20 }}>
        <div style={SECTION_TITLE}>
          <span>📈</span> Technology Growth by Year (R&D Evolution)
        </div>
        <TechnologyTrendChart
          patents={patents}
          taxonomy={taxonomy}
          onSelectTechNode={setSelectedTechNode}
        />
      </div>

      {/* ── 3. Competitive Battlefield (Assignee × Technology Heatmap) ── */}
      <div style={{ ...PANEL_STYLE, marginBottom: 20 }}>
        <div style={SECTION_TITLE}>
          <span>⚔️</span> Competitive Positioning Matrix (Assignee × Technology)
        </div>
        <AssigneeTechHeatmap
          patents={patents}
          taxonomy={taxonomy}
          selectedAssignee={selectedAssignee}
          selectedTechNode={selectedTechNode}
          onSelectCell={(a, t) => {
            setSelectedAssignee(a);
            setSelectedTechNode(t);
          }}
        />
      </div>

      {/* ── 4. Assignee Taxonomy Footprint Cards ───────────────────────── */}
      <div style={{ ...PANEL_STYLE, marginBottom: 20 }}>
        <div style={SECTION_TITLE}>
          <span>🏢</span> Assignee Taxonomy Footprints & Active Years
        </div>
        <AssigneeTaxonomyMatrix
          patents={patents}
          taxonomy={taxonomy}
          selectedAssignee={selectedAssignee}
          onSelectAssignee={setSelectedAssignee}
        />
      </div>

      {/* ── 5. Multi-Dimensional Patent Drill-Down Table ───────────────── */}
      <div style={{ ...PANEL_STYLE }}>
        <div style={SECTION_TITLE}>
          <span>🗂️</span> Patent Drill-Down Explorer
        </div>
        <PatentTaxonomyTable
          patents={patents}
          taxonomy={taxonomy}
          selectedAssignee={selectedAssignee}
          onSelectAssignee={setSelectedAssignee}
          selectedTechNode={selectedTechNode}
          onSelectTechNode={setSelectedTechNode}
        />
      </div>

    </div>
  );
}
