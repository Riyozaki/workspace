import re,sys
for p in sys.argv[1:]:
    t=open(p,encoding='utf-8').read()
    sents=re.split(r'(?<=[.!?…])\s+',t)
    and3=sum(1 for s in sents if len(re.findall(r'(?:^|[\s,—«])и\s',s))>=3)
    and2=sum(1 for s in sents if len(re.findall(r',\s+и\s',s))>=2)
    # «Не X. Y.» / «не X, а Y» / «не потому что» / «это было другое»
    neg_a=len(re.findall(r'\b[Нн]е\s+[^.!?]{1,40}?,\s+а\s',t))
    ne_potomu=len(re.findall(r'[Нн]е потому,? что',t))
    drugoe=len(re.findall(r'это было (?:другое|не то)|что-то другое',t))
    ne_dot=len(re.findall(r'(?:^|[.!?—]\s*)Не\s+[^.!?]{1,50}\.\s+(?:А|Потому|Просто|Просто)\b',t,re.M))
    print(f"{p.split('/')[-1]}: предл.={len(sents)} и≥3={and3} ,и,и={and2} | не…,а={neg_a} не-потому={ne_potomu} другое={drugoe} 'Не X. А/Потому Y'={ne_dot}")
