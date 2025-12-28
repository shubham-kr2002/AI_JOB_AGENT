/**
 * JobHunter Extension - TypeScript Type Definitions
 * Core types for the Hybrid Neuro-Symbolic AI Agent
 */

// ============================================================================
// Form Field Types
// ============================================================================

export interface FormField {
  id: string;
  label: string;
  type: string;
  options?: string[];
}

export interface FieldAnswer {
  id: string;
  answer: string;
  confidence: number;
  source: 'resume' | 'generated' | 'learning' | 'default';
  verified: boolean;
  flagged_claims?: string[];
}

// ============================================================================
// API Request/Response Types
// ============================================================================

export interface GenerateAnswersRequest {
  fields: FormField[];
  job_description?: string;
  page_url?: string;
  user_id?: number;
  use_hallucination_guard?: boolean;
}

export interface GenerateAnswersResponse {
  success: boolean;
  answers: FieldAnswer[];
  fields_processed: number;
  message: string;
  job_context?: JobContext;
}

export interface JobContext {
  title: string;
  company: string;
  skills: string[];
  experience_years?: number;
}

export interface FeedbackRequest {
  question: string;
  original_answer?: string;
  corrected_answer: string;
  field_type?: string;
  job_context?: string;
}

export interface FeedbackResponse {
  success: boolean;
  message: string;
  feedback_id: number;
  question_hash: string;
}

// ============================================================================
// Extension Message Types
// ============================================================================

export type MessageAction = 
  | 'scrapeForm'
  | 'scrapeJD'
  | 'autoFill'
  | 'fillForm'
  | 'stopMonitor'
  | 'captureFeedback'
  | 'newFieldsDetected';

export interface ExtensionMessage {
  action: MessageAction;
  data?: any;
}

export interface ScrapeFormResponse {
  success: boolean;
  fields?: FormField[];
  error?: string;
}

export interface AutoFillResponse {
  success: boolean;
  fieldsFound?: number;
  fieldsFilled?: number;
  fieldsSkipped?: number;
  fieldsFlagged?: number;
  errors?: Array<{ id: string; error: string }>;
  jobContext?: JobContext;
  message?: string;
  error?: string;
}

// ============================================================================
// Fill Result Types
// ============================================================================

export interface FillResults {
  filled: number;
  skipped: number;
  flagged: number;
  errors: Array<{ id: string; error: string }>;
}

// ============================================================================
// UI State Types
// ============================================================================

export type FillStatus = 'idle' | 'scanning' | 'generating' | 'filling' | 'complete' | 'error';

export interface PopupState {
  status: FillStatus;
  message: string;
  fieldsFound: number;
  fieldsFilled: number;
  fieldsFlagged: number;
  jobContext?: JobContext;
  errors: string[];
}

// ============================================================================
// Storage Types
// ============================================================================

export interface StorageData {
  resumeUploaded: boolean;
  lastFillDate?: string;
  totalFieldsFilled?: number;
  apiUrl?: string;
}
