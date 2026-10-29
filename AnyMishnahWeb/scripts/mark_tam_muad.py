"""Insert {{tam}}/{{muad}} markers into en_p of BK 2-6 and BM 1 (BK 1 was hand-marked). --apply to write."""
import json,glob,re,sys
R=[(r"\b(Two|two) tam oxen\b",r"\1 {{tam|p}}"),
   (r"\bA tam ox\b","An ox that is {{tam|a}}"),(r"\ba tam ox\b","{{tam|a}}"),
   (r"\bThe tam ox\b","{{tam|The}}"),(r"\bthe tam ox\b","{{tam|the}}"),
   (r"\bA tam\b(?! status)","{{tam|A}}"),(r"\ba tam\b(?! status)","{{tam|a}}"),
   (r"\bThe tam\b(?! status)","{{tam|The}}"),(r"\bthe tam\b(?! status)","{{tam|the}}"),
   (r"\bAn attested dangers?\b","{{muad|A}}"),(r"\ban attested danger\b","{{muad|a}}"),
   (r"\bThe attested danger\b","{{muad|The}}"),(r"\bthe attested danger\b","{{muad|the}}"),
   (r"\battested dangers\b","{{muad|p}}")]
apply='--apply' in sys.argv
for f in sorted(glob.glob('data/bava_kamma_[2-6].json')+['data/bava_metzia_1.json']):
    d=json.load(open(f)); ch=False
    for m in d['mishnayot']:
        new=[]
        for p in m.get('en_p') or []:
            q=p
            for a,b in R: q=re.sub(a,b,q)
            if q!=p: print(f[10:-5],(m.get('mishnah') or m.get('n') or m.get('num')),'|',q[:160]); ch=True
            new.append(q)
        if m.get('en_p'): m['en_p']=new
    if ch and apply: json.dump(d,open(f,'w'),ensure_ascii=False,indent=1)
    rem=[x for m in d['mishnayot'] for p in (m.get('en_p') or []) for x in re.findall(r".{20}\b(?:tam|attested danger)\b.{15}",re.sub(r"\{\{.*?\}\}","",p))]
    if rem: print('  LEFT',f[10:-5],rem)
