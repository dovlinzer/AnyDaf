#!/usr/bin/env python3
"""
check_segmentation.py — Scan segmentation files for chronological ordering violations.

Checks each output/<masechta_daf>/01_segmentation.json for:
  1. Macro segments not in ascending timestamp order
  2. Micro segments within a macro not in ascending timestamp order
  3. Overlap: last micro of macro N ends after first micro of macro N+1 begins
     (indicates Claude grouped non-contiguous audio thematically)

Writes a shell script of python3 main.py commands to re-run pass 1 for each
flagged daf. Prints a summary to stdout.

Usage:
  python3 check_segmentation.py                          # scans ./output, writes rerun.sh
  python3 check_segmentation.py --output-dir ./output --srt-dir ./srt/processed
  python3 check_segmentation.py --output-file fix_segmentation.sh
"""

import argparse
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


def check_ordering(data: dict) -> list:
    """
    Return a list of violation description strings.
    Empty list means the file is clean.
    """
    violations = []
    macros = data.get("macro_segments", [])

    prev_macro_last_ts = -1.0
    prev_macro_title = None

    for i, macro in enumerate(macros):
        title = macro.get("title", f"macro[{i}]")
        macro_ts = ts_to_seconds(macro.get("timestamp", "0:00"))
        micros = macro.get("micro_segments", [])

        if not micros:
            continue

        # Check micro ordering within this macro
        prev_micro_ts = -1.0
        for j, micro in enumerate(micros):
            mts = ts_to_seconds(micro.get("timestamp", "0:00"))
            if mts < prev_micro_ts:
                violations.append(
                    f"  Macro '{title}': micro[{j}] '{micro.get('title','')}' "
                    f"({micro['timestamp']}) is before micro[{j-1}] ({micros[j-1]['timestamp']})"
                )
            prev_micro_ts = mts

        first_micro_ts = ts_to_seconds(micros[0]["timestamp"])
        last_micro_ts  = ts_to_seconds(micros[-1]["timestamp"])

        # Check macro ordering: this macro's first micro must be after previous macro's last micro
        if prev_macro_last_ts >= 0 and first_micro_ts < prev_macro_last_ts:
            violations.append(
                f"  Macro '{title}' starts at {micros[0]['timestamp']} but previous macro "
                f"'{prev_macro_title}' ends at {macros[i-1]['micro_segments'][-1]['timestamp']} "
                f"— non-contiguous grouping"
            )

        prev_macro_last_ts = last_micro_ts
        prev_macro_title = title

    return violations



# Spelling variants in JSON masechta fields → canonical name for commands and SRT filenames
_MASECHTA_CANONICAL = {
    "chullin": "Hullin",
    "hullin":  "Hullin",
}


def find_srt(masechta: str, daf: int, amud: str, srt_dir: Path) -> str:
    """Return the SRT path string, or a placeholder if not found."""
    # Normalise masechta name to match SRT filename convention
    srt_masechta = _MASECHTA_CANONICAL.get(masechta.lower(), masechta)

    # Build candidate daf strings to try, in order of preference:
    #   "29b", "29" (amud a is usually implicit), "29a"
    daf_strs = []
    if amud and amud != "a":
        daf_strs.append(f"{daf}{amud}")   # e.g. "29b"
    daf_strs.append(str(daf))             # e.g. "29" (no amud suffix)
    if amud:
        daf_strs.append(f"{daf}{amud}")   # e.g. "29a" as last resort

    for daf_str in daf_strs:
        candidate = srt_dir / f"{srt_masechta} {daf_str}.srt"
        if candidate.exists():
            return str(candidate)
        # Case-insensitive fallback
        pattern = f"{srt_masechta.lower()} {daf_str.lower()}.srt"
        for f in srt_dir.iterdir():
            if f.name.lower() == pattern:
                return str(f)

    return f"<SRT NOT FOUND: {srt_masechta} {daf}{amud or ''}.srt in {srt_dir}>"


def main():
    parser = argparse.ArgumentParser(description="Check segmentation JSON files for ordering violations.")
    parser.add_argument("--output-dir", default="./output",
                        help="Directory containing job subdirectories (default: ./output)")
    parser.add_argument("--srt-dir", default="./srt/processed",
                        help="Directory containing SRT files (default: ./srt/processed)")
    parser.add_argument("--output-file", default="rerun_segmentation.sh",
                        help="Shell script to write re-run commands to (default: rerun_segmentation.sh)")
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

    flagged = []

    for seg_file in seg_files:
        data = load_segmentation(seg_file)
        if data is None:
            continue
        if "_parse_error" in data:
            flagged.append((seg_file, data, [f"  Invalid JSON: {data['_parse_error']}"]))
            continue
        violations = check_ordering(data)
        if violations:
            flagged.append((seg_file, data, violations))

    if not flagged:
        print("All segmentation files are clean.")
        return

    print(f"Found {len(flagged)} file(s) with violations:\n")

    found_srts    = []   # SRT paths that were located on disk
    missing_srts  = []   # (label, cmd) for SRTs that need manual attention

    for seg_file, data, violations in flagged:
        masechta = data.get("masechta", "")
        daf      = data.get("daf", 0)
        amud     = data.get("amud", "") or ""
        label    = f"{masechta} {daf}{amud}"

        print(f"{label}  ({seg_file})")
        for v in violations:
            print(v)
        print()

        canonical_masechta = _MASECHTA_CANONICAL.get(masechta.lower(), masechta)
        srt_path = find_srt(masechta, daf, amud, srt_dir)

        if srt_path.startswith("<SRT NOT FOUND"):
            missing_srts.append((label, srt_path, canonical_masechta, daf, amud))
        else:
            found_srts.append(srt_path)

    out_path = Path(args.output_file)
    with out_path.open("w", encoding="utf-8") as f:
        f.write("#!/bin/bash\n")
        f.write(f"# Re-run all passes (1–3) for {len(flagged)} daf(im) with segmentation violations\n")
        f.write("# Generated by check_segmentation.py\n\n")

        if found_srts:
            # Single parallel invocation for all located SRT files
            srt_args = " \\\n    ".join(f'"{p}"' for p in found_srts)
            f.write("# All located SRT files — processed in parallel\n")
            f.write(f"python3 main.py \\\n    {srt_args} \\\n    --workers 5\n")

        if missing_srts:
            f.write("\n# ── SRT files not found — fix path and run individually ──\n")
            for label, srt_path, masechta, daf, amud in missing_srts:
                f.write(f"# {label}: SRT not found at expected path\n")
                cmd = (
                    f'# python3 main.py "<PATH TO {label}.srt>" '
                    f'--masechta "{masechta}" --daf {daf}'
                    + (f' --amud {amud}' if amud else '')
                )
                f.write(cmd + "\n\n")

    out_path.chmod(0o755)
    n_found   = len(found_srts)
    n_missing = len(missing_srts)
    print(f"Re-run command written to: {out_path}")
    print(f"  {n_found} file(s) batched into one parallel run")
    if n_missing:
        print(f"  {n_missing} file(s) not found — commented out, fix paths manually")
    print(f"Run with: bash {out_path}")


if __name__ == "__main__":
    main()
