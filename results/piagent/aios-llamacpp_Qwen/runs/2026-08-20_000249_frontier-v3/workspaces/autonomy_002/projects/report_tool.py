import argparse,csv,json

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    with open(a.input,newline='') as f: rows=list(csv.DictReader(f))
    with open(a.output,'w') as f: json.dump({'rows':len(rows)},f)
if __name__=='__main__': main()
