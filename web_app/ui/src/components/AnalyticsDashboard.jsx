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

  useEffect(() => {
    if (!runId || isPubmed) return;
    setPatents(null);
    setError(null);
    setSelectedAssignee(null);

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
      <div style={{ display: 'flex', gap: 16, marginBottom: 20, flexWrap: 'wrap' }}>
        {[
          { label: 'Total Patents', value: patents.length, icon: '📄' },
          { label: 'Unique Assignees', value: uniqueAssignees, icon: '🏢' },
          { label: 'Taxonomy Nodes', value: taxonomy.length, icon: '🌿' },
          { label: 'With Filing Date', value: withDates, icon: '📅' },
        ].map(({ label, value, icon }) => (
          <div key={label} style={{
            ...PANEL_STYLE,
            flex: '1 1 120px',
            textAlign: 'center',
            padding: '14px 18px',
          }}>
            <div style={{ fontSize: 22 }}>{icon}</div>
            <div style={{ fontSize: 24, fontWeight: 800, color: '#6366f1', marginTop: 4 }}>{value}</div>
            <div style={{ fontSize: 11, color: '#64748b', marginTop: 2, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
          </div>
        ))}
      </div>

      {/* ── Assignee vs Filing Date Chart ─────────────────────────────── */}
      <div style={{ ...PANEL_STYLE, marginBottom: 20 }}>
        <div style={SECTION_TITLE}>
          <span>📊</span> Assignee Filing Activity by Year
        </div>
        <AssigneeFilingChart patents={patents} />
      </div>

      {/* ── Assignee → Taxonomy Matrix / Footprint ────────────────────── */}
      <div style={{ ...PANEL_STYLE, marginBottom: 20 }}>
        <div style={SECTION_TITLE}>
          <span>🏢</span> Assignee Taxonomy Footprint
        </div>
        <AssigneeTaxonomyMatrix
          patents={patents}
          taxonomy={taxonomy}
          selectedAssignee={selectedAssignee}
          onSelectAssignee={setSelectedAssignee}
        />
      </div>

      {/* ── Patent ↔ Taxonomy Table ───────────────────────────────────── */}
      <div style={{ ...PANEL_STYLE }}>
        <div style={SECTION_TITLE}>
          <span>🗂️</span> Patent → Taxonomy Mapping
        </div>
        <PatentTaxonomyTable
          patents={patents}
          taxonomy={taxonomy}
          selectedAssignee={selectedAssignee}
          onSelectAssignee={setSelectedAssignee}
        />
      </div>

    </div>
  );
}
