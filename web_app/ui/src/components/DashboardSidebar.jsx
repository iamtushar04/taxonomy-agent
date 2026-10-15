import React, { useEffect, useState } from 'react';
import axiosClient from '../api/axiosClient';

const DashboardSidebar = ({ currentRunId, onSelectRun, refreshTrigger, optimisticRun }) => {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState("");

  // Instant optimistic session insertion at 0ms
  useEffect(() => {
    if (!optimisticRun || !optimisticRun.id) return;
    setRuns(prev => {
      const idx = prev.findIndex(r => r.id === optimisticRun.id);
      if (idx !== -1) {
        const copy = [...prev];
        copy[idx] = { ...copy[idx], ...optimisticRun };
        return copy;
      }
      return [optimisticRun, ...prev];
    });
  }, [optimisticRun]);

  useEffect(() => {
    const fetchRuns = async () => {
      try {
        // Only show full loading state on first cold boot when no runs exist yet
        if (runs.length === 0) setLoading(true);
        const res = await axiosClient.get('/api/runs');
        const fetched = res.data.runs || [];
        setRuns(prev => {
          // If optimisticRun exists and is not yet in fetched runs, keep it prepended
          if (optimisticRun && optimisticRun.id && !fetched.some(r => r.id === optimisticRun.id)) {
            return [optimisticRun, ...fetched];
          }
          return fetched;
        });
      } catch (err) {
        console.error("Failed to fetch runs history", err);
      } finally {
        setLoading(false);
      }
    };

    fetchRuns();
  }, [refreshTrigger, optimisticRun]);

  // Periodic poll to refresh run statuses if any run is running or pending
  useEffect(() => {
    const hasRunning = runs.some(r => r.status === 'running' || r.status === 'pending');
    if (!hasRunning) return;

    const interval = setInterval(async () => {
      try {
        const res = await axiosClient.get('/api/runs');
        const fetched = res.data.runs || [];
        setRuns(prev => {
          if (optimisticRun && optimisticRun.id && !fetched.some(r => r.id === optimisticRun.id)) {
            return [optimisticRun, ...fetched];
          }
          return fetched;
        });
      } catch (err) {
        console.error("Failed to refresh runs status", err);
      }
    }, 4000);

    return () => clearInterval(interval);
  }, [runs, optimisticRun]);

  const handleEditSubmit = async (e, id) => {
    if (e.key === 'Enter') {
      try {
        await axiosClient.put(`/api/runs/${id}/name`, { name: editName });
        setRuns(runs.map(r => r.id === id ? { ...r, name: editName } : r));
        setEditingId(null);
      } catch (err) {
        console.error(err);
        alert("Failed to rename session");
      }
    }
  };

  const handleDeleteSession = async (e, id) => {
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to delete this session? This action cannot be undone.")) {
      return;
    }
    try {
      // 202 Accepted asynchronous deletion technique
      await axiosClient.delete(`/api/delete/sessions/${id}`);
      setRuns(prev => prev.filter(r => r.id !== id));
      if (currentRunId === id) {
        onSelectRun(null);
      }
    } catch (err) {
      console.error("Failed to delete session", err);
      alert(err.response?.data?.detail || "Failed to delete session");
    }
  };

  return (
    <div style={{ width: '250px', background: '#2c3e50', color: 'white', display: 'flex', flexDirection: 'column', height: '100%', borderRight: '1px solid #1a252f' }}>
      <div style={{ padding: '20px', borderBottom: '1px solid #34495e', background: '#1a252f', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, color: '#ecf0f1' }}>Run History</h3>
        <button 
          onClick={() => onSelectRun(null)}
          title="Create New Taxonomy"
          style={{ 
            background: '#27ae60', color: 'white', border: 'none', borderRadius: '50%', 
            width: '30px', height: '30px', fontSize: '20px', cursor: 'pointer', 
            display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
          }}
        >
          +
        </button>
      </div>
      
      <div style={{ flex: 1, overflowY: 'auto', padding: '10px 0' }}>
        {loading ? (
          <div style={{ padding: '20px', textAlign: 'center', color: '#bdc3c7' }}>Loading...</div>
        ) : runs.length === 0 ? (
          <div style={{ padding: '20px', textAlign: 'center', color: '#bdc3c7', fontSize: '14px' }}>No previous runs found.</div>
        ) : (
          runs.map((run) => (
            <div 
              key={run.id} 
              onClick={() => onSelectRun(run.id)}
              style={{ 
                padding: '12px 20px', 
                cursor: 'pointer',
                background: currentRunId === run.id ? '#34495e' : 'transparent',
                borderLeft: currentRunId === run.id ? '4px solid #3498db' : '4px solid transparent',
                transition: 'background 0.2s',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px'
              }}
              onMouseEnter={(e) => {
                if (currentRunId !== run.id) e.currentTarget.style.background = '#34495e';
              }}
              onMouseLeave={(e) => {
                if (currentRunId !== run.id) e.currentTarget.style.background = 'transparent';
              }}
            >
              <div style={{ fontWeight: 'bold', fontSize: '14px', color: '#ecf0f1', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                {editingId === run.id ? (
                  <input 
                    type="text" 
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    onKeyDown={(e) => handleEditSubmit(e, run.id)}
                    onBlur={() => setEditingId(null)}
                    autoFocus
                    style={{ background: '#1a252f', color: 'white', border: '1px solid #3498db', borderRadius: '4px', padding: '2px 4px', width: '100%', fontSize: '13px' }}
                    onClick={(e) => e.stopPropagation()}
                  />
                ) : (
                  <>
                    <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '140px' }}>
                      {run.name}
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span 
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditingId(run.id);
                          setEditName(run.name);
                        }} 
                        style={{ cursor: 'pointer', fontSize: '12px', opacity: 0.6, padding: '2px' }}
                        title="Rename"
                      >
                        ✏️
                      </span>
                      <span 
                        onClick={(e) => handleDeleteSession(e, run.id)} 
                        style={{ cursor: 'pointer', fontSize: '12px', opacity: 0.6, padding: '2px' }}
                        title="Delete Session"
                      >
                        🗑️
                      </span>
                    </div>
                  </>
                )}
              </div>
              <div style={{ fontSize: '12px', color: '#bdc3c7', display: 'flex', justifyContent: 'space-between' }}>
                <span>ID: {run.id}</span>
                <span style={{ 
                  color: run.status === 'completed' ? '#2ecc71' : run.status === 'failed' ? '#e74c3c' : '#f1c40f',
                  fontWeight: run.status === 'running' || run.status === 'pending' ? 'bold' : 'normal',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px'
                }}>
                  {(run.status === 'running' || run.status === 'pending') && (
                    <span style={{
                      display: 'inline-block',
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      backgroundColor: '#f1c40f',
                      boxShadow: '0 0 6px #f1c40f'
                    }} />
                  )}
                  {run.status}
                </span>
              </div>
              <div style={{ fontSize: '10px', color: '#7f8c8d' }}>
                {new Date(run.created_at).toLocaleString()}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default DashboardSidebar;
