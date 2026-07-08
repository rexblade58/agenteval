/**
 * AgentEval TypeScript SDK - client for the Python CLI's JSON output.
 *
 * The SDK lets Node.js applications run AgentEval evaluations by invoking
 * the `agenteval` CLI and parsing the JSON report, or by calling a remote
 * AgentEval server (roadmap).
 */

import { spawnSync } from "node:child_process";
import type {
  EvaluationReport,
  EvaluatorOptions,
  Message,
  TaskResult,
} from "./types";

const MOCK_RESPONSES: Record<string, string> = {
  default: "This is a mock response for testing.",
  code: "function add(a, b) {\n  return a + b\n}",
  question: "The capital of France is Paris.",
};

function mockComplete(messages: Message[]): string {
  const last = messages.at(-1)?.content.toLowerCase() ?? "";
  if (/code|function/.test(last)) return MOCK_RESPONSES.code;
  if (/capital|france/.test(last)) return MOCK_RESPONSES.question;
  return MOCK_RESPONSES.default;
}

/**
 * In-process mock evaluator (no network, deterministic).
 */
export function evaluateMock(suite: string = "all", tasks: any[]): EvaluationReport {
  const results: TaskResult[] = tasks.map((task) => {
    const output = mockComplete([{ role: "user", content: task.prompt }]);
    const passed = output.includes(task.reference) || !task.reference;
    return {
      task_id: task.id,
      category: task.category,
      passed,
      latency_ms: 1,
      output,
      input_tokens: task.prompt.split(/\s+/).length,
      output_tokens: output.split(/\s+/).length,
      cost_usd: 0,
      attempts: 1,
    };
  });

  const passed = results.filter((r) => r.passed).length;
  const accuracy = results.length ? passed / results.length : 0;

  return {
    provider: "mock",
    model: "mock-model",
    suite,
    total_tasks: results.length,
    passed,
    failed: results.length - passed,
    accuracy,
    pass_at_1: accuracy,
    pass_at_k: accuracy,
    avg_latency_ms: 1,
    total_cost_usd: 0,
    category_breakdown: {},
    results,
  };
}

/**
 * Run the `agenteval` CLI and return the parsed JSON report.
 * Requires the Python package to be installed (`pip install -e packages/core`).
 */
export function runCli(options: EvaluatorOptions): EvaluationReport {
  const args = [
    "run",
    "--provider",
    options.provider,
    "--suite",
    options.suite ?? "all",
    "--format",
    "json",
  ];
  if (options.model) {
    args.push("--model", options.model);
  }
  if (options.nSamples) {
    args.push("--n-samples", String(options.nSamples));
  }
  if (options.temperature !== undefined) {
    args.push("--temperature", String(options.temperature));
  }

  const result = spawnSync("agenteval", args, {
    encoding: "utf-8",
    env: {
      ...process.env,
      ...(options.apiKey ? { OPENAI_API_KEY: options.apiKey } : {}),
    },
  });

  if (result.status !== 0) {
    throw new Error(`agenteval CLI failed (${result.status}): ${result.stderr}`);
  }
  return JSON.parse(result.stdout) as EvaluationReport;
}

export * from "./types";
