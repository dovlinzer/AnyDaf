"""Add paragraph breaks where the speaker switches (or a different tanna's position
begins) inside en_p / he_p. Dry run by default; pass --apply to write."""
import json, re, sys, glob
NAME = r"(?:Rabbi|Rabban|Rav|Abba|Shmuel|Ben|Rabbis?|Sages|Rabbi)"
EN = re.compile(
    r"(?<=[.?!])([\"”]?)\s+(?=(?:(?:But|And)\s+)?(?i:the (?:Sages|Rabbis) (?:say|said|concede|concur))|(?:(?:But|And)\s+)?(?:"
    r"They said (?:to him|before)|He said to (?:them|him)|They said:|"
    r"The (?:Sages|Rabbis) (?:say|said|concede|concur)|"
    r"(?:Rabbi|Rabban|Rav|Abba) [A-Z][\w'’ -]{0,30}? (?:said|says)\b))")
HE = re.compile(
    r"(?<=[.?!:])\s+(?=(?:"
    r"(?:אמרו|אמר|ואמרו|ואמר) (?:להם|לו|לפניו|לפני|רבי|רבן|רב)\b|"
    r"ו?(?:חכמים|רבנן|החכמים) (?:אומרים|אומר|מודים)|"
    r"ו?(?:רבי|רבן|רב|אבא) [^\s.:]+(?: [^\s.:]+){0,3} (?:אומר|אומרת|אמר)\b))")
HE_VERB=re.compile(r"(?<=[.?!:])\s+(?=(?:אמרו|אמר) (?:להם|לו|לפניו))")
def split(paras, rx, en):
    out=[]
    for p in paras:
        if en:
            parts=[]; last=0
            for m in rx.finditer(p):
                parts.append(p[last:m.start()]+m.group(1)); last=m.end()
            parts.append(p[last:])
        else:
            parts=rx.split(p)
        out+= [x for x in parts if x.strip()]
    return out
apply='--apply' in sys.argv
for f in sorted(glob.glob('data/bava_kamma_[1-6].json')+glob.glob('data/bava_metzia_1.json')):
    d=json.load(open(f)); ch=False
    for m in d['mishnayot']:
        n=m.get('mishnah') or m.get('n') or m.get('num')
        if not m.get('en_p'): continue
        e2=split(m['en_p'],EN,True)
        h2=split(m['he_p'],HE_VERB if (f.endswith('kamma_2.json') and n==5) else HE,False) if m.get('he_p') else None
        assert re.sub(r'\s+',' ',' '.join(e2)).strip()==re.sub(r'\s+',' ',' '.join(m['en_p'])).strip(), (f,n)
        if len(e2)!=len(m['en_p']) or (h2 and len(h2)!=len(m['he_p'])):
            flag='' if h2 and len(e2)==len(h2) else '  <-- en/he counts differ'
            print(f"{f.split('/')[-1][:-5]} {n}: en {len(m['en_p'])}->{len(e2)}  he {len(m['he_p'])}->{len(h2)}{flag}")
            m['en_p']=e2
            if h2: m['he_p']=h2
            ch=True
    if ch and apply: json.dump(d,open(f,'w'),ensure_ascii=False,indent=1)
