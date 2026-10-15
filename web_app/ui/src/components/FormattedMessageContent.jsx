/**
 * FormattedMessageContent.jsx
 *
 * Rich Dynamic Text and Markdown Renderer for Chat Messages:
 * - Parses Markdown syntax (headings, bold, italics, lists, tables, blockquotes, code blocks)
 * - Beautifully renders any dynamic data types (Objects, Arrays, Numbers, JSON strings)
 * - Adapts styling smoothly for user vs assistant bubbles
 */

import React from 'react';

// Helper to safely render inline markdown (bold, italic, code, links)
function renderInlineFormatting(text, isUser = false) {
  if (!text || typeof text !== 'string') return text;

  // Regex to match inline patterns: code, bold, italic, links
  // Pattern 1: `code`
  // Pattern 2: **bold** or __bold__
  // Pattern 3: *italic* or _italic_
  // Pattern 4: [title](url)
  const tokens = [];
  let remaining = text;
  let keyIdx = 0;

  // Combined regex with capture groups
  const inlineRegex = /(`[^`]+`)|(\*\*[^*]+\*\*|__[^_]+__)|(\*[^*]+\*|_[^_]+_)|(\[[^\]]+\]\([^)]+\))/;

  while (remaining) {
    const match = remaining.match(inlineRegex);
    if (!match) {
      tokens.push(remaining);
      break;
    }

    const matchStart = match.index;
    const matchText = match[0];

    // Push preceding text
    if (matchStart > 0) {
      tokens.push(remaining.substring(0, matchStart));
    }

    // Determine type
    if (matchText.startsWith('`') && matchText.endsWith('`')) {
      // Inline Code
      tokens.push(
        <code
          key={`code-${keyIdx++}`}
          style={{
            background: isUser ? 'rgba(0, 0, 0, 0.25)' : '#0f172a',
            border: `1px solid ${isUser ? 'rgba(255,255,255,0.2)' : '#334155'}`,
            borderRadius: 4,
            padding: '2px 6px',
            fontSize: '0.88em',
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
            color: isUser ? '#fef08a' : '#38bdf8',
            fontWeight: 500
          }}
        >
          {matchText.slice(1, -1)}
        </code>
      );
    } else if (
      (matchText.startsWith('**') && matchText.endsWith('**')) ||
      (matchText.startsWith('__') && matchText.endsWith('__'))
    ) {
      // Bold
      tokens.push(
        <strong
          key={`bold-${keyIdx++}`}
          style={{
            color: isUser ? '#ffffff' : '#f8fafc',
            fontWeight: 700
          }}
        >
          {matchText.slice(2, -2)}
        </strong>
      );
    } else if (
      (matchText.startsWith('*') && matchText.endsWith('*')) ||
      (matchText.startsWith('_') && matchText.endsWith('_'))
    ) {
      // Italic
      tokens.push(
        <em
          key={`italic-${keyIdx++}`}
          style={{
            color: isUser ? '#e0e7ff' : '#cbd5e1',
            fontStyle: 'italic'
          }}
        >
          {matchText.slice(1, -1)}
        </em>
      );
    } else if (matchText.startsWith('[') && matchText.includes('](') && matchText.endsWith(')')) {
      // Link [title](url)
      const linkMatch = matchText.match(/\[([^\]]+)\]\(([^)]+)\)/);
      if (linkMatch) {
        const title = linkMatch[1];
        let url = linkMatch[2];
        const isDownload = url.includes('/api/export/download/') || url.includes('/api/download-excel/') || url.endsWith('.xlsx') || url.endsWith('.pdf') || title.toLowerCase().includes('download');

        const baseUrl = window.APP_CONFIG?.API_BASE_URL || 'http://localhost:8652';
        const fullUrl = url.startsWith('http') ? url : `${baseUrl}${url.startsWith('/') ? '' : '/'}${url}`;

        if (isDownload) {
          const isPdf = url.includes('.pdf') || title.toLowerCase().includes('pdf');
          tokens.push(
            <a
              key={`link-${keyIdx++}`}
              href={fullUrl}
              download
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 7,
                background: isPdf ? '#881337' : '#064e3b',
                color: '#ffffff',
                border: `1px solid ${isPdf ? '#f43f5e' : '#10b981'}`,
                padding: '6px 14px',
                borderRadius: 8,
                textDecoration: 'none',
                fontWeight: 600,
                fontSize: 13,
                margin: '4px 0',
                boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
              onMouseEnter={e => {
                e.currentTarget.style.transform = 'translateY(-1px)';
                e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.4)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.3)';
              }}
            >
              <span>{isPdf ? '📄' : '📊'}</span>
              <span>{title.replace(/^[📄📊📥\s]+/, '')}</span>
              <span style={{ fontSize: 11, opacity: 0.8, marginLeft: 2 }}>↓</span>
            </a>
          );
        } else {
          tokens.push(
            <a
              key={`link-${keyIdx++}`}
              href={fullUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                color: isUser ? '#ffffff' : '#38bdf8',
                textDecoration: 'underline',
                fontWeight: 500
              }}
            >
              {title}
            </a>
          );
        }
      } else {
        tokens.push(matchText);
      }
    } else {
      tokens.push(matchText);
    }

    remaining = remaining.substring(matchStart + matchText.length);
  }

  return tokens;
}

// Render dynamic structured data (Objects, Arrays)
function DynamicDataCard({ data, isUser }) {
  if (Array.isArray(data)) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, margin: '8px 0' }}>
        {data.map((item, idx) => (
          <div
            key={idx}
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 8,
              padding: '6px 10px',
              background: isUser ? 'rgba(255,255,255,0.08)' : '#0f172a',
              borderRadius: 6,
              border: `1px solid ${isUser ? 'rgba(255,255,255,0.15)' : '#334155'}`,
              fontSize: 13
            }}
          >
            <span style={{ color: '#38bdf8', fontWeight: 700 }}>•</span>
            <div>
              {typeof item === 'object' ? <DynamicDataCard data={item} isUser={isUser} /> : renderInlineFormatting(String(item), isUser)}
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (typeof data === 'object' && data !== null) {
    return (
      <div
        style={{
          background: isUser ? 'rgba(0,0,0,0.2)' : '#0f172a',
          border: `1px solid ${isUser ? 'rgba(255,255,255,0.15)' : '#334155'}`,
          borderRadius: 8,
          padding: '10px 14px',
          margin: '8px 0',
          display: 'grid',
          gridTemplateColumns: 'auto 1fr',
          gap: '6px 12px',
          fontSize: 13
        }}
      >
        {Object.entries(data).map(([key, val], idx) => (
          <React.Fragment key={idx}>
            <span style={{ color: isUser ? '#93c5fd' : '#94a3b8', fontWeight: 600, textTransform: 'capitalize' }}>
              {key.replace(/_/g, ' ')}:
            </span>
            <span style={{ color: isUser ? '#ffffff' : '#f1f5f9' }}>
              {typeof val === 'object' ? <DynamicDataCard data={val} isUser={isUser} /> : renderInlineFormatting(String(val), isUser)}
            </span>
          </React.Fragment>
        ))}
      </div>
    );
  }

  return <span>{String(data)}</span>;
}

export default function FormattedMessageContent({ content, isUser = false }) {
  // 1. Guard against empty / null
  if (content === null || content === undefined || content === '') {
    return null;
  }

  // 2. Dynamic handling: If content is already a structured Object or Array
  if (typeof content === 'object') {
    return <DynamicDataCard data={content} isUser={isUser} />;
  }

  // 3. String handling: Check if it's stringified JSON
  if (typeof content === 'string') {
    const trimmed = content.trim();
    if (
      (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
      (trimmed.startsWith('[') && trimmed.endsWith(']'))
    ) {
      try {
        const parsed = JSON.parse(trimmed);
        if (typeof parsed === 'object') {
          return <DynamicDataCard data={parsed} isUser={isUser} />;
        }
      } catch {
        // Fall through to markdown parsing
      }
    }
  }

  const rawText = String(content);

  // 4. Split content by code blocks first: ```lang ... ```
  const codeBlockRegex = /```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g;
  const sections = [];
  let lastIndex = 0;
  let match;

  while ((match = codeBlockRegex.exec(rawText)) !== null) {
    if (match.index > lastIndex) {
      sections.push({ type: 'text', text: rawText.substring(lastIndex, match.index) });
    }
    sections.push({
      type: 'code',
      lang: match[1] || 'text',
      code: match[2].trimEnd()
    });
    lastIndex = codeBlockRegex.lastIndex;
  }
  if (lastIndex < rawText.length) {
    sections.push({ type: 'text', text: rawText.substring(lastIndex) });
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, width: '100%' }}>
      {sections.map((section, sIdx) => {
        if (section.type === 'code') {
          return (
            <div
              key={`cb-${sIdx}`}
              style={{
                margin: '8px 0',
                background: '#090e17',
                border: '1px solid #1e293b',
                borderRadius: 8,
                overflow: 'hidden'
              }}
            >
              {section.lang && (
                <div
                  style={{
                    background: '#0f172a',
                    padding: '4px 10px',
                    fontSize: 11,
                    fontFamily: 'monospace',
                    color: '#64748b',
                    borderBottom: '1px solid #1e293b',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em'
                  }}
                >
                  {section.lang}
                </div>
              )}
              <pre
                style={{
                  margin: 0,
                  padding: '12px 14px',
                  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                  fontSize: 12.5,
                  lineHeight: 1.5,
                  color: '#e2e8f0',
                  overflowX: 'auto'
                }}
              >
                <code>{section.code}</code>
              </pre>
            </div>
          );
        }

        // Parse markdown text lines
        const lines = section.text.split('\n');
        const elements = [];
        let i = 0;

        while (i < lines.length) {
          const line = lines[i];
          const trimmed = line.trim();

          // Empty line
          if (!trimmed) {
            i++;
            continue;
          }

          // Horizontal rule
          if (trimmed === '---' || trimmed === '***' || trimmed === '___') {
            elements.push(
              <hr
                key={`hr-${i}`}
                style={{
                  border: 'none',
                  borderTop: `1px solid ${isUser ? 'rgba(255,255,255,0.2)' : '#334155'}`,
                  margin: '10px 0'
                }}
              />
            );
            i++;
            continue;
          }

          // Markdown Table (| ... |)
          if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
            const tableLines = [];
            while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
              tableLines.push(lines[i].trim());
              i++;
            }

            if (tableLines.length >= 2) {
              const parseRow = rowStr =>
                rowStr
                  .slice(1, -1)
                  .split('|')
                  .map(c => c.trim());

              const headerCells = parseRow(tableLines[0]);
              // Check if 2nd line is separator |---|---|
              const isSep = tableLines[1].replace(/[-| :]/g, '').length === 0;
              const dataRows = (isSep ? tableLines.slice(2) : tableLines.slice(1)).map(parseRow);

              elements.push(
                <div
                  key={`tbl-${i}`}
                  style={{
                    overflowX: 'auto',
                    margin: '10px 0',
                    borderRadius: 8,
                    border: `1px solid ${isUser ? 'rgba(255,255,255,0.2)' : '#334155'}`
                  }}
                >
                  <table
                    style={{
                      width: '100%',
                      borderCollapse: 'collapse',
                      fontSize: 12.5,
                      background: isUser ? 'rgba(0,0,0,0.15)' : '#0f172a'
                    }}
                  >
                    <thead>
                      <tr style={{ background: isUser ? 'rgba(0,0,0,0.3)' : '#1e293b' }}>
                        {headerCells.map((h, hIdx) => (
                          <th
                            key={hIdx}
                            style={{
                              padding: '8px 12px',
                              textAlign: 'left',
                              color: isUser ? '#ffffff' : '#38bdf8',
                              fontWeight: 700,
                              borderBottom: `1px solid ${isUser ? 'rgba(255,255,255,0.2)' : '#334155'}`
                            }}
                          >
                            {renderInlineFormatting(h, isUser)}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {dataRows.map((row, rIdx) => (
                        <tr
                          key={rIdx}
                          style={{
                            borderBottom: `1px solid ${isUser ? 'rgba(255,255,255,0.08)' : '#1e293b'}`
                          }}
                        >
                          {row.map((cell, cIdx) => (
                            <td key={cIdx} style={{ padding: '7px 12px', color: isUser ? '#f1f5f9' : '#e2e8f0' }}>
                              {renderInlineFormatting(cell, isUser)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              );
              continue;
            }
          }

          // Blockquote (> text)
          if (trimmed.startsWith('>')) {
            const quoteLines = [];
            while (i < lines.length && lines[i].trim().startsWith('>')) {
              quoteLines.push(lines[i].trim().replace(/^>\s?/, ''));
              i++;
            }
            elements.push(
              <div
                key={`bq-${i}`}
                style={{
                  borderLeft: `3px solid ${isUser ? '#60a5fa' : '#38bdf8'}`,
                  padding: '6px 12px',
                  margin: '6px 0',
                  background: isUser ? 'rgba(0,0,0,0.15)' : '#0b1329',
                  borderRadius: '0 6px 6px 0',
                  color: isUser ? '#dbeafe' : '#94a3b8',
                  fontSize: 13,
                  fontStyle: 'italic'
                }}
              >
                {quoteLines.map((ql, qIdx) => (
                  <div key={qIdx}>{renderInlineFormatting(ql, isUser)}</div>
                ))}
              </div>
            );
            continue;
          }

          // Headings (#, ##, ###, ####)
          if (trimmed.startsWith('#')) {
            const headingMatch = trimmed.match(/^(#{1,4})\s+(.+)$/);
            if (headingMatch) {
              const level = headingMatch[1].length;
              const text = headingMatch[2];

              if (level === 1) {
                elements.push(
                  <h3
                    key={`h1-${i}`}
                    style={{
                      margin: '12px 0 6px',
                      fontSize: 17,
                      fontWeight: 700,
                      color: isUser ? '#ffffff' : '#38bdf8',
                      letterSpacing: '-0.01em',
                      borderBottom: `1px solid ${isUser ? 'rgba(255,255,255,0.2)' : '#1e293b'}`,
                      paddingBottom: 4
                    }}
                  >
                    {renderInlineFormatting(text, isUser)}
                  </h3>
                );
              } else if (level === 2) {
                elements.push(
                  <h4
                    key={`h2-${i}`}
                    style={{
                      margin: '10px 0 4px',
                      fontSize: 15.5,
                      fontWeight: 700,
                      color: isUser ? '#f8fafc' : '#7dd3fc',
                      letterSpacing: '-0.01em'
                    }}
                  >
                    {renderInlineFormatting(text, isUser)}
                  </h4>
                );
              } else if (level === 3) {
                elements.push(
                  <h5
                    key={`h3-${i}`}
                    style={{
                      margin: '8px 0 3px',
                      fontSize: 14.5,
                      fontWeight: 600,
                      color: isUser ? '#e2e8f0' : '#bae6fd'
                    }}
                  >
                    {renderInlineFormatting(text, isUser)}
                  </h5>
                );
              } else {
                elements.push(
                  <div
                    key={`h4-${i}`}
                    style={{
                      margin: '6px 0 2px',
                      fontSize: 13.5,
                      fontWeight: 600,
                      color: isUser ? '#cbd5e1' : '#94a3b8',
                      textTransform: 'uppercase',
                      letterSpacing: '0.04em'
                    }}
                  >
                    {renderInlineFormatting(text, isUser)}
                  </div>
                );
              }

              i++;
              continue;
            }
          }

          // Unordered Lists (- item, * item, • item)
          if (/^[-*•]\s+/.test(trimmed)) {
            const listItems = [];
            while (i < lines.length && /^[-*•]\s+/.test(lines[i].trim())) {
              listItems.push(lines[i].trim().replace(/^[-*•]\s+/, ''));
              i++;
            }
            elements.push(
              <ul
                key={`ul-${i}`}
                style={{
                  margin: '6px 0',
                  paddingLeft: 20,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 4
                }}
              >
                {listItems.map((item, lIdx) => (
                  <li
                    key={lIdx}
                    style={{
                      color: isUser ? '#f1f5f9' : '#e2e8f0',
                      lineHeight: 1.55,
                      fontSize: 13.5
                    }}
                  >
                    {renderInlineFormatting(item, isUser)}
                  </li>
                ))}
              </ul>
            );
            continue;
          }

          // Numbered Lists (1. item)
          if (/^\d+\.\s+/.test(trimmed)) {
            const numItems = [];
            while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
              numItems.push(lines[i].trim().replace(/^\d+\.\s+/, ''));
              i++;
            }
            elements.push(
              <ol
                key={`ol-${i}`}
                style={{
                  margin: '6px 0',
                  paddingLeft: 20,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 4
                }}
              >
                {numItems.map((item, lIdx) => (
                  <li
                    key={lIdx}
                    style={{
                      color: isUser ? '#f1f5f9' : '#e2e8f0',
                      lineHeight: 1.55,
                      fontSize: 13.5
                    }}
                  >
                    {renderInlineFormatting(item, isUser)}
                  </li>
                ))}
              </ol>
            );
            continue;
          }

          // Normal Paragraph Lines
          const pLines = [];
          while (
            i < lines.length &&
            lines[i].trim() &&
            !lines[i].trim().startsWith('#') &&
            !lines[i].trim().startsWith('>') &&
            !lines[i].trim().startsWith('|') &&
            !lines[i].trim().startsWith('---') &&
            !/^[-*•]\s+/.test(lines[i].trim()) &&
            !/^\d+\.\s+/.test(lines[i].trim())
          ) {
            pLines.push(lines[i]);
            i++;
          }

          elements.push(
            <p
              key={`p-${i}`}
              style={{
                margin: '3px 0',
                color: isUser ? '#f8fafc' : '#e2e8f0',
                lineHeight: 1.6,
                fontSize: 13.5
              }}
            >
              {pLines.map((pl, plIdx) => (
                <React.Fragment key={plIdx}>
                  {renderInlineFormatting(pl, isUser)}
                  {plIdx < pLines.length - 1 && <br />}
                </React.Fragment>
              ))}
            </p>
          );
        }

        return <React.Fragment key={`sec-${sIdx}`}>{elements}</React.Fragment>;
      })}
    </div>
  );
}
