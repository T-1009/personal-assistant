export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  isStreaming?: boolean;
}

export interface SSEEvent {
  type?: string;
  token?: string;
  done?: boolean;
  error?: string;
  system_message?: string;
  auth_url?: string;
  auth_required?: boolean;
  auth_complete?: boolean;
  auth_failed?: boolean;
  provider?: string;
  oauth2_state?: string;
  report_ready?: boolean;
  report_format?: 'markdown';
  report_filename?: string;
  report_content?: string;
  report_type?: 'daily' | 'weekly' | 'monthly' | 'custom';
  report_window?: {
    start_at?: string;
    end_at?: string;
    timezone?: string;
  };
}
