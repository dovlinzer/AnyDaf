#!/usr/bin/env python3
"""fix_premature_duplication.py — finds and fixes Pass 2's "Governance"/"Governance (II)"
class of bug (see CLAUDE.md, "Pass 2 duplicates substantial content into a 'brief
return-visit' macro", found on Shabbat 11, 2026-08-07): a topic gets a brief mention early
in the shiur, segmentation correctly marks it as continuing later ("... (continued)" in the
raw title), but Pass 2 writes the FULL later explanation under the brief early mention too.

Two stages, mirroring fix_wall_of_text.py's already-proven architecture:
  Stage A (verify, Haiku) — does the transcript window covering the first occurrence
    actually support its current essay prose, or is it a duplicate of the later occurrence?
  Stage B (patch, Sonnet, confirmed duplicates only) — rewrite the first occurrence using
    ONLY the transcript window. If nothing substantive was said, the whole macro+micro
    heading is removed (mirroring the "see above" placeholder fix elsewhere this session);
    otherwise it's trimmed to what was actually said.

Operates on 02_rewrite.md directly (Pass 2's own output) -- a source-level fix, durable by
construction, unlike a patch to any derived v10/relocate output.

Usage:
    python fix_premature_duplication.py --scan                       # find candidates, print + save JSON
    python fix_premature_duplication.py --verify candidates.json      # Stage A only, no writes
    python fix_premature_duplication.py --fix candidates.json         # Stage A + B, writes 02_rewrite.md
    python fix_premature_duplication.py --fix candidates.json --dry-run
"""
import argparse
import glob
import json
import re
import sys
from pathlib import Path

import anthropic
from check_pass2_coverage import content_words, normalize, find_srt
from config import SEGMENTATION_MODEL, REWRITE_MODEL
from srt_parser import parse_srt

HERE = Path(__file__).parent


def prose_under(essay_text, heading):
    pattern = re.compile(r'^### ' + re.escape(heading) + r'\s*$', re.MULTILINE)
    m = pattern.search(essay_text)
    if not m:
        return None
    rest = essay_text[m.end():]
    nxt = re.search(r'^#{2,3} ', rest, re.MULTILINE)
    return (rest[:nxt.start()] if nxt else rest).strip()


def jaccard(a, b):
    wa, wb = set(content_words(normalize(a))), set(content_words(normalize(b)))
    return len(wa & wb) / len(wa | wb) if wa and wb else 0.0


def scan(sim_threshold=0.13, min_len=350):
    candidates = []
    for path in glob.glob(str(HERE / "output" / "*" / "01_segmentation.json")):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue
        macros = data.get("macro_segments", [])
        masechta, daf_num, amud = data.get("masechta"), data.get("daf"), data.get("amud")
        for i, m in enumerate(macros):
            title = m.get("title") or ""
            if not re.search(r'\(continued\)\s*$', title.strip()):
                continue
            base = re.sub(r'\s*\(continued\)\s*$', '', title).strip()
            first_idx = None
            for j in range(i):
                other = re.sub(r'\s*\(continued\)\s*$', '', (macros[j].get("title") or "")).strip()
                if other == base:
                    first_idx = j
                    break
            if first_idx is None:
                continue
            gap = i - first_idx - 1
            first_micros = macros[first_idx].get("micro_segments", [])
            second_micros = m.get("micro_segments", [])
            if not (gap >= 1 and len(first_micros) <= 1 and first_micros and second_micros):
                continue
            daf_dir = Path(path).parent.name
            essay_path = daf_dir and (HERE / "output" / daf_dir / "02_rewrite.md")
            if not essay_path.exists():
                continue
            essay = essay_path.read_text(encoding="utf-8", errors="replace")
            first_h2 = macros[first_idx].get("display_title")
            first_h3 = first_micros[0].get("display_title")
            p1 = prose_under(essay, first_h3)
            if not p1 or len(p1) < min_len:
                continue
            second_h3s = [mm.get("display_title") for mm in second_micros]
            best_sim = 0.0
            for h3 in second_h3s:
                p2 = prose_under(essay, h3)
                if p2:
                    best_sim = max(best_sim, jaccard(p1, p2))
            if best_sim < sim_threshold:
                continue
            next_ts = macros[first_idx + 1].get("timestamp") if first_idx + 1 < len(macros) else None
            candidates.append({
                "daf": daf_dir, "masechta": masechta, "daf_num": daf_num, "amud": amud,
                "first_h2": first_h2, "first_h3": first_h3,
                "first_ts": macros[first_idx].get("timestamp"), "next_ts": next_ts,
                "second_h3s": second_h3s, "sim": round(best_sim, 3), "plen": len(p1),
            })
    return candidates


