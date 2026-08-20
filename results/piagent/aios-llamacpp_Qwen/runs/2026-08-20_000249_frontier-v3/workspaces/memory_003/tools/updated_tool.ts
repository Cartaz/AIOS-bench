/**
 * updated_tool.ts — New automation tool written in TypeScript.
 *
 * Primary language updated from Python to TypeScript as of 2026-08-20.
 * This file replaces the legacy Python-based tooling approach while
 * preserving compatibility with the existing simple tooling style.
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from "fs";
import { join } from "path";

interface RunRecord {
  run: number;
  status: "passed" | "failed";
  error?: string;
}

interface StateFile {
  runs: number;
  history: RunRecord[];
}

let state: StateFile = { runs: 0, history: [] };

/**
 * Load persisted state from disk, or start with an empty state.
 */
function loadState(statePath: string): void {
  if (existsSync(statePath)) {
    state = JSON.parse(readFileSync(statePath, "utf-8"));
  }
}

/**
 * Persist current state to disk.
 */
function saveState(statePath: string): void {
  const dir = statePath.split("/").slice(0, -1).join("/");
  if (dir && !existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }
  writeFileSync(statePath, JSON.stringify(state, null, 2) + "\n", "utf-8");
}

/**
 * Validate a single run. On run #3 the validator intentionally
 * produces a failure to exercise error-path handling.
 */
export function validate(statePath: string = ".state/validator_runs.json"): boolean {
  loadState(statePath);

  state.runs += 1;
  const runNumber = state.runs;

  const record: RunRecord = { run: runNumber, status: "passed" };
  if (runNumber === 3) {
    record.status = "failed";
    record.error = "validator state corruption";
  }

  state.history.push(record);
  saveState(statePath);

  return record.status === "passed";
}

/**
 * CLI entry point.
 */
function main(): void {
  const args = process.argv.slice(2);
  let statePath = ".state/validator_runs.json";

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--state" && args[i + 1]) {
      statePath = args[++i];
    }
  }

  const passed = validate(statePath);
  if (passed) {
    console.log("validator: passed");
  } else {
    console.error("validator: validator state corruption");
    process.exit(1);
  }
}

main();
