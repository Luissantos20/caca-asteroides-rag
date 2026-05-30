export type MessageRole = "user" | "assistant" | "system";

export type ApiErrorKind =
  | "rate_limit"
  | "server"
  | "timeout"
  | "network"
  | "validation"  
  | "unknown";

export interface ApiErrorInfo {
  kind: ApiErrorKind;
  message: string;
}

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
  isOutOfScope?: boolean;
}

export interface ChatRequest {
  message: string;
  history?: HistoryMessage[];
}

export interface ChatResponse {
  should_answer: boolean;
  answer: string;
}

// ===== Streaming types =====

export type StreamEventMetadata = {
  type: "metadata";
  should_answer: boolean;
  request_id: string;
};

export type StreamEventToken = {
  type: "token";
  content: string;
};

export type StreamEventError = {
  type: "error";
  message: string;
};

export type StreamEventDone = {
  type: "done";
};

export type StreamEvent =
  | StreamEventMetadata
  | StreamEventToken
  | StreamEventError
  | StreamEventDone;


// ===== History (memória curta) =====

export type HistoryMessage = {
  role: "user" | "assistant";
  content: string;
};
