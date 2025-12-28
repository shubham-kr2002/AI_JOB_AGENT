/**
 * Project JobHunter V3 - Task Graph Visualization
 * Renders the DAG as a visual timeline with status badges
 */

import { useMemo } from 'react';
import { 
  Circle, 
  CheckCircle2, 
  XCircle, 
  Loader2, 
  Clock,
  ArrowDown,
  GitBranch
} from 'lucide-react';
import { clsx } from 'clsx';
import type { TaskStep, TaskStatus } from '@/types';

interface TaskGraphProps {
  steps: TaskStep[];
  compact?: boolean;
}

interface GraphNode {
  step: TaskStep;
  level: number;
  parallelGroup?: string;
}

export function TaskGraph({ steps, compact = false }: TaskGraphProps) {
  // Group steps by dependency level for visualization
  const graphNodes = useMemo(() => {
    const nodes: GraphNode[] = [];
    const processedIds = new Set<string>();
    
    // Find steps with no dependencies (root nodes)
    const rootSteps = steps.filter(s => s.dependencies.length === 0);
    
    // BFS to assign levels
    let currentLevel = 0;
    let currentLevelSteps = rootSteps;
    
    while (currentLevelSteps.length > 0) {
      // Check for parallel steps at this level
      const parallelGroup = currentLevelSteps.length > 1 
        ? `level-${currentLevel}` 
        : undefined;
      
      currentLevelSteps.forEach(step => {
        if (!processedIds.has(step.id)) {
          nodes.push({
            step,
            level: currentLevel,
            parallelGroup,
          });
          processedIds.add(step.id);
        }
      });
      
      // Find next level - steps whose dependencies are all processed
      const nextLevelSteps = steps.filter(s => 
        !processedIds.has(s.id) &&
        s.dependencies.every(dep => processedIds.has(dep))
      );
      
      currentLevel++;
      currentLevelSteps = nextLevelSteps;
    }
    
    return nodes;
  }, [steps]);

  // Group nodes by level for parallel display
  const levelGroups = useMemo(() => {
    const groups: Map<number, GraphNode[]> = new Map();
    
    graphNodes.forEach(node => {
      const level = groups.get(node.level) || [];
      level.push(node);
      groups.set(node.level, level);
    });
    
    return Array.from(groups.entries()).sort((a, b) => a[0] - b[0]);
  }, [graphNodes]);

  if (steps.length === 0) {
    return (
      <div className="text-center py-8 text-slate-500">
        No steps to display
      </div>
    );
  }

  return (
    <div className={clsx(
      'relative',
      compact ? 'py-2' : 'py-4'
    )}>
      {/* Central timeline line */}
      <div className="absolute left-1/2 top-0 bottom-0 w-px bg-slate-700 transform -translate-x-1/2" />
      
      {levelGroups.map(([level, nodes], levelIndex) => (
        <div key={level} className="relative">
          {/* Level connector arrow */}
          {levelIndex > 0 && (
            <div className="flex justify-center py-2">
              <ArrowDown className="w-4 h-4 text-slate-600" />
            </div>
          )}
          
          {/* Nodes at this level */}
          <div className={clsx(
            'flex justify-center gap-4',
            nodes.length > 1 ? 'flex-row' : 'flex-col items-center'
          )}>
            {nodes.length > 1 && (
              <div className="absolute left-1/2 transform -translate-x-1/2 -top-3">
                <div className="flex items-center gap-1 text-xs text-slate-500">
                  <GitBranch className="w-3 h-3" />
                  <span>Parallel</span>
                </div>
              </div>
            )}
            
            {nodes.map((node) => (
              <TaskNode 
                key={node.step.id} 
                step={node.step} 
                compact={compact}
                isParallel={nodes.length > 1}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

interface TaskNodeProps {
  step: TaskStep;
  compact?: boolean;
  isParallel?: boolean;
}

function TaskNode({ step, compact = false, isParallel = false }: TaskNodeProps) {
  const statusConfig = getStatusConfig(step.status);
  
  return (
    <div
      className={clsx(
        'relative flex items-center gap-3',
        'p-3 rounded-lg border',
        'transition-all duration-300',
        statusConfig.bgClass,
        statusConfig.borderClass,
        compact ? 'min-w-[150px]' : 'min-w-[200px] max-w-[280px]',
        isParallel && 'flex-1'
      )}
    >
      {/* Status Icon */}
      <div className={clsx(
        'flex-shrink-0 p-1 rounded-full',
        statusConfig.iconBgClass
      )}>
        <StatusIcon status={step.status} />
      </div>
      
      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className={clsx(
          'font-medium truncate',
          compact ? 'text-xs' : 'text-sm',
          statusConfig.textClass
        )}>
          {step.name}
        </div>
        <div className="text-xs text-slate-500 terminal-text truncate">
          {step.action}
        </div>
        {step.error && (
          <div className="text-xs text-red-400 mt-1 truncate">
            {step.error}
          </div>
        )}
        {step.duration_ms && step.status === 'completed' && (
          <div className="text-xs text-slate-500 mt-1">
            {formatDuration(step.duration_ms)}
          </div>
        )}
      </div>
      
      {/* Status Badge */}
      <div className={clsx(
        'flex-shrink-0 px-2 py-0.5 rounded text-xs font-medium',
        statusConfig.badgeClass
      )}>
        {step.status}
      </div>
    </div>
  );
}

function StatusIcon({ status }: { status: TaskStatus }) {
  switch (status) {
    case 'completed':
      return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
    case 'running':
      return <Loader2 className="w-4 h-4 text-yellow-400 animate-spin" />;
    case 'failed':
      return <XCircle className="w-4 h-4 text-red-400" />;
    case 'paused':
      return <Clock className="w-4 h-4 text-orange-400" />;
    default:
      return <Circle className="w-4 h-4 text-slate-500" />;
  }
}

function getStatusConfig(status: TaskStatus) {
  switch (status) {
    case 'completed':
      return {
        bgClass: 'bg-emerald-900/20',
        borderClass: 'border-emerald-500/50',
        textClass: 'text-emerald-300',
        iconBgClass: 'bg-emerald-900/50',
        badgeClass: 'bg-emerald-500/20 text-emerald-400',
      };
    case 'running':
      return {
        bgClass: 'bg-yellow-900/20',
        borderClass: 'border-yellow-500/50 animate-pulse',
        textClass: 'text-yellow-300',
        iconBgClass: 'bg-yellow-900/50',
        badgeClass: 'bg-yellow-500/20 text-yellow-400',
      };
    case 'failed':
      return {
        bgClass: 'bg-red-900/20',
        borderClass: 'border-red-500/50',
        textClass: 'text-red-300',
        iconBgClass: 'bg-red-900/50',
        badgeClass: 'bg-red-500/20 text-red-400',
      };
    case 'paused':
      return {
        bgClass: 'bg-orange-900/20',
        borderClass: 'border-orange-500/50',
        textClass: 'text-orange-300',
        iconBgClass: 'bg-orange-900/50',
        badgeClass: 'bg-orange-500/20 text-orange-400',
      };
    default:
      return {
        bgClass: 'bg-slate-800',
        borderClass: 'border-slate-700',
        textClass: 'text-slate-300',
        iconBgClass: 'bg-slate-700',
        badgeClass: 'bg-slate-700 text-slate-400',
      };
  }
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
}
