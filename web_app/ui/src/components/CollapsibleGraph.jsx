import React, { useState } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  Panel,
  MiniMap
} from 'reactflow';
import 'reactflow/dist/style.css';

export default function CollapsibleGraph({
  nodes,
  edges,
  nodeTypes,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onEdgesDelete,
  currentRunName,
  runId,
  isMinimized,
  onToggleMinimize,
  isMaximized,
  onToggleMaximize,
  onPreviewExcel,
  isGeneratingPreview,
  onOpenAnalytics,
  status = 'completed'
}) {
  const [showHelp, setShowHelp] = useState(false);

  const totalNodes = nodes.filter(n => !n.hidden).length;

  if (isMinimized) {
    return (
      <div style={{
        position: 'absolute',
        top: 14,
        right: 18,
        zIndex: 50,
        background: '#1e293b',
        border: '1px solid #38bdf8',
        borderRadius: 24,
        padding: '6px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        boxShadow: '0 4px 16px rgba(2, 132, 199, 0.35)',
        cursor: 'pointer',
        transition: 'all 0.2s ease'
      }}
      onClick={onToggleMinimize}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {status === 'running' ? (
            <div style={{
              width: 14,
              height: 14,
              borderRadius: '50%',
              border: '2px solid #38bdf8',
              borderTopColor: 'transparent',
              animation: 'spin 1s linear infinite'
            }} />
          ) : (
            <span style={{ fontSize: 16 }}>🌿</span>
          )}
          <span style={{ fontSize: 13, fontWeight: 700, color: '#f8fafc' }}>
            {status === 'running' ? 'Preparing Graph...' : (currentRunName || 'Taxonomy Graph')}
          </span>
          {status !== 'running' && (
            <span style={{ fontSize: 11, background: '#0284c7', color: '#f0f9ff', padding: '1px 8px', borderRadius: 10, fontWeight: 600 }}>
              {totalNodes} nodes
            </span>
          )}
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); onToggleMinimize(); }}
          style={{
            background: '#0284c7',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            padding: '4px 10px',
            fontSize: 11,
            fontWeight: 700,
            cursor: 'pointer'
          }}
        >
          ⤢ Expand Graph
        </button>
      </div>
    );
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      width: '100%',
      background: '#ffffff',
      position: 'relative',
      overflow: 'hidden',
      borderLeft: '1px solid #e2e8f0'
    }}>
      {/* Graph Top Action Bar */}
      <div style={{
        padding: '10px 16px',
        background: '#f8fafc',
        borderBottom: '1px solid #e2e8f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0,
        zIndex: 10
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <span style={{ fontSize: 18 }}>🌿</span>
          <div style={{ minWidth: 0 }}>
            <div style={{
              fontSize: 14,
              fontWeight: 700,
              color: '#0f172a',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              maxWidth: '320px'
            }}>
              {currentRunName || 'Taxonomy Hierarchy'}
            </div>
            <div style={{ fontSize: 11, color: '#64748b' }}>
              Interactive Mindmap • {totalNodes} visible nodes
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {onPreviewExcel && (
            <button
              onClick={onPreviewExcel}
              disabled={isGeneratingPreview}
              title="Preview Spreadsheet Matrix"
              style={{
                padding: '5px 12px',
                background: '#0284c7',
                color: 'white',
                border: 'none',
                borderRadius: 6,
                cursor: isGeneratingPreview ? 'wait' : 'pointer',
                fontWeight: 600,
                fontSize: 12,
                display: 'flex',
                alignItems: 'center',
                gap: 5
              }}
            >
              <span>{isGeneratingPreview ? '⏳ Loading...' : '📥 Preview Excel'}</span>
            </button>
          )}

          {onOpenAnalytics && (
            <button
              onClick={onOpenAnalytics}
              title="View In-Depth Analytics Dashboard"
              style={{
                padding: '5px 12px',
                background: '#f1f5f9',
                color: '#334155',
                border: '1px solid #cbd5e1',
                borderRadius: 6,
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: 12,
                display: 'flex',
                alignItems: 'center',
                gap: 5
              }}
            >
              <span>📊 Analytics</span>
            </button>
          )}

          {/* Toggle Fullscreen / Maximize */}
          <button
            onClick={onToggleMaximize}
            title={isMaximized ? "Restore Split View" : "Maximize Graph Fullscreen"}
            style={{
              padding: '5px 10px',
              background: '#f1f5f9',
              color: '#334155',
              border: '1px solid #cbd5e1',
              borderRadius: 6,
              cursor: 'pointer',
              fontSize: 13,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            {isMaximized ? '◫ Split' : '⤢ Full'}
          </button>

          {/* Minimize Graph button */}
          <button
            onClick={onToggleMinimize}
            title="Minimize Graph to focus on Chat"
            style={{
              padding: '5px 10px',
              background: '#f1f5f9',
              color: '#334155',
              border: '1px solid #cbd5e1',
              borderRadius: 6,
              cursor: 'pointer',
              fontSize: 13,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            ─
          </button>
        </div>
      </div>

      {/* ReactFlow Interactive Graph Canvas or Preparing State */}
      <div style={{ flex: 1, position: 'relative', minHeight: 0, minWidth: 0 }}>
        {status === 'running' ? (
          <div style={{
            height: '100%',
            width: '100%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'linear-gradient(180deg, #0f172a 0%, #090d16 100%)',
            color: '#f8fafc',
            padding: 32,
            textAlign: 'center'
          }}>
            <div style={{
              width: 56,
              height: 56,
              borderRadius: '50%',
              border: '4px solid #0284c7',
              borderTopColor: '#38bdf8',
              animation: 'spin 1s linear infinite',
              marginBottom: 20,
              boxShadow: '0 0 24px rgba(56, 189, 248, 0.3)'
            }} />
            <div style={{ fontSize: 20, fontWeight: 700, color: '#f8fafc', marginBottom: 8 }}>
              Preparing Taxonomy Graph...
            </div>
            <div style={{ fontSize: 13, color: '#94a3b8', maxWidth: 440, lineHeight: 1.6, marginBottom: 16 }}>
              Extracting hierarchical patent concepts, clustering technology branches, and mapping claims against your commercial product model.
            </div>
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              padding: '6px 14px',
              borderRadius: 20,
              background: '#1e293b',
              border: '1px solid #334155',
              fontSize: 12,
              color: '#38bdf8'
            }}>
              <span>⚡ Active Pipeline Session: {runId ? runId.slice(0, 8) : 'Generating'}</span>
            </div>
          </div>
        ) : (
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onEdgesDelete={onEdgesDelete}
          fitView
          minZoom={0.1}
        >
          <Panel position="bottom-center">
            {showHelp ? (
              <div style={{
                position: 'relative',
                background: 'white',
                padding: '12px 30px 12px 16px',
                borderRadius: 8,
                border: '1px solid #e2e8f0',
                fontSize: 12,
                boxShadow: '0 4px 16px rgba(0,0,0,0.1)',
                lineHeight: 1.5,
                color: '#334155'
              }}>
                <button
                  onClick={() => setShowHelp(false)}
                  style={{
                    position: 'absolute',
                    right: 6,
                    top: 6,
                    border: 'none',
                    background: 'transparent',
                    cursor: 'pointer',
                    color: '#94a3b8',
                    fontWeight: 'bold'
                  }}
                >
                  ✕
                </button>
                <b>Interactive Mindmap:</b> Hover over nodes for <b>[+]</b> and <b>[-]</b> buttons. Click nodes to collapse/expand.<br />
                <span style={{ color: '#64748b' }}>
                  • <b>Assign node:</b> Drag right handle to another node's left handle.<br />
                  • <b>Delete edge:</b> Select line and press Backspace.<br />
                  • <b>Undo:</b> Press <b>Ctrl+Z</b> anytime.
                </span>
              </div>
            ) : (
              <button
                onClick={() => setShowHelp(true)}
                style={{
                  background: 'white',
                  padding: '4px 10px',
                  borderRadius: 6,
                  border: '1px solid #e2e8f0',
                  cursor: 'pointer',
                  boxShadow: '0 2px 6px rgba(0,0,0,0.06)',
                  fontSize: 12,
                  fontWeight: 600,
                  color: '#475569'
                }}
              >
                ℹ️ Graph Guide
              </button>
            )}
          </Panel>
          <Controls />
          <MiniMap
            nodeColor="#38bdf8"
            maskColor="rgba(240, 244, 248, 0.7)"
            style={{ border: '1px solid #cbd5e1', borderRadius: 6 }}
          />
          <Background color="#cbd5e1" gap={20} size={1} />
        </ReactFlow>
        )}
      </div>
    </div>
  );
}
