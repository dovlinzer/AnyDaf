#!/usr/bin/env python3
"""
check_segmentation.py — Scan segmentation files for chronological ordering violations
and duplicate/near-duplicate macro segment display titles.

Checks each output/<masechta_daf>/01_segmentation.json for:
  1. Macro segments not in strictly ascending timestamp order (including equal timestamps)
  2. Micro segments within a macro not in ascending timestamp order
  3. Overlap: last micro of macro N ends at or after first micro of macro N+1 begins
  4. Duplicate or near-duplicate macro segment display_titles within the same daf

With --fix: rewrites display_title duplicates directly in the JSON files (appends
" (II)", " (III)", etc.). Does NOT auto-fix timestamp violations — those require
re-running the segmentation pipeline.

Usage:
  python3 check_segmentation.py                          # report only
  python3 check_segmentation.py --fix                    # also fix display_title dupes
  python3 check_segmentation.py --output-dir ./output --srt-dir ./srt/processed
  python3 check_segmentation.py --output-file fix_segmentation.sh
"""

import argparse
import difflib
import json
import re
import sys
from pathlib import Path


def ts_to_seconds(ts: str) -> float:
    parts = re.split(r":", ts.strip())
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except (ValueError, IndexError):
        pass
    return 0.0


def load_segmentation(seg_file: Path):
    """Return parsed JSON dict, or None if file is missing or invalid."""
    if not seg_file.exists():
        return None
    raw = seg_file.read_text(encoding="utf-8").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        return {"_parse_error": str(e)}


_RANK_SUFFIX_RE = re.compile(
    r"\s*\((II|III|IV|V|VI|VII|VIII|IX|X|\d+)\)\s*$", re.IGNORECASE
)


def _normalize_title(title: str) -> str:
    """Strip decorative suffixes and lowercase for similarity comparison."""
    t = title.strip()
    t = re.sub(r"[…\.]+$", "", t)          # trailing ellipsis
    t = re.sub(r"\s*\(cont(?:inued)?\.\)\s*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*\(resumed\)\s*$", "", t, flags=re.IGNORECASE)
    return t.lower().strip()


def _is_intentionally_disambiguated(a: str, b: str) -> bool:
    """
    True if b is the same base as a but with a rank suffix added by --fix
    (e.g. 'Role Boundaries' vs 'Role Boundaries (II)').
    """
    b_stripped = _RANK_SUFFIX_RE.sub("", b).strip()
    a_stripped = _RANK_SUFFIX_RE.sub("", a).strip()
    if _normalize_title(b_stripped) == _normalize_title(a_stripped):
        # Only one of them has a rank suffix
        return bool(_RANK_SUFFIX_RE.search(a) or _RANK_SUFFIX_RE.search(b))
    return False


def _titles_are_near_identical(a: str, b: str) -> bool:
    """
    True if two display_titles are the same title (possibly with trailing ellipsis
    or 25-char truncation producing slightly different endings).

    Deliberately avoids:
    - Character-similarity ratios: produce false positives for titles that share
      common words but are genuinely different topics ("Invalid Witnesses" vs
      "Validating Witnesses").
    - Unconstrained prefix matching: flags genuinely distinct sub-topics whose
      names share a common stem ("Spinal Cord" vs "Spinal Cord in Birds",
      "Abandonment" vs "Abandonment Types"). Prefix matching is only applied when
      the shorter title explicitly signals truncation with a trailing "…".
    """
    if _is_intentionally_disambiguated(a, b):
        return False
    na, nb = _normalize_title(a), _normalize_title(b)
    if na == nb:
        return True
    # Prefix match only when the shorter title ends with "…" — explicit truncation
    # signal. Without it, shorter-is-prefix-of-longer means a genuinely distinct topic.
    if len(na) >= 5 and len(nb) >= 5:
        shorter, longer = (a, b) if len(na) < len(nb) else (b, a)
        sna, lna = (na, nb) if len(na) < len(nb) else (nb, na)
        if shorter.rstrip().endswith("…") and lna.startswith(sna):
            return True
    return False


