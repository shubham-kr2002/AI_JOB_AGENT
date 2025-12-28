/**
 * JobHunter Extension - API Client
 * Handles communication with the FastAPI backend
 */

import type { 
  FormField, 
  GenerateAnswersRequest, 
  GenerateAnswersResponse,
  FeedbackRequest,
  FeedbackResponse 
} from '~/types';

const API_BASE_URL = process.env.PLASMO_PUBLIC_API_URL || 'http://localhost:8001/api/v1';

/**
 * API Client for JobHunter Backend
 */
export const api = {
  /**
   * Health check endpoint
   */
  async health(): Promise<{ status: string; service: string }> {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) throw new Error('API not available');
    return response.json();
  },

  /**
   * Generate answers for form fields using RAG
   */
  async generateAnswers(request: GenerateAnswersRequest): Promise<GenerateAnswersResponse> {
    const response = await fetch(`${API_BASE_URL}/generate-answers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to generate answers');
    }

    return response.json();
  },

  /**
   * Submit feedback for learning loop
   */
  async submitFeedback(request: FeedbackRequest): Promise<FeedbackResponse> {
    const response = await fetch(`${API_BASE_URL}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to submit feedback');
    }

    return response.json();
  },

  /**
   * Upload resume (for onboarding)
   */
  async uploadResume(file: File): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/resume/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to upload resume');
    }

    return response.json();
  },

  /**
   * Check resume status
   */
  async checkResumeStatus(): Promise<{ document_count: number }> {
    const response = await fetch(`${API_BASE_URL}/query/stats`);
    if (!response.ok) throw new Error('Failed to check resume status');
    return response.json();
  },
};

export default api;
