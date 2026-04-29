#!/usr/bin/env python3
"""
consolidate_topics.py — Merge duplicate canonical terms in topic_mapping.json.

The normalize_topics.py job ran 517 separate batches with no shared reference,
so the same concept often got different canonical names in different batches
(e.g. "Beit HaMikdash (Temple)", "Beis HaMikdash", "Second Temple").

This script:
  1. Extracts all unique canonical terms from topic_mapping.json (~15-25k)
  2. Sends alphabetical batches to Claude asking which are duplicates
  3. Builds a merge map: {variant → preferred_canonical}
  4. Resolves merge chains (A→B, B→C becomes A→C)
  5. Applies the merge map to produce consolidated_mapping.json
  6. Rebuilds the index with correctly aggregated counts

Output (in --out-dir):
  merge_map.json              {variant → preferred_canonical}
  consolidated_mapping.json   topic_mapping.json with duplicates merged
  consolidated_index.json     hierarchical index with correct aggregated counts
  consolidation_report.tsv    human-readable before/after for review

Usage:
  python3 consolidate_topics.py
  python3 consolidate_topics.py --resume msgbatch_abc123
  python3 consolidate_topics.py --dry-run
  python3 consolidate_topics.py --apply-only   # skip batch, just apply existing merge_map.json
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BATCH_SIZE    = 120     # canonical terms per request (smaller = less chance of missing cross-term merges)
MODEL         = "claude-haiku-4-5-20251001"
MAX_TOKENS    = 8192
POLL_INTERVAL = 30
BATCH_TIMEOUT = 3600 * 4

SYSTEM_PROMPT = """\
You are a Talmud scholar reviewing a list of index terms for a scholarly topical index \
of the Talmud. Your job is to identify DUPLICATE entries — different phrasings, spellings, \
or transliterations that refer to the same concept and should be merged into one canonical entry.

You are NOT being asked to reorganize or reclassify topics. Only flag genuine duplicates \
that should be a single entry in the index.
"""

USER_PROMPT_TEMPLATE = """\
Below are {n} canonical terms from a Talmud topical index. \
Identify any groups that are duplicates of each other — same concept, different wording.

Common duplicate patterns to catch:
- Transliteration variants: "Beit" vs "Beis", "Kavana" vs "Kavanah", "Chazaka" vs "Chazakah"
- With/without gloss: "Shechita" vs "Shechita (ritual slaughter)"
- Hebrew vs English: "Avel" vs "Mourner"
- Capitalization or word order differences
- Abbreviations vs full form: "R. Yochanan" vs "Rabbi Yochanan"
- Minor wording: "Beit HaMikdash (Temple)" vs "Beit HaMikdash (Second Temple)"

Do NOT merge:
- Genuinely distinct concepts that happen to be related
- A main topic with its subentry (e.g. "Shabbat" and "Shabbat, carrying" are NOT duplicates)
- Terms that are similar but cover different legal distinctions

For each group of duplicates, return one JSON object with:
  "preferred": the best canonical form (most complete, most standard transliteration)
  "duplicates": list of the other forms that should merge INTO the preferred

If a term has no duplicates in this list, omit it entirely.

Return ONLY a JSON array of merge groups. If there are no duplicates at all, return [].

