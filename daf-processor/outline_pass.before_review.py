#!/usr/bin/env python3
"""outline_pass.py — generate a nested study outline for each daf (Batch API).

Reads, per daf directory:
  01_segmentation.json            shiur sections (full `title`s are raw material for headings)
  02_rewrite_wall_patched.md      the shiur essay (falls back to 02_rewrite.md)
  sefaria_prev.md / sefaria.md / sefaria_next.md   English translation only (no Hebrew:
                                  the outline doesn't need it and it is token-heavy)
  previous daf's essay tail       the start of a daf is often taught at the end of the
                                  previous shiur (Chagigah 6's opening was)

Writes outline/results/<key>/04_outline_<model-tag>.json (+ .raw.txt), where <key> is the daf
directory name, or <daf>_textonly for a text-only run.

Text-only runs ("--dafim gittin_18:textonly") withhold every piece of shiur material (segmentation,
essay, previous essay tail) to test how the pass does from the Gemara alone. A daf with no
output/ directory at all (never processed, e.g. shabbat_38) is read from outline/textonly/<daf>/,
which holds hand-assembled sefaria*.md files; for such a daf the previous daf's essay tail IS
still sent, as it would be in production.

Each model gets its own batch, so one model's slow queue doesn't hold back the others.

The worked example in the prompt is outline/example_chagigah_6.json, the hand-built outline
the author approved (2026-09-23). Keep Chagigah 6 out of any test set — it is the answer key.

Usage:
    python -u outline_pass.py --dafim gittin_18 shabbat_21 --models claude-sonnet-5 claude-opus-5
    python -u outline_pass.py --dafim gittin_18 --dry-run     # print prompt sizes, no API call
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

HERE = Path(__file__).parent
OUTPUT = HERE / "output"
EXAMPLE = HERE / "outline" / "example_chagigah_6.json"
SPRITE = HERE / "outline" / "sprite.svg"      # shared figure/animal symbols the illustrations draw on
STATE_DIR = HERE / "outline"
RESULTS = HERE / "outline" / "results"
TEXTONLY_DIR = HERE / "outline" / "textonly"
PREV_ESSAY_TAIL_CHARS = 6000
EDGE_ITEMS = 4  # Sefaria items taken from the end of the previous amud / start of the next
POLL_INTERVAL = 60

MODEL_TAGS = {"claude-sonnet-5": "sonnet5", "claude-opus-5": "opus5", "claude-opus-5-5": "opus55"}

SYSTEM_PROMPT = """You are building a study outline of one daf of Talmud for the AnyDaf app. The outline's job is to give a learner a bird's-eye view of how the daf's discussion is built: reading only the headings and their one-line gists, a learner should see what the daf discusses, how the parts relate, and where the Gemara goes next. The bullets then fill in each step.