def ts_to_seconds(ts):
    parts = [float(p) for p in ts.split(":")]
    sec = 0.0
    for p in parts:
        sec = sec * 60 + p
    return sec


def srt_seconds(entry_start):
    h, m, rest = entry_start.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def transcript_window(c):
    """Raw transcript text spoken between the first occurrence's timestamp and the next
    macro's timestamp -- the exact window Pass 2 should have drawn on for this section."""
    srt_path = find_srt(c["masechta"], c["daf_num"], c["amud"])
    if not srt_path:
        return None
    entries = parse_srt(srt_path.read_text(encoding="utf-8", errors="replace"))
    start = ts_to_seconds(c["first_ts"])
    end = ts_to_seconds(c["next_ts"]) if c["next_ts"] else start + 300
    lines = [e.text for e in entries if start <= srt_seconds(e.start_time) < end]
    return " ".join(lines)


VERIFY_PROMPT = """You are checking whether a section of an essay about a Talmud shiur (lecture) matches what was actually said in the transcript at that point in the recording.

TRANSCRIPT (what the lecturer actually said in this time window):
{transcript}

CURRENT ESSAY PROSE for this section (heading "{heading}"):
{prose}

For context, here is what the essay says LATER in the same document, under a different heading, about what appears to be the same underlying topic:
{later_prose}

Segmentation marked the later section as "(continued)" from this one -- meaning the lecturer briefly touched this topic here and returned to it properly later. Your job: does the transcript above actually support the CURRENT ESSAY PROSE's level of detail, or has the essay prematurely included the full explanation that only really belongs in the later section?

Reply with ONLY this JSON object, no other text:
{{"duplicated": true|false, "transcript_summary": "<one sentence: what, if anything, the transcript actually shows at this point>", "reason": "<one sentence>"}}
"""

PATCH_PROMPT = """You are fixing a Talmud shiur essay section that was found to contain premature/duplicated content -- it currently includes a full explanation that a later section already covers properly, but the transcript at THIS point in the recording only supports a brief mention (or nothing at all).

TRANSCRIPT (what the lecturer actually said in this time window):
{transcript}

CURRENT (over-written) ESSAY PROSE:
{prose}

Rewrite this section's prose using ONLY what the transcript above actually supports -- no content that belongs to the later, fuller treatment. If the transcript shows the lecturer said essentially nothing substantive here (just a passing mention, or a segue), reply with exactly the single word NOTHING (no other text) -- the section will be removed entirely, since its real content lives later in the essay. Otherwise, write concise, accurate prose (in the same essay voice, using italics for Hebrew/Aramaic terms as *this*) reflecting only what's genuinely here. Reply with ONLY the prose (or NOTHING), no preamble.
"""


def stage_a_verify(client, candidates):
    results = []
    for c in candidates:
        essay_path = HERE / "output" / c["daf"] / "02_rewrite.md"
        essay = essay_path.read_text(encoding="utf-8", errors="replace")
        prose = prose_under(essay, c["first_h3"])
        later_prose = "\n\n".join(
            p for h3 in c["second_h3s"] if (p := prose_under(essay, h3)))
        transcript = transcript_window(c)
        if transcript is None or not transcript.strip():
            print(f"  {c['daf']} / {c['first_h3']!r}: SKIP (no SRT / empty window)")
            results.append({**c, "verify": None})
            continue
        resp = client.messages.create(
            model=SEGMENTATION_MODEL, max_tokens=300,
            messages=[{"role": "user", "content": VERIFY_PROMPT.format(
                transcript=transcript, heading=c["first_h3"], prose=prose, later_prose=later_prose)}],
        )
        text = resp.content[0].text
        m = re.search(r'\{.*\}', text, re.DOTALL)
        verify = None
        if m:
            try:
                verify = json.loads(m.group())
            except Exception:
                pass
        status = "DUPLICATE" if verify and verify.get("duplicated") else "ok (not duplicate)"
        print(f"  {c['daf']} / {c['first_h3']!r} (sim={c['sim']}): {status}")
        if verify:
            print(f"      transcript shows: {verify.get('transcript_summary')}")
        results.append({**c, "verify": verify})
    return results


