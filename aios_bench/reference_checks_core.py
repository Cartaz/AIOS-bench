from pathlib import Path
import hashlib, json, re, subprocess

def read(w,p): return (w/p).read_text(encoding='utf-8',errors='replace')
def load(w,p): return json.loads(read(w,p))
def run(w,args,timeout=30): return subprocess.run(args,cwd=w,text=True,capture_output=True,timeout=timeout,check=False)
def same(w,f,fx):
 a,b=w/f,fx/f
 return a.is_file() and b.is_file() and hashlib.sha256(a.read_bytes()).digest()==hashlib.sha256(b.read_bytes()).digest()
def ok(v,msg): return bool(v),msg
