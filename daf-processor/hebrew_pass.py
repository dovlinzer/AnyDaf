#!/usr/bin/env python3
"""Hebrew study outlines, adapted from the English ones (Batch API).

Each request gets one daf's English outline (default: Opus 5.5 at Medium) and the Gemara's Hebrew
lines it covers, and writes the outline in Hebrew for Israeli readers: same sections, ids and line
anchors, the same charts, and the pictures redrawn to read right to left. The model is the
hand-written Hebrew Chagigah 6 (outline/example_chagigah_6_he.json), shown beside the English
Chagigah 6 it corresponds to. Results: outline/results/<daf>/04_outline_he.json, which
build_prototype.py reads with `<daf>@he=HE`.

    python hebrew_pass.py --dafim kiddushin_3 bava_metzia_2 --dry-run
    python hebrew_pass.py --dafim kiddushin_3 bava_metzia_2           # submits; resumable

Calls the Anthropic API: never run it without the author's authorization for that run.
"""
import argparse
import copy
import json
import sys
import time
from pathlib import Path

import anthropic
from fix_he_pictures import fix_outline
from dotenv import load_dotenv

from outline_pass import (HERE, RESULTS, SPRITE, STATE_DIR, POLL_INTERVAL, EXAMPLE_SAGES, _pool,
                          check_anchors, label_pool, parse_outline, parse_spec)

load_dotenv(Path(__file__).parent / ".env", override=True)

MODEL = "claude-opus-5-5"
EFFORT = "medium"
TAG = "he"
EDITORIAL = ("judgment_calls", "coverage_notes", "runners_up", "tag_questions")

SYSTEM = """You are adapting a study outline of one daf of Talmud from English into Hebrew, for Israeli readers, mainly students in religious (mamlachti-dati) high schools and midrashot. The English outline has been reviewed and its structure is settled; your job is to make the same outline read as if it had been written in Hebrew from the start.

## What stays exactly the same
- Every section, in the same order and the same nesting, with the same `id`, `text` anchors ("from"/"to" labels, unchanged) and `returns_to` ids. Never add, drop, merge, split or move a section, and never change an anchor.
- Every bullet, with its `detail` and `source`. Translate the bullet; don't add content or leave any out. Shiur insights (`"source": "shiur"`) are translated too.
- Charts: the same rows and columns in the same order, and `tones` unchanged (same shape, same values). The page lays the table out right to left by itself, so don't reverse anything.
- Sages: the same entries with the same `id`s (and `full_name` where given); `name` becomes the sage's usual Hebrew name (רבי יוחנן, רב חסדא, אביי), `hebrew` stays, `sections` unchanged.
- Key terms: the same terms with the same `sections`; see below for how they are written.

## How the Hebrew reads
- Plain, modern Hebrew in full sentences, the register of a good midrasha source sheet, not academic and not yeshivish shorthand. No abbreviations a student wouldn't know (write "רבי", not "ר'"; "כלומר", not "כלו'"). Don't translate word for word: write the sentence a Hebrew writer would write.
- The Gemara's own terms stay in its words, in Hebrew script and without italics or asterisks: קושיה, תיובתא, בעיא, תיקו, מיגו, קל וחומר, גזירה שווה, ספק, קנין חצר, המוציא מחברו עליו הראיה. Where the English transliterates a term (*kinyan chatzer*), write the term itself in Hebrew (קנין חצר), never a Hebrew transliteration of the English. Where the English explains a term in parentheses for an English reader, keep an explanation only if a Hebrew-speaking student would need it, briefly and in Hebrew.
- Quote the Gemara, Mishnah and verses from the Hebrew text you are given (the lines are labeled), not by translating the English back. Short quotations in quotation marks; verses as they are written, with a source in Hebrew ("דברים כד, א").
- Rulings: מותר / אסור, כשר / פסול, חייב / פטור, מקודשת / אינה מקודשת, קנה / לא קנה.
- No markdown: the Hebrew outline uses no `*` at all.
- `amud` labels are Hebrew: "ו." for 6a, "ו:" for 6b, "ה:–ו." for a range, "ו: ← ז." where the English has an arrow.
- `flag` "Gemara text only" becomes "על פי הגמרא בלבד".
- `daf` is the tractate and daf in Hebrew ("קידושין ג", "בבא מציעא יא"); `scope` start and end are translated, keeping the line references in Hebrew form.
- Add `"lang": "he"` at the top level.
- Headings follow the same rules as in English: a heading names the options or positions its section lays out, using the key term when there is one; a Mishnah section's heading starts with "משנה:".

## Key terms
Each key term is written in Hebrew: `term` is the term in Hebrew letters (the Gemara's own form: "קנין חצר", "חצר שאינה משתמרת"), `hebrew` is "" (the term is already Hebrew), `sense` and `definition` and `on_this_daf` are in Hebrew, and `aliases` lists the other Hebrew forms the outline uses for it (with and without a prefix letter, singular and plural), never English or transliterations. Write the term in the outline exactly as `term` or one of its `aliases` has it, so the page can find and link it.

## Pictures
Each picture is redrawn for a right-to-left page, as the Hebrew example shows:
- A sequence, a list, a set of compared items or a timeline that runs left to right in English runs right to left in Hebrew. Do this by wrapping everything except the text labels (background, shapes, figures, arrows, marks) in `<g transform="matrix(-1 0 0 1 900 0)">`, and placing each label outside that group at x = 900 minus its English x, with `text-anchor` "start" and "end" swapped ("middle" stays). Labels must never be inside the mirrored group, or they would read backwards. The ✓ / ✗ marks (`#mark-ok`, `#mark-no`) also stay outside the group, at x = 900 minus their English x minus their width: a check mark reads the same in Hebrew. Don't add `direction` to the labels; the site sets it. Check that each label still sits where it belongs on its drawing.
- A picture of a real physical layout (the Temple, a courtyard with directions, a map) is not mirrored: keep the drawing as it is and only translate the labels.
- Translate every label, the `<title>` and the caption into Hebrew. Every Hebrew `<text>` gets `direction="rtl"`. Use Frank Ruhl Libre for titles and Assistant for labels, as the Hebrew example does. Hebrew text runs longer or shorter than English: make sure no label now runs over a drawing, a figure, another label or the edge, and break, shorten or move it where it would.
- Keep the shared figure library's symbols (`<use href="#...">`), the colors (permitted green, forbidden red, `#mark-ok` / `#mark-no`), the viewBox and everything else as they are.

## Output
Return only the Hebrew outline as one JSON object, with no prose before or after it and no code fence: the same shape as the English outline, plus `"lang": "he"`, without `judgment_calls`, `coverage_notes` or `runners_up`.

## Figure library (already on the page; reference these ids, never redefine them)
{LIBRARY}

## The model: Chagigah 6 in English and as the author approved it in Hebrew
"""