You receive: the shiur's segmentation (the lecture's own section titles, in lecture order), the shiur essay written from the lecture, the tail of the previous daf's essay, and Sefaria's English translation of this daf plus a few lines on either side. Some dafim have no shiur at all; then you receive only the Gemara text (and perhaps the previous daf's essay tail), and you build the whole outline from the text: every bullet is `"source": "gemara"`, and no section carries the "Gemara text only" flag, since the whole outline is.

## Scope
- Outline the Gemara text of THIS daf. If the daf opens mid-exchange, start from the beginning of that exchange on the previous amud (Chagigah 6 starts from the last line of 5b). End with the last unit on the daf; if a discussion begins here and continues onto the next daf, outline what is here and fill in `continues`.
- Shiur material that falls outside that scope is left out; mention it in `coverage_notes`.
- Gemara on this daf that the shiur does not discuss is still outlined, from the text alone, with `"flag": "Gemara text only"` on that section. Check the previous daf's essay tail first: the lecturer may have covered it at the end of the previous shiur, in which case use that material and don't flag it.

## Structure: this is the heart of the task
- Build the hierarchy from the logic of the sugya, not from the shiur segmentation. The segmentation is flat and follows the lecture; use it only as a guide to where topics change.
- A top-level section is a self-contained discussion. Its children are the parts of that discussion. Children share the parent's question even when their topics differ: in the example, "The Olah at Mount Sinai" holds the positions of the tanna'im, the working out of those positions, R. Yosi HaGlili's baraita, the realignment of R. Yishmael and the parsing of the verse. They are different topics in one bucket, because they all serve the question of what the olah at Sinai was.
- Nest as deep as the logic requires: often two or three levels, sometimes four. A section with no natural parts has no children; don't invent a single child.
- Anchor every section to the Gemara lines it covers with `"text": {"from": "6a.8", "to": "6a.15"}`, using the bracketed labels on the Sefaria lines you are given (a label from the previous amud, such as "5b.24", is fine when the section starts there). A parent's range spans its children's. Ranges follow the Gemara's order; a section that `returns_to` an earlier one still anchors to where it falls in the text. The app uses these anchors to scroll the Gemara text in step with the outline, so they must be exact.
- Keep the Gemara's order. Never move a section. When the Gemara returns to an earlier point, leave the section where it falls and add a `returns_to` link to the earlier section's id, with a short note.
- There will be judgment calls. Make the call, and record in `judgment_calls` each place where a different structure would also be reasonable, saying briefly what the alternative was and why you chose as you did.

## Headings and gists
- Write your own headings. Make them specific and meaningful, usually 3 to 10 words, naming the question or content ("R. Yosi HaGlili: Olah vs. Chagigah vs. Shalmei Simchah"), never generic ("The Gemara's Question", "Continued"). The segmentation's `title` fields are raw material only, and they contain errors.
- Every section gets a `gist`: one sentence, readable on its own. Headings plus gists together form the outline's "headlines" view, so they must carry the flow by themselves.

## Bullets
- Each bullet is one step of the discussion: who says what, and on what basis (a verse, a baraita, a sevara).
- `detail`: 2 for the main steps (the standard view); 3 for supporting detail (proof texts, secondary steps, fine points) shown only in the detailed view. Standard view should read as a complete, compact account.
- `source`: "gemara" for what the text itself says, grounded in the Sefaria translation; "shiur" for the lecturer's analysis, including rishonim and acharonim brought in the shiur and conceptual framing. Never present shiur analysis as the Gemara's. Never state Gemara content that isn't in the provided text.
- Mark Hebrew and Aramaic terms in *italics* with single asterisks, as the example does. No other markup.

## When the essay and the Gemara text conflict, the text wins
The Sefaria text is the authority for what the Gemara says; the essay is the authority only for the lecturer's own analysis. The essay was written from a spoken lecture and contains slips. Whenever the two disagree on a matter of fact about the text, follow the text, and record each discrepancy in `coverage_notes` (what the essay says, what the text says, which you followed). `coverage_notes` and `judgment_calls` are editorial notes for the author's review and are never shown to learners: nothing in a title, gist, bullet, chart or `continues` may mention the essay, a discrepancy or a correction. The learner simply sees the text's version. This covers:
- who said something, including the chain of transmission ("R. Yitzchak bar Nachmani in the name of Rav Oshaya", not "in the name of R. Yehoshua"), and spelling of names ("R. Elazar", not "R. Eliezer");
- what a step concludes: whether a proof is accepted or deflected, whether a question is resolved or left as *teiku* or *teyuvta* (the essay may say the Gemara "reassigns" R. Yishmael when the text only strikes him from the list);
- the order of steps: follow the order of the text even when the essay discusses them in a different order;
- which source is cited (Mishnah, baraita or Tosefta), and chapter numbers, verses and counts.
A difference of interpretation is not a conflict: the lecturer's reading of the Gemara stays in the outline, marked `"source": "shiur"`, beside the Gemara step it explains.

## Charts
- Add a `chart` to a section only when its material really is a grid: several parties, cases or arguments compared along the same dimensions (tanna'im by position, cases by ruling, arguments by rebuttal). It needs at least 2 rows and 2 columns of real content, with no filler cells.
- Most dafim have zero to two charts. Never force one. A chart supplements the bullets; it doesn't replace them.
- Orientation, always: the parties go on the rows (tanna'im, amora'im, schools, versions of a tradition such as "R. Meir's version"), and the cases, questions or aspects being compared go on the columns. Beit Shammai and Beit Hillel are two rows; "left on a swept stove" and "taken off on Shabbat" are two columns. When the grid compares things rather than people (the three pilgrimage offerings and what is unique to each), the things are the rows.
- `columns` is the header row; each entry in `rows` is a list of cell strings with the row label first. An empty first header cell is fine.

## Illustrations
Visual learners get 4 to 5 illustrations per daf (fewer only if the daf is very short). Each is a flat, labeled SVG drawing attached to the section it illustrates, as `"illustration": {"caption", "svg"}`. Their purpose is to visualize the discussion, not to decorate it. Good subjects:
- the physical scene the text describes (a stove and where a pot stands on it; the altar and pillars at Sinai);
- the parties to a dispute, grouped by position with their names (the two camps at Sinai);
- counts and comparisons drawn out (Shavuot's 10 olot vs. 2 shelamim, animal by animal);
- a sequence or timeline (Sinai, Ohel Mo'ed, Arvot Mo'av);
- a vivid story or aggada in the text (Rebbi and R. Chama bar Chanina eating shriveled eggs).
Rules:
- Every label is exact text: names as the text has them, a Hebrew or Aramaic key phrase where it helps (as in the example), nothing the outline doesn't support. Never depict God.
- Draw with simple shapes plus the shared figure library below, which the page already contains: reference symbols with `<use href="#id" x y width height/>` and never redefine them. Sages are `#sage`, colored per figure with `style="color:<robe>;--beard:<color>;--wrap:<head-cloth>"`, drawn at width w and height 1.75w. They stand plainly: no waving, no tallit or tzitzit, no modern dress.
- `viewBox="0 0 900 H"` with H between 380 and 560. Start with a full-size background rect. Use the example's palette of soft panel colors, its font families (Newsreader for titles, Public Sans for labels, Frank Ruhl Libre for Hebrew) and minimum text size 12. Keep every element inside the viewBox, and keep labels from overlapping each other or the drawings.
- Give the root `<svg>` `role="img"` and a `<title>` describing the scene. No scripts, no external images or links, no `<style>` blocks, no ids that could collide with the library's.
- The caption is one or two sentences saying what the picture shows and where it comes from in the text.

## Output
Return only a JSON object, with no prose before or after it and no code fence, in exactly the shape of the example:
{"daf", "scope": {"start", "end"}, "sections": [node], "judgment_calls": [string], "coverage_notes": [string]}
node = {"id": "s1", "title", "amud", "text": {"from", "to"}, "gist", "flag"?, "bullets": [{"text", "detail": 2|3, "source": "gemara"|"shiur"}], "chart"?: {"caption", "columns": [string], "rows": [[string]]}, "illustration"?: {"caption", "svg"}, "returns_to"?: [{"id", "note"}], "continues"?: string, "children": [node]}
Ids are unique across the whole outline ("s1", "s2", ... in document order). `amud` is a short label such as "6a", "6a–6b" or "6b → 7a".

## Figure library (already on the page; reference these ids, never redefine them)
{LIBRARY}

## Worked example: Chagigah 6, approved by the author as the model
"""


def sefaria_english(path: Path) -> list[tuple[str, str]]:
    """Return [(label, translation)] for each item, label like '6a.3'."""
    if not path.exists():
        return []
    items, amud = [], ""
    label = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^###\s+\S.*?(\d+[ab])\s*$", line)
        if m:
            amud = m.group(1)
            continue
        m = re.match(r"^\*\*(\d+)\.\*\*\s*$", line)
        if m:
            label = f"{amud}.{m.group(1)}"
            continue
        if line.startswith("*Translation:*") and label:
            items.append((label, line[len("*Translation:*"):].strip().replace("**", "")))
            label = None
    return items


def prev_dir(d: Path) -> Path | None:
    m = re.match(r"^(.*?)_(\d+)(b?)$", d.name)
    if not m:
        return None
    stem, num, b = m.group(1), int(m.group(2)), m.group(3)
    cands = [f"{stem}_{num}"] if b else [f"{stem}_{num - 1}b", f"{stem}_{num - 1}"]
    for c in cands:
        if (OUTPUT / c).is_dir():
            return OUTPUT / c
    return None


def essay_path(d: Path) -> Path:
    p = d / "02_rewrite_wall_patched.md"
    return p if p.exists() else d / "02_rewrite.md"


def segmentation_outline(d: Path) -> str:
    seg = json.loads((d / "01_segmentation.json").read_text(encoding="utf-8"))
    lines = []
    for m in seg.get("macro_segments", []):
        lines.append(f"## {m.get('title', '')}  [{m.get('timestamp', '')}]")
        for s in m.get("micro_segments", []):
            lines.append(f"   - {s.get('title', '')}  [{s.get('timestamp', '')}]")
    return "\n".join(lines)


def parse_spec(spec: str) -> tuple[str, Path, bool]:
    """'gittin_18' or 'gittin_18:textonly' -> (result key, source dir, withhold shiur?)."""
    name, _, mode = spec.partition(":")
    if mode not in ("", "textonly"):
        sys.exit(f"unknown mode in {spec!r}")
    src = OUTPUT / name if (OUTPUT / name).is_dir() else TEXTONLY_DIR / name
    has_shiur = (src / "01_segmentation.json").exists() and essay_path(src).exists()
    textonly = mode == "textonly" or not has_shiur
    key = f"{name}_textonly" if mode == "textonly" else name
    return key, src, textonly


def build_user_prompt(d: Path, textonly: bool = False, withhold_prev: bool = False) -> str:
    parts = [f"# Daf: {d.name}"]
    if textonly:
        parts.append("There is no shiur for this daf. Build the outline from the Gemara text alone.")
    else:
        parts.append("## Shiur segmentation (lecture order, full titles)\n" + segmentation_outline(d))

    pd = None if withhold_prev else prev_dir(d)
    if pd and essay_path(pd).exists():
        tail = essay_path(pd).read_text(encoding="utf-8")[-PREV_ESSAY_TAIL_CHARS:]
        parts.append(f"## Tail of the previous daf's essay ({pd.name}), for context only\n…{tail}")

    if not textonly:
        parts.append("## Shiur essay for this daf\n" + essay_path(d).read_text(encoding="utf-8"))

    def fmt(items):
        return "\n".join(f"[{lab}] {txt}" for lab, txt in items)
    prev_items = sefaria_english(d / "sefaria_prev.md")[-EDGE_ITEMS:]
    next_items = sefaria_english(d / "sefaria_next.md")[:EDGE_ITEMS]
    parts.append("## Sefaria English: end of the previous amud (context)\n" + fmt(prev_items))
    parts.append("## Sefaria English: THIS daf\n" + fmt(sefaria_english(d / "sefaria.md")))
    parts.append("## Sefaria English: start of the next daf (context)\n" + fmt(next_items))
    parts.append("Now produce the outline JSON for this daf.")
    return "\n\n".join(parts)


def system_blocks() -> list[dict]:
    example = EXAMPLE.read_text(encoding="utf-8")
    library = SPRITE.read_text(encoding="utf-8")
    # One cached block: instructions + library + example are identical across every request.
    return [{"type": "text", "text": SYSTEM_PROMPT.replace("{LIBRARY}", library) + example,
             "cache_control": {"type": "ephemeral"}}]


def build_request(spec: str, model: str) -> dict:
    key, d, textonly = parse_spec(spec)
    # A daf that has its own shiur but is run text-only also withholds the previous essay tail,
    # so nothing from any shiur leaks in; a daf with no shiur of its own keeps it, as in production.
    withhold_prev = textonly and ":" in spec
    return {
        "custom_id": f"{key}__{MODEL_TAGS[model]}",
        "params": {
            "model": model,
            # Outline + 4-5 SVG illustrations + adaptive thinking; batch requests aren't subject
            # to the SDK's synchronous-timeout limit, so a generous ceiling costs nothing unused.
            "max_tokens": 64000,
            "thinking": {"type": "adaptive"},
            # Set explicitly so the three models are compared at the same effort
            # (Opus 5.5 defaults to medium, the others to high).
            "output_config": {"effort": "high"},
            "system": system_blocks(),
            "messages": [{"role": "user", "content": build_user_prompt(d, textonly, withhold_prev)}],
        },
    }


def parse_outline(text: str) -> dict:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        from json_repair import repair_json
        return json.loads(repair_json(t))


def label_pool(d: Path) -> list[str]:
    """The Sefaria labels the model was shown, in text order (edges of the neighbours included)."""
    return ([lab for lab, _ in sefaria_english(d / "sefaria_prev.md")[-EDGE_ITEMS:]]
            + [lab for lab, _ in sefaria_english(d / "sefaria.md")]
            + [lab for lab, _ in sefaria_english(d / "sefaria_next.md")[:EDGE_ITEMS]])


def check_anchors(outline: dict, d: Path) -> list[str]:
    """Free local check: every section's text range uses real labels, runs forward, sits inside
    its parent, and starts no earlier than the section before it."""
    pos = {lab: i for i, lab in enumerate(label_pool(d))}
    problems, last_start = [], -1

    def walk(nodes, parent=None):
        nonlocal last_start
        for n in nodes or []:
            rng = n.get("text") or {}
            f, to = pos.get(rng.get("from")), pos.get(rng.get("to"))
            name = n.get("title", n.get("id"))
            if f is None or to is None:
                problems.append(f"{name}: unknown or missing label {rng}")
            else:
                if f > to:
                    problems.append(f"{name}: range runs backward {rng}")
                if f < last_start:
                    problems.append(f"{name}: starts before the previous section")
                if parent and (f < parent[0] or to > parent[1]):
                    problems.append(f"{name}: outside its parent's range")
                last_start = f
            walk(n.get("children"), (f, to) if f is not None and to is not None else parent)
    walk(outline.get("sections"))
    return problems


def harvest(client, batch_id, usage_log, src_dirs):
    for r in client.messages.batches.results(batch_id):
        key, tag = r.custom_id.split("__")
        outdir = RESULTS / key
        outdir.mkdir(parents=True, exist_ok=True)
        if r.result.type != "succeeded":
            print(f"  {r.custom_id}: {r.result.type}")
            continue
        msg = r.result.message
        text = next((blk.text for blk in msg.content if blk.type == "text"), "")
        u = msg.usage
        usage_log.append({"id": r.custom_id, "model": msg.model, "stop": msg.stop_reason,
                          "in": u.input_tokens, "cache_read": u.cache_read_input_tokens,
                          "cache_write": u.cache_creation_input_tokens, "out": u.output_tokens})
        if msg.stop_reason != "end_turn":
            print(f"  {r.custom_id}: stop_reason={msg.stop_reason}")
        (outdir / f"04_outline_{tag}.raw.txt").write_text(text, encoding="utf-8")
        try:
            out = outdir / f"04_outline_{tag}.json"
            outline = parse_outline(text)
            out.write_text(json.dumps(outline, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  wrote {out.relative_to(HERE)}")
            for prob in check_anchors(outline, src_dirs[key]):
                print(f"    anchor: {prob}")
        except Exception as e:
            print(f"  {r.custom_id}: could not parse JSON ({e}); raw text saved")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dafim", nargs="+", required=True, help="daf dir names; append :textonly to withhold the shiur")
    ap.add_argument("--models", nargs="+", default=list(MODEL_TAGS))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    for spec in args.dafim:
        key, d, textonly = parse_spec(spec)
        if not (d / "sefaria.md").exists():
            sys.exit(f"no sefaria.md for {spec} (looked in {d})")
        if d.name == "chagigah_6":
            sys.exit("chagigah_6 is the worked example; leave it out of the run")

    sys_chars = len(system_blocks()[0]["text"])
    print(f"{len(args.dafim)} dafim x {len(args.models)} models = {len(args.dafim) * len(args.models)} requests; "
          f"system prompt {sys_chars:,} chars (cached)")
    for spec in args.dafim:
        key, d, textonly = parse_spec(spec)
        prompt = build_user_prompt(d, textonly, textonly and ":" in spec)
        print(f"  {key:24s} {'TEXT ONLY ' if textonly else ''}user prompt {len(prompt):,} chars")
    if args.dry_run:
        return

    client = anthropic.Anthropic()
    batches = {}
    for model in args.models:
        state = STATE_DIR / f".outline_batch_{MODEL_TAGS[model]}.json"
        if state.exists():
            batches[model] = json.loads(state.read_text())["batch_id"]
            print(f"Resuming {model} batch {batches[model]}")
        else:
            reqs = [build_request(spec, model) for spec in args.dafim]
            batches[model] = client.messages.batches.create(requests=reqs).id
            state.write_text(json.dumps({"batch_id": batches[model]}))
            print(f"Submitted {model} batch {batches[model]} ({len(reqs)} requests)")

    src_dirs = {parse_spec(s)[0]: parse_spec(s)[1] for s in args.dafim}
    usage_log, pending = [], dict(batches)
    while pending:
        for model, bid in list(pending.items()):
            b = client.messages.batches.retrieve(bid)
            c = b.request_counts
            print(f"  {MODEL_TAGS[model]:7s} {b.processing_status}: succeeded={c.succeeded} "
                  f"processing={c.processing} errored={c.errored}")
            if b.processing_status == "ended":
                harvest(client, bid, usage_log, src_dirs)
                (STATE_DIR / f".outline_batch_{MODEL_TAGS[model]}.json").unlink(missing_ok=True)
                del pending[model]
        (STATE_DIR / "last_run_usage.json").write_text(json.dumps(usage_log, indent=1))
        if pending:
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
