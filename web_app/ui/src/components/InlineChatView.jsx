import React, { useState, useEffect, useRef, useCallback } from 'react';
import axiosClient from '../api/axiosClient';
import TaxonomySetupPanel from './TaxonomySetupPanel';
import ProductCardCarousel from './ProductCardCarousel';
import FormattedMessageContent from './FormattedMessageContent';

export default function InlineChatView({
  runId,
  currentRunName,
  status,
  onStartPipeline,
  onTriggeredRun,
  isGraphAvailable,
  isGraphMinimized,
  onToggleGraphMinimize,
  onOpenAnalytics,
  onPreviewExcel,
  runStage = null
}) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  
  // Product & Patent ingestion state
  const [sessionUploadId, setSessionUploadId] = useState(null);
  const [uploadedProducts, setUploadedProducts] = useState([]);
  const [productLinks, setProductLinks] = useState([]);
  const [customInstructions, setCustomInstructions] = useState('');
  const [mentalModel, setMentalModel] = useState(null);
  const [patentIds, setPatentIds] = useState([]);
  
  const messagesEndRef = useRef(null);
  const prevRunIdRef = useRef(null);
  const messagesRef = useRef(messages);
  const isSubmittingPipelineRef = useRef(false);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading, status]);

  // Helper to format timestamp safely without "Invalid Date"
  const formatTimestamp = (ts) => {
    if (!ts) return '';
    if (typeof ts === 'string' && (ts.includes('AM') || ts.includes('PM') || (ts.includes(':') && !ts.includes('T') && !ts.includes('-')))) {
      return ts;
    }
    const d = new Date(ts);
    if (isNaN(d.getTime())) return '';
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const fetchHistory = useCallback(async (id = runId) => {
    if (!id) return;
    setLoading(true);
    try {
      const res = await axiosClient.get(`/api/chat/${id}/history`);
      if (res.data.messages && res.data.messages.length > 0) {
        setMessages(res.data.messages.map((m, idx) => ({
          id: `hist-${idx}-${Date.now()}`,
          role: m.role,
          content: m.content,
          intent: m.intent,
          metadata: m.metadata || {},
          isProductCard: !!(m.metadata?.isProductCard || m.isProductCard),
          mentalModel: m.metadata?.mentalModel || m.mentalModel || (m.metadata?.isProductCard ? res.data.mental_model : null),
          timestamp: formatTimestamp(m.timestamp)
        })));
      } else {
        setMessages([
          {
            id: 'run-welcome',
            role: 'assistant',
            content: res.data.greeting || `🌿 **Taxonomy Loaded: ${currentRunName || id.slice(0, 8)}**\n\nThe taxonomy graph is visible on the right. Ask me anything about node classifications, patent contexts, or type *'Map X under Y'* to reorganize branches.`,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          }
        ]);
      }
      if (res.data.mental_model) {
        setMentalModel(res.data.mental_model);
      }
    } catch (err) {
      console.error('Failed to load chat history for run ' + id, err);
      setMessages([
        {
          id: 'run-welcome-err',
          role: 'assistant',
          content: `🌿 **Taxonomy Loaded: ${currentRunName || id.slice(0, 8)}**\n\nThe taxonomy graph is visible on the right. Ask me anything about node classifications, patent contexts, or type *'Map X under Y'* to reorganize branches.`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setLoading(false);
    }
  }, [runId, currentRunName]);

  // Initial greeting when in New Taxonomy mode, or fetch history for existing run
  useEffect(() => {
    try {
      sessionStorage.removeItem('tax_copilot_draft');
    } catch (e) {}

    if (!runId) {
      setMessages([
        {
          id: 'welcome-msg',
          role: 'assistant',
          content: "👋 **Welcome to Taxonomy Co-Pilot!**\n\nI can help you build structured, evidence-backed patent and scientific taxonomies tailored to your domain.\n\n**To get started, you can:**\n1. 📦 **Upload your product document** (.pdf, .docx, .xlsx) — I'll extract technical capabilities and prioritize relevant patent categories.\n2. 🧬 **Provide patent or PubMed IDs** (e.g., `US10293847`, `34567890`) and tell me what technical areas to focus on.\n3. 💬 **Chat with me** directly below with your requirements!",
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
      setSessionUploadId(null);
      setUploadedProducts([]);
      setMentalModel(null);
      setPatentIds([]);
      setProductLinks([]);
      setCustomInstructions('');
      return;
    }

    // Existing run selected: clear transient input state
    setMentalModel(null);
    setPatentIds([]);
    setUploadedProducts([]);
    setProductLinks([]);
    fetchHistory(runId);
  }, [runId, fetchHistory]);

  // When pipeline finishes ('running' -> 'completed'), reload history so completion message appears automatically
  const prevStatusRef = useRef(status);
  useEffect(() => {
    if (runId && prevStatusRef.current === 'running' && status === 'completed') {
      fetchHistory(runId);
    }
    prevStatusRef.current = status;
  }, [status, runId, fetchHistory]);

  // Handle uploading product documents (.pdf, .docx, .xlsx, .csv)
  const processProductFiles = async (files) => {
    if (!files || files.length === 0) return;

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
    }

    setIsUploading(true);
    const userNotice = {
      id: `usr-upload-${Date.now()}`,
      role: 'user',
      content: `📎 Attached ${files.length} product document(s): ${Array.from(files).map(f => f.name).join(', ')}`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    setMessages(prev => [...prev, userNotice]);

    try {
      const res = await axiosClient.post('/api/products/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      const uploadId = res.data.session_upload_id;
      setSessionUploadId(uploadId);
      setUploadedProducts(res.data.products || []);

      // Trigger AI understanding extraction
      const analyzeRes = await axiosClient.post('/api/chat/pre-run/analyze-product', {
        session_upload_id: uploadId
      });

      const extracted = {
        ...analyzeRes.data.mental_model,
        products: res.data.products || analyzeRes.data.products || []
      };
      setMentalModel(extracted);

      const prodCount = (res.data.products || []).length;
      const assistantMsg = {
        id: `ast-upload-${Date.now()}`,
        role: 'assistant',
        isProductCard: true,
        mentalModel: extracted,
        content: prodCount > 1
          ? `I've analyzed **${prodCount} product documents**.\n\nBrowse the carousel below to inspect each product's specifications and technical capabilities!`
          : `I've analyzed your product specification for **${extracted.product_name}**.\n\nReview the capabilities and priority areas below. You can refine the focus or provide your Patent IDs to build!`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, assistantMsg]);

    } catch (err) {
      console.error(err);
      const errMsg = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: `⚠️ Failed to process product files: ${err.response?.data?.detail || err.message}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setIsUploading(false);
      const panelInput = document.getElementById('panel-product-file-input');
      if (panelInput) panelInput.value = '';
    }
  };

  // Handle ingesting product from web links / URLs
  const processProductUrls = async (urls) => {
    if (!urls || urls.length === 0) return;

    setIsUploading(true);
    const userNotice = {
      id: `usr-links-${Date.now()}`,
      role: 'user',
      content: `🔗 Provided ${urls.length} product link(s):\n${urls.map((u, i) => `${i + 1}. ${u}`).join('\n')}`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    setMessages(prev => [...prev, userNotice]);

    try {
      const res = await axiosClient.post('/api/products/urls', { urls });
      const uploadId = res.data.session_upload_id;
      setSessionUploadId(uploadId);
      setUploadedProducts(res.data.products || []);

      // Trigger AI understanding extraction from the fetched specification
      const analyzeRes = await axiosClient.post('/api/chat/pre-run/analyze-product', {
        session_upload_id: uploadId
      });

      const extracted = {
        ...analyzeRes.data.mental_model,
        products: res.data.products || analyzeRes.data.products || []
      };
      setMentalModel(extracted);

      const prodCount = (res.data.products || []).length;
      const assistantMsg = {
        id: `ast-links-${Date.now()}`,
        role: 'assistant',
        isProductCard: true,
        mentalModel: extracted,
        content: prodCount > 1
          ? `I've fetched and extracted specifications for **${prodCount} products**.\n\nBrowse the carousel below to view the technical capabilities for each product!`
          : `I've fetched and extracted the specifications from your link(s) for **${extracted.product_name}**.\n\nReview the capabilities and priority areas below. You can refine the focus or provide your Patent IDs to build!`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, assistantMsg]);

    } catch (err) {
      console.error(err);
      const errMsg = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: `⚠️ Failed to process product links: ${err.response?.data?.detail || err.message}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setIsUploading(false);
    }
  };

  // Trigger building taxonomy with extracted mental model and patents
  const handleTriggerBuild = async (overridePatentIds = null, overrideLinks = null) => {
    if (isSubmittingPipelineRef.current) return;
    isSubmittingPipelineRef.current = true;

    const idsToUse = overridePatentIds || patentIds;
    if (!idsToUse || idsToUse.length === 0) {
      const promptMsg = {
        id: `ast-prompt-${Date.now()}`,
        role: 'assistant',
        content: "Please provide at least one Patent ID or PubMed ID (e.g. `US10293847`, `US9876543`) in the configuration panel above to build the taxonomy.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, promptMsg]);
      isSubmittingPipelineRef.current = false;
      return;
    }

    let activeUploadId = sessionUploadId;
    let activeMentalModel = mentalModel;
    const linksToUse = (overrideLinks && overrideLinks.length > 0) ? overrideLinks : productLinks;

    // AUTO-EXTRACT PRODUCT LINKS IF NOT EXTRACTED YET
    if (!activeUploadId && linksToUse && linksToUse.length > 0) {
      setIsUploading(true);

      // 1. Post immediate status to UI: Fetching products
      const fetchNotice = {
        id: `usr-links-${Date.now()}`,
        role: 'user',
        content: `🔗 Ingesting ${linksToUse.length} product link(s) for taxonomy context:\n${linksToUse.map((u, i) => `${i + 1}. ${u}`).join('\n')}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      const extractingMsg = {
        id: `ast-fetching-${Date.now()}`,
        role: 'assistant',
        content: `⏳ **Step 1/2: Fetching & Extracting Product Specifications...**\nReading multi-page documents, specification tables, and technical parameters from ${linksToUse.length} link(s)...`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, fetchNotice, extractingMsg]);

      try {
        const res = await axiosClient.post('/api/products/urls', { urls: linksToUse });
        activeUploadId = res.data.session_upload_id;
        setSessionUploadId(activeUploadId);
        setUploadedProducts(res.data.products || []);

        const analyzeRes = await axiosClient.post('/api/chat/pre-run/analyze-product', {
          session_upload_id: activeUploadId
        });
        const productsList = res.data.products || analyzeRes.data.products || [];
        activeMentalModel = {
          ...analyzeRes.data.mental_model,
          products: productsList
        };
        setMentalModel(activeMentalModel);

        // 2. SHOW PRODUCT SPECIFICATIONS CAROUSEL CARD ON UI!
        const productCardMsg = {
          id: `ast-product-card-${Date.now()}`,
          role: 'assistant',
          isProductCard: true,
          mentalModel: activeMentalModel,
          content: productsList.length > 1
            ? `✅ **Specifications Extracted for ${productsList.length} Products**\n\nDomain: **${activeMentalModel.domain}**\n\nBrowse each product in the carousel below. Now proceeding to build taxonomy grounded in these specifications!`
            : `✅ **Product Specifications Extracted: ${activeMentalModel.product_name}**\n\nDomain: **${activeMentalModel.domain}**\n\nReviewing key technical capabilities and priority focus areas below. Now proceeding to build taxonomy grounded in these specifications!`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages(prev => [...prev, productCardMsg]);

        // Brief 1.5s delay so the user clearly sees the extracted product card on UI before switching into building state!
        await new Promise(resolve => setTimeout(resolve, 1500));

      } catch (err) {
        console.error("Auto-extracting product links error:", err);
        const errMsg = {
          id: `ast-err-${Date.now()}`,
          role: 'assistant',
          content: `⚠️ Failed to extract product links: ${err.response?.data?.detail || err.message}. Continuing with patent specifications.`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages(prev => [...prev, errMsg]);
      } finally {
        setIsUploading(false);
      }
    }

    // Assemble mental model context guidance and custom instructions
    let contextGuidance = '';
    if (activeMentalModel) {
      contextGuidance = `Product: ${activeMentalModel.product_name}\nDomain: ${activeMentalModel.domain}\nPriority Focus: ${(activeMentalModel.focus_areas || []).join(', ')}\nDeprioritize: ${(activeMentalModel.avoid_areas || []).join(', ')}`;
    }
    if (linksToUse && linksToUse.length > 0) {
      contextGuidance += (contextGuidance ? '\n' : '') + `Product Web Links:\n${linksToUse.map((l, i) => `${i + 1}. ${l}`).join('\n')}`;
    }
    if (customInstructions) {
      contextGuidance += (contextGuidance ? '\n' : '') + `User Custom Guidelines / Focus:\n${customInstructions}`;
    }

    let detailParts = [];
    if (activeMentalModel) {
      detailParts.push(`Grounded in Product: ${activeMentalModel.product_name} (${activeMentalModel.domain})`);
    } else if (uploadedProducts.length > 0) {
      detailParts.push(`Product: ${uploadedProducts.map(p => p.product_name || p.source_filename).join(', ')}`);
    } else if (linksToUse && linksToUse.length > 0) {
      detailParts.push(`Product Links (${linksToUse.length})`);
    }
    if (customInstructions) {
      detailParts.push(`Focus: ${customInstructions}`);
    }

    const startMsg = {
      id: `usr-start-${Date.now()}`,
      role: 'user',
      content: `🚀 Building taxonomy for ${idsToUse.length} patent(s): ${idsToUse.join(', ')}` + (detailParts.length > 0 ? `\n(${detailParts.join(' • ')})` : ''),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    // Safely snapshot messages using ref to avoid React StrictMode duplicate updater triggers
    const currentMsgs = messagesRef.current || messages;
    const updatedMessages = [...currentMsgs, startMsg];
    const serializableMessages = updatedMessages.map(m => ({
      role: m.role || 'user',
      content: m.content || '',
      intent: m.intent || null,
      metadata: {
        ...(m.metadata || {}),
        isProductCard: !!m.isProductCard,
        mentalModel: m.mentalModel || (m.isProductCard ? activeMentalModel : null)
      },
      timestamp: m.timestamp || new Date().toISOString()
    }));

    setMessages(updatedMessages);

    setPatentIds([]);
    setUploadedProducts([]);
    setProductLinks([]);
    setCustomInstructions('');

    try {
      // Execute the pipeline trigger strictly outside setMessages so React 18 cannot invoke it twice
      await onStartPipeline(idsToUse, activeUploadId, contextGuidance, serializableMessages, activeMentalModel, linksToUse);
    } finally {
      setTimeout(() => {
        isSubmittingPipelineRef.current = false;
      }, 2000);
    }
  };

  // Send conversational message
  const handleSendMessage = async (textToSend = null) => {
    const text = (textToSend || input).trim();
    if (!text || loading || status === 'running') return;

    const userMsg = {
      id: `usr-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    setMessages(prev => [...prev, userMsg]);
    if (!textToSend) setInput('');
    setLoading(true);

    try {
      if (runId) {
        // Post-run conversation (explaining nodes, mapping rules, general questions)
        const res = await axiosClient.post(`/api/chat/${runId}/message`, { message: text });
        const assistantMsg = {
          id: `ast-${Date.now()}`,
          role: 'assistant',
          content: res.data.response || 'No response received.',
          intent: res.data.intent,
          metadata: res.data.metadata,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages(prev => [...prev, assistantMsg]);

        // If this message triggered a background taxonomy run, switch active run and begin tracking
        if (res.data.triggered_run_id && onTriggeredRun) {
          onTriggeredRun(res.data.triggered_run_id);
        }
      } else {
        // Pre-run conversation (guiding product focus, instructions, supplying patents)
        const res = await axiosClient.post('/api/chat/pre-run/message', {
          message: text,
          session_upload_id: sessionUploadId,
          mental_model: mentalModel,
          patent_ids: patentIds,
          history: messages.slice(-6).map(m => ({ role: m.role, content: m.content }))
        });

        if (res.data.mental_model) {
          setMentalModel(res.data.mental_model);
        }

        let updatedPatents = [...patentIds];
        if (res.data.detected_patent_ids && res.data.detected_patent_ids.length > 0) {
          updatedPatents = Array.from(new Set([...updatedPatents, ...res.data.detected_patent_ids]));
          setPatentIds(updatedPatents);
        }

        const assistantMsg = {
          id: `ast-${Date.now()}`,
          role: 'assistant',
          content: res.data.response,
          detectedPatents: res.data.detected_patent_ids,
          readyToBuild: res.data.ready_to_build,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages(prev => [...prev, assistantMsg]);

        // If user confirmed to start, proceed, or build, and patents are present
        const lowerText = text.toLowerCase();
        const startWords = ['start', 'then start', 'go ahead', 'proceed', 'build', 'run', 'generate', 'launch', 'do it'];
        const userWantsToStart = startWords.some(w => lowerText.includes(w));

        if ((res.data.trigger_build || userWantsToStart) && updatedPatents.length > 0) {
          handleTriggerBuild(updatedPatents);
        }
      }
    } catch (err) {
      console.error('Chat error:', err);
      const errMsg = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: `⚠️ Error: ${err.response?.data?.detail || err.message || 'Failed to communicate with assistant.'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      background: '#0f172a',
      color: '#f8fafc',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Top Banner / Session Bar */}
      <div style={{
        padding: '12px 18px',
        background: '#1e293b',
        borderBottom: '1px solid #334155',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 34,
            height: 34,
            borderRadius: 10,
            background: 'linear-gradient(135deg, #0284c7 0%, #38bdf8 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 18,
            boxShadow: '0 2px 8px rgba(2, 132, 199, 0.3)'
          }}>
            🤖
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: 8 }}>
              <span>Taxonomy Co-Pilot</span>
              {runId ? (
                <span style={{ fontSize: 11, padding: '2px 8px', background: '#0369a1', color: '#bae6fd', borderRadius: 12, fontWeight: 600 }}>
                  Active Run: {runId.slice(0, 8)}
                </span>
              ) : (
                <span style={{ fontSize: 11, padding: '2px 8px', background: '#065f46', color: '#a7f3d0', borderRadius: 12, fontWeight: 600 }}>
                  New Session
                </span>
              )}
            </div>
            <div style={{ fontSize: 11, color: '#94a3b8' }}>
              {runId ? 'Ask questions about taxonomy nodes or apply custom hierarchy rules' : 'Upload product documents, set guidelines & build customized taxonomy'}
            </div>
          </div>
        </div>

        {/* View Controls & Action buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {!runId && messages.length > 1 && (
            <button
              onClick={() => {
                setMessages([
                  {
                    id: 'welcome-msg',
                    role: 'assistant',
                    content: "👋 **Welcome to Taxonomy Co-Pilot!**\n\nI can help you build structured, evidence-backed patent and scientific taxonomies tailored to your domain.\n\n**To get started, you can:**\n1. 📦 **Upload your product document** (.pdf, .docx, .xlsx) — I'll extract technical capabilities and prioritize relevant patent categories.\n2. 🧬 **Provide patent or PubMed IDs** (e.g., `US10293847`, `34567890`) and tell me what technical areas to focus on.\n3. 💬 **Chat with me** directly below with your requirements!",
                    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                  }
                ]);
                setSessionUploadId(null);
                setUploadedProducts([]);
                setMentalModel(null);
                setPatentIds([]);
                setProductLinks([]);
                setCustomInstructions('');
              }}
              title="Start a fresh chat"
              style={{
                background: '#334155',
                color: '#cbd5e1',
                border: 'none',
                borderRadius: 8,
                padding: '6px 12px',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 5
              }}
            >
              <span>🔄 Reset Chat</span>
            </button>
          )}

          {isGraphAvailable && (
            <button
              onClick={onToggleGraphMinimize}
              title={isGraphMinimized ? "Expand Graph View" : "Minimize Graph View"}
              style={{
                background: isGraphMinimized ? '#0284c7' : '#334155',
                color: '#f8fafc',
                border: 'none',
                borderRadius: 8,
                padding: '6px 12px',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                transition: 'all 0.2s ease',
                boxShadow: isGraphMinimized ? '0 0 12px rgba(2, 132, 199, 0.4)' : 'none'
              }}
            >
              <span>{isGraphMinimized ? '⤢ Expand Graph' : '─ Minimize Graph'}</span>
            </button>
          )}
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '20px 24px',
        display: 'flex',
        flexDirection: 'column',
        gap: 16
      }}>
        {messages.map((msg) => {
          const isUser = msg.role === 'user';
          return (
            <div
              key={msg.id}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: isUser ? 'flex-end' : 'flex-start',
                maxWidth: '100%'
              }}
            >
              <div style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 10,
                maxWidth: isUser ? '85%' : (msg.id === 'welcome-msg' ? '96%' : '90%'),
                flexDirection: isUser ? 'row-reverse' : 'row'
              }}>
                {/* Avatar */}
                <div style={{
                  width: 30,
                  height: 30,
                  borderRadius: '50%',
                  background: isUser ? '#3b82f6' : '#0284c7',
                  color: 'white',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 14,
                  flexShrink: 0,
                  marginTop: 2
                }}>
                  {isUser ? '👤' : '🤖'}
                </div>

                {/* Message Bubble Container */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0, width: msg.id === 'welcome-msg' ? '100%' : 'auto' }}>
                  <div style={{
                    padding: '12px 16px',
                    borderRadius: 14,
                    borderBottomRightRadius: isUser ? 2 : 14,
                    borderBottomLeftRadius: isUser ? 14 : 2,
                    background: isUser ? '#1e40af' : '#1e293b',
                    color: '#f8fafc',
                    fontSize: 14,
                    lineHeight: 1.6,
                    border: `1px solid ${isUser ? '#3b82f6' : '#334155'}`,
                    boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
                    wordBreak: 'break-word',
                    whiteSpace: 'normal'
                  }}>
                    <FormattedMessageContent content={msg.content} isUser={isUser} />

                    {/* Dedicated Setup Panel rendered right below the welcome card */}
                    {msg.id === 'welcome-msg' && !runId && (
                      <TaxonomySetupPanel
                        patentIds={patentIds}
                        onUpdatePatentIds={setPatentIds}
                        uploadedProducts={uploadedProducts}
                        onProductUpload={processProductFiles}
                        productLinks={productLinks}
                        onUpdateProductLinks={setProductLinks}
                        onProductUrls={processProductUrls}
                        mentalModel={mentalModel}
                        onClearProduct={() => {
                          setUploadedProducts([]);
                          setMentalModel(null);
                          setSessionUploadId(null);
                          setProductLinks([]);
                        }}
                        customInstructions={customInstructions}
                        onUpdateInstructions={setCustomInstructions}
                        onTriggerBuild={(links) => handleTriggerBuild(null, links)}
                        isUploading={isUploading}
                      />
                    )}

                    {/* Rich Product Understanding Carousel Card */}
                    {msg.isProductCard && msg.mentalModel && (
                      <ProductCardCarousel
                        mentalModel={msg.mentalModel}
                        uploadedProducts={uploadedProducts}
                        patentIds={patentIds}
                        onTriggerBuild={handleTriggerBuild}
                        onSendMessage={handleSendMessage}
                        onSetInput={setInput}
                      />
                    )}

                    {/* Detected Patent IDs Callout */}
                    {msg.detectedPatents && msg.detectedPatents.length > 0 && (
                      <div style={{ marginTop: 10, padding: '8px 12px', background: '#0c4a6e', borderRadius: 8, border: '1px solid #0284c7' }}>
                        <div style={{ fontSize: 12, fontWeight: 600, color: '#7dd3fc', marginBottom: 4 }}>
                          Detected Patent IDs ({msg.detectedPatents.length}):
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                          {msg.detectedPatents.map((pid, idx) => (
                            <span key={idx} style={{ background: '#0369a1', color: '#f0f9ff', padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700 }}>
                              {pid}
                            </span>
                          ))}
                        </div>
                        <button
                          onClick={() => handleTriggerBuild(msg.detectedPatents)}
                          style={{
                            marginTop: 8,
                            background: '#0284c7',
                            color: 'white',
                            border: 'none',
                            borderRadius: 6,
                            padding: '6px 14px',
                            fontSize: 12,
                            fontWeight: 600,
                            cursor: 'pointer'
                          }}
                        >
                          🚀 Build Taxonomy with these {msg.detectedPatents.length} Patents
                        </button>
                      </div>
                    )}
                  </div>

                  <span style={{ fontSize: 10, color: '#64748b', alignSelf: isUser ? 'flex-end' : 'flex-start', padding: '0 4px' }}>
                    {msg.timestamp}
                  </span>
                </div>
              </div>
            </div>
          );
        })}

        {/* Live Status Card while taxonomy is building */}
        {status === 'running' && (
          <div style={{
            padding: 16,
            background: runStage?.stage === 'auditing_hierarchy'
              ? 'linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%)'
              : 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
            border: runStage?.stage === 'auditing_hierarchy'
              ? '1px solid #818cf8'
              : '1px solid #0284c7',
            borderRadius: 12,
            boxShadow: runStage?.stage === 'auditing_hierarchy'
              ? '0 4px 16px rgba(129, 140, 248, 0.25)'
              : '0 4px 16px rgba(2, 132, 199, 0.2)',
            display: 'flex',
            alignItems: 'center',
            gap: 14
          }}>
            <div style={{
              width: 36,
              height: 36,
              borderRadius: '50%',
              border: `3px solid ${runStage?.stage === 'auditing_hierarchy' ? '#818cf8' : '#38bdf8'}`,
              borderTopColor: 'transparent',
              animation: 'spin 1s linear infinite'
            }} />
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 14, fontWeight: 700, color: runStage?.stage === 'auditing_hierarchy' ? '#a5b4fc' : '#38bdf8' }}>
                  {runStage?.title || "Building Taxonomy Pipeline..."}
                </span>
                {runStage?.step && (
                  <span style={{
                    fontSize: 10,
                    fontWeight: 700,
                    padding: '2px 8px',
                    borderRadius: 10,
                    background: runStage?.stage === 'auditing_hierarchy' ? '#4338ca' : '#0369a1',
                    color: '#ffffff'
                  }}>
                    Step {runStage.step} of {runStage.totalSteps || 5}
                  </span>
                )}
              </div>
              <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 2 }}>
                {runStage?.description || "Extracting technical concepts, clustering branches, and mapping claims against your product model."}
              </div>
            </div>
          </div>
        )}

        {/* Assistant typing indicator */}
        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 30, height: 30, borderRadius: '50%', background: '#0284c7', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14 }}>
              🤖
            </div>
            <div style={{ padding: '10px 16px', background: '#1e293b', borderRadius: 14, border: '1px solid #334155', color: '#94a3b8', fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}>
              <span>AI is thinking</span>
              <span style={{ animation: 'pulse 1.5s infinite' }}>...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Quick Prompt Chips */}
      <div style={{
        padding: '6px 20px',
        display: 'flex',
        flexWrap: 'wrap',
        gap: 6,
        background: '#090d16',
        borderTop: '1px solid #1e293b'
      }}>
        {status === 'running' ? (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            color: '#f59e0b',
            fontSize: 12,
            fontWeight: 500,
            padding: '4px 10px',
            background: 'rgba(245, 158, 11, 0.1)',
            borderRadius: 6,
            border: '1px solid rgba(245, 158, 11, 0.25)',
            width: '100%'
          }}>
            <span style={{ display: 'inline-block', animation: 'spin 2s linear infinite' }}>⚙️</span>
            <span>Taxonomy graph is generating & auditing... Chat co-pilot will unlock automatically once complete.</span>
          </div>
        ) : runId ? (
          <>
            {[
              "Why are patents grouped this way?",
              "What are the top technical concepts?",
              "Map Mechanism of Action under Pharmacology",
              "Show commercial product coverage"
            ].map((prompt, i) => (
              <button
                key={i}
                onClick={() => handleSendMessage(prompt)}
                style={{
                  background: '#1e293b',
                  color: '#94a3b8',
                  border: '1px solid #334155',
                  borderRadius: 12,
                  padding: '3px 10px',
                  fontSize: 11,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
                onMouseEnter={e => { e.currentTarget.style.color = '#38bdf8'; e.currentTarget.style.borderColor = '#0284c7'; }}
                onMouseLeave={e => { e.currentTarget.style.color = '#94a3b8'; e.currentTarget.style.borderColor = '#334155'; }}
              >
                {prompt}
              </button>
            ))}
          </>
        ) : (
          <>
            {[
              "Focus on mechanism of action, exclude packaging",
              "Build taxonomy for US10293847, US9876543",
              "Prioritize battery thermal runaway prevention",
              "Identify core technological differentiation"
            ].map((prompt, i) => (
              <button
                key={i}
                onClick={() => handleSendMessage(prompt)}
                style={{
                  background: '#1e293b',
                  color: '#94a3b8',
                  border: '1px solid #334155',
                  borderRadius: 12,
                  padding: '3px 10px',
                  fontSize: 11,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
                onMouseEnter={e => { e.currentTarget.style.color = '#38bdf8'; e.currentTarget.style.borderColor = '#0284c7'; }}
                onMouseLeave={e => { e.currentTarget.style.color = '#94a3b8'; e.currentTarget.style.borderColor = '#334155'; }}
              >
                {prompt}
              </button>
            ))}
          </>
        )}
      </div>

      {/* Input Box Area */}
      <div style={{
        padding: '12px 20px',
        background: '#1e293b',
        borderTop: '1px solid #334155',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        flexShrink: 0
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          background: status === 'running' ? '#0b1120' : '#0f172a',
          borderRadius: 24,
          padding: '6px 14px',
          border: status === 'running' ? '1px dashed #475569' : '1px solid #334155',
          boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
          opacity: status === 'running' ? 0.75 : 1,
          transition: 'all 0.2s ease'
        }}>
          {/* Conversational Text Input */}
          <input
            type="text"
            value={input}
            disabled={status === 'running' || loading}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSendMessage();
            }}
            placeholder={
              status === 'running'
                ? "🔒 Pipeline is generating graph... Chat locked until complete"
                : runId
                  ? "Ask AI about this taxonomy or type 'Map X under Y'..."
                  : "Type instructions or ask Taxonomy Co-Pilot..."
            }
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: status === 'running' ? '#64748b' : '#f8fafc',
              fontSize: 14,
              padding: '6px 0',
              cursor: status === 'running' ? 'not-allowed' : 'text'
            }}
          />

          {/* Send Button */}
          <button
            onClick={() => handleSendMessage()}
            disabled={loading || status === 'running' || !input.trim()}
            title={status === 'running' ? "Locked while graph is generating" : "Send message"}
            style={{
              width: 32,
              height: 32,
              borderRadius: '50%',
              background: status === 'running' ? '#1e293b' : (input.trim() ? '#0284c7' : '#334155'),
              color: status === 'running' ? '#64748b' : 'white',
              border: 'none',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: status === 'running' ? 'not-allowed' : (input.trim() ? 'pointer' : 'default'),
              fontSize: status === 'running' ? 12 : 14,
              fontWeight: 'bold',
              transition: 'background 0.2s ease'
            }}
          >
            {status === 'running' ? '🔒' : '↑'}
          </button>
        </div>
      </div>

      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  );
}
