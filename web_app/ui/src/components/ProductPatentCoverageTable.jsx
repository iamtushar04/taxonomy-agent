/**
 * ProductPatentCoverageTable.jsx
 *
 * Commercialization Matrix & Coverage Table:
 * - Shows each Product (uploaded doc)
 * - Number of patents protecting that product
 * - Which exact patents protect which product features
 * - Which taxonomy nodes it implements
 */

import React, { useMemo, useState } from 'react';

const TH_STYLE = {
  padding: '10px 14px',
  background: '#0f172a',
  color: '#10b981',
  fontSize: 12,
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  textAlign: 'left',
  position: 'sticky',
  top: 0,
  zIndex: 1,
  borderBottom: '1px solid #1e293b'
};

const TD_STYLE = {
  padding: '12px 14px',
  borderBottom: '1px solid #1e293b',
  color: '#e2e8f0',
  fontSize: 13,
  verticalAlign: 'top',
};

export default function ProductPatentCoverageTable({ products = [], taxonomy = [], patents = [] }) {
  const [search, setSearch] = useState('');
  const [selectedPatentModal, setSelectedPatentModal] = useState(null);
  const [selectedProductModal, setSelectedProductModal] = useState(null);

  // Quick lookup map for patent details
  const patentLookup = useMemo(() => {
    const map = {};
    patents.forEach(p => { map[p.patent_id] = p; });
    return map;
  }, [patents]);

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
          map[prodId].nodes.push(node.name);
          patentsOnNode.forEach(patId => map[prodId].patentIds.add(patId));
        }
      });
    });

    return Object.values(map);
  }, [products, taxonomy]);

  const filtered = useMemo(() => {
    if (!search.trim()) return productMapping;
    const q = search.toLowerCase();
    return productMapping.filter(item =>
      item.product.product_name.toLowerCase().includes(q) ||
      (item.product.brand_or_assignee || '').toLowerCase().includes(q) ||
      item.nodes.some(n => n.toLowerCase().includes(q)) ||
      Array.from(item.patentIds).some(pid => pid.toLowerCase().includes(q))
    );
  }, [productMapping, search]);

  if (products.length === 0) {
    return (
      <div style={{ color: '#64748b', textAlign: 'center', padding: 32, fontSize: 13 }}>
        No product documents were uploaded for this session. Upload product documents when generating a new taxonomy to see Product-to-Patent mapping.
      </div>
    );
  }

  return (
    <div>
      {/* Search / Filter */}
      <div style={{ marginBottom: 14 }}>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="🔍  Search product, protecting patent #, or taxonomy branch..."
          style={{
            width: '100%',
            padding: '9px 14px',
            borderRadius: 8,
            border: '1px solid #334155',
            background: '#1e293b',
            color: '#f1f5f9',
            fontSize: 13,
            outline: 'none',
            boxSizing: 'border-box'
          }}
        />
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto', overflowY: 'auto', maxHeight: 420, borderRadius: 10, border: '1px solid #1e293b' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 750 }}>
          <thead>
            <tr>
              <th style={{ ...TH_STYLE, width: 220 }}>Commercial Product</th>
              <th style={{ ...TH_STYLE, width: 140 }}>Brand / Vendor</th>
              <th style={{ ...TH_STYLE, width: 110 }}>Patent Protection</th>
              <th style={{ ...TH_STYLE, minWidth: 200 }}>Protecting Patents</th>
              <th style={{ ...TH_STYLE, minWidth: 220 }}>Implemented Taxonomy Branches</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ ...TD_STYLE, textAlign: 'center', color: '#64748b', padding: 24 }}>
                  No matching products found.
                </td>
              </tr>
            ) : (
              filtered.map(({ product, nodes, patentIds }) => {
                const patentCount = patentIds.size;
                const isProtected = patentCount > 0;
                return (
                  <tr key={product.product_id}
                    onMouseEnter={e => e.currentTarget.style.background = '#1e293b'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  >
                    {/* Product Name */}
                    <td style={{ ...TD_STYLE, fontWeight: 700, color: '#f1f5f9' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span>📦</span>
                        <span>{product.product_name}</span>
                      </div>
                      {product.source_filename && (
                        <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
                          {product.source_filename}
                        </div>
                      )}
                    </td>

                    {/* Commercial Product (Clickable for feature inspection) */}
                    <td 
                      style={{ ...TD_STYLE, fontWeight: 700, color: '#f1f5f9', cursor: 'pointer' }}
                      onClick={() => setSelectedProductModal(product)}
                      title="Click to inspect extracted technical features and specs"
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span>📦</span>
                        <span style={{ textDecoration: 'underline' }}>{product.product_name}</span>
                      </div>
                      {product.source_filename && (
                        <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
                          {product.source_filename}
                        </div>
                      )}
                    </td>

                    {/* Brand */}
                    <td style={{ ...TD_STYLE, color: '#94a3b8' }}>
                      {product.brand_or_assignee || '—'}
                    </td>

                    {/* Protection Status Badge */}
                    <td style={{ ...TD_STYLE }}>
                      {isProtected ? (
                        <span style={{
                          background: '#065f46',
                          color: '#6ee7b7',
                          padding: '3px 8px',
                          borderRadius: 99,
                          fontSize: 11,
                          fontWeight: 700,
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 4
                        }}>
                          🛡️ {patentCount} Patent{patentCount > 1 ? 's' : ''}
                        </span>
                      ) : (
                        <span style={{
                          background: '#7f1d1d',
                          color: '#fca5a5',
                          padding: '3px 8px',
                          borderRadius: 99,
                          fontSize: 11,
                          fontWeight: 700
                        }}>
                          ⚠️ Unprotected
                        </span>
                      )}
                    </td>

                    {/* Protecting Patents (Clickable for full patent view) */}
                    <td style={{ ...TD_STYLE }}>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                        {patentCount === 0 ? (
                          <span style={{ color: '#ef4444', fontSize: 12 }}>No patent coverage found</span>
                        ) : (
                          Array.from(patentIds).map(pid => {
                            const pData = patentLookup[pid] || { patent_id: pid, title: 'Patent Details' };
                            return (
                              <button
                                key={pid}
                                onClick={() => setSelectedPatentModal(pData)}
                                title={`Click to view patent details for ${pid}`}
                                style={{
                                  fontFamily: 'monospace',
                                  background: '#312e81',
                                  color: '#a5b4fc',
                                  border: '1px solid #4338ca',
                                  padding: '2px 8px',
                                  borderRadius: 4,
                                  fontSize: 11,
                                  fontWeight: 600,
                                  cursor: 'pointer',
                                  transition: 'all 0.15s ease',
                                }}
                                onMouseEnter={e => { e.currentTarget.style.background = '#4338ca'; e.currentTarget.style.color = '#fff'; }}
                                onMouseLeave={e => { e.currentTarget.style.background = '#312e81'; e.currentTarget.style.color = '#a5b4fc'; }}
                              >
                                📄 {pid}
                              </button>
                            );
                          })
                        )}
                      </div>
                    </td>

                    {/* Implemented Taxonomy Nodes */}
                    <td style={{ ...TD_STYLE }}>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                        {nodes.length === 0 ? (
                          <span style={{ color: '#64748b', fontSize: 12 }}>No taxonomy overlap</span>
                        ) : (
                          nodes.map((nName, i) => (
                            <span key={i} style={{
                              background: '#064e3b',
                              color: '#a7f3d0',
                              padding: '2px 8px',
                              borderRadius: 99,
                              fontSize: 11,
                              fontWeight: 500,
                            }}>
                              {nName}
                            </span>
                          ))
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Product Technical Inspection Modal */}
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
                  Brand / Vendor: {selectedProductModal.brand_or_assignee || 'Unknown'} • Category: {selectedProductModal.category || 'General'}
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

            {/* Product Document Text Excerpt */}
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

      {/* Patent Detail Modal */}
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
