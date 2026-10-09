"""Sample random mishnayot (stratified by seder) and classify what kind of picture each suits.
Output: data/sample_types.json. Reads ANTHROPIC_API_KEY from AnyYCTorah's content_index/.env (never printed)."""
import json, random, re, time, urllib.request, urllib.parse
ENV = "/Users/dovlinzer/claudecode/AnyYCTorah/scripts/content_index/.env"
KEY = re.search(r"^ANTHROPIC_API_KEY=(.+)$", open(ENV).read(), re.M).group(1).strip().strip('"\'')
def get(u):
    for i in range(5):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "x"}), timeout=60))
        except Exception: time.sleep(2 * (i + 1))
    raise RuntimeError(u)
random.seed(7)
idx = get("https://www.sefaria.org/api/index")
m = [c for c in idx if c.get("category") == "Mishnah"][0]
by_seder = {}
for seder in m["contents"]:
    by_seder[seder["category"]] = [t["title"] for t in seder["contents"] if t.get("title", "").startswith("Mishnah ")]
items = []
for seder, titles in by_seder.items():
    for t in random.sample(titles, min(10, len(titles))):
        shape = get("https://www.sefaria.org/api/shape/" + t.replace(" ", "_"))[0]["chapters"]
        c = random.randrange(len(shape)); n = random.randrange(shape[c]) + 1
        ref = f"{t.replace(' ', '_')}.{c+1}.{n}"
        txt = get("https://www.sefaria.org/api/texts/" + ref + "?context=0&commentary=0&ven=" + urllib.parse.quote("Mishnah Yomit by Dr. Joshua Kulp"))["text"]
        items.append({"seder": seder, "ref": f"{t} {c+1}:{n}", "en": re.sub(r"<[^>]+>", "", txt)})
TOOL = {"name": "classify", "description": "classify", "input_schema": {"type": "object", "properties": {"results": {"type": "array", "items": {"type": "object", "properties": {
  "i": {"type": "integer"},
  "kind": {"type": "string", "enum": ["case", "sequence", "object", "list_or_definition"],
           "description": "case = people in a situation with a question or dispute; sequence = a procedure/events in order; object = static classification of things (grain, vessels, fields); list_or_definition = enumeration or abstract rule with no scene"},
  "at_stake": {"type": "string", "description": "the issue the mishnah decides, one short sentence"},
  "picture": {"type": "string", "description": "one-sentence idea for a picture showing the situation and what is at stake; 'none' if nothing sensible"}},
  "required": ["i", "kind", "at_stake", "picture"]}}}, "required": ["results"]}}
out = []
for s in range(0, len(items), 10):
    batch = items[s:s + 10]
    prompt = "For each mishnah (translation by Kulp), classify and describe a picture idea.\n\n" + "\n\n".join(f"[{k}] {it['ref']}: {it['en'][:1200]}" for k, it in enumerate(batch))
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps({"model": "claude-haiku-4-5", "max_tokens": 4000,
        "tools": [TOOL], "tool_choice": {"type": "tool", "name": "classify"}, "messages": [{"role": "user", "content": prompt}]}).encode(),
        headers={"x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=120))
    res = [b for b in r["content"] if b["type"] == "tool_use"][0]["input"]["results"]
    for x in res: batch[x["i"]].update(kind=x["kind"], at_stake=x["at_stake"], picture=x["picture"])
    out += batch
json.dump(out, open("data/sample_types.json", "w"), ensure_ascii=False, indent=1)
from collections import Counter
print(Counter(o.get("kind") for o in out))
for sd in by_seder: print(sd, Counter(o.get("kind") for o in out if o["seder"] == sd))
