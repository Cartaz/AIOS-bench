import subprocess,sys

def test_empty_dataset():
    p=subprocess.run([sys.executable,'tools/robust_report.py','--input','data/expenses_empty.csv','--output','/tmp/robust_empty.txt'],text=True,capture_output=True)
    assert p.returncode==0,p.stderr

def test_invalid_dataset():
    p=subprocess.run([sys.executable,'tools/robust_report.py','--input','data/does_not_exist.csv','--output','/tmp/robust_bad.txt'],text=True,capture_output=True)
    assert p.returncode!=0
