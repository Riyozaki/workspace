import sys,pathlib
def run(path, pairs):
    P=pathlib.Path(path); t=P.read_text(encoding='utf-8'); n=0
    for a,b in pairs:
        c=t.count(a)
        if c!=1: print("FAIL",c,repr(a[:80])); sys.exit(1)
        t=t.replace(a,b); n+=1
    P.write_text(t,encoding='utf-8'); print(path,"OK",n)
