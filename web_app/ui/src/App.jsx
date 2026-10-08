import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react';
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
import axios from 'axios';

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
    
    // SYNCHRONOUS LAYOUT (Fixes overlapping nodes bug!)
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

// --- MAIN APP ---
function TaxonomyEditor() {
  const [patentInput, setPatentInput] = useState('US20170349734A1, US11691998B2');
  const [status, setStatus] = useState('idle');
  const [currentRunId, setCurrentRunId] = useState(null);
  
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

  const nodeTypes = useMemo(() => ({ mindmap: MindmapNode }), []);

  const handleRunPipeline = async () => {
    try {
      setStatus('running');
      const patentList = patentInput.split(',').map((id) => id.trim());
      const res = await axios.post('http://127.0.0.1:8000/api/build-taxonomy', { patent_ids: patentList });
      pollStatus(res.data.run_id);
    } catch (error) {
      alert("Error starting pipeline.");
      setStatus('idle');
    }
  };

  const pollStatus = async (id) => {
    const interval = setInterval(async () => {
      try {
        const res = await axios.get(`http://127.0.0.1:8000/api/status/${id}`);
        if (res.data.status === 'completed') {
          clearInterval(interval);
          setStatus('completed');
          setCurrentRunId(id);
          fetchGraph(id);
        } else if (res.data.status === 'failed') {
          clearInterval(interval);
          setStatus('idle');
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
    const res = await axios.get(`http://127.0.0.1:8000/api/taxonomy/${id}`);
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
          contexts_by_pmid: item.contexts_by_pmid
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
      setStatus('running'); // visual feedback
      const response = await axios.post(`http://127.0.0.1:8000/api/download-excel/${currentRunId}`, {
        nodes: getNodes(),
        edges: getEdges()
      }, {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Taxonomy_Matrix_${currentRunId}.xlsx`);
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
    <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: 15, background: '#fff', borderBottom: '1px solid #eee', display: 'flex', alignItems: 'center', boxShadow: '0 2px 4px rgba(0,0,0,0.05)', zIndex: 10 }}>
        <h3 style={{ margin: 0, marginRight: 20 }}>Taxonomy Graph</h3>
        <input 
          type="text" value={patentInput} onChange={(e) => setPatentInput(e.target.value)} 
          style={{ width: '300px', padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }}
        />
        <button onClick={handleRunPipeline} disabled={status === 'running'} style={{ marginLeft: 10, padding: '8px 15px', background: '#007bff', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>
          {status === 'running' ? 'Running Pipeline...' : 'Generate Graph'}
        </button>
        {currentRunId && (
          <button onClick={handleDownload} 
                  style={{ marginLeft: 10, padding: '8px 15px', background: '#28a745', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>
            Download Excel Report 📥
          </button>
        )}
      </div>

      <div style={{ flex: 1, background: '#fdfdfd' }}>
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
             <div style={{ background: 'white', padding: '10px', borderRadius: 8, border: '1px solid #ddd', fontSize: '14px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
                <b>Editable UI:</b> Hover over nodes for <b>[+]</b> and <b>[-]</b> buttons. Click nodes to collapse/expand. Press <b>Ctrl+Z</b> to Undo.
             </div>
          </Panel>
          <Controls />
          <Background color="#eee" gap={20} size={1} />
        </ReactFlow>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ReactFlowProvider>
      <TaxonomyEditor />
    </ReactFlowProvider>
  );
}