def strip_editorial(o: dict) -> dict:
    o = copy.deepcopy(o)
    for k in EDITORIAL:
        o.pop(k, None)
    return o


def example_pair() -> str:
    # the English version the Hebrew model was written from (the example was revised afterwards, 2026-10-18)
    en = json.loads((HERE / "outline" / "example_chagigah_6.before_voice.json").read_text(encoding="utf-8"))
    en["key_terms"] = json.loads((HERE / "outline" / "key_terms_example_chagigah_6.json").read_text(encoding="utf-8"))["key_terms"]
    en["sages"] = EXAMPLE_SAGES
    he = json.loads((HERE / "outline" / "example_chagigah_6_he.json").read_text(encoding="utf-8"))
    return ("### English\n" + json.dumps(strip_editorial(en), ensure_ascii=False)
            + "\n\n### Hebrew\n" + json.dumps(strip_editorial(he), ensure_ascii=False))


def system_blocks() -> list[dict]:
    text = SYSTEM.replace("{LIBRARY}", SPRITE.read_text(encoding="utf-8")) + example_pair()
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def hebrew_lines(outline: dict, d: Path) -> list[tuple[str, str]]:
    """The Gemara's Hebrew lines from the outline's first anchor to its last."""
    pool = _pool(d)
    labs = [lab for lab, _ in pool]
    secs = outline.get("sections") or []
    try:
        a, b = labs.index(secs[0]["text"]["from"]), labs.index(secs[-1]["text"]["to"])
    except (ValueError, KeyError, IndexError):
        return pool
    return pool[a:b + 1]


def build_user_prompt(key: str, d: Path, source_tag: str) -> str:
    en = json.loads((RESULTS / key / f"04_outline_{source_tag}.json").read_text(encoding="utf-8"))
    lines = "\n".join(f"[{lab}] {he}" for lab, he in hebrew_lines(en, d))
    return (f"# Daf: {key}\n\n## The Gemara's Hebrew text for these lines\n{lines}\n\n"
            f"## The English outline to adapt\n{json.dumps(strip_editorial(en), ensure_ascii=False)}")


def build_request(key: str, d: Path, source_tag: str) -> dict:
    return {"custom_id": f"{key}__{TAG}",
            "params": {"model": MODEL, "max_tokens": 128000, "thinking": {"type": "adaptive"},
                       "output_config": {"effort": EFFORT}, "system": system_blocks(),
                       "messages": [{"role": "user", "content": build_user_prompt(key, d, source_tag)}]}}


