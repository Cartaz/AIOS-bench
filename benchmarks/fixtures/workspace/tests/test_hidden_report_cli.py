import subprocess, sys
from pathlib import Path

def test_alternate_dataset():
    p=subprocess.run([sys.executable,'tools/report_cli.py','--input','data/sales_alt.csv','--output','.hidden_alt.html'],text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    assert '742.50' in Path('.hidden_alt.html').read_text()

def test_missing_input_rejected():
    p=subprocess.run([sys.executable,'tools/report_cli.py','--input','data/does_not_exist.csv','--output','.hidden_missing.html'],text=True,capture_output=True)
    assert p.returncode!=0

def test_malformed_fixture_is_handled():
    p=subprocess.run([sys.executable,'tools/report_cli.py','--input','data/expenses.csv','--output','.hidden_expenses.html'],text=True,capture_output=True)
    assert p.returncode==0,p.stderr
