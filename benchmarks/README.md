# Benchmark fixtures and acceptance criteria

Each runnable task should eventually have:

1. a deterministic starting workspace;
2. an acceptance specification;
3. an evaluator that can verify the result without judging prose subjectively.

The active frontier-v3 catalog uses deterministic acceptance checks declared in
`benchmarks/tasks/frontier_v3/*.json`. The evaluator supports structural checks
(`exists`, `contains`, `contains_any`, `regex`, `min_lines`, `json_valid`),
integrity checks (`sha256`, `unchanged`), executable checks (`command`) and
benchmark-owned `reference` oracles. Reference oracles are preferred whenever
correctness depends on grounded values or behavior; free-form keyword checks
alone are not considered evidence of task completion.

Each task starts from an isolated deterministic workspace. The long-horizon
task materializes its larger synthetic corpus at workspace creation time so
the repository remains compact without weakening the context/recovery test.