def check_ordering(data: dict) -> list:
    """
    Return a list of (violation_type, description) tuples.
      violation_type: "timestamp" | "title"
    Empty list means the file is clean.
    """
    violations = []
    macros = data.get("macro_segments", [])

    prev_macro_last_ts = -1.0
    prev_macro_title = None

    for i, macro in enumerate(macros):
        title = macro.get("title", f"macro[{i}]")
        micros = macro.get("micro_segments", [])

        if not micros:
            continue

        # Check micro ordering within this macro
        prev_micro_ts = -1.0
        for j, micro in enumerate(micros):
            mts = ts_to_seconds(micro.get("timestamp", "0:00"))
            if mts < prev_micro_ts:
                violations.append((
                    "timestamp",
                    f"  Macro '{title}': micro[{j}] '{micro.get('title','')}' "
                    f"({micro['timestamp']}) is before micro[{j-1}] ({micros[j-1]['timestamp']})"
                ))
            prev_micro_ts = mts

        first_micro_ts = ts_to_seconds(micros[0]["timestamp"])
        last_micro_ts  = ts_to_seconds(micros[-1]["timestamp"])

        # Check macro ordering: this macro's first micro must be STRICTLY after
        # the previous macro's last micro (equal timestamps also flagged).
        if prev_macro_last_ts >= 0 and first_micro_ts <= prev_macro_last_ts:
            prev_last_ts_str = macros[i-1]["micro_segments"][-1]["timestamp"]
            if first_micro_ts == prev_macro_last_ts:
                desc = (
                    f"  Macro[{i}] '{title}' starts at {micros[0]['timestamp']} — "
                    f"SAME timestamp as end of macro[{i-1}] '{prev_macro_title}' "
                    f"({prev_last_ts_str})"
                )
            else:
                desc = (
                    f"  Macro[{i}] '{title}' starts at {micros[0]['timestamp']} but "
                    f"macro[{i-1}] '{prev_macro_title}' ends at {prev_last_ts_str} "
                    f"— non-contiguous grouping / overlap"
                )
            violations.append(("timestamp", desc))

        prev_macro_last_ts = last_micro_ts
        prev_macro_title = title

    # Check macro display_title uniqueness
    display_titles = [m.get("display_title", "") for m in macros]
    flagged_pairs = set()
    for i in range(len(display_titles)):
        for j in range(i + 1, len(display_titles)):
            if (i, j) in flagged_pairs:
                continue
            if _titles_are_near_identical(display_titles[i], display_titles[j]):
                flagged_pairs.add((i, j))
                violations.append((
                    "title",
                    f"  Duplicate display_title: macro[{i}] '{display_titles[i]}' "
                    f"≈ macro[{j}] '{display_titles[j]}'"
                ))

    return violations


