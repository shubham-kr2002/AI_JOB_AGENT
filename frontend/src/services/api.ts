/**
 * API Configuration and Client
 * Handles all API calls to the backend
 */

// Environment-aware API URL
const API_BASE_URL = import.meta.env.VITE_API_URL || '';
const WS_BASE_URL = import.meta.env.VITE_WS_URL || '';

// Build full API URL
const getApiUrl = (path: string) => {
  // In development with proxy, use relative path
  if (!API_BASE_URL) {
    return `/api/v1${path}`;
  }
  // In production, use full URL
  return `${API_BASE_URL}/api/v1${path}`;
};

// Build WebSocket URL
export const getWsUrl = (path: string) => {
  if (!WS_BASE_URL) {
    // Use current host with ws protocol
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/api/v1${path}`;
  }
  return `${WS_BASE_URL}/api/v1${path}`;
};

// Generic fetch wrapper with error handling
async function fetchApi<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = getApiUrl(path);
  
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  
  return response.json();
}

// ============================================================================
// Health & Status
// ============================================================================

export const checkHealth = () => fetchApi<{ status: string }>('/health');

// ============================================================================
// Agent API
// ============================================================================

export interface ProcessCommandRequest {
  command: string;
  context?: Record<string, unknown>;
}

export interface TaskResponse {
  id: string;
  status: string;
  command: string;
  created_at: string;
  steps?: TaskStep[];
}

export interface TaskStep {
  id: string;
  name: string;
  status: string;
  result?: unknown;
}

export const processCommand = (request: ProcessCommandRequest) =>
  fetchApi<TaskResponse>('/agent/process', {
    method: 'POST',
    body: JSON.stringify(request),
  });

export const getTasks = () => fetchApi<TaskResponse[]>('/agent/tasks');

export const getTask = (taskId: string) =>
  fetchApi<TaskResponse>(`/agent/tasks/${taskId}`);

export const pauseTask = (taskId: string) =>
  fetchApi<TaskResponse>(`/agent/tasks/${taskId}/pause`, { method: 'POST' });

export const resumeTask = (taskId: string) =>
  fetchApi<TaskResponse>(`/agent/tasks/${taskId}/resume`, { method: 'POST' });

export const cancelTask = (taskId: string) =>
  fetchApi<TaskResponse>(`/agent/tasks/${taskId}/cancel`, { method: 'POST' });

// ============================================================================
// Resume API
// ============================================================================

export const uploadResume = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const url = getApiUrl('/resume/upload');
  const response = await fetch(url, {
    method: 'POST',
    body: formData,
  });
  
  if (!response.ok) {
    throw new Error('Resume upload failed');
  }
  
  return response.json();
};

// ============================================================================
// Intervention API
// ============================================================================

export interface Intervention {
  id: string;
  task_id: string;
  intervention_type: string;
  title: string;
  message: string;
  status: string;
  input_fields?: Array<{
    name: string;
    type: string;
    label: string;
    required?: boolean;
  }>;
}

export const getInterventions = () =>
  fetchApi<Intervention[]>('/interventions');

export const respondToIntervention = (
  interventionId: string,
  response: Record<string, unknown>
) =>
  fetchApi<Intervention>(`/interventions/${interventionId}/respond`, {
    method: 'POST',
    body: JSON.stringify({ response }),
  });

// ============================================================================
// World Model API
// ============================================================================

export interface SiteConfig {
  id: string;
  site_name: string;
  domain: string;
  selectors: Record<string, unknown>;
  is_active: boolean;
}

export const getSiteConfigs = () => fetchApi<SiteConfig[]>('/world-model/sites');

export const updateSiteConfig = (siteId: string, config: Partial<SiteConfig>) =>
  fetchApi<SiteConfig>(`/world-model/sites/${siteId}`, {
    method: 'PATCH',
    body: JSON.stringify(config),
  });
