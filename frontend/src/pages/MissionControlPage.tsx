/**
 * Project JobHunter V3 - Mission Control Page
 * Main dashboard combining CommandInput, TaskGraph, and LiveTerminal
 */

import { Crosshair, Zap } from 'lucide-react';
import { CommandInput, PlanPreview, TaskGraph, LiveTerminal } from '@/components/mission';
import { useTaskStore, useUIStore } from '@/store';

export function MissionControlPage() {
  const { currentPlan, taskStatus } = useTaskStore();
  const { showPlanPreview } = useUIStore();
  
  const hasActiveMission = currentPlan && taskStatus !== 'pending';

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 p-6 pb-4">
        <div className="p-2 rounded-lg bg-emerald-500/20">
          <Crosshair className="w-6 h-6 text-emerald-400" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-slate-200">Mission Control</h1>
          <p className="text-sm text-slate-400">
            {hasActiveMission 
              ? `Executing: ${currentPlan.goal}` 
              : 'Enter a natural language command to begin'
            }
          </p>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-hidden p-6 pt-0">
        {hasActiveMission ? (
          <ActiveMissionView />
        ) : (
          <NewMissionView />
        )}
      </div>

      {/* Plan Preview Modal */}
      {showPlanPreview && <PlanPreview />}
    </div>
  );
}

/**
 * View when no active mission - shows command input
 */
function NewMissionView() {
  return (
    <div className="h-full flex flex-col items-center justify-center">
      <div className="w-full max-w-3xl space-y-8">
        {/* Hero */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm mb-4">
            <Zap className="w-4 h-4" />
            <span>Ready for Mission</span>
          </div>
          <h2 className="text-2xl font-bold text-slate-200 mb-2">
            What would you like to accomplish?
          </h2>
          <p className="text-slate-400">
            Describe your job hunting goal and the agent will create an execution plan
          </p>
        </div>

        {/* Command Input */}
        <CommandInput />

        {/* Tips */}
        <div className="grid grid-cols-3 gap-4 text-sm">
          <TipCard
            title="Be Specific"
            description="Include job titles, locations, and company preferences"
          />
          <TipCard
            title="Set Limits"
            description="Specify how many jobs to apply for per session"
          />
          <TipCard
            title="Save Progress"
            description="The agent learns and improves from each session"
          />
        </div>
      </div>
    </div>
  );
}

interface TipCardProps {
  title: string;
  description: string;
}

function TipCard({ title, description }: TipCardProps) {
  return (
    <div className="card text-center">
      <div className="text-slate-300 font-medium mb-1">{title}</div>
      <div className="text-slate-500 text-xs">{description}</div>
    </div>
  );
}

/**
 * View when mission is active - shows graph and terminal
 */
function ActiveMissionView() {
  const { currentPlan, taskStatus, steps } = useTaskStore();
  
  if (!currentPlan) return null;

  return (
    <div className="h-full grid grid-cols-2 gap-6">
      {/* Left: Task Graph */}
      <div className="flex flex-col min-h-0">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-slate-300">Execution Graph</h3>
          <StatusBadge status={taskStatus} />
        </div>
        <div className="flex-1 overflow-auto">
          <TaskGraph steps={steps} />
        </div>
      </div>

      {/* Right: Live Terminal */}
      <div className="flex flex-col min-h-0">
        <h3 className="text-sm font-medium text-slate-300 mb-3">Live Feed</h3>
        <div className="flex-1 min-h-0">
          <LiveTerminal taskId={currentPlan.id} />
        </div>
      </div>
    </div>
  );
}

interface StatusBadgeProps {
  status: string;
}

function StatusBadge({ status }: StatusBadgeProps) {
  const statusConfig: Record<string, { bg: string; text: string; label: string }> = {
    pending: { bg: 'bg-slate-500/20', text: 'text-slate-400', label: 'Pending' },
    running: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: 'Running' },
    completed: { bg: 'bg-emerald-500/20', text: 'text-emerald-400', label: 'Completed' },
    failed: { bg: 'bg-red-500/20', text: 'text-red-400', label: 'Failed' },
    cancelled: { bg: 'bg-slate-500/20', text: 'text-slate-400', label: 'Cancelled' },
  };

  const config = statusConfig[status] || statusConfig.pending;

  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${config.bg} ${config.text}`}>
      {config.label}
    </span>
  );
}
