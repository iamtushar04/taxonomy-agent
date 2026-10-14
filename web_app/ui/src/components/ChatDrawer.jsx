import React, { useState, useEffect, useRef } from 'react';
import axiosClient from '../api/axiosClient';

export default function ChatDrawer({ isOpen, onClose, runId, initialMessage, onClearInitialMessage }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [fetchingHistory, setFetchingHistory] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  // Fetch chat history whenever drawer opens for a run
  useEffect(() => {
    if (!isOpen || !runId) return;

    const fetchHistory = async () => {
      setFetchingHistory(true);
      try {
        const res = await axiosClient.get(`/api/chat/${runId}/history`);
        if (res.data.messages && res.data.messages.length > 0) {
          setMessages(res.data.messages);
        } else if (res.data.greeting) {
          setMessages([
            {
              role: 'assistant',
              content: res.data.greeting,
              timestamp: new Date().toISOString()
            }
          ]);
        }
      } catch (err) {
        console.error('Failed to load chat history:', err);
      } finally {
        setFetchingHistory(false);
      }
    };

    fetchHistory();
  }, [isOpen, runId]);

  // If triggered with an initial message from the bottom input bar
  useEffect(() => {
    if (isOpen && runId && initialMessage && initialMessage.trim()) {
      sendMessage(initialMessage.trim());
      if (onClearInitialMessage) onClearInitialMessage();
    }
  }, [isOpen, runId, initialMessage]);

  const sendMessage = async (textToSend) => {
    const text = textToSend || input.trim();
    if (!text || loading) return;

    const userMsg = {
      role: 'user',
      content: text,
      timestamp: new Date().toISOString()
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setInput('');
    setLoading(true);

    try {
      const res = await axiosClient.post(`/api/chat/${runId}/message`, { message: text });
      const assistantMsg = {
        role: 'assistant',
        content: res.data.response || 'No response received.',
        intent: res.data.intent,
        metadata: res.data.metadata,
        mappingRules: res.data.mapping_rules,
        timestamp: new Date().toISOString()
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      console.error('Chat error:', err);
      const errMsg = {
        role: 'assistant',
        content: `⚠️ Error: ${err.response?.data?.detail || err.message || 'Failed to get response.'}`,
        timestamp: new Date().toISOString()
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      right: 0,
      bottom: 0,
      width: '460px',
      maxWidth: '92vw',
      background: '#ffffff',
      boxShadow: '-4px 0 24px rgba(0,0,0,0.15)',
      zIndex: 1100,
      display: 'flex',
      flexDirection: 'column',
      borderLeft: '1px solid #e2e8f0',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    }}>
      {/* Drawer Header */}
      <div style={{
        padding: '16px 20px',
        background: '#1e293b',
        color: '#ffffff',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid #334155'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            background: '#0284c7',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 16
          }}>
            🤖
          </div>
          <div>
            <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: '#f8fafc' }}>
              Taxonomy AI Assistant
            </h3>
            <span style={{ fontSize: 11, color: '#94a3b8' }}>
              Run ID: <code style={{ color: '#38bdf8' }}>{runId ? runId.slice(0, 8) : 'None'}</code>
            </span>
          </div>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'transparent',
            border: 'none',
            color: '#94a3b8',
            fontSize: 20,
            cursor: 'pointer',
            padding: '4px 8px',
            borderRadius: 6
          }}
          title="Close chat"
        >
          ✕
        </button>
      </div>

      {/* Messages Container */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
        background: '#f8fafc'
      }}>
        {fetchingHistory && (
          <div style={{ textAlign: 'center', color: '#64748b', fontSize: 13, padding: 20 }}>
            Loading conversation...
          </div>
        )}

        {messages.map((msg, i) => {
          const isUser = msg.role === 'user';
          return (
            <div
              key={i}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: isUser ? 'flex-end' : 'flex-start'
              }}
            >
              <div
                style={{
                  maxWidth: '85%',
                  padding: '12px 16px',
                  borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                  background: isUser ? '#0284c7' : '#ffffff',
                  color: isUser ? '#ffffff' : '#1e293b',
                  fontSize: 14,
                  lineHeight: 1.55,
                  boxShadow: isUser ? '0 2px 6px rgba(2,132,199,0.25)' : '0 1px 3px rgba(0,0,0,0.06)',
                  border: isUser ? 'none' : '1px solid #e2e8f0',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word'
                }}
              >
                {msg.content}
              </div>

              {/* Show intent or badge for assistant if available */}
              {!isUser && msg.intent && (
                <div style={{
                  fontSize: 10,
                  color: '#64748b',
                  marginTop: 4,
                  marginLeft: 4,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4
                }}>
                  <span style={{
                    background: '#e0f2fe',
                    color: '#0369a1',
                    padding: '2px 6px',
                    borderRadius: 4,
                    fontWeight: 500
                  }}>
                    {msg.intent.replace('_', ' ')}
                  </span>
                </div>
              )}
            </div>
          );
        })}

        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#0284c7', fontSize: 13, padding: 8 }}>
            <span style={{ animation: 'spin 1s infinite linear' }}>⏳</span> Analyzing taxonomy context...
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Drawer Input Bar */}
      <div style={{
        padding: '14px 16px',
        background: '#ffffff',
        borderTop: '1px solid #e2e8f0',
        display: 'flex',
        gap: 8,
        alignItems: 'center'
      }}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question or type 'Map X under Y'..."
          disabled={loading}
          onKeyDown={(e) => {
            if (e.key === 'Enter') sendMessage();
          }}
          style={{
            flex: 1,
            padding: '10px 14px',
            borderRadius: 20,
            border: '1px solid #cbd5e1',
            outline: 'none',
            fontSize: 14
          }}
        />
        <button
          onClick={() => sendMessage()}
          disabled={loading || !input.trim()}
          style={{
            background: loading || !input.trim() ? '#94a3b8' : '#0284c7',
            color: '#ffffff',
            border: 'none',
            borderRadius: '50%',
            width: 38,
            height: 38,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
            fontSize: 16,
            fontWeight: 'bold',
            flexShrink: 0
          }}
        >
          ↑
        </button>
      </div>
    </div>
  );
}
