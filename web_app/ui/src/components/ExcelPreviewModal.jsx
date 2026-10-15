/**
 * ExcelPreviewModal.jsx
 *
 * Full-fidelity Excel preview modal showing the exact Matrix Excel spreadsheet:
 * - Multi-level merged headers with exact category palette colors
 * - Fixed metadata columns (S.No, Patent Number, Patent Title, Assignee, Summary)
 * - Dynamic taxonomy columns with claim evidence quotes / checkmarks
 * - Sticky headers with horizontal & vertical scrolling
 * - Floating/Fixed Download button at the bottom-right corner
 */

import React, { useState } from 'react';

export default function ExcelPreviewModal({ previewData, onClose, onDownload, isDownloading }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSheet, setSelectedSheet] = useState(
    previewData?.active_sheet || (previewData?.sheet_names && previewData.sheet_names[0]) || ''
  );

  if (!previewData) {
    return null;
  }

  const activeSheetData = (previewData.sheets && selectedSheet && previewData.sheets[selectedSheet]) || previewData;
  const { title = '', rows = [], col_widths = {} } = activeSheetData;
  const filename = previewData.filename;

  // Filter rows if user types in search
  const filteredRows = searchTerm.trim() === '' ? rows : rows.filter((r, idx) => {
    // Keep header rows (rows with col > 5 having titles or row < max header)
    if (idx < 5) return true;
    const rowText = r.map(c => String(c.value || '')).join(' ').toLowerCase();
    return rowText.includes(searchTerm.toLowerCase());
  });

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(5, 10, 24, 0.85)',
        zIndex: 99999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
        backdropFilter: 'blur(6px)',
        fontFamily: 'Inter, system-ui, -apple-system, sans-serif'
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: '#0b1329',
          border: '1px solid #1e293b',
          borderRadius: 16,
          width: '96vw',
          maxWidth: '1600px',
          height: '92vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.7)',
          overflow: 'hidden',
          position: 'relative'
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Top Header Bar */}
        <div
          style={{
            padding: '16px 24px',
            borderBottom: '1px solid #1e293b',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: '#0f172a'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 24 }}>📑</span>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <h3 style={{ margin: 0, fontSize: 17, color: '#f8fafc', fontWeight: 700 }}>
                  Excel Matrix Preview
                </h3>
                <span style={{
                  background: '#1e293b',
                  color: '#38bdf8',
                  padding: '3px 8px',
                  borderRadius: 6,
                  fontSize: 12,
                  fontFamily: 'monospace'
                }}>
                  {filename || 'Taxonomy_Matrix.xlsx'}
                </span>
              </div>
              <p style={{ margin: '3px 0 0', fontSize: 12, color: '#94a3b8' }}>
                Multi-sheet workbook with exact merged hierarchy headers & commercial products catalog
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {/* Search Input */}
            <input
              type="text"
              placeholder={`Search ${selectedSheet || 'sheet'}...`}
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              style={{
                background: '#1e293b',
                border: '1px solid #334155',
                color: '#f8fafc',
                padding: '7px 12px',
                borderRadius: 8,
                fontSize: 12,
                outline: 'none',
                width: 260
              }}
            />

            {/* Download Excel Button in Top Bar */}
            <button
              onClick={onDownload}
              disabled={isDownloading}
              title="Download full multi-sheet Excel matrix (.xlsx)"
              style={{
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                color: '#ffffff',
                border: 'none',
                borderRadius: 8,
                padding: '7px 16px',
                cursor: isDownloading ? 'not-allowed' : 'pointer',
                fontWeight: 700,
                fontSize: 13,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                boxShadow: '0 2px 8px rgba(16, 185, 129, 0.3)',
                transition: 'all 0.15s ease',
                opacity: isDownloading ? 0.7 : 1
              }}
            >
              <span>{isDownloading ? '⏳' : '📥'}</span>
              <span>{isDownloading ? 'Downloading...' : 'Download Excel'}</span>
            </button>

            {/* Close Button */}
            <button
              onClick={onClose}
              style={{
                background: '#1e293b',
                border: '1px solid #475569',
                color: '#cbd5e1',
                borderRadius: 8,
                padding: '6px 14px',
                cursor: 'pointer',
                fontSize: 13,
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: 4
              }}
            >
              ✕ Close
            </button>
          </div>
        </div>

        {/* Multi-Sheet Selector Tabs */}
        {previewData.sheet_names && previewData.sheet_names.length > 1 && (
          <div
            style={{
              padding: '8px 24px',
              background: '#090e1a',
              borderBottom: '1px solid #1e293b',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              overflowX: 'auto'
            }}
          >
            <span style={{ fontSize: 12, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', marginRight: 4 }}>
              Sheets:
            </span>
            {previewData.sheet_names.map(name => {
              const isSelected = (selectedSheet || previewData.active_sheet) === name;
              const icon = name.includes('Patent') ? '📜' : name.includes('Specification') ? '📋' : '📦';
              return (
                <button
                  key={name}
                  onClick={() => {
                    setSelectedSheet(name);
                    setSearchTerm('');
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '6px 14px',
                    borderRadius: 6,
                    border: isSelected ? '1px solid #38bdf8' : '1px solid #1e293b',
                    background: isSelected ? '#1e293b' : '#0f172a',
                    color: isSelected ? '#38bdf8' : '#94a3b8',
                    fontSize: 12,
                    fontWeight: isSelected ? 600 : 500,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    boxShadow: isSelected ? '0 2px 8px rgba(56, 189, 248, 0.15)' : 'none'
                  }}
                >
                  <span>{icon}</span>
                  <span>{name}</span>
                </button>
              );
            })}
          </div>
        )}

        {/* Spreadsheet Content Area */}
        <div
          style={{
            flex: 1,
            overflowX: 'auto',
            overflowY: 'auto',
            background: '#ffffff',
            position: 'relative'
          }}
        >
          <table
            style={{
              borderCollapse: 'collapse',
              width: 'max-content',
              tableLayout: 'fixed',
              fontSize: 12,
              fontFamily: 'Segoe UI, Calibri, Arial, sans-serif'
            }}
          >
            <tbody>
              {filteredRows.map((rowCells, rIdx) => (
                <tr key={rIdx}>
                  {rowCells.map((cell, cIdx) => {
                    const isHeader = cell.bold || cell.bg;
                    const cellBg = cell.bg || (rIdx % 2 === 0 ? '#ffffff' : '#f9fafb');
                    const cellColor = cell.color || (isHeader ? '#000000' : '#1e293b');

                    // Compute clean width for each column:
                    // Col 1 (S.No): 65px
                    // Col 2 (Patent Number): 160px
                    // Col 3 (Patent Title): 280px
                    // Col 4 (Assignee): 240px
                    // Col 5 (Summary): 340px
                    // Dynamic taxonomy cols: 200px
                    let explicitWidth = undefined;
                    let explicitMinWidth = undefined;
                    if (!cell.colspan || cell.colspan === 1) {
                      if (cell.col === 1) {
                        explicitWidth = 65;
                        explicitMinWidth = 65;
                      } else if (cell.col === 2) {
                        explicitWidth = 160;
                        explicitMinWidth = 160;
                      } else if (cell.col === 3) {
                        explicitWidth = 280;
                        explicitMinWidth = 280;
                      } else if (cell.col === 4) {
                        explicitWidth = 240;
                        explicitMinWidth = 240;
                      } else if (cell.col === 5) {
                        explicitWidth = 340;
                        explicitMinWidth = 340;
                      } else {
                        explicitWidth = 200;
                        explicitMinWidth = 200;
                      }
                    }

                    // Freeze S.No (Col 1) and Patent Number (Col 2)
                    let stickyStyle = {};
                    if (cell.col === 1) {
                      stickyStyle = {
                        position: 'sticky',
                        left: 0,
                        zIndex: isHeader ? 30 : 20,
                        boxShadow: '1px 0 0 #cbd5e1'
                      };
                    } else if (cell.col === 2) {
                      stickyStyle = {
                        position: 'sticky',
                        left: 65,
                        zIndex: isHeader ? 30 : 20,
                        boxShadow: '2px 0 6px -2px rgba(0, 0, 0, 0.25), 1px 0 0 #cbd5e1'
                      };
                    }

                    return (
                      <td
                        key={cIdx}
                        rowSpan={cell.rowspan || 1}
                        colSpan={cell.colspan || 1}
                        style={{
                          background: cellBg,
                          color: cellColor,
                          fontWeight: cell.bold ? 700 : 400,
                          textAlign: cell.align_h || (cell.col === 1 ? 'center' : 'left'),
                          verticalAlign: cell.align_v || 'top',
                          border: '1px solid #d1d5db',
                          padding: '8px 12px',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          width: explicitWidth,
                          minWidth: explicitMinWidth,
                          maxWidth: explicitWidth,
                          lineHeight: 1.45,
                          boxSizing: 'border-box',
                          ...stickyStyle
                        }}
                      >
                        {cell.value}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Bottom Bar showing metadata */}
        <div
          style={{
            padding: '12px 24px',
            background: '#0f172a',
            borderTop: '1px solid #1e293b',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}
        >
          <div style={{ fontSize: 13, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 16 }}>
            <span>📊 Total Rows: <strong style={{ color: '#f1f5f9' }}>{rows.length}</strong></span>
            <span>📑 Sheet: <strong style={{ color: '#38bdf8' }}>{title || 'Patent Taxonomy Matrix'}</strong></span>
          </div>
        </div>
      </div>
    </div>
  );
}
