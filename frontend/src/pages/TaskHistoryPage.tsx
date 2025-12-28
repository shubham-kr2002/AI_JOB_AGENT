/**
 * Project JobHunter V3 - Task History Page
 * Shows past missions and their results
 */

import { useState, useEffect } from 'react';
import { 
  History, 
  Clock, 
  CheckCircle2, 
  XCircle, 
  PlayCircle,
  ChevronRight,
  Search,
  Calendar,
  Target
} from 'lucide-react';
import { clsx } from 'clsx';
import type { TaskStatus } from '@/types';

interface TaskHistoryItem {
  id: string;
  goal: string;
  constraints: string[];
  status: TaskStatus;
  steps_completed: number;
  steps_total: number;
  created_at: string;
  completed_at?: string;
  duration_seconds?: number;
}

export function TaskHistoryPage() {
  const [tasks, setTasks] = useState<TaskHistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<TaskStatus | 'all'>('all');

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    setIsLoading(true);
    // TODO: Implement API call to get task history
    // For now, using mock data
    setTimeout(() => {
      setTasks(mockTasks);
      setIsLoading(false);
    }, 500);
  };

  const filteredTasks = tasks
    .filter(task => 
      task.goal.toLowerCase().includes(searchQuery.toLowerCase())
    )
    .filter(task => 
      statusFilter === 'all' || task.status === statusFilter
    );

  const stats = {
    total: tasks.length,
    completed: tasks.filter(t => t.status === 'completed').length,
    failed: tasks.filter(t => t.status === 'failed').length,
    running: tasks.filter(t => t.status === 'running').length,
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-purple-500/20">
          <History className="w-6 h-6 text-purple-400" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-slate-200">Task History</h1>
          <p className="text-sm text-slate-400">
            Review past missions and their outcomes
          </p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Total Missions" value={stats.total} color="text-slate-300" />
        <StatCard label="Completed" value={stats.completed} color="text-emerald-400" />
        <StatCard label="Failed" value={stats.failed} color="text-red-400" />
        <StatCard label="Running" value={stats.running} color="text-yellow-400" />
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search tasks..."
            className="w-full pl-10 input-primary"
          />
        </div>
        
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as TaskStatus | 'all')}
          className="input-primary"
        >
          <option value="all">All Status</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="running">Running</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      {/* Task List */}
      <div className="space-y-3">
        {isLoading ? (
          <div className="card text-center py-8 text-slate-400">
            Loading task history...
          </div>
        ) : filteredTasks.length === 0 ? (
          <div className="card text-center py-8">
            <History className="w-8 h-8 mx-auto mb-2 text-slate-500" />
            <p className="text-slate-400">No tasks found</p>
          </div>
        ) : (
          filteredTasks.map((task) => (
            <TaskCard key={task.id} task={task} />
          ))
        )}
      </div>
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: number;
  color: string;
}

function StatCard({ label, value, color }: StatCardProps) {
  return (
    <div className="card">
      <div className={clsx('text-2xl font-bold mb-1', color)}>{value}</div>
      <div className="text-sm text-slate-400">{label}</div>
    </div>
  );
}

interface TaskCardProps {
  task: TaskHistoryItem;
}

function TaskCard({ task }: TaskCardProps) {
  const statusIcon: Record<TaskStatus, JSX.Element> = {
    completed: <CheckCircle2 className="w-5 h-5 text-emerald-400" />,
    failed: <XCircle className="w-5 h-5 text-red-400" />,
    running: <PlayCircle className="w-5 h-5 text-yellow-400 animate-pulse" />,
    pending: <Clock className="w-5 h-5 text-slate-400" />,
    cancelled: <XCircle className="w-5 h-5 text-slate-500" />,
    paused: <Clock className="w-5 h-5 text-orange-400" />,
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '-';
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  return (
    <div className="card hover:bg-slate-700/50 cursor-pointer transition-colors">
      <div className="flex items-center gap-4">
        {/* Status Icon */}
        <div className="p-2 rounded-lg bg-slate-800">
          {statusIcon[task.status]}
        </div>

        {/* Task Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Target className="w-4 h-4 text-slate-400" />
            <span className="font-medium text-slate-200 truncate">{task.goal}</span>
          </div>
          <div className="flex items-center gap-4 text-sm text-slate-400">
            <span className="flex items-center gap-1">
              <Calendar className="w-3 h-3" />
              {formatDate(task.created_at)}
            </span>
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDuration(task.duration_seconds)}
            </span>
            <span>
              Steps: {task.steps_completed}/{task.steps_total}
            </span>
          </div>
        </div>

        {/* Progress */}
        <div className="w-24">
          <div className="h-2 rounded-full bg-slate-700 overflow-hidden">
            <div 
              className={clsx(
                'h-full rounded-full',
                task.status === 'completed' ? 'bg-emerald-500' :
                task.status === 'failed' ? 'bg-red-500' :
                task.status === 'running' ? 'bg-yellow-500' : 'bg-slate-500'
              )}
              style={{ width: `${(task.steps_completed / task.steps_total) * 100}%` }}
            />
          </div>
        </div>

        <ChevronRight className="w-4 h-4 text-slate-500" />
      </div>
    </div>
  );
}

// Mock data for development
const mockTasks: TaskHistoryItem[] = [
  {
    id: '1',
    goal: 'Apply to 10 Software Engineer jobs in San Francisco',
    constraints: ['Remote friendly', 'Salary > $150k'],
    steps_completed: 10,
    steps_total: 10,
    status: 'completed',
    created_at: '2024-01-15T10:30:00Z',
    completed_at: '2024-01-15T11:15:00Z',
    duration_seconds: 2700,
  },
  {
    id: '2',
    goal: 'Search and save Frontend Developer positions',
    constraints: ['React experience', 'Startup culture'],
    steps_completed: 5,
    steps_total: 8,
    status: 'running',
    created_at: '2024-01-15T14:00:00Z',
  },
  {
    id: '3',
    goal: 'Update LinkedIn profile with new skills',
    constraints: [],
    steps_completed: 2,
    steps_total: 5,
    status: 'failed',
    created_at: '2024-01-14T09:00:00Z',
    duration_seconds: 180,
  },
];
