/**
 * JobHunter Extension - Popup Component
 * React-based popup UI with Tailwind CSS styling
 * 
 * Features (from FR-04):
 * - UI Overlay displaying AI's "Thought Process"
 * - One-Click Approve action
 * - Status indicators
 */

import { useState, useEffect } from 'react';
import type { PopupState, FillStatus, JobContext } from './types';
import './styles/globals.css';

// Status icons
const StatusIcon = ({ status }: { status: FillStatus }) => {
  const icons = {
    idle: '🎯',
    scanning: '🔍',
    generating: '🧠',
    filling: '✍️',
    complete: '✅',
    error: '❌',
  };
  return <span className="text-2xl">{icons[status]}</span>;
};

// Job context display
const JobContextCard = ({ context }: { context: JobContext }) => (
  <div className="bg-primary-50 border border-primary-200 rounded-lg p-3 mb-4">
    <h4 className="text-sm font-semibold text-primary-800 mb-1">📋 Job Detected</h4>
    {context.title && <p className="text-xs text-primary-700">{context.title}</p>}
    {context.company && <p className="text-xs text-primary-600">{context.company}</p>}
    {context.skills && context.skills.length > 0 && (
      <div className="flex flex-wrap gap-1 mt-2">
        {context.skills.slice(0, 5).map((skill) => (
          <span
            key={skill}
            className="px-2 py-0.5 bg-primary-100 text-primary-700 text-xs rounded-full"
          >
            {skill}
          </span>
        ))}
      </div>
    )}
  </div>
);