def fix_display_titles(data: dict) -> int:
    """
    Rename duplicate macro display_titles in-place by appending ' (II)', ' (III)', etc.
    Groups by normalized title, also treating titles as equal when one is a prefix of the
    other (handles 25-char truncation producing slightly different endings).
    Returns the number of titles changed.
    """
    macros = data.get("macro_segments", [])
    changed = 0

    norms = [_normalize_title(m.get("display_title", "")) for m in macros]

    # Union-find: merge indices whose normalized titles are identical or one is a prefix
    parent = list(range(len(macros)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    raw_titles = [m.get("display_title", "") for m in macros]

    for i in range(len(norms)):
        for j in range(i + 1, len(norms)):
            na, nb = norms[i], norms[j]
            if na == nb:
                union(i, j)
            elif len(na) >= 5 and len(nb) >= 5:
                # Prefix match only when the SHORTER title ends with "…" — that's
                # the explicit signal the model used to indicate truncation at the
                # 25-char limit. Without "…", a shorter title that happens to be a
                # prefix of a longer one is a genuinely distinct topic
                # (e.g. "Abandonment" vs "Abandonment Categories").
                shorter_raw = raw_titles[i] if len(na) < len(nb) else raw_titles[j]
                if shorter_raw.rstrip().endswith("…") and (nb.startswith(na) or na.startswith(nb)):
                    union(i, j)

    # Group by root
    groups: dict[int, list[int]] = {}
    for i in range(len(macros)):
        root = find(i)
        groups.setdefault(root, []).append(i)

    suffixes = ["", " (II)", " (III)", " (IV)", " (V)", " (VI)"]

    for root, indices in groups.items():
        if len(indices) < 2:
            continue
        # Indices are already in document order (0..n). First keeps its title.
        for rank, idx in enumerate(indices[1:], start=1):
            suffix = suffixes[rank] if rank < len(suffixes) else f" ({rank + 1})"
            base = macros[idx]["display_title"].rstrip("…").rstrip(".").strip()
            max_base = 25 - len(suffix)
            if len(base) > max_base:
                base = base[:max_base].rstrip()
            macros[idx]["display_title"] = base + suffix
            changed += 1

    return changed


# Spelling variants in JSON masechta fields → canonical name for commands and SRT filenames
_MASECHTA_CANONICAL = {
    "chullin": "Hullin",
    "hullin":  "Hullin",
}


def find_srt(masechta: str, daf: int, amud: str, srt_dir: Path) -> str:
    """Return the SRT path string, or a placeholder if not found."""
    srt_masechta = _MASECHTA_CANONICAL.get(masechta.lower(), masechta)

    daf_strs = []
    if amud and amud != "a":
        daf_strs.append(f"{daf}{amud}")
    daf_strs.append(str(daf))
    if amud:
        daf_strs.append(f"{daf}{amud}")

    for daf_str in daf_strs:
        candidate = srt_dir / f"{srt_masechta} {daf_str}.srt"
        if candidate.exists():
            return str(candidate)
        pattern = f"{srt_masechta.lower()} {daf_str.lower()}.srt"
        for f in srt_dir.iterdir():
            if f.name.lower() == pattern:
                return str(f)

    return f"<SRT NOT FOUND: {srt_masechta} {daf}{amud or ''}.srt in {srt_dir}>"


def main():
    parser = argparse.ArgumentParser(
        description="Check segmentation JSON files for ordering violations and duplicate titles."
    )
    parser.add_argument("--output-dir", default="./output",
                        help="Directory containing job subdirectories (default: ./output)")
    parser.add_argument("--srt-dir", default="./srt/processed",
                        help="Directory containing SRT files (default: ./srt/processed)")
    parser.add_argument("--output-file", default="rerun_segmentation.sh",
                        help="Shell script to write re-run commands to (default: rerun_segmentation.sh)")
    parser.add_argument("--fix", action="store_true",
                        help="Auto-fix duplicate display_titles in place (appends II/III/etc.). "
                             "Does NOT fix timestamp violations — those need pipeline re-runs.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    srt_dir    = Path(args.srt_dir)

    if not output_dir.exists():
        print(f"Error: output directory '{output_dir}' not found.", file=sys.stderr)
        sys.exit(1)

    seg_files = sorted(output_dir.glob("*/01_segmentation.json"))
    if not seg_files:
        print(f"No segmentation files found under '{output_dir}'.")
        sys.exit(0)

    print(f"Checking {len(seg_files)} segmentation file(s) in '{output_dir}'…\n")

    # Each entry: (seg_file, data, violations_list)
    # violations_list: list of (type, description)
    all_results = []

    for seg_file in seg_files:
        data = load_segmentation(seg_file)
        if data is None:
            continue
        if "_parse_error" in data:
            all_results.append((seg_file, data, [("error", f"  Invalid JSON: {data['_parse_error']}")]))
            continue
        violations = check_ordering(data)
        if violations:
            all_results.append((seg_file, data, violations))

    if not all_results:
        print("All segmentation files are clean — no timestamp or title issues found.")
        return

    # Separate timestamp vs. title-only violations
    ts_flagged    = [(f, d, v) for f, d, v in all_results if any(t == "timestamp" for t, _ in v)]
    title_flagged = [(f, d, v) for f, d, v in all_results if any(t == "title"     for t, _ in v)]

    print(f"{'=' * 60}")
    print(f"TIMESTAMP VIOLATIONS ({len(ts_flagged)} file(s))")
    print(f"{'=' * 60}")
    if ts_flagged:
        for seg_file, data, violations in ts_flagged:
            label = f"{data.get('masechta','')} {data.get('daf','')}{ data.get('amud','') or ''}"
            print(f"\n{label}  ({seg_file})")
            for vtype, desc in violations:
                if vtype == "timestamp":
                    print(desc)
    else:
        print("  None.")

    print(f"\n{'=' * 60}")
    print(f"DUPLICATE / NEAR-DUPLICATE DISPLAY TITLES ({len(title_flagged)} file(s))")
    print(f"{'=' * 60}")
    if title_flagged:
        total_title_fixes = 0
        for seg_file, data, violations in title_flagged:
            label = f"{data.get('masechta','')} {data.get('daf','')}{ data.get('amud','') or ''}"
            print(f"\n{label}  ({seg_file})")
            for vtype, desc in violations:
                if vtype == "title":
                    print(desc)
            if args.fix:
                n = fix_display_titles(data)
                if n:
                    seg_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8")
                    print(f"  → Fixed {n} display_title(s) in {seg_file.name}")
                    total_title_fixes += n
        if args.fix:
            print(f"\nTotal display_titles rewritten: {total_title_fixes}")
    else:
        print("  None.")

    # Write re-run shell script for timestamp violations only
    if ts_flagged:
        found_srts   = []
        missing_srts = []

        for seg_file, data, violations in ts_flagged:
            masechta = data.get("masechta", "")
            daf      = data.get("daf", 0)
            amud     = data.get("amud", "") or ""
            canonical = _MASECHTA_CANONICAL.get(masechta.lower(), masechta)
            srt_path = find_srt(masechta, daf, amud, srt_dir)
            label = f"{masechta} {daf}{amud}"
            if srt_path.startswith("<SRT NOT FOUND"):
                missing_srts.append((label, srt_path, canonical, daf, amud))
            else:
                found_srts.append(srt_path)

        out_path = Path(args.output_file)
        with out_path.open("w", encoding="utf-8") as f:
            f.write("#!/bin/bash\n")
            f.write(f"# Re-run segmentation (pass 1) for {len(ts_flagged)} daf(im) "
                    f"with timestamp violations\n")
            f.write("# Generated by check_segmentation.py\n\n")

            if found_srts:
                srt_args = " \\\n    ".join(f'"{p}"' for p in found_srts)
                f.write("# All located SRT files — processed in parallel\n")
                f.write(f"python3 main.py \\\n    {srt_args} \\\n    --workers 5\n")

            if missing_srts:
                f.write("\n# ── SRT files not found — fix path and run individually ──\n")
                for label, _, masechta, daf, amud in missing_srts:
                    f.write(f"# {label}: SRT not found\n")
                    cmd = (
                        f'# python3 main.py "<PATH TO {label}.srt>" '
                        f'--masechta "{masechta}" --daf {daf}'
                        + (f' --amud {amud}' if amud else '')
                    )
                    f.write(cmd + "\n\n")

        out_path.chmod(0o755)
        print(f"\nRe-run script for timestamp violations: {out_path}")
        print(f"  {len(found_srts)} file(s) batched | {len(missing_srts)} SRT(s) not found")
        print(f"Run with: bash {out_path}")

    if not args.fix and title_flagged:
        print(f"\nTo auto-fix duplicate display_titles, rerun with: --fix")


if __name__ == "__main__":
    main()
