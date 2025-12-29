/**
 * JobHunter Extension - Popup Component (V3)
 * AI Agent with prompt-based input - works from ANY webpage
 * 
 * Features:
 * - Natural language prompt input
 * - Real-time task execution status (persists across tab switches)
 * - Resume PDF upload
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
  const [resumeUploading, setResumeUploading] = useState(false);
  const [showResumeUpload, setShowResumeUpload] = useState(false);
  const [history, setHistory] = useState<string[]>([]);
  const [executionMode, setExecutionMode] = useState<'playwright' | 'in_tab'>('playwright');
  const [useCdp, setUseCdp] = useState(false);
  const [showCdpDoc, setShowCdpDoc] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [skipInTabConfirm, setSkipInTabConfirm] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Check API status and restore task state on mount
  useEffect(() => {
    checkStatus();
    loadHistory();
    restoreTaskState();
    
    // Load user preference for skipping in-tab confirmation
    chrome.storage.local.get(['skipInTabConfirm'], (res) => {
      if (res.skipInTabConfirm) setSkipInTabConfirm(Boolean(res.skipInTabConfirm));
    });

    // Set up listener for task state updates from background
    const handleStorageChange = () => {
      restoreTaskState();
    };
    
    // Poll for updates while popup is open
    const pollInterval = setInterval(restoreTaskState, 2000);
    
    return () => {
      clearInterval(pollInterval);
    };
  }, []);

  async function restoreTaskState() {
    try {
      const response = await chrome.runtime.sendMessage({ action: 'getTaskState' });
      if (response?.task) {
        const task = response.task;
        setTaskState({
          status: task.status as TaskStatus,
          message: task.message || '',
          taskId: task.taskId,
          progress: task.progress || 0,
          currentStep: task.currentStep || '',
          thoughtProcess: task.thoughtProcess || [],
        });
      }
    } catch (error) {
      console.log('[Popup] No active task state');
    }
  }

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

  async function handleResumeUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      alert('Please upload a PDF file');
      return;
    }
    
    setResumeUploading(true);
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await fetch('http://localhost:8001/api/v1/resume/upload', {
        method: 'POST',
        body: formData,
      });
      
      if (response.ok) {
        setResumeReady(true);
        setShowResumeUpload(false);
        alert('Resume uploaded successfully! 🎉');
      } else {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Upload failed');
      }
    } catch (error: any) {
      alert(`Failed to upload resume: ${error.message}`);
    } finally {
      setResumeUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  }

  async function executeCommand() {
    if (!prompt.trim() || apiStatus !== 'online') return;

    // If in-tab and confirmation required, show modal first
    if (executionMode === 'in_tab' && !skipInTabConfirm && !showConfirmModal) {
      setShowConfirmModal(true);
      return;
    }

    await proceedWithExecute();
  }

  // The actual executor (called directly or from the confirmation modal)
  async function proceedWithExecute() {
    if (!prompt.trim() || apiStatus !== 'online') return;

    const command = prompt.trim();
    saveToHistory(command);

    const initialState: TaskState = {
      status: 'planning',
      message: 'AI is analyzing your request...',
      taskId: null,
      progress: 10,
      currentStep: 'Intent Analysis',
      thoughtProcess: [`📝 Received: "${command}"`, '🧠 Parsing intent...'],
    };

    setTaskState(initialState);

    try {
      if (executionMode === 'in_tab') {
        // 1) Generate a plan (preview)
        const planResp = await fetch('http://localhost:8001/api/v1/agent/plan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt: command }),
        });
        if (!planResp.ok) throw new Error('Failed to generate plan');
        const planData = await planResp.json();

        // 2) Create task but do NOT auto-start - extension will claim and execute
        const createResp = await fetch('http://localhost:8001/api/v1/agent/tasks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt: command, auto_start: false, dry_run: false, execution_mode: 'in_tab' }),
        });
        if (!createResp.ok) {
          const err = await createResp.json().catch(() => ({}));
          throw new Error(err.detail || 'Failed to create in-tab task');
        }
        const createData: AgentResponse = await createResp.json();
        if (!createData.success || !createData.task_id) throw new Error('Task creation failed');

        // Send startInTabTask to background to claim & forward plan nodes to the active tab
        chrome.runtime.sendMessage({ action: 'startInTabTask', taskId: createData.task_id, planNodes: planData.plan.nodes }, (resp) => {
          // Start polling for task updates
          chrome.runtime.sendMessage({
            action: 'startTaskPolling',
            taskId: createData.task_id,
            initialState: {
              taskId: createData.task_id,
              status: 'waiting',
              progress: 0,
              currentStep: 'Waiting for tab to claim task',
              message: createData.plan_summary || 'Waiting for claim',
              thoughtProcess: [...initialState.thoughtProcess, `🔁 Created in-tab task ${createData.task_id}`],
              lastUpdated: Date.now(),
            },
          });
        });

        setTaskState({
          status: 'waiting',
          message: 'Waiting for your active tab to claim and execute the task',
          taskId: createData.task_id,
          progress: 0,
          currentStep: 'Waiting to be claimed',
          thoughtProcess: [...initialState.thoughtProcess, `🔁 Created in-tab task`],
        });

      } else {
        // Playwright (backend) execution - include CDP flag when requested
        const response = await fetch('http://localhost:8001/api/v1/agent/tasks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            prompt: command,
            auto_start: true,
            dry_run: false,
            use_cdp: useCdp,
          }),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || `HTTP ${response.status}`);
        }

        const data: AgentResponse = await response.json();

        if (data.success && data.task_id) {
          const executingState: TaskState = {
            status: 'executing',
            message: data.plan_summary || 'Executing task...',
            taskId: data.task_id,
            progress: 30,
            currentStep: 'Task Started',
            thoughtProcess: [
              ...initialState.thoughtProcess,
              `✅ Plan created: ${data.total_steps} steps`,
              `🚀 Task ID: ${data.task_id}`,
              '🔄 Executing...',
            ],
          };
          
          setTaskState(executingState);

          // Start background polling (persists even when popup closes)
          chrome.runtime.sendMessage({
            action: 'startTaskPolling',
            taskId: data.task_id,
            initialState: {
              taskId: data.task_id,
              status: 'executing',
              progress: 30,
              currentStep: 'Task Started',
              message: data.plan_summary || 'Executing task...',
              thoughtProcess: executingState.thoughtProcess,
              lastUpdated: Date.now(),
            },
          });
        } else {
          throw new Error(data.message || 'Failed to create task');
        }
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
    // Clear background task state
    if (taskState.taskId) {
      chrome.runtime.sendMessage({ action: 'stopTaskPolling', taskId: taskState.taskId });
    }
    chrome.runtime.sendMessage({ action: 'clearTaskState' });
    
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
          <div className="mt-3 flex items-center gap-3">
            <label className="text-xs text-gray-400">Execution mode:</label>
            <select
              value={executionMode}
              onChange={(e) => setExecutionMode(e.target.value as 'playwright' | 'in_tab')}
              className="text-xs bg-gray-800 border border-gray-600 rounded px-2 py-1"
            >
              <option value="playwright">Isolated browser (safe)</option>
              <option value="in_tab">Run in active tab (use your session)</option>
            </select>
            {executionMode === 'in_tab' && (
              <span className="text-xs text-yellow-300">⚠️ Will use the current tab's session</span>
            )}
          </div>

        {/* Quick Examples + Execution Mode */}
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

            {/* Execution Mode */}
            <div className="mt-3">
              <p className="text-xs text-gray-500 mb-1">Execution mode:</p>
              <div className="flex items-center gap-3">
                <label className={`text-xs px-2 py-1 rounded ${executionMode === 'playwright' ? 'bg-gray-700 text-white' : 'bg-gray-800 text-gray-300'}`}>
                  <input type="radio" name="execMode" className="mr-2" checked={executionMode === 'playwright'} onChange={() => setExecutionMode('playwright')} /> Isolated browser
                </label>
                <label className={`text-xs px-2 py-1 rounded ${executionMode === 'in_tab' ? 'bg-gray-700 text-white' : 'bg-gray-800 text-gray-300'}`}>
                  <input type="radio" name="execMode" className="mr-2" checked={executionMode === 'in_tab'} onChange={() => setExecutionMode('in_tab')} /> Run in active tab
                </label>
              </div>

              {executionMode === 'playwright' && (
                <div className="mt-2 text-xs text-gray-400 flex items-center gap-2">
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={useCdp} onChange={(e) => setUseCdp(e.target.checked)} />
                    Enable Playwright CDP attach (advanced)
                  </label>
                  <button className="text-xs text-blue-400 hover:underline" onClick={() => { setShowCdpDoc(true); window.open('https://github.com/shubham-kr2002/AI_JOB_AGENT/blob/main/design/CDP.md'); }}>
                    How to use CDP
                  </button>
                </div>
              )}
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

      {/* Resume Upload Section */}
      {apiStatus === 'online' && taskState.status === 'idle' && (
        <div className="px-4 pb-4">
          {/* Hidden file input */}
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleResumeUpload}
            accept=".pdf"
            className="hidden"
          />
          
          {showResumeUpload ? (
            <div className="bg-gray-800 border border-gray-600 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium">Upload Resume (PDF)</h3>
                <button
                  onClick={() => setShowResumeUpload(false)}
                  className="text-gray-400 hover:text-white text-lg"
                >
                  ×
                </button>
              </div>
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={resumeUploading}
                className="w-full py-3 border-2 border-dashed border-gray-500 hover:border-blue-500 rounded-lg text-center transition-colors disabled:opacity-50"
              >
                {resumeUploading ? (
                  <span className="text-sm text-gray-400">Uploading...</span>
                ) : (
                  <>
                    <span className="text-2xl block mb-1">📄</span>
                    <span className="text-sm text-gray-400">Click to select PDF</span>
                  </>
                )}
              </button>
              <p className="text-xs text-gray-500 mt-2 text-center">
                Your resume will be used to tailor applications
              </p>
            </div>
          ) : !resumeReady ? (
            <div className="bg-yellow-900/30 border border-yellow-700 rounded-lg p-3">
              <div className="flex items-center justify-between">
                <p className="text-sm text-yellow-400">
                  ⚠️ Upload your resume for personalized applications
                </p>
              </div>
              <button
                onClick={() => setShowResumeUpload(true)}
                className="mt-2 w-full py-2 bg-yellow-600 hover:bg-yellow-700 rounded text-sm font-medium transition-colors"
              >
                📤 Upload Resume
              </button>
            </div>
          ) : (
            <div className="bg-green-900/30 border border-green-700 rounded-lg p-3">
              <div className="flex items-center justify-between">
                <p className="text-sm text-green-400">
                  ✅ Resume uploaded
                </p>
                <button
                  onClick={() => setShowResumeUpload(true)}
                  className="text-xs text-green-500 hover:text-green-400"
                >
                  Update
                </button>
              </div>
            </div>
          )}
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

      {/* In-Tab Confirmation Modal */}
      {showConfirmModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-gray-800 rounded-lg p-6 w-80">
            <h3 className="text-lg font-bold mb-2">Confirm running in active tab</h3>
            <p className="text-sm text-gray-400 mb-3">This will execute steps within your current tab using your logged-in session. Only proceed if you trust the site and want to use your account.</p>
            <label className="flex items-center gap-2 text-sm mb-3">
              <input type="checkbox" checked={skipInTabConfirm} onChange={(e) => { setSkipInTabConfirm(e.target.checked); chrome.storage.local.set({ skipInTabConfirm: e.target.checked }); }} />
              Don't ask me again
            </label>
            <div className="flex justify-end gap-2">
              <button className="px-3 py-1 rounded bg-gray-700 hover:bg-gray-600" onClick={() => setShowConfirmModal(false)}>Cancel</button>
              <button className="px-3 py-1 rounded bg-blue-600 hover:bg-blue-700" onClick={() => { setShowConfirmModal(false); proceedWithExecute(); }}>Confirm</button>
            </div>
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
