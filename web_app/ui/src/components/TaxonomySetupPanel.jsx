import React, { useState, useEffect } from 'react';

/**
 * TaxonomySetupPanel — Dedicated configuration card rendered on the New Taxonomy Workspace.
 * 
 * Provides:
 * 1. Dedicated Patent / PubMed IDs input box with instant chip parsing & counter.
 * 2. Optional Product Ingestion: Dual-tab (Upload Document .pdf/.docx/.xlsx OR Product Web Link).
 * 3. Optional Custom Focus / Guidelines instructions with quick suggestion pills.
 * 4. Dedicated "Build Taxonomy" action button.
 */
export default function TaxonomySetupPanel({
  patentIds = [],
  onUpdatePatentIds,
  uploadedProducts = [],
  onProductUpload,
  productLinks = [],
  onUpdateProductLinks,
  onProductUrls,
  mentalModel = null,
  onClearProduct,
  customInstructions = '',
  onUpdateInstructions,
  onTriggerBuild,
  isUploading = false
}) {
  const [patentInputText, setPatentInputText] = useState('');
  const [productMode, setProductMode] = useState('file'); // 'file' | 'link'
  const [linkInputText, setLinkInputText] = useState('');
  const [fileDragActive, setFileDragActive] = useState(false);

  // Sync internal text with incoming patentIds if text is empty
  useEffect(() => {
    if (patentIds.length > 0 && !patentInputText) {
      setPatentInputText(patentIds.join(', '));
    }
  }, [patentIds]);

  // Sync internal text with incoming productLinks if text is empty
  useEffect(() => {
    if (productLinks.length > 0 && !linkInputText) {
      setLinkInputText(productLinks.join('\n'));
    }
  }, [productLinks]);

  // Extract patent/pubmed IDs from text input automatically
  const handlePatentTextChange = (text) => {
    setPatentInputText(text);
    const regex = /\b(?:US|EP|WO|JP|CN|KR)?\d{6,12}[A-Z0-9]*\b/gi;
    const matches = text.match(regex) || [];
    const uniqueIds = Array.from(new Set(matches.map(m => m.toUpperCase().trim())));
    onUpdatePatentIds(uniqueIds);
  };

  const handleRemovePatent = (pid) => {
    const updated = patentIds.filter(id => id !== pid);
    onUpdatePatentIds(updated);
    setPatentInputText(updated.join(', '));
  };

  const handleAddSamplePatents = () => {
    const sample = [
      'WO2010148089A1',
      'US20130089545A1',
      'US10683334B2',
      'WO2023207107A1',
      'US20150011467A1',
      'CN107496932A',
      'US4598065A',
      'EP3075385A1'
    ];
    const combined = Array.from(new Set([...patentIds, ...sample]));
    onUpdatePatentIds(combined);
    setPatentInputText(combined.join(', '));
  };

  const handleClearPatents = () => {
    onUpdatePatentIds([]);
    setPatentInputText('');
  };

  // Helper to extract and normalize URLs and file paths from multiline text
  const extractLinksAndPaths = (text) => {
    if (!text || !text.trim()) return [];
    const lines = text.split(/[\r\n]+/);
    const links = [];

    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (!line) continue;

      // Check if line is a local file path with spaces e.g. C:\Users\...
      if (/^[a-zA-Z]:[\\\/]/.test(line)) {
        links.push(line);
        continue;
      }

      // Otherwise split by commas or spaces
      const tokens = line.split(/[\s,]+/).filter(Boolean);
      for (let token of tokens) {
        token = token.replace(/^[<("'[]+|[>)"'\]]+$/g, '').replace(/[.,;]+$/, '').trim();
        if (token.length < 3) continue;

        if (token.startsWith('http://') || token.startsWith('https://') || token.startsWith('file://') || /^[a-zA-Z]:[\\\/]/.test(token)) {
          links.push(token);
        } else if (token.startsWith('www.')) {
          links.push(`https://${token}`);
        } else if (token.includes('.') && token.length > 4) {
          links.push(`https://${token}`);
        }
      }
    }

    return Array.from(new Set(links));
  };

  // Helper to clean up link display for chips
  const formatLinkDisplay = (url) => {
    if (!url) return '';
    try {
      if (url.startsWith('http://') || url.startsWith('https://')) {
        const u = new URL(url);
        const segments = u.pathname.split('/').filter(Boolean);
        let filename = segments.length > 0 ? segments[segments.length - 1] : '';
        try { filename = decodeURIComponent(filename); } catch (e) {}
        if (filename && (filename.includes('.') || filename.length > 15)) {
          return filename;
        }
        if (filename) {
          return `${u.hostname}/.../${filename}`;
        }
        return u.hostname;
      }
      const parts = url.split(/[\\/]/).filter(Boolean);
      return parts.length > 0 ? parts[parts.length - 1] : url;
    } catch (e) {
      return url;
    }
  };

  const handleLinkTextChange = (text) => {
    setLinkInputText(text);
    const uniqueLinks = extractLinksAndPaths(text);
    onUpdateProductLinks(uniqueLinks);
  };

  const handleRemoveLink = (linkToRemove) => {
    const updated = productLinks.filter(l => l !== linkToRemove);
    onUpdateProductLinks(updated);
    setLinkInputText(updated.join('\n'));
  };

  const handleClearLinks = () => {
    onUpdateProductLinks([]);
    setLinkInputText('');
  };

  const handleAnalyzeLinks = () => {
    let finalLinks = [...productLinks];
    if (linkInputText.trim()) {
      const parsed = extractLinksAndPaths(linkInputText);
      if (parsed.length > 0) {
        finalLinks = Array.from(new Set([...productLinks, ...parsed]));
        onUpdateProductLinks(finalLinks);
      }
    }
    if (finalLinks.length > 0 && onProductUrls) {
      onProductUrls(finalLinks);
    }
  };

  const handleApplyInstructionChip = (pill) => {
    if (!customInstructions) {
      onUpdateInstructions(pill);
    } else if (!customInstructions.includes(pill)) {
      onUpdateInstructions(`${customInstructions}; ${pill}`);
    }
  };

  const handleFileDrop = (e) => {
    e.preventDefault();
    setFileDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onProductUpload(e.dataTransfer.files);
    }
  };

  const handleBuildClick = () => {
    let finalLinks = [...productLinks];
    if (linkInputText.trim()) {
      const parsed = extractLinksAndPaths(linkInputText);
      if (parsed.length > 0) {
        finalLinks = Array.from(new Set([...productLinks, ...parsed]));
        onUpdateProductLinks(finalLinks);
      }
    }
    onTriggerBuild(finalLinks);
  };

  const hasProduct = uploadedProducts.length > 0 || productLinks.length > 0 || !!mentalModel || linkInputText.trim().length > 0;

  return (
    <div style={{
      marginTop: 14,
      background: 'linear-gradient(145deg, #131d31 0%, #0d1527 100%)',
      border: '1px solid #1e3a5f',
      borderRadius: 14,
      padding: '20px 22px',
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), 0 0 1px rgba(56, 189, 248, 0.2)',
      display: 'flex',
      flexDirection: 'column',
      gap: 18,
      maxWidth: '100%'
    }}>
      {/* Panel Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #1e293b', paddingBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 16
          }}>
            ⚙️
          </div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#f8fafc', letterSpacing: '-0.01em' }}>
              Taxonomy Configuration & Ingestion
            </div>
            <div style={{ fontSize: 12, color: '#94a3b8' }}>
              Enter patent identifiers, optionally attach product specifications or a link, and build your hierarchy.
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            fontSize: 11,
            fontWeight: 600,
            padding: '4px 10px',
            borderRadius: 12,
            background: patentIds.length > 0 ? '#064e3b' : '#334155',
            color: patentIds.length > 0 ? '#6ee7b7' : '#94a3b8',
            border: `1px solid ${patentIds.length > 0 ? '#059669' : '#475569'}`
          }}>
            {patentIds.length > 0 ? `✓ ${patentIds.length} Patent(s) Ready` : '0 Patents'}
          </span>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 1: Patent / PubMed IDs Input (Required)
         ───────────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <label style={{ fontSize: 13, fontWeight: 700, color: '#38bdf8', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>📄</span>
            <span>1. Patent / PubMed IDs</span>
            <span style={{ fontSize: 11, color: '#f43f5e', fontWeight: 600 }}>*Required</span>
          </label>

          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              onClick={handleAddSamplePatents}
              style={{
                background: 'transparent',
                border: '1px solid #0284c7',
                color: '#38bdf8',
                borderRadius: 6,
                padding: '2px 8px',
                fontSize: 11,
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              + Add Sample Patents
            </button>
            {patentIds.length > 0 && (
              <button
                type="button"
                onClick={handleClearPatents}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#94a3b8',
                  fontSize: 11,
                  cursor: 'pointer'
                }}
              >
                Clear
              </button>
            )}
          </div>
        </div>

        <textarea
          rows={3}
          value={patentInputText}
          onChange={(e) => handlePatentTextChange(e.target.value)}
          placeholder="Paste or type Patent or PubMed IDs (e.g., US10293847, WO2023207107A1, US4598065A, 34567890)... Separated by commas, spaces, or new lines."
          style={{
            width: '100%',
            boxSizing: 'border-box',
            background: '#090d16',
            color: '#f8fafc',
            border: '1px solid #334155',
            borderRadius: 8,
            padding: '10px 12px',
            fontSize: 13,
            lineHeight: 1.5,
            resize: 'vertical',
            outline: 'none',
            fontFamily: 'inherit'
          }}
          onFocus={(e) => e.target.style.borderColor = '#0284c7'}
          onBlur={(e) => e.target.style.borderColor = '#334155'}
        />

        {/* Detected Patent Chips */}
        {patentIds.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center', marginTop: 2 }}>
            <span style={{ fontSize: 11, color: '#94a3b8', fontWeight: 600 }}>
              Detected ({patentIds.length}):
            </span>
            {patentIds.map((pid) => (
              <span
                key={pid}
                style={{
                  background: '#0c4a6e',
                  color: '#7dd3fc',
                  border: '1px solid #0284c7',
                  borderRadius: 12,
                  padding: '2px 8px',
                  fontSize: 11,
                  fontWeight: 600,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4
                }}
              >
                <span>{pid}</span>
                <button
                  type="button"
                  onClick={() => handleRemovePatent(pid)}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: '#f87171',
                    cursor: 'pointer',
                    padding: 0,
                    fontSize: 11,
                    lineHeight: 1
                  }}
                  title="Remove this patent"
                >
                  ✕
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 2: Product Specification (Optional: File or Link)
         ───────────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, borderTop: '1px solid #1e293b', paddingTop: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <label style={{ fontSize: 13, fontWeight: 700, color: '#34d399', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>📦</span>
            <span>2. Product Context (Document or Web Link)</span>
            <span style={{ fontSize: 11, color: '#94a3b8', fontWeight: 500 }}>(Optional)</span>
          </label>

          {/* Toggle File vs Link */}
          <div style={{ display: 'flex', background: '#090d16', padding: 2, borderRadius: 8, border: '1px solid #334155' }}>
            <button
              type="button"
              onClick={() => setProductMode('file')}
              style={{
                background: productMode === 'file' ? '#059669' : 'transparent',
                color: productMode === 'file' ? '#ffffff' : '#94a3b8',
                border: 'none',
                borderRadius: 6,
                padding: '4px 10px',
                fontSize: 11,
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              📁 Document File
            </button>
            <button
              type="button"
              onClick={() => setProductMode('link')}
              style={{
                background: productMode === 'link' ? '#0284c7' : 'transparent',
                color: productMode === 'link' ? '#ffffff' : '#94a3b8',
                border: 'none',
                borderRadius: 6,
                padding: '4px 10px',
                fontSize: 11,
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              🔗 Web Link / URL
            </button>
          </div>
        </div>

        {/* Tab A: Document File Upload */}
        {productMode === 'file' && (
          <div>
            {uploadedProducts.length === 0 ? (
              <div
                onDragOver={(e) => { e.preventDefault(); setFileDragActive(true); }}
                onDragLeave={() => setFileDragActive(false)}
                onDrop={handleFileDrop}
                style={{
                  border: `2px dashed ${fileDragActive ? '#34d399' : '#334155'}`,
                  borderRadius: 10,
                  padding: '16px',
                  background: fileDragActive ? '#064e3b15' : '#090d16',
                  textAlign: 'center',
                  transition: 'all 0.2s ease',
                  cursor: 'pointer'
                }}
                onClick={() => {
                  const inputEl = document.getElementById('panel-product-file-input');
                  if (inputEl) inputEl.click();
                }}
              >
                <input
                  id="panel-product-file-input"
                  type="file"
                  multiple
                  accept=".pdf,.docx,.xlsx,.xls,.csv,.txt"
                  style={{ display: 'none' }}
                  onChange={(e) => {
                    if (e.target.files && e.target.files.length > 0) {
                      onProductUpload(e.target.files);
                    }
                  }}
                />
                <div style={{ fontSize: 24, marginBottom: 4 }}>📄</div>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0' }}>
                  {isUploading ? 'Uploading & Extracting Specifications...' : 'Click to Upload or Drag & Drop Product Document'}
                </div>
                <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
                  Supports .pdf, .docx, .xlsx, .csv — extracts product capabilities & focus areas
                </div>
              </div>
            ) : (
              /* Attached Product Card */
              <div style={{
                background: '#064e3b25',
                border: '1px solid #059669',
                borderRadius: 8,
                padding: '10px 14px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ fontSize: 20 }}>📦</div>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#6ee7b7' }}>
                      {uploadedProducts.map(p => p.product_name || p.source_filename).join(', ')}
                    </div>
                    {mentalModel && (
                      <div style={{ fontSize: 11, color: '#a7f3d0' }}>
                        Domain: {mentalModel.domain} • {mentalModel.focus_areas?.length || 0} Priority Focus Areas Extracted
                      </div>
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={onClearProduct}
                  style={{
                    background: 'transparent',
                    border: '1px solid #f43f5e',
                    color: '#f87171',
                    borderRadius: 6,
                    padding: '3px 8px',
                    fontSize: 11,
                    cursor: 'pointer'
                  }}
                >
                  Remove
                </button>
              </div>
            )}
          </div>
        )}

        {/* Tab B: Product Web Link / URL (Multiple Links Support) */}
        {productMode === 'link' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 12, color: '#94a3b8' }}>
                Paste product webpage or PDF links (separated by new lines, commas, or spaces):
              </span>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <button
                  type="button"
                  onClick={handleAnalyzeLinks}
                  disabled={isUploading || (productLinks.length === 0 && !linkInputText.trim())}
                  style={{
                    background: (isUploading || (productLinks.length === 0 && !linkInputText.trim())) ? 'transparent' : '#0284c7',
                    color: (isUploading || (productLinks.length === 0 && !linkInputText.trim())) ? '#475569' : '#ffffff',
                    border: '1px solid ' + ((isUploading || (productLinks.length === 0 && !linkInputText.trim())) ? '#334155' : '#0284c7'),
                    borderRadius: 6,
                    padding: '3px 10px',
                    fontSize: 11,
                    fontWeight: 600,
                    cursor: (isUploading || (productLinks.length === 0 && !linkInputText.trim())) ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 5
                  }}
                >
                  {isUploading ? '⏳ Extracting...' : '⚡ Extract & Analyze Link(s)'}
                </button>
                {(productLinks.length > 0 || linkInputText.trim().length > 0) && (
                  <button
                    type="button"
                    onClick={handleClearLinks}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: '#94a3b8',
                      fontSize: 11,
                      cursor: 'pointer'
                    }}
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>

            <textarea
              rows={3}
              value={linkInputText}
              onChange={(e) => handleLinkTextChange(e.target.value)}
              placeholder="Paste or type product URLs or PDF links (e.g. https://polymers.totalenergies.com/.../brochure.pdf, https://example.com/spec.pdf)... Separated by commas, spaces, or new lines."
              style={{
                width: '100%',
                boxSizing: 'border-box',
                background: '#090d16',
                color: '#f8fafc',
                border: '1px solid #334155',
                borderRadius: 8,
                padding: '10px 12px',
                fontSize: 13,
                lineHeight: 1.5,
                resize: 'vertical',
                outline: 'none',
                fontFamily: 'inherit'
              }}
              onFocus={(e) => e.target.style.borderColor = '#0284c7'}
              onBlur={(e) => e.target.style.borderColor = '#334155'}
            />

            {/* Detected Link Chips (Exact visual match to Patent / PubMed IDs section) */}
            {productLinks.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center', marginTop: 2 }}>
                <span style={{ fontSize: 11, color: '#94a3b8', fontWeight: 600 }}>
                  Detected ({productLinks.length}):
                </span>
                {productLinks.map((link, idx) => (
                  <span
                    key={`${link}-${idx}`}
                    title={link}
                    style={{
                      background: '#0c4a6e',
                      color: '#7dd3fc',
                      border: '1px solid #0284c7',
                      borderRadius: 12,
                      padding: '2px 8px',
                      fontSize: 11,
                      fontWeight: 600,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                      maxWidth: '100%'
                    }}
                  >
                    <span style={{ fontSize: 11 }}>🔗</span>
                    <span style={{
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      maxWidth: 260
                    }}>
                      {formatLinkDisplay(link)}
                    </span>
                    <button
                      type="button"
                      onClick={() => handleRemoveLink(link)}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: '#f87171',
                        cursor: 'pointer',
                        padding: 0,
                        fontSize: 11,
                        lineHeight: 1
                      }}
                      title="Remove this link"
                    >
                      ✕
                    </button>
                  </span>
                ))}
              </div>
            )}

            {isUploading && (
              <div style={{ fontSize: 11, color: '#38bdf8', display: 'flex', alignItems: 'center', gap: 6, fontStyle: 'italic', marginTop: 2 }}>
                <span>⏳</span>
                <span>Fetching and extracting product specification tables from URL(s)...</span>
              </div>
            )}

            {/* Extracted Product / Mental Model Card (if analysis already completed) */}
            {mentalModel && (
              <div style={{
                background: '#064e3b25',
                border: '1px solid #059669',
                borderRadius: 8,
                padding: '8px 12px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginTop: 4
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ fontSize: 16 }}>✓📦</div>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: '#6ee7b7' }}>
                      {mentalModel.product_name || 'Product Specification Analyzed'}
                    </div>
                    <div style={{ fontSize: 11, color: '#a7f3d0' }}>
                      Domain: {mentalModel.domain} • {mentalModel.focus_areas?.length || 0} Priority Focus Areas Extracted
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={onClearProduct}
                  style={{
                    background: 'transparent',
                    border: '1px solid #f43f5e',
                    color: '#f87171',
                    borderRadius: 6,
                    padding: '2px 6px',
                    fontSize: 11,
                    cursor: 'pointer'
                  }}
                >
                  Clear Analysis
                </button>
              </div>
            )}
          </div>
        )}

        <div style={{ fontSize: 11, color: '#64748b', fontStyle: 'italic' }}>
          *Note: If no product is uploaded or linked, the pipeline will build the taxonomy directly from patent specifications.
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 3: Custom Focus / Guidelines (Optional)
         ───────────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, borderTop: '1px solid #1e293b', paddingTop: 14 }}>
        <label style={{ fontSize: 13, fontWeight: 700, color: '#f59e0b', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span>🎯</span>
          <span>3. Focus Guidelines & Rules</span>
          <span style={{ fontSize: 11, color: '#94a3b8', fontWeight: 500 }}>(Optional)</span>
        </label>

        <textarea
          rows={2}
          value={customInstructions}
          onChange={(e) => onUpdateInstructions(e.target.value)}
          placeholder="e.g., Focus specifically on mechanism of action, avoid manufacturing and packaging. Prioritize cellular permeability and macrocyclization."
          style={{
            width: '100%',
            boxSizing: 'border-box',
            background: '#090d16',
            color: '#f8fafc',
            border: '1px solid #334155',
            borderRadius: 8,
            padding: '8px 12px',
            fontSize: 13,
            lineHeight: 1.4,
            resize: 'vertical',
            outline: 'none',
            fontFamily: 'inherit'
          }}
          onFocus={(e) => e.target.style.borderColor = '#f59e0b'}
          onBlur={(e) => e.target.style.borderColor = '#334155'}
        />

        {/* Suggestion Pills */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {[
            'Focus on mechanism of action',
            'Exclude packaging & manufacturing',
            'Prioritize cellular permeability',
            'Drug design & formulation focus',
            'Macrocyclization strategies'
          ].map((pill, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handleApplyInstructionChip(pill)}
              style={{
                background: '#1e293b',
                color: '#94a3b8',
                border: '1px solid #334155',
                borderRadius: 12,
                padding: '2px 8px',
                fontSize: 11,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
              onMouseEnter={(e) => { e.currentTarget.style.color = '#fbbf24'; e.currentTarget.style.borderColor = '#f59e0b'; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = '#94a3b8'; e.currentTarget.style.borderColor = '#334155'; }}
            >
              + {pill}
            </button>
          ))}
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 4: Build Action & Summary
         ───────────────────────────────────────────────────────────── */}
      <div style={{
        borderTop: '1px solid #1e293b',
        paddingTop: 14,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 12
      }}>
        {/* Summary indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 12, color: '#94a3b8' }}>
          <span>Summary:</span>
          <span style={{ color: patentIds.length > 0 ? '#38bdf8' : '#64748b', fontWeight: 600 }}>
            📄 {patentIds.length} Patent(s)
          </span>
          <span>•</span>
          <span style={{ color: hasProduct ? '#34d399' : '#94a3b8', fontWeight: 600 }}>
            📦 {hasProduct
                ? (uploadedProducts.length > 0
                    ? `${uploadedProducts.length} Product File(s)`
                    : (productLinks.length > 0 ? `${productLinks.length} Product Link(s)` : 'Product Attached'))
                : 'Pure Patent Pipeline'}
          </span>
          {customInstructions && (
            <>
              <span>•</span>
              <span style={{ color: '#fbbf24', fontWeight: 600 }}>🎯 Custom Focus Set</span>
            </>
          )}
        </div>

        {/* Action Button */}
        <button
          type="button"
          disabled={patentIds.length === 0 || isUploading}
          onClick={handleBuildClick}
          style={{
            background: isUploading
              ? '#0369a1'
              : (patentIds.length > 0
                ? 'linear-gradient(135deg, #059669 0%, #0284c7 100%)'
                : '#334155'),
            color: (patentIds.length > 0 || isUploading) ? 'white' : '#64748b',
            border: 'none',
            borderRadius: 10,
            padding: '10px 22px',
            fontSize: 13,
            fontWeight: 700,
            cursor: (patentIds.length > 0 && !isUploading) ? 'pointer' : (isUploading ? 'wait' : 'not-allowed'),
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            boxShadow: patentIds.length > 0 ? '0 4px 16px rgba(5, 150, 105, 0.35)' : 'none',
            transition: 'all 0.2s ease'
          }}
        >
          <span>{isUploading ? '⏳' : '🚀'}</span>
          <span>
            {isUploading
              ? 'Step 1/2: Extracting Product Specifications...'
              : (patentIds.length > 0
                ? `Build Taxonomy with ${patentIds.length} Patent(s)`
                : 'Enter at Least 1 Patent ID to Build')}
          </span>
        </button>
      </div>
    </div>
  );
}
