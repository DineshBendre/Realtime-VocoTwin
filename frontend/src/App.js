import React, { useState, useEffect, useRef } from 'react';
import './App.css';

function App() {
  const [sessionActive, setSessionActive] = useState(false);
  const [mode, setMode] = useState('none');
  const [text, setText] = useState('');
  const [status, setStatus] = useState('Loading...');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const API_URL = 'http://localhost:5000/api';
  const statusIntervalRef = useRef(null);

  // Check status periodically
  useEffect(() => {
    checkStatus();
    
    if (sessionActive) {
      statusIntervalRef.current = setInterval(checkStatus, 5000);
    } else if (statusIntervalRef.current) {
      clearInterval(statusIntervalRef.current);
    }
    
    return () => {
      if (statusIntervalRef.current) {
        clearInterval(statusIntervalRef.current);
      }
    };
  }, [sessionActive]);

  const checkStatus = async () => {
    try {
      const response = await fetch(`${API_URL}/status`);
      const data = await response.json();
      
      setSessionActive(data.status === 'active');
      setMode(data.mode);
      setStatus(`Session ${data.status}, Mode: ${data.mode}`);
    } catch (err) {
      setError('Failed to check status. Server might be down.');
      console.error('Error checking status:', err);
    }
  };

  const startSession = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_URL}/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ mode })
      });
      
      const data = await response.json();
      
      if (response.ok) {
        setSessionActive(true);
        setStatus(`Session started with ${mode} mode`);
      } else {
        setError(data.message || 'Failed to start session');
      }
    } catch (err) {
      setError('Failed to start session. Is the server running?');
      console.error('Error starting session:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const stopSession = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_URL}/stop`, {
        method: 'POST'
      });
      
      const data = await response.json();
      
      if (response.ok) {
        setSessionActive(false);
        setStatus('Session stopped');
      } else {
        setError(data.message || 'Failed to stop session');
      }
    } catch (err) {
      setError('Failed to stop session');
      console.error('Error stopping session:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const sendText = async (e) => {
    e.preventDefault();
    
    if (!text.trim()) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_URL}/send_text`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ text })
      });
      
      const data = await response.json();
      
      if (response.ok) {
        setText('');
      } else {
        setError(data.message || 'Failed to send text');
      }
    } catch (err) {
      setError('Failed to send text');
      console.error('Error sending text:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const changeMode = async (newMode) => {
    if (newMode === mode) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_URL}/change_mode`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ mode: newMode })
      });
      
      const data = await response.json();
      
      if (response.ok) {
        setMode(newMode);
        setStatus(`Mode changed to ${newMode}`);
      } else {
        setError(data.message || 'Failed to change mode');
      }
    } catch (err) {
      setError('Failed to change mode');
      console.error('Error changing mode:', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Gemini Live API Controller</h1>
        <div className="status-indicator">
          <span className={`status-dot ${sessionActive ? 'active' : 'inactive'}`}></span>
          <span>{status}</span>
        </div>
        {error && <div className="error-message">{error}</div>}
      </header>
      
      <main>
        <section className="control-panel">
          <div className="card">
            <h2>Session Control</h2>
            <div className="button-group">
              <button 
                onClick={startSession} 
                disabled={sessionActive || isLoading}
                className={sessionActive ? "disabled" : "primary"}
              >
                Start Session
              </button>
              <button 
                onClick={stopSession} 
                disabled={!sessionActive || isLoading}
                className={!sessionActive ? "disabled" : "danger"}
              >
                Stop Session
              </button>
            </div>
          </div>

          <div className="card">
            <h2>Mode Selection</h2>
            <div className="mode-selector">
              <div className={`mode-option ${mode === 'none' ? 'selected' : ''}`} onClick={() => !sessionActive ? setMode('none') : changeMode('none')}>
                <div className="mode-icon">🔇</div>
                <div>None</div>
              </div>
              <div className={`mode-option ${mode === 'camera' ? 'selected' : ''}`} onClick={() => !sessionActive ? setMode('camera') : changeMode('camera')}>
                <div className="mode-icon">📷</div>
                <div>Camera</div>
              </div>
              <div className={`mode-option ${mode === 'screen' ? 'selected' : ''}`} onClick={() => !sessionActive ? setMode('screen') : changeMode('screen')}>
                <div className="mode-icon">🖥️</div>
                <div>Screen</div>
              </div>
            </div>
          </div>
        </section>

        <section className="messaging">
          <div className="card">
            <h2>Send Message</h2>
            <form onSubmit={sendText}>
              <input
                type="text"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Type a message to Gemini..."
                disabled={!sessionActive || isLoading}
              />
              <button 
                type="submit" 
                disabled={!sessionActive || isLoading || !text.trim()}
                className={!sessionActive || !text.trim() ? "disabled" : "primary"}
              >
                Send
              </button>
            </form>
          </div>
        </section>
      </main>

      <footer>
        <p>Gemini Live API Controller | {new Date().getFullYear()}</p>
      </footer>
    </div>
  );
}

export default App;