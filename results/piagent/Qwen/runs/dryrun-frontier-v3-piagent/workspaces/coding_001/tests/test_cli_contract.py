import subprocess,sys

def test_cli_contract():
    p=subprocess.run([sys.executable,'projects/report_tool.py','--input','data/sales.csv','--output','/tmp/contract.json'],text=True,capture_output=True)
    assert p.returncode==0,p.stderr
