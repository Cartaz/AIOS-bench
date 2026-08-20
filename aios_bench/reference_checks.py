import os
from pathlib import Path
from .reference_checks_knowledge import check as check_knowledge
from .reference_checks_data import check as check_data
from .reference_checks_long import check as check_long
from .reference_checks_subagents import check as check_subagents
from .reference_checks_system import check as check_system

def check_task(task_id,workspace,fixture_root,run_dir=None,events=None):
    # Route by category explicitly.  Several historical modules still contain
    # compatibility branches for older catalogs; probing them in sequence made
    # a stale branch silently win when task IDs overlapped.
    if task_id.startswith('knowledge_'):
        return check_knowledge(task_id,workspace,fixture_root)
    if task_id.startswith(('autonomy_', 'coding_', 'learning_')) or task_id == 'tool_use_003':
        return check_data(task_id,workspace,fixture_root)
    if task_id.startswith('long_horizon_'):
        return check_long(task_id,workspace,fixture_root)
    run_dir=run_dir or (Path(os.environ['AIOS_BENCH_RUN_DIR']) if os.environ.get('AIOS_BENCH_RUN_DIR') else None)
    if task_id.startswith('subagents_'):
        return check_subagents(task_id,workspace,fixture_root,run_dir,events=events or [])
    return check_system(task_id,workspace,fixture_root,run_dir)
