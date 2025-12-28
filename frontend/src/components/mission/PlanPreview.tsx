/**
 * Project JobHunter V3 - Plan Preview Component
 * Shows the compiled plan before execution
 */

import { X, Play, AlertCircle, CheckCircle2, Clock, Layers } from 'lucide-react';
import { clsx } from 'clsx';
import { useTaskStore, useUIStore } from '@/store';
import { api } from '@/lib/api';

export function PlanPreview() {
  const { currentPlan, setTaskStatus } = useTaskStore();
  const { showPlanPreview, setShowPlanPreview, setLoading } = useUIStore();

  if (!showPlanPreview || !currentPlan) return null;

  const handleExecute = async () => {
    setShowPlanPreview(false);
    setLoading(true, 'Executing mission...');
    setTaskStatus('running');
    
    try {
      await api.executeTask(currentPlan.id);
    } catch (error) {
      console.error('Error executing task:', error);
      setTaskStatus('failed');
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    setShowPlanPreview(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className={clsx(
        'w-full max-w-2xl max-h-[80vh] overflow-hidden',
        'bg-slate-900 border border-slate-700 rounded-xl shadow-2xl',
        'animate-in fade-in zoom-in-95 duration-200'
      )}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-700">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-emerald-500/20">
              <Layers className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <h3 className="font-semibold text-slate-200">Mission Plan Compiled</h3>
              <p className="text-xs text-slate-500 terminal-text">
                Task ID: {currentPlan.id}
              </p>
            </div>
          </div>
          <button
            onClick={handleCancel}
            className="p-2 text-slate-400 hover:text-slate-200 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 overflow-y-auto max-h-[calc(80vh-140px)]">
          {/* Goal Section */}
          <div className="mb-6">
            <h4 className="text-sm font-medium text-slate-400 mb-2 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
              GOAL
            </h4>
            <div className="p-3 rounded-lg bg-slate-800 border border-slate-700">
              <div className="text-slate-200 text-lg">
                {currentPlan.goal}
              </div>
            </div>
          </div>

          {/* Constraints Section */}
          {currentPlan.constraints.length > 0 && (
            <div className="mb-6">
              <h4 className="text-sm font-medium text-slate-400 mb-2 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-yellow-500" />
                CONSTRAINTS
              </h4>
              <div className="flex flex-wrap gap-2">
                {currentPlan.constraints.map((constraint, index) => (
                  <span
                    key={index}
                    className="px-3 py-1.5 rounded-lg text-sm bg-slate-800 border border-slate-700 text-slate-300"
                  >
                    {constraint}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Steps Section */}
          <div>
            <h4 className="text-sm font-medium text-slate-400 mb-2 flex items-center gap-2">
              <Clock className="w-4 h-4 text-cyan-500" />
              EXECUTION STEPS ({currentPlan.steps.length})
            </h4>
            <div className="space-y-2">
              {currentPlan.steps.map((step, index) => (
                <div
                  key={step.id}
                  className={clsx(
                    'p-3 rounded-lg border',
                    'bg-slate-800/50 border-slate-700',
                    'flex items-center gap-3'
                  )}
                >
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-slate-700 flex items-center justify-center text-xs text-slate-400">
                    {index + 1}
                  </div>
                  <div className="flex-1">
                    <div className="text-slate-200 text-sm font-medium">{step.name}</div>
                    <div className="text-slate-500 text-xs terminal-text">{step.action}</div>
                  </div>
                  {step.dependencies.length > 0 && (
                    <div className="text-xs text-slate-500">
                      ← depends on: {step.dependencies.join(', ')}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Estimated Time */}
          {currentPlan.estimated_duration_seconds && (
            <div className="mt-4 p-3 rounded-lg bg-cyan-500/10 border border-cyan-500/20">
              <div className="flex items-center gap-2 text-cyan-400 text-sm">
                <Clock className="w-4 h-4" />
                <span>
                  Estimated time: {formatDuration(currentPlan.estimated_duration_seconds)}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-4 border-t border-slate-700 bg-slate-900/50">
          <button
            onClick={handleCancel}
            className="btn-secondary"
          >
            Cancel
          </button>
          <button
            onClick={handleExecute}
            className="btn-primary flex items-center gap-2"
          >
            <Play className="w-4 h-4" />
            Execute Mission
          </button>
        </div>
      </div>
    </div>
  );
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds} seconds`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 60) {
    return remainingSeconds > 0 
      ? `${minutes}m ${remainingSeconds}s` 
      : `${minutes} minutes`;
  }
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}
