/**
 * Project JobHunter V3 - API Service
 * Handles all backend communication
 */

import type { ApiResponse, PlanResponse, TaskPlan, SiteConfig } from '@/types';

const API_BASE = '/api/v1';

class ApiService {
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        ...options,
      });

      const data = await response.json();

      if (!response.ok) {
        return {
          success: false,
          error: data.detail || data.message || 'Request failed',
        };
      }

      return {
        success: true,
        data,
      };
    } catch (error) {
      console.error('API Error:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
      };
    }
  }

  /**
   * Create a new task plan from a natural language prompt
   * POST /agent/plan
   */
  async createPlan(prompt: string): Promise<ApiResponse<PlanResponse>> {
    return this.request<PlanResponse>('/agent/plan', {
      method: 'POST',
      body: JSON.stringify({ prompt }),
    });
  }

  /**
   * Execute a task plan
   * POST /agent/tasks/{task_id}/execute
   */
  async executeTask(taskId: string): Promise<ApiResponse<{ status: string }>> {
    return this.request<{ status: string }>(`/agent/tasks/${taskId}/execute`, {
      method: 'POST',
    });
  }

  /**
   * Get task status
   * GET /agent/tasks/{task_id}
   */
  async getTaskStatus(taskId: string): Promise<ApiResponse<TaskPlan>> {
    return this.request<TaskPlan>(`/agent/tasks/${taskId}`);
  }

  /**
   * Get all site configurations (World Model)
   * GET /world-model/sites
   */
  async getSites(): Promise<ApiResponse<SiteConfig[]>> {
    return this.request<SiteConfig[]>('/world-model/sites');
  }

  /**
   * Get a specific site configuration
   * GET /world-model/sites/{domain}
   */
  async getSite(domain: string): Promise<ApiResponse<SiteConfig>> {
    return this.request<SiteConfig>(`/world-model/sites/${encodeURIComponent(domain)}`);
  }

  /**
   * Intervene in a paused task
   * POST /agent/tasks/{task_id}/intervene
   */
  async intervene(
    taskId: string,
    stepId: string,
    action: 'retry' | 'skip' | 'abort',
    humanInput?: string
  ): Promise<ApiResponse<{ status: string }>> {
    return this.request<{ status: string }>(`/agent/tasks/${taskId}/intervene`, {
      method: 'POST',
      body: JSON.stringify({
        step_id: stepId,
        action,
        human_input: humanInput,
      }),
    });
  }
}

export const api = new ApiService();

/**
 * WebSocket connection for real-time task updates
 */
export class TaskWebSocket {
  private ws: WebSocket | null = null;
  private taskId: string;
  private onMessage: (data: unknown) => void;
  private onError: (error: Event) => void;
  private onClose: () => void;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;

  constructor(
    taskId: string,
    handlers: {
      onMessage: (data: unknown) => void;
      onError?: (error: Event) => void;
      onClose?: () => void;
    }
  ) {
    this.taskId = taskId;
    this.onMessage = handlers.onMessage;
    this.onError = handlers.onError || (() => {});
    this.onClose = handlers.onClose || (() => {});
  }

  connect(): void {
    const wsUrl = `ws://${window.location.host}/ws/agent/tasks/${this.taskId}/stream`;
    
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log(`[WS] Connected to task ${this.taskId}`);
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.onMessage(data);
      } catch (error) {
        console.error('[WS] Failed to parse message:', error);
      }
    };

    this.ws.onerror = (error) => {
      console.error('[WS] Error:', error);
      this.onError(error);
    };

    this.ws.onclose = () => {
      console.log(`[WS] Disconnected from task ${this.taskId}`);
      this.onClose();
      
      // Attempt reconnection
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        setTimeout(() => this.connect(), 1000 * this.reconnectAttempts);
      }
    };
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  send(data: unknown): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }
}
