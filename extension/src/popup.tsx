/**
 * JobHunter Extension - Popup Component (V3)
 * AI Agent with prompt-based input - works from ANY webpage
 * 
 * Features:
 * - Natural language prompt input
 * - Real-time task execution status
 * - Works from any webpage (not just job sites)
 * - AI Thought Process display
 */

import { useState, useEffect, useRef } from 'react';
import './styles/globals.css';

type TaskStatus = 'idle' | 'planning' | 'executing' | 'waiting' | 'complete' | 'error';

interface TaskState {
  status: TaskStatus;
  message: string;
  taskId: string | null;
  progress: number;
  currentStep: string;
  thoughtProcess: string[];
}

interface AgentResponse {
  success: boolean;
  task_id?: string;
  plan_summary?: string;
  total_steps?: number;
  message?: string;
  error?: string;
}

function Popup() {
  const [prompt, setPrompt] = useState('');
  const [taskState, setTaskState] = useState<TaskState>({
    status: 'idle',
    message: 'Enter a command to get started',
    taskId: null,
    progress: 0,
    currentStep: '',
    thoughtProcess: [],
  });
  
  const [apiStatus, setApiStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [resumeReady, setResumeReady] = useState(false);
  const [history, setHistory] = useState<string[]>([]);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Check API status on mount
  useEffect(() => {
    checkStatus();
    loadHistory();
  }, []);

  async function checkStatus() {
    try {
      const response = await fetch('http://localhost:8001/api/v1/health');
      if (response.ok) {
        setApiStatus('online');
        
        // Check if resume is uploaded
        try {
          const statsResponse = await fetch('http://localhost:8001/api/v1/query/stats');
          if (statsResponse.ok) {
            const stats = await statsResponse.json();
            setResumeReady(stats.document_count > 0);
          }
        } catch {
          setResumeReady(false);
        }
      } else {
        setApiStatus('offline');
      }
    } catch {
      setApiStatus('offline');
    }
  }

  function loadHistory() {
    try {
      const saved = localStorage.getItem('jobhunter_history');
      if (saved) {
        setHistory(JSON.parse(saved).slice(0, 5));
      }
    } catch {
      setHistory([]);
    }
  }

  function saveToHistory(cmd: string) {
    const newHistory = [cmd, ...history.filter(h => h !== cmd)].slice(0, 5);
    setHistory(newHistory);
    localStorage.setItem('jobhunter_history', JSON.stringify(newHistory));
  }

  async function executeCommand() {
    if (!prompt.trim() || apiStatus !== 'online') return;
    
    const command = prompt.trim();
    saveToHistory(command);
    
    setTaskState({
      status: 'planning',
      message: 'AI is analyzing your request...',
      taskId: null,
      progress: 10,
      currentStep: 'Intent Analysis',
      thoughtProcess: [`📝 Received: "${command}"`, '🧠 Parsing intent...'],
    });

    try {
      // Step 1: Create a task with the prompt
      const response = await fetch('http://localhost:8001/api/v1/agent/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: command,
          auto_start: true,
          dry_run: false,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const data: AgentResponse = await response.json();

      if (data.success && data.task_id) {
        setTaskState(prev => ({
          ...prev,
          status: 'executing',
          message: data.plan_summary || 'Executing task...',
          taskId: data.task_id,
          progress: 30,
          currentStep: 'Task Started',
          thoughtProcess: [
            ...prev.thoughtProcess,
            `✅ Plan created: ${data.total_steps} steps`,
            `🚀 Task ID: ${data.task_id}`,
            '🔄 Executing...',
          ],
        }));

        // Start polling for status
        pollTaskStatus(data.task_id);
      } else {
        throw new Error(data.message || 'Failed to create task');
      }
    } catch (error: any) {
      setTaskState(prev => ({
        ...prev,
        status: 'error',
        message: error.message || 'Failed to execute command',
        thoughtProcess: [...prev.thoughtProcess, `❌ Error: ${error.message}`],
      }));
    }
  }

  async function pollTaskStatus(taskId: string) {
    let attempts = 0;
    const maxAttempts = 60; // 5 minutes max

    const poll = async () => {
      if (attempts >= maxAttempts) {
        setTaskState(prev => ({
          ...prev,
          status: 'error',
          message: 'Task timed out',
        }));
        return;
      }

      try {
        const response = await fetch(`http://localhost:8001/api/v1/agent/tasks/${taskId}`);
        if (!response.ok) throw new Error('Failed to get status');

        const data = await response.json();
        
        setTaskState(prev => ({
          ...prev,
          progress: data.progress_percent || prev.progress,
          currentStep: data.current_step || prev.currentStep,
          thoughtProcess: data.current_step 
            ? [...prev.thoughtProcess.slice(-5), `🔄 ${data.current_step}`]
            : prev.thoughtProcess,
        }));

        if (data.status === 'completed' || data.status === 'success') {
          setTaskState(prev => ({
            ...prev,
            status: 'complete',
            message: data.message || 'Task completed successfully!',
            progress: 100,
            thoughtProcess: [...prev.thoughtProcess.slice(-5), '✅ Task completed!'],
          }));
        } else if (data.status === 'failed' || data.status === 'error') {
          setTaskState(prev => ({
            ...prev,
            status: 'error',
            message: data.error_message || 'Task failed',
            thoughtProcess: [...prev.thoughtProcess.slice(-5), `❌ ${data.error_message}`],
          }));
        } else if (data.status === 'waiting_intervention') {
          setTaskState(prev => ({
            ...prev,
            status: 'waiting',
            message: 'Waiting for your input...',
            thoughtProcess: [...prev.thoughtProcess.slice(-5), '⏸️ Human input required'],
          }));
        } else {
          // Still running, continue polling
          attempts++;
          setTimeout(poll, 5000);
        }
      } catch (error: any) {
        attempts++;
        setTimeout(poll, 5000);
      }
    };

    poll();
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      executeCommand();
    }
  }

  function openDashboard() {
    chrome.tabs.create({ url: 'http://localhost:3000' });
  }

  function openDocs() {
    chrome.tabs.create({ url: 'http://localhost:8001/docs' });
  }

  function resetState() {
    setTaskState({
      status: 'idle',
      message: 'Enter a command to get started',
      taskId: null,
      progress: 0,
      currentStep: '',
      thoughtProcess: [],
    });
    setPrompt('');
  }

  const isProcessing = ['planning', 'executing', 'waiting'].includes(taskState.status);

  return (
    <div className="w-96 bg-gradient-to-br from-gray-900 to-gray-800 text-white min-h-[480px] relative">
      {/* Header */}
      <div className="p-4 border-b border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-2xl">🎯</span>
            <div>
              <h1 className="text-lg font-bold">JobHunter AI</h1>
              <p className="text-xs text-gray-400">Autonomous Job Agent</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                apiStatus === 'online'
                  ? 'bg-green-500'
                  : apiStatus === 'offline'
                  ? 'bg-red-500'
                  : 'bg-yellow-500 animate-pulse'
              }`}
            />
            <span className="text-xs text-gray-400">
              {apiStatus === 'online' ? 'Online' : apiStatus === 'offline' ? 'Offline' : '...'}
            </span>
          </div>
        </div>
      </div>

      {/* Prompt Input */}
      <div className="p-4">
        <div className="relative">
          <textarea
            ref={inputRef}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="What would you like me to do? e.g., 'Apply to 5 remote Python developer jobs'"
            disabled={isProcessing || apiStatus !== 'online'}
            className="w-full h-24 p-3 pr-12 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-500 resize-none focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
          />
          <button
            onClick={executeCommand}
            disabled={!prompt.trim() || isProcessing || apiStatus !== 'online'}
            className="absolute bottom-3 right-3 p-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg transition-colors"
            title="Execute (Enter)"
          >
            {isProcessing ? (
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              <span>🚀</span>
            )}
          </button>
        </div>

        {/* Quick Examples */}
        {!isProcessing && taskState.status === 'idle' && (
          <div className="mt-3 space-y-2">
            <p className="text-xs text-gray-500">Examples:</p>
            <div className="flex flex-wrap gap-2">
              {['Find 5 remote jobs', 'Apply to PM roles in NYC', 'Search Python developer jobs'].map((example) => (
                <button
                  key={example}
                  onClick={() => setPrompt(example)}
                  className="text-xs px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded-full text-gray-300 transition-colors"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Status Display */}
      {taskState.status !== 'idle' && (
        <div className="px-4 pb-4">
          <div className="bg-gray-800 rounded-lg p-4">
            {/* Progress Bar */}
            <div className="mb-3">
              <div className="flex justify-between text-xs text-gray-400 mb-1">
                <span>{taskState.currentStep}</span>
                <span>{taskState.progress}%</span>
              </div>
              <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-500 ${
                    taskState.status === 'error'
                      ? 'bg-red-500'
                      : taskState.status === 'complete'
                      ? 'bg-green-500'
                      : 'bg-blue-500'
                  }`}
                  style={{ width: `${taskState.progress}%` }}
                />
              </div>
            </div>

            {/* Status Message */}
            <div className="flex items-center gap-2 mb-3">
              <span className="text-lg">
                {taskState.status === 'planning' && '🧠'}
                {taskState.status === 'executing' && '⚡'}
                {taskState.status === 'waiting' && '⏸️'}
                {taskState.status === 'complete' && '✅'}
                {taskState.status === 'error' && '❌'}
              </span>
              <span className="text-sm flex-1">{taskState.message}</span>
              {(taskState.status === 'complete' || taskState.status === 'error') && (
                <button
                  onClick={resetState}
                  className="text-xs text-gray-400 hover:text-white"
                >
                  New Task
                </button>
              )}
            </div>

            {/* Thought Process */}
            <div className="bg-gray-900 rounded p-3 max-h-28 overflow-y-auto">
              <p className="text-xs text-gray-500 mb-2">AI Thought Process:</p>
              {taskState.thoughtProcess.slice(-5).map((thought, i) => (
                <p key={i} className="text-xs text-gray-400 mb-1">
                  {thought}
                </p>
              ))}
            </div>

            {/* Task ID */}
            {taskState.taskId && (
              <p className="text-xs text-gray-600 mt-2">
                Task: {taskState.taskId.substring(0, 8)}...
              </p>
            )}
          </div>
        </div>
      )}

      {/* Resume Warning */}
      {!resumeReady && apiStatus === 'online' && taskState.status === 'idle' && (
        <div className="px-4 pb-4">
          <div className="bg-yellow-900/30 border border-yellow-700 rounded-lg p-3">
            <p className="text-sm text-yellow-400">
              ⚠️ Upload your resume for personalized applications
            </p>
            <button
              onClick={openDocs}
              className="mt-2 text-xs text-yellow-500 hover:text-yellow-400 underline"
            >
              Upload at API Docs →
            </button>
          </div>
        </div>
      )}

      {/* History */}
      {history.length > 0 && taskState.status === 'idle' && (
        <div className="px-4 pb-4">
          <p className="text-xs text-gray-500 mb-2">Recent:</p>
          <div className="space-y-1">
            {history.slice(0, 3).map((cmd, i) => (
              <button
                key={i}
                onClick={() => setPrompt(cmd)}
                className="w-full text-left text-xs p-2 bg-gray-800 hover:bg-gray-700 rounded text-gray-400 truncate transition-colors"
              >
                {cmd}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-700 bg-gray-900">
        <div className="flex justify-between items-center">
          <button
            onClick={openDashboard}
            className="text-xs text-gray-400 hover:text-white transition-colors"
          >
            📊 Dashboard
          </button>
          <span className="text-xs text-gray-600">v3.0.0</span>
          <button
            onClick={openDocs}
            className="text-xs text-gray-400 hover:text-white transition-colors"
          >
            📚 API Docs
          </button>
        </div>
      </div>
    </div>
  );
}

export default Popup;
