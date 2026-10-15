/**
 * ProductPatentCoverageTable.jsx
 *
 * Commercialization Matrix & IP Coverage:
 * - Maps commercial products (datasheets, product ranges) directly to protecting patents
 * - Displays IP protection status (Protected vs Unprotected gaps)
 * - Highlights implemented taxonomy technology branches
 * - Provides interactive modals for Technical Specs, Patent Abstract/Claims, and Feature Overlap
 */

import React, { useMemo, useState } from 'react';
import axiosClient from '../api/axiosClient';

const TH_STYLE = {
  padding: '12px 16px',
  background: '#090d16',
  color: '#34d399',
  fontSize: 12,
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  textAlign: 'left',
  borderBottom: '2px solid #1e293b'
};

const TD_STYLE = {
  padding: '14px 16px',
  borderBottom: '1px solid #1e293b',
  color: '#e2e8f0',
  fontSize: 13,
  verticalAlign: 'top',
};

export default function ProductPatentCoverageTable({ products = [], taxonomy = [], patents = [] }) {
  const [search, setSearch] = useState('');
  const [filterMode, setFilterMode] = useState('all'); // 'all' | 'protected' | 'unprotected'
  const [selectedPatentModal, setSelectedPatentModal] = useState(null);
  const [selectedProductModal, setSelectedProductModal] = useState(null);
  const [selectedOverlapModal, setSelectedOverlapModal] = useState(null);
  const [isExporting, setIsExporting] = useState(false);

  // Quick lookup map for patent details
  const patentLookup = useMemo(() => {
    const map = {};
    patents.forEach(p => { map[p.patent_id] = p; });
    return map;
  }, [patents]);

  // Smart Brand/Manufacturer resolver to avoid "Unknown"
  const resolveBrand = (product, patentIds) => {
    if (product.brand_or_assignee && product.brand_or_assignee !== 'Unknown' && product.brand_or_assignee !== 'Unknown Vendor') {
      return product.brand_or_assignee;
    }
    const nameAndFile = `${product.product_name} ${product.source_filename}`.toLowerCase();
    if (nameAndFile.includes('totalenergies') || nameAndFile.includes('total energies')) return 'TotalEnergies';
    if (nameAndFile.includes('basf')) return 'BASF';
    if (nameAndFile.includes('dow')) return 'Dow Chemical';
    if (nameAndFile.includes('exxon')) return 'ExxonMobil';
    if (nameAndFile.includes('sabic')) return 'SABIC';
    if (nameAndFile.includes('lyondell')) return 'LyondellBasell';
    if (nameAndFile.includes('lumicene')) return 'TotalEnergies';

    const assignees = new Set();
    patentIds.forEach(pid => {
      const pat = patentLookup[pid];
      if (pat && pat.assignee && pat.assignee !== 'Unknown') assignees.add(pat.assignee);
    });
    if (assignees.size > 0) {
      return Array.from(assignees).join(', ');
    }
    return 'TotalEnergies';
  };

  // 1. Build map: product_id -> { mappedNodes: [...], protectingPatentIds: Set(...) }
  const productMapping = useMemo(() => {
    const map = {};
    products.forEach(p => {
      map[p.product_id] = {
        product: p,
        nodes: [],
        patentIds: new Set(),
      };
    });

    taxonomy.forEach(node => {
      const pids = node.supporting_product_ids || [];
      const patentsOnNode = node.supporting_patent_ids || [];

      pids.forEach(prodId => {
        if (map[prodId]) {
          // Deduplicate nodes
          if (!map[prodId].nodes.includes(node.name)) {
            map[prodId].nodes.push(node.name);
          }
          patentsOnNode.forEach(patId => map[prodId].patentIds.add(patId));
        }
      });
    });

    return Object.values(map);
  }, [products, taxonomy]);

  // Overall Coverage KPIs
  const totalProducts = productMapping.length;
  const protectedProducts = productMapping.filter(m => m.patentIds.size > 0).length;
  const unprotectedProducts = totalProducts - protectedProducts;
  const totalLinkedPatents = useMemo(() => {
    const set = new Set();
    productMapping.forEach(m => m.patentIds.forEach(pid => set.add(pid)));
    return set.size;
  }, [productMapping]);

  const filtered = useMemo(() => {
    return productMapping.filter(item => {
      const isProtected = item.patentIds.size > 0;
      if (filterMode === 'protected' && !isProtected) return false;
      if (filterMode === 'unprotected' && isProtected) return false;

      if (!search.trim()) return true;
      const q = search.toLowerCase();
      const brand = resolveBrand(item.product, item.patentIds).toLowerCase();
      return (
        item.product.product_name.toLowerCase().includes(q) ||
        brand.includes(q) ||
        (item.product.source_filename || '').toLowerCase().includes(q) ||
        item.nodes.some(n => n.toLowerCase().includes(q)) ||
        Array.from(item.patentIds).some(pid => pid.toLowerCase().includes(q))
      );
    });
  }, [productMapping, search, filterMode]);

  const handleExport = async (format = 'excel') => {
    setIsExporting(true);
    try {
      const mappingRows = productMapping.map(m => {
        const brand = resolveBrand(m.product, m.patentIds);
        const pats = Array.from(m.patentIds).join(', ') || 'None';
        const nodesStr = m.nodes.join(', ') || 'General';
        const feats = (m.product.features || []).slice(0, 5).join('; ') || 'N/A';
        return [
          m.product.product_name,
          brand,
          m.patentIds.size > 0 ? `Protected (${m.patentIds.size} Patents)` : 'Unprotected Gap',
          pats,
          feats,
          nodesStr
        ];
      });

      const tables = [{
        sheet_title: "Commercialization Matrix",
        columns: [
          "Commercial Product",
          "Manufacturer / Brand",
          "IP Protection Status",
          "Protecting Patents",
          "Key Technical Features & Specs",
          "Mapped Taxonomy Branches"
        ],
        rows: mappingRows
      }];

      const res = await axiosClient.post('/api/export/generate', {
        title: "Product_Patent_Commercialization_Matrix",
        format: format,
        summary: `Cross-reference of ${totalProducts} commercial product lines against patent protection coverage and taxonomy domains.`,
        tables: tables
      });

      if (res.data && res.data.download_url) {
        const baseUrl = window.APP_CONFIG?.API_BASE_URL || 'http://localhost:8652';
        const fullUrl = `${baseUrl}${res.data.download_url}`;
        window.open(fullUrl, '_blank');
      }
    } catch (err) {
      console.error("Export error:", err);
      alert("Failed to generate export file. Please try again.");
    } finally {
      setIsExporting(false);
    }
  };

  if (products.length === 0) {
    return (
      <div style={{
        background: '#090d16',
        borderRadius: 12,
        border: '1px dashed #334155',
        color: '#94a3b8',
        textAlign: 'center',
        padding: 36,
        fontSize: 14
      }}>
        <div style={{ fontSize: 24, marginBottom: 8 }}>📦</div>
        <div style={{ fontWeight: 600, color: '#f1f5f9', marginBottom: 4 }}>No Commercial Products Uploaded</div>
        <div>Upload product datasheets or product portfolio documents to map patents directly against commercial product lines.</div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* ── Explanation & Context Card ──── */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(14, 165, 233, 0.05) 100%)',
        border: '1px solid rgba(16, 185, 129, 0.25)',
        borderRadius: 10,
        padding: '12px 18px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 12
      }}>
        <div style={{ maxWidth: 680 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#34d399', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
            <span>💡</span> Purpose & Commercial Intelligence
          </div>
          <div style={{ fontSize: 12, color: '#cbd5e1', lineHeight: 1.5 }}>
            This matrix matches your <strong>commercial product datasheets</strong> with <strong>patents</strong> across the taxonomy tree. It identifies which competitive patents protect your product lines, flags unprotected commercial gaps, and exposes overlapping technical claims.
          </div>
        </div>

        {/* Top KPI Badges */}
        <div style={{ display: 'flex', gap: 10 }}>
          <div style={{
            background: '#090d16',
            border: '1px solid #1e293b',
            borderRadius: 8,
            padding: '6px 12px',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: 10, color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Products</div>
            <div style={{ fontSize: 15, fontWeight: 800, color: '#f8fafc' }}>{totalProducts}</div>
          </div>
          <div style={{
            background: '#064e3b',
            border: '1px solid #059669',
            borderRadius: 8,
            padding: '6px 12px',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: 10, color: '#a7f3d0', textTransform: 'uppercase', fontWeight: 600 }}>IP Protected</div>
            <div style={{ fontSize: 15, fontWeight: 800, color: '#6ee7b7' }}>{protectedProducts} / {totalProducts}</div>
          </div>
          <div style={{
            background: '#1e1b4b',
            border: '1px solid #4338ca',
            borderRadius: 8,
            padding: '6px 12px',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: 10, color: '#c7d2fe', textTransform: 'uppercase', fontWeight: 600 }}>Protecting Patents</div>
            <div style={{ fontSize: 15, fontWeight: 800, color: '#a5b4fc' }}>{totalLinkedPatents}</div>
          </div>
        </div>
      </div>

      {/* ── Search & Filter Controls ──── */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 260 }}>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="🔍  Search product name, manufacturer, patent ID (e.g. EP2360192A1), or taxonomy branch..."
            style={{
              width: '100%',
              padding: '9px 14px',
              borderRadius: 8,
              border: '1px solid #334155',
              background: '#0f172a',
              color: '#f1f5f9',
              fontSize: 13,
              outline: 'none',
              boxSizing: 'border-box'
            }}
          />
        </div>

        {/* Filter Pills */}
        <div style={{ display: 'flex', gap: 6 }}>
          {[
            { id: 'all', label: `All (${totalProducts})` },
            { id: 'protected', label: `🛡️ Protected (${protectedProducts})` },
            { id: 'unprotected', label: `⚠️ Unprotected (${unprotectedProducts})` }
          ].map(btn => (
            <button
              key={btn.id}
              onClick={() => setFilterMode(btn.id)}
              style={{
                background: filterMode === btn.id ? '#0284c7' : '#1e293b',
                color: filterMode === btn.id ? '#ffffff' : '#94a3b8',
                border: filterMode === btn.id ? '1px solid #38bdf8' : '1px solid #334155',
                padding: '6px 12px',
                borderRadius: 20,
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              {btn.label}
            </button>
          ))}
        </div>

        {/* Direct Export Buttons */}
        <div style={{ display: 'flex', gap: 6, marginLeft: 'auto' }}>
          <button
            onClick={() => handleExport('excel')}
            disabled={isExporting}
            style={{
              background: '#064e3b',
              color: '#a7f3d0',
              border: '1px solid #059669',
              padding: '6px 12px',
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 600,
              cursor: isExporting ? 'wait' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              opacity: isExporting ? 0.7 : 1,
              transition: 'all 0.15s ease'
            }}
          >
            <span>📊</span> {isExporting ? 'Exporting...' : 'Export Sheet (.xlsx)'}
          </button>
          <button
            onClick={() => handleExport('pdf')}
            disabled={isExporting}
            style={{
              background: '#881337',
              color: '#fecdd3',
              border: '1px solid #e11d48',
              padding: '6px 12px',
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 600,
              cursor: isExporting ? 'wait' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              opacity: isExporting ? 0.7 : 1,
              transition: 'all 0.15s ease'
            }}
          >
            <span>📄</span> {isExporting ? 'Exporting...' : 'Export PDF'}
          </button>
        </div>
      </div>

      {/* ── Table Container ──── */}
      <div style={{
        background: '#0f172a',
        borderRadius: 10,
        border: '1px solid #1e293b',
        overflowX: 'auto',
        boxShadow: '0 4px 16px rgba(0,0,0,0.2)'
      }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 850 }}>
          <thead>
            <tr>
              <th style={{ ...TH_STYLE, width: 240 }}>Commercial Product</th>
              <th style={{ ...TH_STYLE, width: 140 }}>Manufacturer / Brand</th>
              <th style={{ ...TH_STYLE, width: 130 }}>IP Coverage Status</th>
              <th style={{ ...TH_STYLE, minWidth: 200 }}>Protecting Patents</th>
              <th style={{ ...TH_STYLE, minWidth: 210 }}>Mapped Taxonomy Branches</th>
              <th style={{ ...TH_STYLE, width: 130, textAlign: 'center' }}>Analysis</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ ...TD_STYLE, textAlign: 'center', color: '#64748b', padding: 32 }}>
                  No matching commercial products found for the current search filter.
                </td>
              </tr>
            ) : (
              filtered.map(({ product, nodes, patentIds }) => {
                const patentCount = patentIds.size;
                const isProtected = patentCount > 0;
                const brand = resolveBrand(product, patentIds);

                return (
                  <tr
                    key={product.product_id}
                    style={{ transition: 'background 0.15s ease' }}
                    onMouseEnter={e => e.currentTarget.style.background = '#1e293b'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  >
                    {/* Column 1: Commercial Product Details */}
                    <td style={{ ...TD_STYLE }}>
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                        <span style={{ fontSize: 16, marginTop: 1 }}>📦</span>
                        <div>
                          <div style={{ fontWeight: 700, color: '#f8fafc', fontSize: 13, lineHeight: 1.35 }}>
                            {product.product_name}
                          </div>
                          {product.category && product.category !== 'General' && (
                            <span style={{
                              display: 'inline-block',
                              marginTop: 4,
                              background: '#1e293b',
                              border: '1px solid #334155',
                              color: '#38bdf8',
                              fontSize: 10,
                              fontWeight: 600,
                              padding: '1px 6px',
                              borderRadius: 4
                            }}>
                              {product.category}
                            </span>
                          )}
                          {product.source_filename && (
                            <div style={{ fontSize: 11, color: '#64748b', marginTop: 4, fontFamily: 'monospace' }}>
                              📄 {product.source_filename}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>

                    {/* Column 2: Brand / Manufacturer */}
                    <td style={{ ...TD_STYLE }}>
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 5,
                        background: '#1e293b',
                        border: '1px solid #334155',
                        color: '#e2e8f0',
                        fontSize: 12,
                        fontWeight: 600,
                        padding: '3px 8px',
                        borderRadius: 6
                      }}>
                        🏢 {brand}
                      </span>
                    </td>

                    {/* Column 3: IP Coverage Status */}
                    <td style={{ ...TD_STYLE }}>
                      {isProtected ? (
                        <span style={{
                          background: 'rgba(5, 150, 105, 0.15)',
                          border: '1px solid #059669',
                          color: '#6ee7b7',
                          padding: '4px 9px',
                          borderRadius: 20,
                          fontSize: 11,
                          fontWeight: 700,
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 5
                        }}>
                          🛡️ {patentCount} Patent{patentCount > 1 ? 's' : ''}
                        </span>
                      ) : (
                        <span style={{
                          background: 'rgba(239, 68, 68, 0.15)',
                          border: '1px solid #b91c1c',
                          color: '#fca5a5',
                          padding: '4px 9px',
                          borderRadius: 20,
                          fontSize: 11,
                          fontWeight: 700,
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 5
                        }}>
                          ⚠️ Unprotected IP Gap
                        </span>
                      )}
                    </td>

                    {/* Column 4: Protecting Patents (Clickable) */}
                    <td style={{ ...TD_STYLE }}>
                      {patentCount === 0 ? (
                        <span style={{ color: '#94a3b8', fontSize: 12, fontStyle: 'italic' }}>
                          No overlapping patents identified in current portfolio.
                        </span>
                      ) : (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                          {Array.from(patentIds).map(pid => {
                            const pData = patentLookup[pid] || { patent_id: pid, title: 'Patent Details' };
                            const year = pData.filing_date ? String(pData.filing_date).slice(0, 4) : '';
                            return (
                              <button
                                key={pid}
                                onClick={() => setSelectedPatentModal(pData)}
                                title={`Click to view abstract & claims for ${pid} (${pData.title || 'Patent'})`}
                                style={{
                                  fontFamily: 'monospace',
                                  background: '#1e1b4b',
                                  color: '#c7d2fe',
                                  border: '1px solid #4338ca',
                                  padding: '3px 8px',
                                  borderRadius: 5,
                                  fontSize: 11,
                                  fontWeight: 600,
                                  cursor: 'pointer',
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: 4,
                                  transition: 'all 0.15s ease'
                                }}
                                onMouseEnter={e => { e.currentTarget.style.background = '#4338ca'; e.currentTarget.style.color = '#fff'; }}
                                onMouseLeave={e => { e.currentTarget.style.background = '#1e1b4b'; e.currentTarget.style.color = '#c7d2fe'; }}
                              >
                                <span>📄</span>
                                <span>{pid}</span>
                                {year && <span style={{ opacity: 0.7, fontSize: 10 }}>({year})</span>}
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </td>

                    {/* Column 5: Mapped Taxonomy Branches */}
                    <td style={{ ...TD_STYLE }}>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                        {nodes.length === 0 ? (
                          <span style={{ color: '#64748b', fontSize: 12 }}>No explicit taxonomy branch mapped</span>
                        ) : (
                          nodes.map((nName, i) => (
                            <span
                              key={i}
                              style={{
                                background: '#064e3b',
                                border: '1px solid #047857',
                                color: '#a7f3d0',
                                padding: '2px 8px',
                                borderRadius: 12,
                                fontSize: 11,
                                fontWeight: 500,
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 4
                              }}
                            >
                              <span>🌿</span>
                              <span>{nName}</span>
                            </span>
                          ))
                        )}
                      </div>
                    </td>

                    {/* Column 6: Actions / Feature Overlap Drill-down */}
                    <td style={{ ...TD_STYLE, textAlign: 'center' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'center' }}>
                        <button
                          onClick={() => setSelectedOverlapModal({ product, nodes, patentIds })}
                          title="Compare product technical features against protecting patent claims"
                          style={{
                            background: '#0369a1',
                            color: '#ffffff',
                            border: '1px solid #0284c7',
                            padding: '4px 10px',
                            borderRadius: 6,
                            fontSize: 11,
                            fontWeight: 600,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 4,
                            whiteSpace: 'nowrap',
                            transition: 'background 0.15s ease'
                          }}
                          onMouseEnter={e => e.currentTarget.style.background = '#0284c7'}
                          onMouseLeave={e => e.currentTarget.style.background = '#0369a1'}
                        >
                          <span>⚡</span> Overlap Specs
                        </button>
                        <button
                          onClick={() => setSelectedProductModal(product)}
                          title="Inspect full product specs & engineering attributes"
                          style={{
                            background: '#1e293b',
                            color: '#94a3b8',
                            border: '1px solid #334155',
                            padding: '3px 8px',
                            borderRadius: 6,
                            fontSize: 10,
                            cursor: 'pointer',
                            whiteSpace: 'nowrap'
                          }}
                          onMouseEnter={e => { e.currentTarget.style.color = '#38bdf8'; e.currentTarget.style.borderColor = '#0284c7'; }}
                          onMouseLeave={e => { e.currentTarget.style.color = '#94a3b8'; e.currentTarget.style.borderColor = '#334155'; }}
                        >
                          Specs ({product.features?.length || 0})
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* ── Modal 1: Feature Overlap & Patent Mapping Drill-down ──── */}
      {selectedOverlapModal && (
        <div
          style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(0, 0, 0, 0.75)', zIndex: 9999,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 20, backdropFilter: 'blur(4px)'
          }}
          onClick={() => setSelectedOverlapModal(null)}
        >
          <div
            style={{
              background: '#0f172a', border: '1px solid #334155', borderRadius: 16,
              maxWidth: 820, width: '100%', maxHeight: '88vh', overflowY: 'auto',
              padding: 24, boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)', color: '#f8fafc'
            }}
            onClick={e => e.stopPropagation()}
          >
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid #334155', paddingBottom: 16, marginBottom: 16 }}>
              <div>
                <span style={{ background: '#0369a1', color: '#e0f2fe', padding: '3px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, textTransform: 'uppercase' }}>
                  ⚡ Commercial Overlap Analysis
                </span>
                <h3 style={{ fontSize: 18, fontWeight: 700, marginTop: 8, marginBottom: 4, color: '#f1f5f9' }}>
                  📦 {selectedOverlapModal.product.product_name}
                </h3>
                <div style={{ fontSize: 12, color: '#94a3b8' }}>
                  Brand: <strong style={{ color: '#38bdf8' }}>{resolveBrand(selectedOverlapModal.product, selectedOverlapModal.patentIds)}</strong> • Covered by {selectedOverlapModal.patentIds.size} competitive patents
                </div>
              </div>
              <button
                onClick={() => setSelectedOverlapModal(null)}
                style={{
                  background: '#1e293b', border: '1px solid #475569', color: '#cbd5e1',
                  borderRadius: 8, padding: '6px 12px', cursor: 'pointer', fontSize: 14, fontWeight: 'bold'
                }}
              >
                ✕ Close
              </button>
            </div>

            {/* Split Grid: Product Specs vs Protecting Patent Claims */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 16, marginBottom: 16 }}>
              {/* Left Column: Product Technical Features */}
              <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 10, padding: 14 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#38bdf8', textTransform: 'uppercase', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span>📦</span> Product Technical Specifications
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {(!selectedOverlapModal.product.features || selectedOverlapModal.product.features.length === 0) ? (
                    <div style={{ color: '#94a3b8', fontSize: 12, fontStyle: 'italic' }}>
                      No granular features extracted from product document.
                    </div>
                  ) : (
                    selectedOverlapModal.product.features.map((feat, idx) => (
                      <div key={idx} style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 6, padding: '8px 10px', fontSize: 12, color: '#e2e8f0', display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                        <span style={{ color: '#10b981', fontWeight: 'bold' }}>✓</span>
                        <span>{feat}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Right Column: Protecting Patents & Claims Scope */}
              <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 10, padding: 14 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#a5b4fc', textTransform: 'uppercase', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span>🛡️</span> Protecting Patent Portfolio ({selectedOverlapModal.patentIds.size})
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {Array.from(selectedOverlapModal.patentIds).map(pid => {
                    const pat = patentLookup[pid] || { patent_id: pid };
                    return (
                      <div key={pid} style={{ background: '#0f172a', border: '1px solid #312e81', borderRadius: 6, padding: '8px 10px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                          <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#c7d2fe', fontSize: 12 }}>
                            📄 {pid}
                          </span>
                          <span style={{ fontSize: 11, color: '#94a3b8' }}>
                            {pat.filing_date ? `Filed ${String(pat.filing_date).slice(0, 10)}` : 'Patent Document'}
                          </span>
                        </div>
                        <div style={{ fontSize: 11, color: '#cbd5e1', lineHeight: 1.4 }}>
                          {pat.title || 'Technical Invention'}
                        </div>
                        {pat.summary && (
                          <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4, fontStyle: 'italic', background: '#1e1b4b', padding: '4px 6px', borderRadius: 4 }}>
                            {pat.summary.slice(0, 150)}...
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Bottom: Taxonomy Technical Grounding */}
            <div style={{ background: 'rgba(6, 78, 59, 0.2)', border: '1px solid #047857', borderRadius: 10, padding: 12 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#6ee7b7', textTransform: 'uppercase', marginBottom: 6 }}>
                🌿 Taxonomy Grounding & Functional Classification
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {selectedOverlapModal.nodes.map((n, i) => (
                  <span key={i} style={{ background: '#064e3b', color: '#a7f3d0', padding: '3px 10px', borderRadius: 12, fontSize: 11, fontWeight: 500 }}>
                    {n}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal 2: Product Technical Features Only ──── */}
      {selectedProductModal && (
        <div
          style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(0, 0, 0, 0.75)', zIndex: 9999,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 20, backdropFilter: 'blur(4px)'
          }}
          onClick={() => setSelectedProductModal(null)}
        >
          <div
            style={{
              background: '#0f172a', border: '1px solid #334155', borderRadius: 16,
              maxWidth: 700, width: '100%', maxHeight: '85vh', overflowY: 'auto',
              padding: 24, boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)', color: '#f8fafc'
            }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid #334155', paddingBottom: 16, marginBottom: 16 }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ background: '#065f46', color: '#6ee7b7', padding: '3px 8px', borderRadius: 6, fontSize: 12, fontWeight: 700 }}>
                    Commercial Product
                  </span>
                  <span style={{ fontSize: 12, color: '#94a3b8' }}>
                    {selectedProductModal.source_filename}
                  </span>
                </div>
                <h3 style={{ fontSize: 18, fontWeight: 700, marginTop: 10, marginBottom: 4, color: '#f1f5f9' }}>
                  📦 {selectedProductModal.product_name}
                </h3>
                <div style={{ fontSize: 13, color: '#38bdf8' }}>
                  Brand / Vendor: {resolveBrand(selectedProductModal, [])} • Category: {selectedProductModal.category || 'General'}
                </div>
              </div>
              <button
                onClick={() => setSelectedProductModal(null)}
                style={{
                  background: '#1e293b', border: '1px solid #475569', color: '#cbd5e1',
                  borderRadius: 8, padding: '6px 12px', cursor: 'pointer', fontSize: 14, fontWeight: 'bold'
                }}
              >
                ✕ Close
              </button>
            </div>

            {/* Extracted Features List */}
            <div style={{ marginBottom: 18 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#38bdf8', textTransform: 'uppercase', marginBottom: 8 }}>
                Extracted Engineering Features & Specs ({selectedProductModal.features?.length || 0})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {(!selectedProductModal.features || selectedProductModal.features.length === 0) ? (
                  <div style={{ color: '#64748b', fontSize: 13 }}>No explicit features extracted.</div>
                ) : (
                  selectedProductModal.features.map((feat, idx) => (
                    <div key={idx} style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#e2e8f0', display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                      <span style={{ color: '#10b981', fontWeight: 'bold' }}>✓</span>
                      <span>{feat}</span>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Raw Excerpt */}
            {selectedProductModal.full_text_snippet && (
              <div style={{ marginTop: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginBottom: 8 }}>
                  Raw Document Excerpt
                </div>
                <div style={{
                  background: '#090d16', padding: 14, borderRadius: 10,
                  border: '1px solid #1e293b', fontSize: 12, color: '#94a3b8',
                  lineHeight: 1.6, maxHeight: 200, overflowY: 'auto', whiteSpace: 'pre-wrap', fontFamily: 'monospace'
                }}>
                  {selectedProductModal.full_text_snippet}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Modal 3: Patent Detail View ──── */}
      {selectedPatentModal && (
        <div
          style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(0, 0, 0, 0.75)', zIndex: 9999,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 20, backdropFilter: 'blur(4px)'
          }}
          onClick={() => setSelectedPatentModal(null)}
        >
          <div
            style={{
              background: '#0f172a', border: '1px solid #334155', borderRadius: 16,
              maxWidth: 720, width: '100%', maxHeight: '85vh', overflowY: 'auto',
              padding: 24, boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)', color: '#f8fafc'
            }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid #334155', paddingBottom: 16, marginBottom: 16 }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ background: '#312e81', color: '#a5b4fc', padding: '3px 8px', borderRadius: 6, fontSize: 13, fontFamily: 'monospace', fontWeight: 700 }}>
                    {selectedPatentModal.patent_id}
                  </span>
                  <span style={{ fontSize: 12, color: '#94a3b8' }}>
                    Filed: {selectedPatentModal.filing_date ? String(selectedPatentModal.filing_date).slice(0, 10) : 'N/A'}
                  </span>
                </div>
                <h3 style={{ fontSize: 17, fontWeight: 700, marginTop: 10, marginBottom: 4, color: '#f1f5f9', lineHeight: 1.4 }}>
                  {selectedPatentModal.title || 'Patent Specification'}
                </h3>
                <div style={{ fontSize: 13, color: '#38bdf8' }}>
                  Assignee: {selectedPatentModal.assignee || 'Unknown'}
                </div>
              </div>
              <button
                onClick={() => setSelectedPatentModal(null)}
                style={{
                  background: '#1e293b', border: '1px solid #475569', color: '#cbd5e1',
                  borderRadius: 8, padding: '6px 12px', cursor: 'pointer', fontSize: 14, fontWeight: 'bold'
                }}
              >
                ✕ Close
              </button>
            </div>

            {/* AI Summary / Abstract */}
            {selectedPatentModal.summary && (
              <div style={{ marginBottom: 18, background: '#1e293b', padding: 14, borderRadius: 10, border: '1px solid #334155' }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#38bdf8', marginBottom: 6 }}>
                  ✨ Patent Abstract & Technical Summary
                </div>
                <div style={{ fontSize: 13, color: '#cbd5e1', lineHeight: 1.5 }}>
                  {selectedPatentModal.summary}
                </div>
              </div>
            )}

            {/* Full Text / Claims Snippet */}
            {selectedPatentModal.full_text && (
              <div style={{ marginTop: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginBottom: 8 }}>
                  Claims & Description Preview
                </div>
                <div style={{
                  background: '#090d16', padding: 14, borderRadius: 10,
                  border: '1px solid #1e293b', fontSize: 12, color: '#94a3b8',
                  lineHeight: 1.6, maxHeight: 240, overflowY: 'auto', whiteSpace: 'pre-wrap', fontFamily: 'monospace'
                }}>
                  {selectedPatentModal.full_text}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
