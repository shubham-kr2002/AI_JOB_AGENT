/**
 * Project JobHunter V3 - Type Definitions
 * Matches backend API schemas
 */

// ============================================================================
// Task & Plan Types
// ============================================================================

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'paused' | 'cancelled';

export interface TaskStep {
  id: string;
  name: string;
  action: string;
  status: TaskStatus;
  dependencies: string[];
  payload?: Record<string, unknown>;
  error?: string;
  duration_ms?: number;
}

export interface TaskPlan {
  id: string;
  goal: string;
  constraints: string[];
  steps: TaskStep[];
  status: TaskStatus;
  estimated_duration_seconds?: number;
  created_at: string;
}

export interface TaskGraph {
  nodes: TaskStep[];
  edges: { from: string; to: string }[];
}

// ============================================================================
// Log Types
// ============================================================================

export type LogLevel = 'INFO' | 'ACTION' | 'SUCCESS' | 'ERROR' | 'WARNING' | 'DEBUG';

export interface LogEntry {
  id: string;
  timestamp: string;
  level: LogLevel;
  message: string;
  step_id?: string;
  metadata?: Record<string, unknown>;
}

// ============================================================================
// World Model Types
// ============================================================================

export interface SiteConfig {
  domain: string;
  name: string;
  category: 'job_board' | 'ats' | 'company_career' | 'aggregator';
  selectors: Record<string, unknown>;
  workflows?: Record<string, unknown>;
  login_config?: Record<string, unknown>;
  behavior?: Record<string, unknown>;
  success_count: number;
  failure_count: number;
  last_successful_at?: string;
  last_failed_at?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface WorldModelStats {
  total_domains: number;
  total_selectors: number;
  average_success_rate: number;
  most_used_domains: { domain: string; usage_count: number }[];
}

// ============================================================================
// API Response Types
// ============================================================================

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface PlanResponse {
  task_id: string;
  plan: TaskPlan;
  message: string;
}

// ============================================================================
// WebSocket Message Types
// ============================================================================

export interface WSMessage {
  type: 'log' | 'status_update' | 'step_complete' | 'task_complete' | 'error';
  payload: LogEntry | TaskStep | { task_id: string; status: TaskStatus };
}
