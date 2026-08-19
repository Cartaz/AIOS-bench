from __future__ import annotations

import argparse
import json
from pathlib import Path

from .scoring import overall_score
from .tasks import load_tasks


def main() -> None:
    parser = argparse.ArgumentParser(description="AIOS-bench runner and utilities")
    sub = parser.add_subparsers(dest="command", required=True)

    list_cmd = sub.add_parser("list", help="List benchmark tasks")
    list_cmd.add_argument("--tasks", default="benchmarks/tasks")

    score_cmd = sub.add_parser("score", help="Score trajectory JSON files")
    score_cmd.add_argument("path", type=Path)

    args = parser.parse_args()

    if args.command == "list":
        tasks = load_tasks(args.tasks)
        for task in tasks:
            print(f"{task.id}\t{task.category}\t{task.mode}\t{task.prompt}")
    elif args.command == "score":
        data = json.loads(args.path.read_text(encoding="utf-8"))
        from .models import Trajectory

        print(f"{overall_score(Trajectory(**data)):.2f}")


if __name__ == "__main__":
    main()
