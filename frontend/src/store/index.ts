/**
 * Project JobHunter V3 - Global State Store
 * Using Zustand for lightweight state management
 */

import { create } from 'zustand';
import type { TaskPlan, TaskStep, LogEntry, TaskStatus, SiteConfig } from '@/types';

// ============================================================================
// Task Store - Manages current mission/task state
// ============================================================================

interface TaskState {
  // Current task
  currentPlan: TaskPlan | null;
  taskStatus: TaskStatus;
  steps: TaskStep[];
  logs: LogEntry[];
  
  // Task history
  taskHistory: TaskPlan[];
  
  // Actions
  setPlan: (plan: TaskPlan) => void;
  updateStepStatus: (stepId: string, status: TaskStatus, error?: string) => void;
  addLog: (log: LogEntry) => void;
  clearLogs: () => void;
  setTaskStatus: (status: TaskStatus) => void;
  reset: () => void;
}

export const useTaskStore = create<TaskState>((set) => ({
  currentPlan: null,
  taskStatus: 'pending',
  steps: [],
  logs: [],
  taskHistory: [],
  
  setPlan: (plan) => set({ 
    currentPlan: plan, 
    steps: plan.steps,
    taskStatus: 'pending',
    logs: [],
  }),
  
  updateStepStatus: (stepId, status, error) => set((state) => ({
    steps: state.steps.map((step) =>
      step.id === stepId ? { ...step, status, error } : step
    ),
  })),
  
  addLog: (log) => set((state) => ({
    logs: [...state.logs, log],
  })),
  
  clearLogs: () => set({ logs: [] }),
  
  setTaskStatus: (status) => set({ taskStatus: status }),
  
  reset: () => set({
    currentPlan: null,
    taskStatus: 'pending',
    steps: [],
    logs: [],
  }),
}));

// ============================================================================
// UI Store - Manages UI state
// ============================================================================

interface UIState {
  sidebarCollapsed: boolean;
  currentPage: 'mission' | 'history' | 'world-model' | 'settings';
  isLoading: boolean;
  loadingMessage: string;
  
  // Modal states
  showPlanPreview: boolean;
  showWorldModelDetail: boolean;
  selectedDomain: string | null;
  
  // Actions
  toggleSidebar: () => void;
  setCurrentPage: (page: UIState['currentPage']) => void;
  setLoading: (loading: boolean, message?: string) => void;
  setShowPlanPreview: (show: boolean) => void;
  setShowWorldModelDetail: (show: boolean, domain?: string) => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: false,
  currentPage: 'mission',
  isLoading: false,
  loadingMessage: '',
  showPlanPreview: false,
  showWorldModelDetail: false,
  selectedDomain: null,
  
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setCurrentPage: (page) => set({ currentPage: page }),
  setLoading: (loading, message = '') => set({ isLoading: loading, loadingMessage: message }),
  setShowPlanPreview: (show) => set({ showPlanPreview: show }),
  setShowWorldModelDetail: (show, domain) => set({ 
    showWorldModelDetail: show, 
    selectedDomain: domain || null 
  }),
}));

// ============================================================================
// World Model Store - Manages learned site configurations
// ============================================================================

interface WorldModelState {
  sites: SiteConfig[];
  isLoading: boolean;
  error: string | null;
  
  // Actions
  setSites: (sites: SiteConfig[]) => void;
  updateSite: (domain: string, updates: Partial<SiteConfig>) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useWorldModelStore = create<WorldModelState>((set) => ({
  sites: [],
  isLoading: false,
  error: null,
  
  setSites: (sites) => set({ sites, error: null }),
  
  updateSite: (domain, updates) => set((state) => ({
    sites: state.sites.map((site) =>
      site.domain === domain ? { ...site, ...updates } : site
    ),
  })),
  
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
}));
