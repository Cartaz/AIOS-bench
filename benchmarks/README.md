# Benchmark fixtures and acceptance criteria

Each runnable task should eventually have:

1. a deterministic starting workspace;
2. an acceptance specification;
3. an evaluator that can verify the result without judging prose subjectively.

Acceptance specs use `benchmarks/tasks/specs/*.json` and currently support `exists`, `contains`, and `sha256` checks.

The fixture workspace is intentionally small in v0.1. It is a seed for expanding the benchmark into isolated, repeatable workspaces per task.
