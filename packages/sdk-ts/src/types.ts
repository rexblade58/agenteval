/**
 * AgentEval TypeScript SDK types.
 */

export type Role = "system" | "user" | "assistant";

export interface Message {
  role: Role;
  content: string;
}

export type ProviderName = "mock" | "openai" | "anthropic" | "ollama";

export type SuiteName =
  | "codegen"
  | "qa"
  | "reasoning"
  | "summarization"
  | "tool-use"
  | "all";

export interface Task {
  id: string;
  category: string;
  prompt: string;
  reference: string;
  difficulty: "easy" | "medium" | "hard";
  tags: string[];
}

export interface TaskResult {
  task_id: string;
  category: string;
  passed: boolean;
  latency_ms: number;
  output: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  attempts: number;
  error?: string;
}

export interface CategoryBreakdown {
  total: number;
  passed: number;
  accuracy: number;
}

export interface EvaluationReport {
  provider: string;
  model: string;
  suite: string;
  total_tasks: number;
  passed: number;
  failed: number;
  accuracy: number;
  pass_at_1: number;
  pass_at_k: number;
  avg_latency_ms: number;
  total_cost_usd: number;
  category_breakdown: Record<string, CategoryBreakdown>;
  results: TaskResult[];
}

export interface EvaluatorOptions {
  provider: ProviderName;
  model?: string;
  suite?: SuiteName;
  apiKey?: string;
  baseUrl?: string;
  nSamples?: number;
  temperature?: number;
}