function Popup() {
  const [state, setState] = useState<PopupState>({
    status: 'idle',
    message: 'Ready to auto-fill',
    fieldsFound: 0,
    fieldsFilled: 0,
    fieldsFlagged: 0,
    errors: [],
  });

  const [apiStatus, setApiStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [resumeUploaded, setResumeUploaded] = useState(false);

  // Check API and resume status on mount
  useEffect(() => {
    checkStatus();
  }, []);

  async function checkStatus() {
    try {
      // Check API
      const response = await fetch('http://localhost:8001/api/v1/health');
      if (response.ok) {
        setApiStatus('online');
        
        // Check resume status
        const statsResponse = await fetch('http://localhost:8001/api/v1/query/stats');
        if (statsResponse.ok) {
          const stats = await statsResponse.json();
          setResumeUploaded(stats.document_count > 0);
        }
      } else {
        setApiStatus('offline');
      }
    } catch {
      setApiStatus('offline');
    }
  }

  async function handleAutoFill() {
    if (apiStatus !== 'online') {
      setState((s) => ({ ...s, status: 'error', message: 'Backend not available' }));
      return;
    }

    if (!resumeUploaded) {
      setState((s) => ({ ...s, status: 'error', message: 'Please upload your resume first' }));
      return;
    }

    setState((s) => ({ ...s, status: 'scanning', message: 'Scanning form...' }));

    try {
      // Get current tab
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab.id) throw new Error('No active tab');

      // Send message to content script
      const response = await chrome.tabs.sendMessage(tab.id, { action: 'autoFill' });

      if (response.success) {
        setState({
          status: 'complete',
          message: response.message,
          fieldsFound: response.fieldsFound || 0,
          fieldsFilled: response.fieldsFilled || 0,
          fieldsFlagged: response.fieldsFlagged || 0,
          jobContext: response.jobContext,
          errors: response.errors?.map((e: any) => e.error) || [],
        });
      } else {
        setState((s) => ({
          ...s,
          status: 'error',
          message: response.error || response.message || 'Auto-fill failed',
        }));
      }
    } catch (error: any) {
      setState((s) => ({
        ...s,
        status: 'error',
        message: error.message || 'Failed to communicate with page',
      }));
    }
  }

  async function handleCaptureFeedback() {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab.id) return;

      await chrome.tabs.sendMessage(tab.id, { action: 'captureFeedback' });
      setState((s) => ({ ...s, message: 'Feedback captured!' }));
    } catch (error) {
      console.error('Feedback error:', error);
    }
  }

  return (
    <div className="w-80 p-4 bg-white">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🎯</span>
          <h1 className="text-lg font-bold text-gray-800">JobHunter</h1>
        </div>
        <div className="flex items-center gap-1">
          <span
            className={`w-2 h-2 rounded-full ${
              apiStatus === 'online'
                ? 'bg-green-500'
                : apiStatus === 'offline'
                ? 'bg-red-500'
                : 'bg-yellow-500 animate-pulse'
            }`}
          />
          <span className="text-xs text-gray-500">
            {apiStatus === 'online' ? 'Connected' : apiStatus === 'offline' ? 'Offline' : 'Checking...'}
          </span>
        </div>
      </div>

      {/* Resume Status */}
      {!resumeUploaded && apiStatus === 'online' && (
        <div className="bg-warning-50 border border-warning-200 rounded-lg p-3 mb-4">
          <p className="text-sm text-warning-800">
            ⚠️ No resume uploaded. Please upload your resume at{' '}
            <span className="font-mono text-xs">localhost:8001/docs</span>
          </p>
        </div>
      )}

      {/* Status Display */}
      <div className="bg-gray-50 rounded-lg p-4 mb-4">
        <div className="flex items-center gap-3 mb-2">
          <StatusIcon status={state.status} />
          <div>
            <p className="font-medium text-gray-800">
              {state.status === 'idle' && 'Ready'}
              {state.status === 'scanning' && 'Scanning...'}
              {state.status === 'generating' && 'AI Thinking...'}
              {state.status === 'filling' && 'Filling Form...'}
              {state.status === 'complete' && 'Complete!'}
              {state.status === 'error' && 'Error'}
            </p>
            <p className="text-sm text-gray-600">{state.message}</p>
          </div>
        </div>

        {/* Results */}
        {state.status === 'complete' && (
          <div className="grid grid-cols-3 gap-2 mt-3 pt-3 border-t border-gray-200">
            <div className="text-center">
              <p className="text-lg font-bold text-primary-600">{state.fieldsFilled}</p>
              <p className="text-xs text-gray-500">Filled</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-bold text-gray-400">{state.fieldsFound - state.fieldsFilled}</p>
              <p className="text-xs text-gray-500">Skipped</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-bold text-warning-500">{state.fieldsFlagged}</p>
              <p className="text-xs text-gray-500">Review</p>
            </div>
          </div>
        )}
      </div>

      {/* Job Context */}
      {state.jobContext && <JobContextCard context={state.jobContext} />}

      {/* Action Buttons */}
      <div className="space-y-2">
        <button
          onClick={handleAutoFill}
          disabled={state.status === 'scanning' || state.status === 'generating' || state.status === 'filling'}
          className={`w-full py-3 px-4 rounded-lg font-medium text-white transition-all ${
            state.status === 'scanning' || state.status === 'generating' || state.status === 'filling'
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-primary-600 hover:bg-primary-700 active:scale-98 shadow-md hover:shadow-lg'
          }`}
        >
          {state.status === 'scanning' || state.status === 'generating' || state.status === 'filling' ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                  fill="none"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              Processing...
            </span>
          ) : (
            '🚀 Auto-Fill Application'
          )}
        </button>

        {state.status === 'complete' && state.fieldsFilled > 0 && (
          <button
            onClick={handleCaptureFeedback}
            className="w-full py-2 px-4 rounded-lg font-medium text-primary-700 bg-primary-50 hover:bg-primary-100 transition-all"
          >
            💾 Save My Edits
          </button>
        )}
      </div>

      {/* Errors */}
      {state.errors.length > 0 && (
        <div className="mt-4 p-3 bg-danger-50 rounded-lg">
          <p className="text-sm font-medium text-danger-600 mb-1">Issues:</p>
          <ul className="text-xs text-danger-500 space-y-1">
            {state.errors.slice(0, 3).map((err, i) => (
              <li key={i}>• {err}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Footer */}
      <div className="mt-4 pt-3 border-t border-gray-100 text-center">
        <p className="text-xs text-gray-400">JobHunter v1.0.0 • AI-Powered</p>
      </div>
    </div>
  );
}

export default Popup;
