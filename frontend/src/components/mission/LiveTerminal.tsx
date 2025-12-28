/**
 * Project JobHunter V3 - Live Terminal Component
 * Real-time execution log viewer with WebSocket connection
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { 
  Terminal as TerminalIcon, 
  Pause, 
  Play, 
  Trash2, 
  Download,
  Maximize2,
  Minimize2
} from 'lucide-react';
import { clsx } from 'clsx';
import { useTaskStore } from '@/store';
import { TaskWebSocket } from '@/lib/api';
import type { LogEntry, LogLevel, WSMessage } from '@/types';

interface LiveTerminalProps {
  taskId?: string;
  className?: string;
}

export function LiveTerminal({ taskId, className }: LiveTerminalProps) {
  const { logs, addLog, clearLogs, updateStepStatus, setTaskStatus } = useTaskStore();
  const [isPaused, setIsPaused] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const terminalRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<TaskWebSocket | null>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (!isPaused && terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [logs, isPaused]);

  // WebSocket connection
  useEffect(() => {
    if (!taskId) return;

    wsRef.current = new TaskWebSocket(taskId, {
      onMessage: (data: unknown) => handleWSMessage(data as WSMessage),
      onError: () => setIsConnected(false),
      onClose: () => setIsConnected(false),
    });

    wsRef.current.connect();
    setIsConnected(true);

    return () => {
      wsRef.current?.disconnect();
    };
  }, [taskId]);

  const handleWSMessage = useCallback((message: WSMessage) => {
    switch (message.type) {
      case 'log':
        addLog(message.payload as LogEntry);
        break;
      case 'step_complete':
        const step = message.payload as { id: string; status: 'completed' | 'failed'; error?: string };
        updateStepStatus(step.id, step.status, step.error);
        break;
      case 'task_complete':
        const task = message.payload as { status: 'completed' | 'failed' };
        setTaskStatus(task.status);
        break;
      case 'error':
        addLog({
          id: `error-${Date.now()}`,
          timestamp: new Date().toISOString(),
          level: 'ERROR',
          message: String(message.payload),
        });
        break;
    }
  }, [addLog, updateStepStatus, setTaskStatus]);

  const handleExport = () => {
    const content = logs
      .map(log => `[${log.timestamp}] [${log.level}] ${log.message}`)
      .join('\n');
    
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `task-${taskId || 'logs'}-${Date.now()}.log`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className={clsx(
      'flex flex-col bg-black rounded-lg border border-slate-700 overflow-hidden',
      isExpanded ? 'fixed inset-4 z-50' : '',
      className
    )}>
      {/* Terminal Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-slate-900 border-b border-slate-700">
        <div className="flex items-center gap-3">
          {/* Window dots */}
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500" />
            <div className="w-3 h-3 rounded-full bg-yellow-500" />
            <div className="w-3 h-3 rounded-full bg-green-500" />
          </div>
          
          <div className="flex items-center gap-2 text-slate-400">
            <TerminalIcon className="w-4 h-4" />
            <span className="text-sm terminal-text">Live Execution Feed</span>
          </div>
          
          {/* Connection status */}
          <div className={clsx(
            'flex items-center gap-1.5 px-2 py-0.5 rounded text-xs',
            isConnected 
              ? 'bg-emerald-900/50 text-emerald-400' 
              : 'bg-slate-800 text-slate-500'
          )}>
            <div className={clsx(
              'w-1.5 h-1.5 rounded-full',
              isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'
            )} />
            {isConnected ? 'Connected' : 'Disconnected'}
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setIsPaused(!isPaused)}
            className="p-1.5 text-slate-400 hover:text-white transition-colors"
            title={isPaused ? 'Resume auto-scroll' : 'Pause auto-scroll'}
          >
            {isPaused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
          </button>
          <button
            onClick={clearLogs}
            className="p-1.5 text-slate-400 hover:text-white transition-colors"
            title="Clear logs"
          >
            <Trash2 className="w-4 h-4" />
          </button>
          <button
            onClick={handleExport}
            className="p-1.5 text-slate-400 hover:text-white transition-colors"
            title="Export logs"
          >
            <Download className="w-4 h-4" />
          </button>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1.5 text-slate-400 hover:text-white transition-colors"
            title={isExpanded ? 'Minimize' : 'Maximize'}
          >
            {isExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Terminal Content */}
      <div
        ref={terminalRef}
        className={clsx(
          'flex-1 overflow-y-auto p-4 terminal-text text-sm',
          'scrollbar-thin scrollbar-track-black scrollbar-thumb-slate-700'
        )}
      >
        {logs.length === 0 ? (
          <div className="text-slate-600 italic">
            Waiting for task execution...
            <span className="cursor-blink ml-1" />
          </div>
        ) : (
          logs.map((log) => (
            <LogLine key={log.id} log={log} />
          ))
        )}
      </div>

      {/* Status bar */}
      <div className="flex items-center justify-between px-4 py-1.5 bg-slate-900 border-t border-slate-800 text-xs text-slate-500">
        <span>{logs.length} entries</span>
        {isPaused && <span className="text-yellow-500">⏸ Auto-scroll paused</span>}
        <span>{taskId ? `Task: ${taskId.slice(0, 8)}...` : 'No active task'}</span>
      </div>
    </div>
  );
}

function LogLine({ log }: { log: LogEntry }) {
  const colorClass = getLogColorClass(log.level);
  const timestamp = new Date(log.timestamp).toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

  return (
    <div className="flex gap-2 py-0.5 hover:bg-slate-900/50">
      {/* Timestamp */}
      <span className="text-slate-600 flex-shrink-0">
        [{timestamp}]
      </span>
      
      {/* Level badge */}
      <span className={clsx('flex-shrink-0 font-medium', colorClass)}>
        [{log.level}]
      </span>
      
      {/* Message */}
      <span className={clsx('flex-1', colorClass)}>
        {formatMessage(log.message, log.level)}
      </span>
    </div>
  );
}

function getLogColorClass(level: LogLevel): string {
  switch (level) {
    case 'INFO':
      return 'text-slate-300';
    case 'ACTION':
      return 'text-cyan-400';
    case 'SUCCESS':
      return 'text-emerald-400';
    case 'ERROR':
      return 'text-red-400';
    case 'WARNING':
      return 'text-yellow-400';
    case 'DEBUG':
      return 'text-slate-500';
    default:
      return 'text-slate-400';
  }
}

function formatMessage(message: string, level: LogLevel): React.ReactNode {
  // Highlight URLs
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  const parts = message.split(urlRegex);
  
  return parts.map((part, i) => {
    if (part.match(urlRegex)) {
      return (
        <a
          key={i}
          href={part}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-400 hover:underline"
        >
          {part}
        </a>
      );
    }
    
    // Highlight selectors (CSS-like patterns)
    if (level === 'ACTION') {
      return part.replace(
        /(['"]\.?[a-zA-Z#][^'"]*['"])/g,
        '<span class="text-yellow-300">$1</span>'
      );
    }
    
    return part;
  });
}