def check_same(he: dict, en: dict) -> list[str]:
    """Free local check: same section ids, nesting and anchors as the English outline."""
    def flat(ns, depth=0):
        for n in ns or []:
            yield n.get("id"), depth, (n.get("text") or {}).get("from"), (n.get("text") or {}).get("to"), \
                len(n.get("bullets") or []), bool(n.get("chart")), bool(n.get("illustration"))
            yield from flat(n.get("children"), depth + 1)
    a, b = list(flat(en.get("sections"))), list(flat(he.get("sections")))
    probs = []
    if [x[:4] for x in a] != [x[:4] for x in b]:
        probs.append(f"sections/anchors differ from the English ({len(a)} vs {len(b)})")
    for x, y in zip(a, b):
        if x[:4] == y[:4] and x[4:] != y[4:]:
            probs.append(f"{x[0]}: bullets/chart/picture differ (en {x[4:]}, he {y[4:]})")
    if he.get("lang") != "he":
        probs.append('missing "lang": "he"')
    txt = json.dumps(he, ensure_ascii=False)
    if "*" in txt:
        probs.append(f"{txt.count('*')} asterisks left")
    if {s.get("id") for s in en.get("sages") or []} != {s.get("id") for s in he.get("sages") or []}:
        probs.append("sage ids differ")
    return probs


def harvest(client, batch_id, usage_log, src, source_tag):
    for r in client.messages.batches.results(batch_id):
        key = r.custom_id.split("__")[0]
        if r.result.type != "succeeded":
            print(f"  {r.custom_id}: {r.result.type}")
            continue
        msg = r.result.message
        text = next((blk.text for blk in msg.content if blk.type == "text"), "")
        u = msg.usage
        usage_log.append({"id": r.custom_id, "model": msg.model, "stop": msg.stop_reason, "in": u.input_tokens,
                          "cache_read": u.cache_read_input_tokens, "cache_write": u.cache_creation_input_tokens,
                          "out": u.output_tokens})
        if msg.stop_reason != "end_turn":
            print(f"  {r.custom_id}: stop_reason={msg.stop_reason}")
        outdir = RESULTS / key
        (outdir / f"04_outline_{TAG}.raw.txt").write_text(text, encoding="utf-8")
        try:
            he = parse_outline(text)
            out = outdir / f"04_outline_{TAG}.json"
            fix_outline(he)                          # marks unmirrored, label anchors in the rtl sense
            he["_pictures_fixed"] = True
            out.write_text(json.dumps(he, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  wrote {out.relative_to(HERE)}")
            en = json.loads((outdir / f"04_outline_{source_tag}.json").read_text(encoding="utf-8"))
            for p in check_same(he, en) + check_anchors(he, src[key]):
                print(f"    check: {p}")
        except Exception as e:
            print(f"  {r.custom_id}: could not parse JSON ({e}); raw text saved")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dafim", nargs="+", required=True)
    ap.add_argument("--source", default="opus55_medium", help="tag of the English outline to adapt")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    src = {}
    for name in args.dafim:
        key, d, _ = parse_spec(name)
        if not (RESULTS / key / f"04_outline_{args.source}.json").exists():
            sys.exit(f"no {args.source} outline for {key}")
        src[key] = d
    sys_chars = len(system_blocks()[0]["text"])
    print(f"{len(src)} requests ({MODEL}, effort {EFFORT}); system prompt {sys_chars:,} chars (cached)")
    for key, d in src.items():
        print(f"  {key:22s} user prompt {len(build_user_prompt(key, d, args.source)):,} chars")
    if args.dry_run:
        return
    client = anthropic.Anthropic()
    state = STATE_DIR / f".outline_batch_{TAG}.json"
    if state.exists():
        bid = json.loads(state.read_text())["batch_id"]
        print(f"Resuming batch {bid}")
    else:
        bid = client.messages.batches.create(requests=[build_request(k, d, args.source) for k, d in src.items()]).id
        state.write_text(json.dumps({"batch_id": bid}))
        print(f"Submitted batch {bid} ({len(src)} requests)")
    usage_log = []
    while True:
        b = client.messages.batches.retrieve(bid)
        c = b.request_counts
        print(f"  {b.processing_status}: succeeded={c.succeeded} processing={c.processing} errored={c.errored}", flush=True)
        if b.processing_status == "ended":
            harvest(client, bid, usage_log, src, args.source)
            state.unlink(missing_ok=True)
            break
        time.sleep(POLL_INTERVAL)
    (STATE_DIR / "last_run_usage_he.json").write_text(json.dumps(usage_log, indent=1))


if __name__ == "__main__":
    main()
