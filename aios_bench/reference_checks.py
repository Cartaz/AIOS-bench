from .reference_checks_data import check as check_data
from .reference_checks_system import check as check_system

def check_task(task_id, workspace, fixture_root, run_dir=None):
    result = check_data(task_id, workspace, fixture_root)
    if result is not None:
        return result
    return check_system(task_id, workspace, fixture_root, run_dir)
