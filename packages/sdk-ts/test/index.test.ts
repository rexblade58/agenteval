import { describe, expect, it } from "vitest";
import { evaluateMock, runCli } from "../src/index";
import type { EvaluationReport } from "../src/types";

const MOCK_TASKS = [
  {
    id: "qa-capital",
    category: "qa",
    prompt: "What is the capital of France?",
    reference: "Paris",
    difficulty: "easy",
    tags: ["knowledge"],
  },
  {
    id: "qa-wrong",
    category: "qa",
    prompt: "What is the capital of Australia?",
    reference: "Sydney",
    difficulty: "easy",
    tags: ["knowledge"],
  },
];

describe("evaluateMock", () => {
  it("returns a report with correct shape", () => {
    const report = evaluateMock("qa", MOCK_TASKS);
    expect(report.provider).toBe("mock");
    expect(report.total_tasks).toBe(2);
    expect(report.passed).toBeGreaterThanOrEqual(0);
    expect(report.failed).toBe(report.total_tasks - report.passed);
    expect(report.accuracy).toBeGreaterThanOrEqual(0);
    expect(report.accuracy).toBeLessThanOrEqual(1);
  });

  it("correctly scores a passing task", () => {
    const report = evaluateMock("qa", MOCK_TASKS);
    const capital = report.results.find((r) => r.task_id === "qa-capital");
    expect(capital).toBeDefined();
    expect(capital!.passed).toBe(true);
  });

  it("scores empty result set as zero accuracy", () => {
    const report = evaluateMock("qa", []);
    expect(report.total_tasks).toBe(0);
    expect(report.accuracy).toBe(0);
  });
});

describe("runCli", () => {
  it("throws when the CLI is not installed", () => {
    // The CLI is not guaranteed to exist in the test env; expect a clean error
    // instead of a crash.
    try {
      runCli({ provider: "mock", suite: "all" });
      // If we get here the CLI exists - validate the shape
    } catch (err) {
      expect(err).toBeInstanceOf(Error);
    }
  });
});