Terms:
{terms_json}
"""

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

def load_mapping(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_unique_canonicals(mapping: dict) -> list[str]:
    """Return sorted list of all unique canonical values in the mapping."""
    canonicals = {v["canonical"] for v in mapping.values() if v.get("canonical")}
    return sorted(canonicals, key=str.lower)


# ---------------------------------------------------------------------------
# Batch submission
# ---------------------------------------------------------------------------

def chunk(lst: list, size: int) -> list[list]:
    return [lst[i:i + size] for i in range(0, len(lst), size)]


def build_requests(canonical_chunks: list[list[str]]) -> list[dict]:
    reqs = []
    for i, terms in enumerate(canonical_chunks):
        terms_json = json.dumps(terms, ensure_ascii=False, indent=2)
        user_msg = USER_PROMPT_TEMPLATE.format(n=len(terms), terms_json=terms_json)
        reqs.append({
            "custom_id": f"dedup_{i:04d}",
            "params": {
                "model":      MODEL,
                "max_tokens": MAX_TOKENS,
                "system":     SYSTEM_PROMPT,
                "messages":   [{"role": "user", "content": user_msg}],
            },
        })
    return reqs


def submit_batch(client, requests: list[dict], state_file: Path) -> str:
    print(f"Submitting {len(requests)} deduplication requests to Batch API…")
    batch = client.messages.batches.create(requests=requests)
    print(f"  Batch ID: {batch.id}  (saved to {state_file})")
    state_file.write_text(json.dumps({"batch_id": batch.id}), encoding="utf-8")
    return batch.id


def poll_until_done(client, batch_id: str) -> None:
    start = time.time()
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        c = batch.request_counts
        elapsed = int(time.time() - start)
        print(
            f"  [{elapsed:>5}s] {batch.processing_status} — "
            f"succeeded={c.succeeded} processing={c.processing} errored={c.errored}",
            flush=True,
        )
        if batch.processing_status == "ended":
            return
        if time.time() - start > BATCH_TIMEOUT:
            sys.exit(f"Timed out. Re-run with --resume {batch_id}")
        time.sleep(POLL_INTERVAL)


# ---------------------------------------------------------------------------
# Parse results → raw merge groups
# ---------------------------------------------------------------------------

def parse_merge_groups(client, batch_id: str) -> list[dict]:
    """
    Returns a flat list of merge group dicts:
      [{"preferred": str, "duplicates": [str, ...]}, ...]
    """
    groups = []
    errors = 0

    for result in client.messages.batches.results(batch_id):
        if result.result.type != "succeeded":
            errors += 1
            print(f"  Request {result.custom_id} failed: {result.result.type}")
            continue

        msg = result.result.message
        if msg.stop_reason == "max_tokens":
            errors += 1
            print(f"  TRUNCATED {result.custom_id} — raise MAX_TOKENS or lower BATCH_SIZE")
            continue

        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            batch_groups = json.loads(raw)
        except json.JSONDecodeError as e:
            errors += 1
            print(f"  JSON error in {result.custom_id}: {e}  (first 150: {raw[:150]})")
            continue

        if not isinstance(batch_groups, list):
            errors += 1
            print(f"  {result.custom_id}: expected list, got {type(batch_groups)}")
            continue

        for grp in batch_groups:
            preferred   = (grp.get("preferred") or "").strip()
            duplicates  = [d.strip() for d in grp.get("duplicates", []) if d.strip()]
            if preferred and duplicates:
                groups.append({"preferred": preferred, "duplicates": duplicates})

    print(f"Collected {len(groups)} merge groups ({errors} errors)")
    return groups


# ---------------------------------------------------------------------------
# Build & resolve merge map
# ---------------------------------------------------------------------------

def build_merge_map(groups: list[dict], all_canonicals: set[str]) -> dict[str, str]:
    """
    Returns {variant → preferred} for every variant that should be merged.
    Resolves chains: if A→B and B→C, A→C.
    The preferred form itself is NOT included as a key.

    Only merges terms that actually exist in the canonical set (guards against
    Claude hallucinating terms that weren't in the input).
    """
    raw_map: dict[str, str] = {}  # variant → preferred (unresolved)

    for grp in groups:
        preferred = grp["preferred"]
        for dup in grp["duplicates"]:
            if dup == preferred:
                continue
            # Only record if both ends exist in our actual canonical list
            # (preferred may not exist if Claude invented a new form — keep it anyway
            #  since it may be the best form; duplicates must exist)
            if dup in all_canonicals:
                raw_map[dup] = preferred

    # Resolve chains iteratively
    def resolve(term: str, visited: set) -> str:
        if term in visited:
            return term  # cycle guard
        if term not in raw_map:
            return term
        visited.add(term)
        return resolve(raw_map[term], visited)

    resolved: dict[str, str] = {}
    for variant in raw_map:
        final = resolve(variant, set())
        if final != variant:
            resolved[variant] = final

    return resolved


# ---------------------------------------------------------------------------
# Apply merge map
# ---------------------------------------------------------------------------

def apply_merge_map(mapping: dict, merge_map: dict[str, str]) -> dict:
    """
    Returns a new mapping with all canonical values remapped through merge_map.
    Also remaps parent values.
    """
    consolidated = {}
    for raw_term, entry in mapping.items():
        new_entry = dict(entry)
        canonical = entry.get("canonical", "")
        new_entry["canonical"] = merge_map.get(canonical, canonical)
        parent = entry.get("parent")
        if parent:
            new_entry["parent"] = merge_map.get(parent, parent)
        consolidated[raw_term] = new_entry
    return consolidated


# ---------------------------------------------------------------------------
# Rebuild index (same logic as normalize_topics.build_index)
# ---------------------------------------------------------------------------

def build_index(mapping: dict, raw_topics: dict) -> dict:
    entries: dict[str, dict] = {}

    def get_or_create(canonical: str, parent, is_auth: bool) -> dict:
        if canonical not in entries:
            entries[canonical] = {
                "canonical":    canonical,
                "parent":       parent,
                "is_authority": is_auth,
                "raw_terms":    [],
                "occurrences":  [],
                "subentries":   {},
            }
        return entries[canonical]

    for raw_term, norm in mapping.items():
        canonical = norm["canonical"]
        parent    = norm.get("parent") or None
        is_auth   = norm.get("is_authority", False)
        entry = get_or_create(canonical, parent, is_auth)
        entry["raw_terms"].append(raw_term)
        if raw_term in raw_topics:
            entry["occurrences"].extend(raw_topics[raw_term]["occurrences"])
        if parent:
            get_or_create(parent, None, False)

    for entry in entries.values():
        parent = entry["parent"]
        if parent and parent in entries:
            entries[parent]["subentries"][entry["canonical"]] = entry

    for entry in entries.values():
        tractates = sorted({o["tractate"] for o in entry["occurrences"]})
        entry["daf_count"]      = len(entry["occurrences"])
        entry["tractate_count"] = len(tractates)
        entry["tractates"]      = tractates

    top_level = {k: v for k, v in entries.items()
                 if not v["parent"] or v["parent"] not in entries}
    return {"entries": entries, "top_level": top_level}


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_merge_map(merge_map: dict, path: Path) -> None:
    path.write_text(json.dumps(merge_map, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {path}  ({len(merge_map):,} merges)")


def write_consolidated_mapping(mapping: dict, path: Path) -> None:
    path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {path}  ({len(mapping):,} raw terms)")


def write_index(index: dict, path: Path) -> None:
    def slim(e: dict) -> dict:
        return {
            "canonical":      e["canonical"],
            "parent":         e["parent"],
            "is_authority":   e["is_authority"],
            "daf_count":      e["daf_count"],
            "tractate_count": e["tractate_count"],
            "tractates":      e["tractates"],
            "raw_terms":      e["raw_terms"],
            "subentries":     {k: slim(v) for k, v in e["subentries"].items()},
        }
    top = sorted(
        index["top_level"].values(),
        key=lambda e: (not e["is_authority"], -e["tractate_count"], -e["daf_count"], e["canonical"].lower()),
    )
    path.write_text(json.dumps([slim(e) for e in top], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {path}  ({len(top):,} top-level entries)")


def write_report(merge_map: dict, before: dict, after: dict, path: Path) -> None:
    """TSV showing what merged into what, with before/after daf counts."""
    # Build reverse map: preferred → [variants]
    by_preferred: dict[str, list] = defaultdict(list)
    for variant, preferred in merge_map.items():
        by_preferred[preferred].append(variant)

    lines = ["preferred_canonical\tmerged_from\tbefore_daf_count\tafter_daf_count"]
    for preferred, variants in sorted(by_preferred.items(), key=lambda kv: kv[0].lower()):
        before_count = before.get(preferred, {}).get("daf_count", 0)
        after_count  = after.get(preferred,  {}).get("daf_count", 0)
        lines.append(f"{preferred}\t{'; '.join(variants)}\t{before_count}\t{after_count}")
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {path}  ({len(by_preferred):,} merge groups)")


def print_stats(merge_map: dict, before_canonicals: int, after_index: dict) -> None:
    after_canonicals = len(after_index["entries"])
    top_level = after_index["top_level"]
    subjects  = [e for e in top_level.values() if not e["is_authority"]]
    auths     = [e for e in top_level.values() if e["is_authority"]]

    print()
    print("=" * 60)
    print("CONSOLIDATION SUMMARY")
    print("=" * 60)
    print(f"  Unique canonicals before:  {before_canonicals:>6,}")
    print(f"  Merges applied:            {len(merge_map):>6,}")
    print(f"  Unique canonicals after:   {after_canonicals:>6,}")
    print()
    print(f"  Top-level entries:         {len(top_level):>6,}")
    print(f"    Authorities:             {len(auths):>6,}")
    print(f"    Subject topics:          {len(subjects):>6,}")
    print()
    print("TOP 30 SUBJECT ENTRIES BY TRACTATE BREADTH (after consolidation):")
    print(f"  {'CANONICAL':<52} {'DAFS':>5}  {'TRACTS':>6}  {'SUBS':>5}")
    print(f"  {'-'*52} {'-----':>5}  {'------':>6}  {'----':>5}")
    top30 = sorted(subjects, key=lambda e: (-e["tractate_count"], -e["daf_count"]))[:30]
    for e in top30:
        print(f"  {e['canonical'][:52]:<52} {e['daf_count']:>5}  {e['tractate_count']:>6}  {len(e['subentries']):>5}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Consolidate duplicate canonicals in topic_mapping.json")
    parser.add_argument("--input",      default="./topic_analysis/topic_mapping.json")
    parser.add_argument("--raw-topics", default="./topic_analysis/topics_raw.json",
                        help="topics_raw.json from extract_topics.py (for occurrence data)")
    parser.add_argument("--out-dir",    default="./topic_analysis")
    parser.add_argument("--resume",     metavar="BATCH_ID")
    parser.add_argument("--dry-run",    action="store_true")
    parser.add_argument("--apply-only", action="store_true",
                        help="Skip batch submission; apply existing merge_map.json directly")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    state_file  = out_dir / ".consolidate_batch_state.json"
    merge_path  = out_dir / "merge_map.json"

    mapping_path = Path(args.input)
    if not mapping_path.exists():
        sys.exit(f"Input not found: {mapping_path}\nRun normalize_topics.py first.")

    raw_topics_path = Path(args.raw_topics)
    raw_topics = json.loads(raw_topics_path.read_text(encoding="utf-8")) if raw_topics_path.exists() else {}

    print(f"Loading {mapping_path}…")
    mapping = load_mapping(mapping_path)
    canonicals = extract_unique_canonicals(mapping)
    print(f"  {len(mapping):,} raw terms → {len(canonicals):,} unique canonical forms")

    # ---- Apply-only mode ----
    if args.apply_only:
        if not merge_path.exists():
            sys.exit(f"--apply-only requires {merge_path} to exist. Run without --apply-only first.")
        merge_map = json.loads(merge_path.read_text(encoding="utf-8"))
        print(f"Loaded existing merge_map.json ({len(merge_map):,} merges)")
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            sys.exit("ANTHROPIC_API_KEY not set")
        client = anthropic.Anthropic(api_key=api_key)

        chunks = chunk(canonicals, BATCH_SIZE)
        print(f"Will submit {len(chunks)} deduplication requests ({BATCH_SIZE} canonicals each)")

        # ---- Dry run ----
        if args.dry_run:
            sample = build_requests([chunks[0]])[0]
            print("\n--- SAMPLE REQUEST ---")
            print(f"  Terms in chunk: {len(chunks[0])}")
            print(sample["params"]["messages"][0]["content"][:600])
            print("…")
            n = len(canonicals)
            print(f"\nEst. input tokens:  ~{n * 12:,}  (~${n * 12 * 0.000000025:.3f})")
            print(f"Est. output tokens: ~{len(chunks) * 300:,}  (~${len(chunks) * 300 * 0.000000125:.3f})")
            return

        # ---- Determine batch ID ----
        if args.resume:
            batch_id = args.resume
            print(f"Resuming batch {batch_id}")
        elif state_file.exists():
            saved = json.loads(state_file.read_text())
            batch_id = saved["batch_id"]
            print(f"Found existing batch state: {batch_id}")
        else:
            requests_list = build_requests(chunks)
            batch_id = submit_batch(client, requests_list, state_file)

        print("Polling for completion…")
        poll_until_done(client, batch_id)

        print("Collecting results…")
        groups = parse_merge_groups(client, batch_id)

        print("Building merge map…")
        merge_map = build_merge_map(groups, set(canonicals))
        write_merge_map(merge_map, merge_path)

    # ---- Apply merges ----
    print("Applying merge map to topic mapping…")
    consolidated = apply_merge_map(mapping, merge_map)
    write_consolidated_mapping(consolidated, out_dir / "consolidated_mapping.json")

    # ---- Rebuild index ----
    print("Rebuilding index with aggregated counts…")
    index = build_index(consolidated, raw_topics)
    write_index(index, out_dir / "consolidated_index.json")

    # ---- Report ----
    before_index = build_index(mapping, raw_topics)
    write_report(
        merge_map,
        before_index["entries"],
        index["entries"],
        out_dir / "consolidation_report.tsv",
    )

    print_stats(merge_map, len(canonicals), index)

    # Clean up state so a fresh run starts clean
    if state_file.exists():
        state_file.unlink()
        print(f"\n(Deleted batch state file — next run will start fresh)")


if __name__ == "__main__":
    main()
