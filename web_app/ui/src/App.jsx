import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './pages/Login';
import DashboardSidebar from './components/DashboardSidebar';
import axiosClient from './api/axiosClient';

import {
  ReactFlow,
  addEdge,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  Panel,
  Handle,
  Position,
  useReactFlow,
  ReactFlowProvider
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';

// --- DAGRE LAYOUT ---
const getLayoutedElements = (nodes, edges) => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  // Removed align to prevent weird shifting
  dagreGraph.setGraph({ rankdir: 'LR', nodesep: 25, ranksep: 200 });

  nodes.forEach((node) => {
    if (!node.hidden) {
      dagreGraph.setNode(node.id, { width: 180, height: 40 });
    }
  });

  edges.forEach((edge) => {
    if (!edge.hidden) {
      dagreGraph.setEdge(edge.source, edge.target);
    }
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    if (!node.hidden && dagreGraph.hasNode(node.id)) {
      const nodeWithPosition = dagreGraph.node(node.id);
      return {
        ...node,
        targetPosition: 'left',
        sourcePosition: 'right',
        position: {
          x: nodeWithPosition.x - 90,
          y: nodeWithPosition.y - 20,
        },
        style: { ...node.style, transition: 'transform 0.4s cubic-bezier(0.25, 0.8, 0.25, 1)' }
      };
    }
    return node;
  });

  return { nodes: layoutedNodes, edges };
};

