/**
 * WebSocket Service
 * Real-time connection to backend for task updates
 */

import { getWsUrl } from './api';

export type MessageHandler = (message: WebSocketMessage) => void;

export interface WebSocketMessage {
  type: string;
  task_id?: string;
  timestamp?: string;
  [key: string]: unknown;
}

class WebSocketService {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private handlers: Set<MessageHandler> = new Set();
  private subscribedTasks: Set<string> = new Set();
  private url: string = '';

  connect(clientId?: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    const queryParam = clientId ? `?client_id=${clientId}` : '';
    this.url = getWsUrl(`/ws${queryParam}`);
    
    try {
      this.ws = new WebSocket(this.url);
      
      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        
        // Resubscribe to tasks
        this.subscribedTasks.forEach(taskId => {
          this.send({ action: 'subscribe', task_id: taskId });
        });
      };
      
      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as WebSocketMessage;
          this.handlers.forEach(handler => handler(message));
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };
      
      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
        this.attemptReconnect();
      };
      
      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    } catch (e) {
      console.error('Failed to create WebSocket:', e);
    }
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('Max reconnect attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
    
    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    
    setTimeout(() => {
      this.connect();
    }, delay);
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.subscribedTasks.clear();
  }

  subscribe(taskId: string): void {
    this.subscribedTasks.add(taskId);
    this.send({ action: 'subscribe', task_id: taskId });
  }

  unsubscribe(taskId: string): void {
    this.subscribedTasks.delete(taskId);
    this.send({ action: 'unsubscribe', task_id: taskId });
  }

  addHandler(handler: MessageHandler): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  private send(data: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  sendInterventionResponse(taskId: string, response: Record<string, unknown>): void {
    this.send({
      action: 'intervention_response',
      task_id: taskId,
      response,
    });
  }
}

// Singleton instance
export const wsService = new WebSocketService();