def stage_b_patch(client, verified, dry_run):
    confirmed = [c for c in verified if c.get("verify") and c["verify"].get("duplicated")]
    print(f"\n{len(confirmed)} of {len(verified)} confirmed as genuine duplicates -- patching" +
          (" (dry run)" if dry_run else ""))
    by_daf = {}
    for c in confirmed:
        by_daf.setdefault(c["daf"], []).append(c)

    for daf, items in by_daf.items():
        essay_path = HERE / "output" / daf / "02_rewrite.md"
        essay = essay_path.read_text(encoding="utf-8", errors="replace")
        for c in items:
            prose = prose_under(essay, c["first_h3"])
            transcript = transcript_window(c)
            resp = client.messages.create(
                model=REWRITE_MODEL, max_tokens=1000,
                messages=[{"role": "user", "content": PATCH_PROMPT.format(
                    transcript=transcript or "", prose=prose)}],
            )
            new_text = resp.content[0].text.strip()
            if new_text == "NOTHING":
                # Remove the whole macro (## first_h2) + micro (### first_h3) heading and
                # body. 02_rewrite.md (Pass 2's own output) has no "---" dividers between
                # macros -- those only get added later, by v10 assembly -- so the boundary
                # is just the next "## "/"### " heading of any level, or end of file.
                macro_pat = re.compile(
                    r'## ' + re.escape(c["first_h2"]) +
                    r'\n\n### ' + re.escape(c["first_h3"]) + r'\n\n.*?(?=\n## |\Z)',
                    re.DOTALL)
                new_essay, n = macro_pat.subn("", essay, count=1)
                action = "REMOVED (transcript shows nothing substantive)"
            else:
                old_block = f"### {c['first_h3']}\n\n{prose}"
                new_block = f"### {c['first_h3']}\n\n{new_text}"
                new_essay = essay.replace(old_block, new_block, 1)
                n = 1 if new_essay != essay else 0
                action = f"TRIMMED to {len(new_text)} chars"
            if n == 0:
                print(f"  {daf} / {c['first_h3']!r}: FAILED to apply patch (pattern not found)")
                continue
            print(f"  {daf} / {c['first_h3']!r}: {action}")
            essay = new_essay
        if not dry_run:
            essay_path.write_text(essay, encoding="utf-8")
            print(f"  {daf}: wrote {essay_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--verify", metavar="FILE")
    ap.add_argument("--fix", metavar="FILE")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sim-threshold", type=float, default=0.13)
    ap.add_argument("--out", default="/tmp/dup_candidates.json")
    args = ap.parse_args()

    if args.scan:
        candidates = scan(sim_threshold=args.sim_threshold)
        print(f"{len(candidates)} candidates found")
        Path(args.out).write_text(json.dumps(candidates, indent=2, ensure_ascii=False))
        print(f"wrote {args.out}")
        return

    if args.verify or args.fix:
        path = args.verify or args.fix
        candidates = json.loads(Path(path).read_text())
        client = anthropic.Anthropic()
        print(f"Stage A: verifying {len(candidates)} candidate(s)...")
        verified = stage_a_verify(client, candidates)
        verified_path = str(Path(path).with_suffix("")) + "_verified.json"
        Path(verified_path).write_text(json.dumps(verified, indent=2, ensure_ascii=False))
        print(f"wrote {verified_path}")
        if args.fix:
            stage_b_patch(client, verified, args.dry_run)
        return

    print("Pass --scan, --verify FILE, or --fix FILE")


if __name__ == "__main__":
    main()