// --- CUSTOM NODE ---
const MindmapNode = ({ id, data }) => {
  const [isHovered, setIsHovered] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);
  const { setNodes, setEdges, getNodes, getEdges } = useReactFlow();

  const applyLayoutAndState = (newNodes, newEdges) => {
    const layouted = getLayoutedElements(newNodes, newEdges);
    setNodes(layouted.nodes);
    setEdges(layouted.edges);
    data.saveHistory(layouted.nodes, layouted.edges);
  };

  const handleToggle = () => {
    const allNodes = getNodes();
    const allEdges = getEdges();
    const isExpanded = data.isExpanded;

    const getDescendants = (nodeId, edgesList) => {
      let desc = [];
      const children = edgesList.filter(e => e.source === nodeId).map(e => e.target);
      for (const child of children) {
        desc.push(child);
        desc = desc.concat(getDescendants(child, edgesList));
      }
      return desc;
    };

    const descendants = getDescendants(id, allEdges);
    const immediateChildren = allEdges.filter(e => e.source === id).map(e => e.target);

    const newNodes = allNodes.map(n => {
      if (isExpanded && descendants.includes(n.id)) {
        return { ...n, hidden: true, data: { ...n.data, isExpanded: false } };
      }
      if (!isExpanded && immediateChildren.includes(n.id)) {
        return { ...n, hidden: false };
      }
      if (n.id === id) {
        return { ...n, data: { ...n.data, isExpanded: !isExpanded } };
      }
      return n;
    });

    const newEdges = allEdges.map(e => {
      if (isExpanded && descendants.includes(e.target)) return { ...e, hidden: true };
      if (!isExpanded && immediateChildren.includes(e.target)) return { ...e, hidden: false };
      return e;
    });
    
    // SYNCHRONOUS LAYOUT
    applyLayoutAndState(newNodes, newEdges);
  };

  const handleAdd = (e) => {
    e.stopPropagation();
    const name = prompt("Enter new node name:");
    if (!name) return;
    const newNodeId = `node_${Date.now()}`;
    
    const newNode = {
      id: newNodeId,
      type: 'mindmap',
      data: { label: name, isExpanded: true, saveHistory: data.saveHistory },
      position: { x: 0, y: 0 },
      hidden: false
    };
    
    const newEdge = {
      id: `e-${id}-${newNodeId}`,
      source: id,
      target: newNodeId,
      type: 'bezier',
      style: { stroke: '#ccc', strokeWidth: 1.5 }
    };

    const newNodes = getNodes().concat(newNode).map(n => n.id === id ? { ...n, data: { ...n.data, isExpanded: true } } : n);
    const newEdges = getEdges().concat(newEdge);
    applyLayoutAndState(newNodes, newEdges);
  };

  const handleDelete = (e) => {
    e.stopPropagation();
    const getDescendants = (nodeId, edgesList) => {
      let desc = [];
      const children = edgesList.filter(e => e.source === nodeId).map(e => e.target);
      for (const child of children) {
        desc.push(child);
        desc = desc.concat(getDescendants(child, edgesList));
      }
      return desc;
    };
    const toDelete = [id, ...getDescendants(id, getEdges())];

    const newNodes = getNodes().filter(n => !toDelete.includes(n.id));
    const newEdges = getEdges().filter(e => !toDelete.includes(e.source) && !toDelete.includes(e.target));
    applyLayoutAndState(newNodes, newEdges);
  };

  const hasChildren = getEdges().some(e => e.source === id);

  return (
    <div 
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        display: 'flex', alignItems: 'center', background: '#fff', border: '1px solid #ddd',
        borderRadius: '20px', padding: '8px 15px', fontSize: '13px', color: '#333', cursor: 'pointer',
        boxShadow: isHovered ? '0 4px 12px rgba(0,0,0,0.15)' : '0 1px 3px rgba(0,0,0,0.05)',
        transition: 'all 0.2s ease', position: 'relative'
      }}
      onClick={handleToggle}
    >
      <Handle type="target" position={Position.Left} style={{ background: '#a0c0e8', width: '8px', height: '8px', border: 'none' }} />
      
      <div style={{ padding: '0 5px', userSelect: 'none', display: 'flex', alignItems: 'center' }}>
        {data.label}
        {data.contexts_by_patent && Object.keys(data.contexts_by_patent).length > 0 && (
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center', marginLeft: 6 }}
               onMouseEnter={() => setShowTooltip(true)}
               onMouseLeave={() => setShowTooltip(false)}>
            <span style={{ cursor: 'help', fontSize: '13px', opacity: 0.7 }}>ℹ️</span>
            {showTooltip && (
              <div style={{
                position: 'absolute', bottom: '100%', left: '50%', transform: 'translateX(-50%)', marginBottom: 8,
                width: 300, background: '#222', color: '#fff', padding: '10px 14px', borderRadius: 8,
                fontSize: 12, zIndex: 1000, boxShadow: '0 8px 24px rgba(0,0,0,0.2)', lineHeight: 1.4,
                cursor: 'default', maxHeight: '200px', overflowY: 'auto'
              }} onClick={(e) => e.stopPropagation()}>
                <div style={{ fontWeight: 'bold', marginBottom: 8, color: '#a0c0e8', borderBottom: '1px solid #444', paddingBottom: 4 }}>Patent Contexts</div>
                {Object.entries(data.contexts_by_patent).map(([pid, ctxs], idx, arr) => (
                  <div key={pid} style={{ marginBottom: idx < arr.length - 1 ? 8 : 0 }}>
                    <div style={{ fontWeight: 'bold', color: '#ffd700', fontSize: '11px', marginBottom: 2 }}>{pid}</div>
                    {ctxs.map((ctx, i) => (
                      <div key={i} style={{ paddingLeft: 6, borderLeft: '2px solid #555', marginBottom: 4 }}>
                        "{ctx}"
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        {hasChildren && <span style={{ marginLeft: 8, color: '#aaa', fontSize: '10px' }}>{data.isExpanded ? '▼' : '▶'}</span>}
      </div>

      {isHovered && (
        <div style={{ position: 'absolute', top: -35, left: '50%', transform: 'translateX(-50%)', display: 'flex', gap: 6, background: 'white', padding: '4px', borderRadius: 6, border: '1px solid #ccc', boxShadow: '0 4px 10px rgba(0,0,0,0.1)', zIndex: 100 }}>
          <button onClick={handleAdd} style={{ cursor: 'pointer', border: 'none', background: '#d4edda', color: '#155724', borderRadius: 4, padding: '4px 10px', fontSize: 14, fontWeight: 'bold' }}>+</button>
          <button onClick={handleDelete} style={{ cursor: 'pointer', border: 'none', background: '#f8d7da', color: '#721c24', borderRadius: 4, padding: '4px 10px', fontSize: 14, fontWeight: 'bold' }}>-</button>
        </div>
      )}

      <Handle type="source" position={Position.Right} style={{ background: '#a0c0e8', width: '8px', height: '8px', border: 'none' }} />
    </div>
  );
};

// --- EDITOR ---
function TaxonomyEditor({ currentRunId, setCurrentRunId, onRunComplete, showSidebar, setShowSidebar }) {
  const { logout, userName, userId } = useAuth();
  const [patentInput, setPatentInput] = useState('');
  const [status, setStatus] = useState('idle');
  const [showHelp, setShowHelp] = useState(true);
  const [currentRunName, setCurrentRunName] = useState('');
  
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const { getNodes, getEdges } = useReactFlow();

  // Undo/Redo State
  const history = useRef([]);
  const historyPointer = useRef(-1);

  const saveHistory = useCallback((n, e) => {
    const newHistory = history.current.slice(0, historyPointer.current + 1);
    newHistory.push({ nodes: JSON.parse(JSON.stringify(n)), edges: JSON.parse(JSON.stringify(e)) });
    history.current = newHistory;
    historyPointer.current = newHistory.length - 1;
  }, []);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
        if (historyPointer.current > 0) {
          historyPointer.current -= 1;
          const prevState = history.current[historyPointer.current];
          setNodes(prevState.nodes);
          setEdges(prevState.edges);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [setNodes, setEdges]);

  // Handle switching runs from the sidebar
  useEffect(() => {
    if (currentRunId && status !== 'running') {
      fetchGraph(currentRunId);
    } else if (!currentRunId) {
      // Clear the canvas when creating a new session
      setNodes([]);
      setEdges([]);
      setStatus('idle');
      history.current = [];
      historyPointer.current = -1;
    }
  }, [currentRunId]);

  const nodeTypes = useMemo(() => ({ mindmap: MindmapNode }), []);

  const handleRunPipeline = async () => {
    try {
      if (currentRunId) {
        setCurrentRunId(null);
        setNodes([]);
        setEdges([]);
      }
      setStatus('running');
      const patentList = patentInput.split(',').map((id) => id.trim());
      const res = await axiosClient.post(`/api/build-taxonomy`, { patent_ids: patentList });
      if (onRunComplete) onRunComplete(); // Trigger immediate refresh to show pending status in sidebar
      pollStatus(res.data.run_id);
    } catch (error) {
      alert("Error starting pipeline.");
      setStatus('idle');
    }
  };

  const pollStatus = async (id) => {
    const interval = setInterval(async () => {
      try {
        const res = await axiosClient.get(`/api/status/${id}`);
        if (res.data.status === 'completed') {
          clearInterval(interval);
          setStatus('completed');
          setCurrentRunId(id);
          fetchGraph(id);
          if (onRunComplete) onRunComplete(); // Trigger refresh to show completed status
        } else if (res.data.status === 'failed') {
          clearInterval(interval);
          setStatus('idle');
          if (onRunComplete) onRunComplete();
          alert("Pipeline failed: " + res.data.error);
        }
      } catch (e) {
        if (e.response && e.response.status === 404) {
          clearInterval(interval);
          setStatus('idle');
          console.warn("Pipeline interrupted (server restart or invalid ID).");
        }
      }
    }, 5000);
  };

  const fetchGraph = async (id) => {
    try {
      const res = await axiosClient.get(`/api/taxonomy/${id}`);
      if (res.data.name) {
        setCurrentRunName(res.data.name);
      }
      const taxonomyArray = res.data.taxonomy;

      const initialNodes = [];
      const initialEdges = [];

      taxonomyArray.forEach((item) => {
        const isHidden = item.level > 1; 
        const isExpanded = item.level <= 0;

        initialNodes.push({
          id: item.node_id,
          type: 'mindmap',
          data: { 
            label: item.name, 
            isExpanded, 
            saveHistory, 
            patent_contexts: item.patent_contexts,
            contexts_by_patent: item.contexts_by_patent,
            contexts_by_pmid: item.contexts_by_pmid,
            supporting_patent_ids: item.supporting_patent_ids,
            supporting_pmids: item.supporting_pmids
          },
          position: { x: 0, y: 0 },
          hidden: isHidden
        });

        if (item.parent_node_id) {
          initialEdges.push({
            id: `e-${item.parent_node_id}-${item.node_id}`,
            source: item.parent_node_id,
            target: item.node_id,
            type: 'bezier',
            style: { stroke: '#ccc', strokeWidth: 1.5 },
            hidden: isHidden
          });
        }
      });

      const layouted = getLayoutedElements(initialNodes, initialEdges);
      setNodes(layouted.nodes);
      setEdges(layouted.edges);
      
      history.current = [{ nodes: layouted.nodes, edges: layouted.edges }];
      historyPointer.current = 0;
    } catch (error) {
      console.error("Failed to load graph", error);
      alert("Failed to load the taxonomy graph. You might not have permission.");
    }
  };

  const onConnect = useCallback(
    (params) => {
      const newEdge = { ...params, type: 'bezier', style: { stroke: '#ccc', strokeWidth: 1.5 } };
      const newEdges = getEdges().concat(newEdge);
      const layouted = getLayoutedElements(getNodes(), newEdges);
      setNodes(layouted.nodes);
      setEdges(layouted.edges);
      saveHistory(layouted.nodes, layouted.edges);
    },
    [getNodes, getEdges, setNodes, setEdges, saveHistory]
  );

  const onEdgesDelete = useCallback(
    (edgesToDelete) => {
      const allEdges = getEdges();
      const allNodes = getNodes();
      let edgesToRemove = [...edgesToDelete];
      let nodesToRemove = [];
      
      edgesToDelete.forEach(deletedEdge => {
        const targetId = deletedEdge.target;
        const incomingEdges = allEdges.filter(e => e.target === targetId && !edgesToDelete.find(d => d.id === e.id));
        
        if (incomingEdges.length === 0) {
          const getDescendants = (nodeId, currentEdges) => {
            let desc = [nodeId];
            const children = currentEdges.filter(e => e.source === nodeId).map(e => e.target);
            for (const child of children) {
              desc = desc.concat(getDescendants(child, currentEdges));
            }
            return desc;
          };
          const toDelete = getDescendants(targetId, allEdges);
          nodesToRemove = [...new Set([...nodesToRemove, ...toDelete])];
        }
      });

      if (nodesToRemove.length > 0) {
         const newNodes = allNodes.filter(n => !nodesToRemove.includes(n.id));
         const newEdges = allEdges.filter(e => !nodesToRemove.includes(e.source) && !nodesToRemove.includes(e.target) && !edgesToRemove.find(d => d.id === e.id));
         const layouted = getLayoutedElements(newNodes, newEdges);
         setNodes(layouted.nodes);
         setEdges(layouted.edges);
         saveHistory(layouted.nodes, layouted.edges);
      }
    },
    [getNodes, getEdges, setNodes, setEdges, saveHistory]
  );

  const handleDownload = async () => {
    try {
      setStatus('running'); 
      const response = await axiosClient.post(`/api/download-excel/${currentRunId}`, {
        nodes: getNodes(),
        edges: getEdges()
      }, {
        responseType: 'blob'
      });
      
      let filename = `Taxonomy_Matrix_${currentRunId}.xlsx`;
      const disposition = response.headers['content-disposition'];
      if (disposition && disposition.indexOf('filename=') !== -1) {
          const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
          const matches = filenameRegex.exec(disposition);
          if (matches != null && matches[1]) { 
              filename = matches[1].replace(/['"]/g, '');
          }
      } else if (currentRunName) {
         filename = `${currentRunName.replace(/ /g, '_')}.xlsx`;
      }
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      setStatus('completed');
    } catch (error) {
      console.error(error);
      alert("Failed to download excel");
      setStatus('completed');
    }
  };

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: 15, background: '#fff', borderBottom: '1px solid #eee', display: 'flex', alignItems: 'center', boxShadow: '0 2px 4px rgba(0,0,0,0.05)', zIndex: 10 }}>
        <button 
          onClick={() => setShowSidebar(!showSidebar)}
          title="Toggle Sidebar"
          style={{ background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '20px', marginRight: '15px' }}
        >
          {showSidebar ? '◀' : '☰'}
        </button>
        <h3 style={{ margin: 0, marginRight: 20 }}>
          {currentRunId ? 'Viewing Taxonomy' : 'Create New Taxonomy'}
        </h3>
        
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '15px' }}>
          {currentRunId && (
            <button onClick={handleDownload} 
                    style={{ padding: '8px 15px', background: '#28a745', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>
              Download Excel Report 📥
            </button>
          )}
          <span style={{ fontSize: '13px', color: '#555', fontWeight: 'bold', display: 'flex', alignItems: 'center' }}>
            <span style={{ marginRight: '6px', fontSize: '16px' }}>👤</span>
            {userName || `User ${userId}`}
          </span>
          <button 
            onClick={logout} 
            title="Logout"
            style={{ padding: '8px 10px', background: '#b91c1c', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
              <polyline points="16 17 21 12 16 7"></polyline>
              <line x1="21" y1="12" x2="9" y2="12"></line>
            </svg>
          </button>
        </div>
      </div>

      <div style={{ flex: 1, background: '#fdfdfd', position: 'relative' }}>
        {!currentRunId && status === 'idle' && (
           <div style={{ position: 'absolute', top: '40%', left: '50%', transform: 'translate(-50%, -50%)', textAlign: 'center', color: '#888', zIndex: 5 }}>
              <div style={{ fontSize: '48px', marginBottom: '10px' }}>📊</div>
              <h2>What would you like to build?</h2>
              <p>Enter your Patent or PubMed IDs in the chat bar below.</p>
           </div>
        )}
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
              <div style={{ position: 'relative', background: 'white', padding: '12px 30px 12px 15px', borderRadius: 8, border: '1px solid #ddd', fontSize: '13px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
                  <button onClick={() => setShowHelp(false)} style={{ position: 'absolute', right: '5px', top: '5px', border: 'none', background: 'transparent', cursor: 'pointer', color: '#888', fontWeight: 'bold' }}>✖</button>
                  <b>Editable UI:</b> Hover over nodes for <b>[+]</b> and <b>[-]</b> buttons. Click nodes to collapse/expand. Press <b>Ctrl+Z</b> to Undo.<br/>
                  <span style={{color: '#555', marginTop: '4px', display: 'inline-block'}}>
                    <b>Assign node:</b> Drag a node's right handle to another node's left handle.<br/>
                    <b>Delete edge:</b> Click on a connection line and press Backspace.
                  </span>
              </div>
            ) : (
              <button onClick={() => setShowHelp(true)} style={{ background: 'white', padding: '5px 10px', borderRadius: '8px', border: '1px solid #ddd', cursor: 'pointer', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
                 ℹ️ Help
              </button>
            )}
          </Panel>
          <Controls />
          <Background color="#eee" gap={20} size={1} />
        </ReactFlow>
      </div>

      {/* ChatGPT Style Bottom Input Bar */}
      <div style={{ padding: '20px', background: 'white', borderTop: '1px solid #eaeaea', display: 'flex', justifyContent: 'center', zIndex: 10 }}>
        <div style={{ display: 'flex', width: '800px', maxWidth: '100%', background: '#f4f4f4', borderRadius: '24px', padding: '8px 12px', alignItems: 'center', boxShadow: '0 2px 6px rgba(0,0,0,0.05)' }}>
            <button 
              title="Upload Excel (Coming Soon)"
              style={{ background: 'transparent', border: 'none', fontSize: '20px', cursor: 'pointer', color: '#555', padding: '0 10px', display: 'flex', alignItems: 'center' }}
              onClick={() => alert("Excel upload functionality coming soon!")}
            >
              ➕
            </button>
            <input 
              type="text" 
              value={patentInput} 
              onChange={(e) => setPatentInput(e.target.value)} 
              placeholder="Message Taxonomy AI or enter Patent / PubMed IDs..."
              style={{ flex: 1, background: 'transparent', border: 'none', padding: '10px', fontSize: '15px', outline: 'none' }}
              onKeyDown={(e) => { if (e.key === 'Enter') handleRunPipeline(); }}
            />
            <button 
              onClick={handleRunPipeline} 
              disabled={status === 'running'} 
              style={{ background: status === 'running' ? '#ccc' : '#000', color: 'white', border: 'none', borderRadius: '50%', width: '36px', height: '36px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }}
            >
              {status === 'running' ? '⏳' : '↑'}
            </button>
        </div>
      </div>
    </div>
  );
}

// --- MAIN LAYOUT ---
function AppLayout() {
  const [currentRunId, setCurrentRunId] = useState(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [showSidebar, setShowSidebar] = useState(true);

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden' }}>
      {showSidebar && <DashboardSidebar currentRunId={currentRunId} onSelectRun={setCurrentRunId} refreshTrigger={refreshTrigger} />}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative' }}>
        <TaxonomyEditor 
          currentRunId={currentRunId} 
          setCurrentRunId={setCurrentRunId} 
          onRunComplete={() => setRefreshTrigger(prev => prev + 1)} 
          showSidebar={showSidebar}
          setShowSidebar={setShowSidebar}
        />
      </div>
    </div>
  );
}

// --- APP ---
export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={
              <ReactFlowProvider>
                <AppLayout />
              </ReactFlowProvider>
            } />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
