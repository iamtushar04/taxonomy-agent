import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './pages/Login';
import DashboardSidebar from './components/DashboardSidebar';
import AnalyticsDashboard from './components/AnalyticsDashboard';
import ExcelPreviewModal from './components/ExcelPreviewModal';
import InlineChatView from './components/InlineChatView';
import CollapsibleGraph from './components/CollapsibleGraph';
import ChatDrawer from './components/ChatDrawer';
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
  const [showProductTooltip, setShowProductTooltip] = useState(false);
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
        {data.supporting_product_ids && data.supporting_product_ids.length > 0 && (
          <div 
            style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', marginLeft: 6 }}
            onMouseEnter={() => setShowProductTooltip(true)}
            onMouseLeave={() => setShowProductTooltip(false)}
            onClick={(e) => e.stopPropagation()}
          >
            <span
              style={{
                background: '#065f46',
                color: '#6ee7b7',
                fontSize: '10px',
                fontWeight: 700,
                padding: '2px 7px',
                borderRadius: 10,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                cursor: 'pointer',
                border: '1px solid #059669',
                boxShadow: showProductTooltip ? '0 0 8px rgba(110,231,183,0.5)' : 'none'
              }}
            >
              📦 {data.supporting_product_ids.length}
            </span>

            {/* Rich Commercial Product Tooltip Popover */}
            {showProductTooltip && (
              <div 
                style={{
                  position: 'absolute',
                  bottom: '125%',
                  left: '50%',
                  transform: 'translateX(-50%)',
                  marginBottom: 8,
                  width: 320,
                  background: '#0f172a',
                  color: '#f8fafc',
                  padding: '12px 14px',
                  borderRadius: 10,
                  fontSize: 12,
                  zIndex: 9999,
                  boxShadow: '0 12px 28px rgba(0,0,0,0.4), 0 0 0 1px #334155',
                  lineHeight: 1.4,
                  cursor: 'default',
                  maxHeight: '280px',
                  overflowY: 'auto'
                }}
                onClick={(e) => e.stopPropagation()}
              >
                {/* Node-specific header */}
                <div style={{ fontWeight: 'bold', marginBottom: 6, color: '#6ee7b7', borderBottom: '1px solid #1e293b', paddingBottom: 6, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span>📦 {data.label}</span>
                  <span style={{ fontSize: 10, color: '#94a3b8' }}>Commercial Alignment</span>
                </div>

                {/* Node Technical Definition / Description */}
                {data.description && (
                  <div style={{ fontSize: 11, color: '#cbd5e1', marginBottom: 8, background: '#1e293b', padding: '6px 8px', borderRadius: 6, borderLeft: '2px solid #059669', lineHeight: 1.35 }}>
                    {data.description}
                  </div>
                )}

                {data.supporting_product_ids.map(prodId => {
                  const pInfo = data.products_map?.[prodId] || {
                    product_name: prodId,
                    brand_or_assignee: 'Unknown Vendor',
                    features: []
                  };

                  // Filter features specifically relevant to this node name or keywords
                  const nodeKeywords = data.label.toLowerCase().split(/\s+/).filter(w => w.length > 3);
                  const relevantFeatures = (pInfo.features || []).filter(feat => {
                    const fLower = feat.toLowerCase();
                    return nodeKeywords.some(kw => fLower.includes(kw));
                  });

                  // If specific features matched, show those; otherwise show top 2 features with attribution
                  const displayFeatures = relevantFeatures.length > 0 
                    ? relevantFeatures 
                    : (pInfo.features || []).slice(0, 2);

                  return (
                    <div key={prodId} style={{ marginTop: 6, paddingBottom: 6, borderBottom: '1px solid #1e293b' }}>
                      <div style={{ fontWeight: 700, color: '#f1f5f9', fontSize: 12, marginBottom: 2 }}>
                        {pInfo.product_name || prodId}
                      </div>
                      <div style={{ fontSize: 11, color: '#38bdf8', marginBottom: 4 }}>
                        Vendor: {pInfo.brand_or_assignee || 'Unknown'} {pInfo.source_filename && `• ${pInfo.source_filename}`}
                      </div>

                      {displayFeatures.length > 0 && (
                        <div style={{ marginTop: 4 }}>
                          <div style={{ fontSize: 10, fontWeight: 700, color: relevantFeatures.length > 0 ? '#10b981' : '#94a3b8', textTransform: 'uppercase', marginBottom: 3 }}>
                            {relevantFeatures.length > 0 ? `🎯 Node-Specific Features (${displayFeatures.length}):` : 'Product Capabilities:'}
                          </div>
                          {displayFeatures.map((feat, fi) => (
                            <div key={fi} style={{ paddingLeft: 6, borderLeft: `2px solid ${relevantFeatures.length > 0 ? '#10b981' : '#334155'}`, color: '#e2e8f0', fontSize: 11, marginBottom: 3 }}>
                              "{feat}"
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
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
function TaxonomyEditor({ currentRunId, setCurrentRunId, onRunComplete, onOptimisticRun, showSidebar, setShowSidebar }) {
  const { logout, userName, userId } = useAuth();
  const [status, setStatus] = useState('idle');
  const [currentRunName, setCurrentRunName] = useState('');
  const [activeTab, setActiveTab] = useState('graph');   // 'graph' | 'analytics'
  const [isPubmed, setIsPubmed] = useState(false);
  const [taxonomyData, setTaxonomyData] = useState([]);  // raw taxonomy array for analytics
  
  // Graph collapse/expand state
  const [isGraphMinimized, setIsGraphMinimized] = useState(false);
  const [isGraphMaximized, setIsGraphMaximized] = useState(false);

  // Excel Preview & Download
  const [excelPreviewData, setExcelPreviewData] = useState(null);
  const [isGeneratingPreview, setIsGeneratingPreview] = useState(false);
  const [isDownloadingExcel, setIsDownloadingExcel] = useState(false);

  // Draggable Split Screen State
  const [chatWidthPercent, setChatWidthPercent] = useState(42);
  const [isDraggingSplitter, setIsDraggingSplitter] = useState(false);
  const splitContainerRef = useRef(null);

  useEffect(() => {
    if (!isDraggingSplitter) return;

    const handleMouseMove = (e) => {
      if (!splitContainerRef.current) return;
      const rect = splitContainerRef.current.getBoundingClientRect();
      const currentX = e.clientX - rect.left;
      const newPercent = (currentX / rect.width) * 100;
      // Clamp between 20% and 80%
      const clamped = Math.max(20, Math.min(80, newPercent));
      setChatWidthPercent(clamped);
    };

    const handleMouseUp = () => {
      setIsDraggingSplitter(false);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDraggingSplitter]);

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const { getNodes, getEdges } = useReactFlow();

  // Undo/Redo State
  const history = useRef([]);
  const historyPointer = useRef(-1);

  // Background pollers to track ongoing jobs across multiple sessions without cross-session bleeding
  const runningPollersRef = useRef(new Map());
  const currentRunIdRef = useRef(currentRunId);
  const [runStage, setRunStage] = useState(null);

  useEffect(() => {
    currentRunIdRef.current = currentRunId;
  }, [currentRunId]);

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

  // Clean up all background intervals on unmount
  useEffect(() => {
    return () => {
      runningPollersRef.current.forEach(interval => clearInterval(interval));
      runningPollersRef.current.clear();
    };
  }, []);

  // Poll status for a given run ID safely in the background
  const ensurePolling = useCallback((id) => {
    if (!id) return;
    if (runningPollersRef.current.has(id)) {
      return; // Already polling this run
    }

    const interval = setInterval(async () => {
      try {
        const res = await axiosClient.get(`/api/status/${id}`);
        const runStatus = res.data.status;

        // Live verification & pipeline stage tracking
        if (currentRunIdRef.current === id && res.data.stage) {
          setRunStage({
            stage: res.data.stage,
            title: res.data.stage_title,
            description: res.data.stage_description,
            step: res.data.step || 1,
            totalSteps: res.data.total_steps || 5
          });
        }

        if (runStatus === 'completed') {
          clearInterval(interval);
          runningPollersRef.current.delete(id);
          if (onRunComplete) onRunComplete();

          // Only update UI if the user is currently viewing this exact session
          if (currentRunIdRef.current === id) {
            setRunStage(null);
            setStatus('completed');
            setIsGraphMinimized(false);
            setIsGraphMaximized(false);
            fetchGraph(id);
          }
        } else if (runStatus === 'failed') {
          clearInterval(interval);
          runningPollersRef.current.delete(id);
          if (onRunComplete) onRunComplete();

          if (currentRunIdRef.current === id) {
            setRunStage(null);
            setStatus('failed');
            alert("Pipeline failed: " + (res.data.error || "Unknown error"));
          }
        }
      } catch (e) {
        if (e.response && e.response.status === 404) {
          clearInterval(interval);
          runningPollersRef.current.delete(id);
          if (currentRunIdRef.current === id) {
            setStatus('idle');
          }
        }
      }
    }, 3000);

    runningPollersRef.current.set(id, interval);
  }, [onRunComplete]);

  // Handle switching runs from the sidebar
  useEffect(() => {
    let isCancelled = false;

    if (!currentRunId) {
      setNodes([]);
      setEdges([]);
      setStatus('idle');
      setCurrentRunName('');
      setTaxonomyData([]);
      setIsPubmed(false);
      setActiveTab('graph');
      setIsGraphMinimized(true);
      setIsGraphMaximized(false);
      history.current = [];
      historyPointer.current = -1;
      return;
    }

    // Existing or preparing run selected
    const checkAndLoadRun = async () => {
      try {
        const statusRes = await axiosClient.get(`/api/status/${currentRunId}`);
        if (isCancelled) return;
        const runStatus = statusRes.data.status;

        if (runStatus === 'running' || runStatus === 'pending') {
          setStatus('running');
          setNodes([]);
          setEdges([]);
          setTaxonomyData([]);
          setIsGraphMinimized(false);
          setIsGraphMaximized(false);
          ensurePolling(currentRunId);
        } else if (runStatus === 'completed') {
          setStatus('completed');
          setIsGraphMinimized(false);
          setIsGraphMaximized(false);
          fetchGraph(currentRunId);
        } else if (runStatus === 'failed') {
          setStatus('failed');
          setNodes([]);
          setEdges([]);
          setTaxonomyData([]);
          alert("Pipeline previously failed: " + (statusRes.data.error || 'Unknown error'));
        }
      } catch (err) {
        if (isCancelled) return;
        console.error("Failed to check status for run", currentRunId, err);
        fetchGraph(currentRunId);
      }
    };

    checkAndLoadRun();

    return () => {
      isCancelled = true;
    };
  }, [currentRunId, ensurePolling]);

  const nodeTypes = useMemo(() => ({ mindmap: MindmapNode }), []);

  const handleStartPipeline = async (patentList, uploadId, contextGuidance, messagesList = [], mentalModelObj = null, productLinksList = []) => {
    // 1. Generate unique 8-character run ID on the client immediately at 0ms!
    const immediateRunId = (typeof crypto !== 'undefined' && crypto.randomUUID) 
      ? crypto.randomUUID().replace(/-/g, '').slice(0, 8) 
      : Math.random().toString(36).substring(2, 10);

    const isPubmed = patentList && patentList.some(pid => /^\d+$/.test(pid.trim()));
    const initialName = patentList && patentList.length > 0 
      ? `${isPubmed ? 'PubMed' : 'Patent'} Graph (${patentList.length} items)`
      : 'Patent Graph';

    const optimisticSession = {
      id: immediateRunId,
      name: initialName,
      status: 'running',
      created_at: new Date().toISOString()
    };

    // 2. Immediately create and display the session at the left sidebar at the moment of the request!
    setCurrentRunId(immediateRunId);
    if (onOptimisticRun) onOptimisticRun(optimisticSession);

    try {
      setStatus('running');
      setNodes([]);
      setEdges([]);
      setTaxonomyData([]);
      setIsGraphMinimized(false);
      setIsGraphMaximized(false);

      const payload = {
        run_id: immediateRunId,
        patent_ids: patentList,
        session_upload_id: uploadId,
        product_urls: productLinksList && productLinksList.length > 0 ? productLinksList : undefined,
        mental_model_context: contextGuidance,
        messages: messagesList,
        mental_model: mentalModelObj
      };
      const res = await axiosClient.post(`/api/build-taxonomy`, payload);
      const newRunId = res.data.run_id || immediateRunId;

      // Clear new session draft since it's now an active run
      sessionStorage.removeItem('tax_copilot_draft');

      // Immediately activate the new run ID if different
      if (newRunId !== immediateRunId) {
        setCurrentRunId(newRunId);
      }

      // Refresh sidebar to sync with backend DB
      if (onRunComplete) onRunComplete();

      // Begin background polling
      ensurePolling(newRunId);
    } catch (error) {
      alert("Error starting pipeline: " + (error.response?.data?.detail || error.message));
      setStatus('idle');
      if (onOptimisticRun) onOptimisticRun({ id: immediateRunId, status: 'failed' });
    }
  };

  const handleTriggeredRun = (targetRunId) => {
    if (!targetRunId) return;
    setStatus('running');
    setNodes([]);
    setEdges([]);
    setTaxonomyData([]);
    setIsGraphMinimized(false);
    setIsGraphMaximized(false);
    // Refresh sidebar so the existing run reflects 'running' without adding any new item
    if (onRunComplete) onRunComplete();
    ensurePolling(targetRunId);
  };

  const fetchGraph = async (id) => {
    try {
      const res = await axiosClient.get(`/api/taxonomy/${id}`);
      if (res.data.name) {
        setCurrentRunName(res.data.name);
      }
      const taxonomyArray = res.data.taxonomy;
      const productsMap = res.data.products_map || {};
      const patentsMeta = res.data.patents_meta || {};
      setTaxonomyData(taxonomyArray || []);
      const hasPmids = taxonomyArray?.some(n => n.supporting_pmids?.length > 0);
      setIsPubmed(!!hasPmids);

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
            description: item.description,
            isExpanded, 
            saveHistory, 
            patent_contexts: item.patent_contexts,
            contexts_by_patent: item.contexts_by_patent,
            contexts_by_pmid: item.contexts_by_pmid,
            supporting_patent_ids: item.supporting_patent_ids,
            supporting_pmids: item.supporting_pmids,
            supporting_product_ids: item.supporting_product_ids || [],
            products_map: productsMap,
            patents_meta: patentsMeta
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
      setIsGraphMinimized(false);
      
      history.current = [{ nodes: layouted.nodes, edges: layouted.edges }];
      historyPointer.current = 0;
    } catch (error) {
      console.error("Failed to load graph", error);
      if (error.response?.status !== 400) {
        alert("Failed to load the taxonomy graph: " + (error.response?.data?.detail || error.message));
      }
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

  const handlePreviewExcel = async () => {
    if (!currentRunId) return;
    try {
      setIsGeneratingPreview(true);
      const response = await axiosClient.post(`/api/preview-excel/${currentRunId}`, {
        nodes: getNodes(),
        edges: getEdges()
      });
      setExcelPreviewData(response.data);
    } catch (error) {
      console.error("Preview failed:", error);
      alert("Failed to generate Excel preview: " + (error.response?.data?.detail || error.message));
    } finally {
      setIsGeneratingPreview(false);
    }
  };

  const handleDownload = async () => {
    try {
      setIsDownloadingExcel(true);
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
    } catch (error) {
      console.error(error);
      alert("Failed to download excel");
    } finally {
      setIsDownloadingExcel(false);
    }
  };

  return (
    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0, overflow: 'hidden' }}>
      {/* Top Navbar */}
      <div style={{
        padding: '10px 16px',
        background: '#1e293b',
        borderBottom: '1px solid #334155',
        display: 'flex',
        alignItems: 'center',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
        zIndex: 20,
        gap: 12
      }}>
        {/* Sidebar toggle */}
        <button 
          onClick={() => setShowSidebar(!showSidebar)}
          title="Toggle Sidebar"
          style={{ background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '18px', color: '#94a3b8', flexShrink: 0 }}
        >
          {showSidebar ? '◀' : '☰'}
        </button>

        {/* Page / Session title */}
        <h3 style={{ margin: 0, fontSize: 15, whiteSpace: 'nowrap', color: '#f8fafc', fontWeight: 600 }}>
          {currentRunId ? (currentRunName || `Taxonomy: ${currentRunId.slice(0, 8)}`) : 'New Taxonomy Workspace'}
        </h3>

        {/* Tab switcher — visible when a session is loaded */}
        {currentRunId && (
          <div style={{ display: 'flex', background: '#0f172a', borderRadius: 8, padding: 3, gap: 2, border: '1px solid #334155' }}>
            {[['graph', '🌿 Workspace & Chat'], ['analytics', '📊 Analytics']].map(([key, label]) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                style={{
                  padding: '5px 14px',
                  border: 'none',
                  borderRadius: 6,
                  cursor: 'pointer',
                  fontSize: 12,
                  fontWeight: 600,
                  transition: 'all 0.15s',
                  background: activeTab === key ? '#0284c7' : 'transparent',
                  color: activeTab === key ? '#ffffff' : '#94a3b8',
                  boxShadow: activeTab === key ? '0 1px 4px rgba(0,0,0,0.2)' : 'none',
                }}
              >
                {label}
              </button>
            ))}
          </div>
        )}

        {/* Right side: user + Excel actions + logout */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '10px' }}>
          {currentRunId && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginRight: '4px' }}>
              <button
                onClick={handlePreviewExcel}
                disabled={isGeneratingPreview}
                title="Preview Spreadsheet with exact merged hierarchy & download options"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '6px 14px',
                  background: '#0f172a',
                  border: '1px solid #38bdf8',
                  borderRadius: 6,
                  color: '#38bdf8',
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: isGeneratingPreview ? 'wait' : 'pointer',
                  transition: 'all 0.15s ease',
                  boxShadow: '0 1px 4px rgba(56, 189, 248, 0.15)'
                }}
              >
                <span>{isGeneratingPreview ? '⏳' : '📊'}</span>
                <span>{isGeneratingPreview ? 'Loading Preview...' : 'Preview Excel'}</span>
              </button>
            </div>
          )}
          <span style={{ fontSize: '13px', color: '#cbd5e1', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>👤</span>
            <span>{userName || `User ${userId}`}</span>
          </span>
          <button 
            onClick={logout} 
            title="Logout"
            style={{
              padding: '6px 10px',
              background: '#ef4444',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 1px 3px rgba(0,0,0,0.2)'
            }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
              <polyline points="16 17 21 12 16 7"></polyline>
              <line x1="21" y1="12" x2="9" y2="12"></line>
            </svg>
          </button>
        </div>
      </div>

      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', display: 'flex', minHeight: 0, minWidth: 0 }}>
        {/* ── ANALYTICS TAB ─────────────────────────────────────────── */}
        {activeTab === 'analytics' && currentRunId && (
          <div style={{ flex: 1, background: '#0a0f1e', overflowY: 'auto', minHeight: 0, minWidth: 0, height: '100%' }}>
            <AnalyticsDashboard
              runId={currentRunId}
              taxonomy={taxonomyData}
              isPubmed={isPubmed}
            />
          </div>
        )}

        {/* ── UNIFIED WORKSPACE (CONVERSATION + GRAPH) ─────────────────── */}
        {activeTab === 'graph' && (
          <div 
            ref={splitContainerRef}
            style={{ 
              flex: 1, 
              display: 'flex', 
              minHeight: 0, 
              minWidth: 0, 
              position: 'relative', 
              width: '100%', 
              height: '100%',
              userSelect: isDraggingSplitter ? 'none' : 'auto',
              cursor: isDraggingSplitter ? 'col-resize' : 'auto'
            }}
          >
            {/* Conversational Hub */}
            <div style={{
              flex: (!currentRunId || isGraphMinimized) ? '1 1 100%' : (isGraphMaximized ? '0 0 0' : `0 0 ${chatWidthPercent}%`),
              width: isGraphMaximized ? 0 : ((!currentRunId || isGraphMinimized) ? '100%' : `${chatWidthPercent}%`),
              display: isGraphMaximized ? 'none' : 'flex',
              flexDirection: 'column',
              minWidth: 0,
              height: '100%',
              transition: isDraggingSplitter ? 'none' : 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
              zIndex: 5
            }}>
              <InlineChatView
                runId={currentRunId}
                currentRunName={currentRunName}
                status={status}
                onStartPipeline={handleStartPipeline}
                onTriggeredRun={handleTriggeredRun}
                isGraphAvailable={!!currentRunId && (nodes.length > 0 || status === 'running')}
                isGraphMinimized={isGraphMinimized}
                onToggleGraphMinimize={() => {
                  setIsGraphMinimized(prev => !prev);
                  if (isGraphMaximized) setIsGraphMaximized(false);
                }}
                onOpenAnalytics={() => setActiveTab('analytics')}
                onPreviewExcel={handlePreviewExcel}
                runStage={runStage}
              />
            </div>

            {/* Draggable Splitter Handle */}
            {currentRunId && !isGraphMinimized && !isGraphMaximized && (
              <div
                onMouseDown={(e) => {
                  e.preventDefault();
                  setIsDraggingSplitter(true);
                }}
                title="Drag left or right to resize Chat & Graph panes"
                style={{
                  width: '6px',
                  background: isDraggingSplitter ? '#38bdf8' : '#334155',
                  cursor: 'col-resize',
                  position: 'relative',
                  zIndex: 20,
                  transition: 'background 0.15s ease',
                  flexShrink: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
                onMouseEnter={e => {
                  if (!isDraggingSplitter) e.currentTarget.style.background = '#0284c7';
                }}
                onMouseLeave={e => {
                  if (!isDraggingSplitter) e.currentTarget.style.background = '#334155';
                }}
              >
                {/* Visual grab notches */}
                <div style={{
                  width: '2px',
                  height: '28px',
                  borderRadius: '2px',
                  background: isDraggingSplitter ? '#ffffff' : '#94a3b8'
                }} />
              </div>
            )}

            {/* Collapsible / Interactive Graph View */}
            {currentRunId && !isGraphMinimized && (
              <div style={{
                flex: isGraphMaximized ? '1 1 100%' : `0 0 ${100 - chatWidthPercent}%`,
                width: isGraphMaximized ? '100%' : `${100 - chatWidthPercent}%`,
                minWidth: 0,
                display: 'flex',
                height: '100%',
                position: 'relative',
                transition: isDraggingSplitter ? 'none' : 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
                zIndex: 4,
                pointerEvents: isDraggingSplitter ? 'none' : 'auto'
              }}>
                <CollapsibleGraph
                  nodes={nodes}
                  edges={edges}
                  nodeTypes={nodeTypes}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  onConnect={onConnect}
                  onEdgesDelete={onEdgesDelete}
                  currentRunName={currentRunName}
                  runId={currentRunId}
                  status={status}
                  isMinimized={false}
                  onToggleMinimize={() => setIsGraphMinimized(true)}
                  isMaximized={isGraphMaximized}
                  onToggleMaximize={() => setIsGraphMaximized(prev => !prev)}
                  onPreviewExcel={handlePreviewExcel}
                  isGeneratingPreview={isGeneratingPreview}
                  onOpenAnalytics={() => setActiveTab('analytics')}
                  runStage={runStage}
                />
              </div>
            )}

            {/* Minimized Graph Floating Status Pill */}
            {currentRunId && isGraphMinimized && (
              <CollapsibleGraph
                nodes={nodes}
                edges={edges}
                nodeTypes={nodeTypes}
                currentRunName={currentRunName}
                runId={currentRunId}
                status={status}
                isMinimized={true}
                onToggleMinimize={() => {
                  setIsGraphMinimized(false);
                  setIsGraphMaximized(false);
                }}
              />
            )}
          </div>
        )}
      </div>

      {/* Full-fidelity Excel Spreadsheet Preview Modal */}
      {excelPreviewData && (
        <ExcelPreviewModal
          previewData={excelPreviewData}
          onClose={() => setExcelPreviewData(null)}
          onDownload={handleDownload}
          isDownloading={isDownloadingExcel}
        />
      )}
    </div>
  );
}

// --- MAIN LAYOUT ---
function AppLayout() {
  const [currentRunId, setCurrentRunId] = useState(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [showSidebar, setShowSidebar] = useState(true);
  const [optimisticRun, setOptimisticRun] = useState(null);

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden' }}>
      {showSidebar && (
        <DashboardSidebar 
          currentRunId={currentRunId} 
          onSelectRun={setCurrentRunId} 
          refreshTrigger={refreshTrigger} 
          optimisticRun={optimisticRun}
        />
      )}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', position: 'relative' }}>
        <TaxonomyEditor 
          currentRunId={currentRunId} 
          setCurrentRunId={setCurrentRunId} 
          onRunComplete={() => setRefreshTrigger(prev => prev + 1)} 
          onOptimisticRun={setOptimisticRun}
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
