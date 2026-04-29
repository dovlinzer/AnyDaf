#!/usr/bin/env python3
"""
normalize_topics.py — Phase 1 of the Talmud topical index build.

Reads the raw term list from extract_topics.py output and uses the Anthropic
Messages Batch API to normalize every term into:
  - canonical:     standardized spelling/form
  - parent:        canonical name of the parent topic, or null for main entries
  - is_authority:  true for named sages/rishonim/acharonim (always main entries)

Output (all in --out-dir):
  topic_mapping.json       {raw_term → {canonical, parent, is_authority}}
  topic_index_draft.json   hierarchical index: main entries → subentries → occurrences
  topic_mapping.tsv        TSV for human review in Numbers/Excel

Usage:
  python3 normalize_topics.py
  python3 normalize_topics.py --input ./topic_analysis/topics_raw.json
  python3 normalize_topics.py --resume msgbatch_abc123   # pick up existing batch
  python3 normalize_topics.py --dry-run                  # show batch plan, no submission

Requires ANTHROPIC_API_KEY (from .env or environment).
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

BATCH_SIZE      = 100          # terms per Batch API request
MODEL           = "claude-haiku-4-5-20251001"
MAX_TOKENS      = 8192         # Haiku's output ceiling; 100 terms × ~55 tokens ≈ 5500
POLL_INTERVAL   = 30           # seconds between batch status polls
BATCH_TIMEOUT   = 3600 * 4    # 4 hours max wait

SYSTEM_PROMPT = """\
You are a Talmud scholar building a formal scholarly index — like the index in a major \
reference work — of topics discussed across the entire Talmud.

You will receive a list of raw terms extracted from daf yomi lecture transcripts. \
Each term is a topic tag that was attached to one or more moments in a lecture. \
Your job is to normalize each term into a clean, consistent index entry.

Return ONLY a JSON array with one object per input term, in the same order. \
No markdown, no explanation, no wrapper object — just the raw JSON array.
"""

USER_PROMPT_TEMPLATE = """\
Normalize each of the following {n} terms. For each, return:

  "raw":          the original term (copy exactly, character-for-character)
  "canonical":    the normalized index entry form (see rules below)
  "parent":       the canonical form of the parent topic if this is a subentry; \
otherwise null
  "is_authority": true if this is primarily a named scholar/sage, false otherwise

RULES FOR canonical:
1. SPELLING — pick the most widely recognized English transliteration. \
   Capitalize first letters of proper nouns. E.g.: "Kavana" not "Kavanah" or "kawana".
2. GLOSS — include a brief English gloss in parentheses for Hebrew/Aramaic terms \
   that are not widely known in English. E.g.: "Shechita (ritual slaughter)". \
   Omit the gloss for terms that are already in English or are well-known proper names.
3. FORMAT — main entries use the form "Concept (gloss)" or just "Concept" if \
   no gloss is needed. Subentries use the form "...in [context]" as a display hint \
   (e.g., "Kavana in prayer"), but the actual canonical form should still be readable \
   on its own (e.g., "Kavana in prayer (intention in prayer)").
4. MAIN vs. SUBENTRY — a term is a SUBENTRY (needs a parent) when it is a specific \
   application, context, or facet of a broader concept that also appears (or should \
   appear) in the index. Examples:
     "Kavana for korbanot"  → parent: "Kavana (intention)"
     "Mitasek in Shabbat"   → parent: "Mitasek (unintentional action)"
     "Mi-d'oraita obligation" → main entry (not a subentry of "Torah law")
   A term is a MAIN ENTRY (parent: null) when:
     - It is a named sage, rishon, or acharon (ALWAYS main entry)
     - It is a well-defined halachic category, concept, or topic in its own right
     - It is tractate-specific but stands alone (e.g., "Yayin Nesech")
5. AUTHORITIES — Rabbi X, Rav X, Rashi, Tosafot, Rambam, Ramban, Rashba, Rif, \
   Ran, Tur, Shulchan Aruch, Rav Soloveitchik, etc. are ALWAYS main entries. \
   "Tosafot interpretation" and "Rashi's view" normalize to "Tosafot" and "Rashi".
6. CONSISTENCY — if two terms in this list are the same concept with different \
   phrasing or spelling, give them the SAME canonical form.

Terms:
{terms_json}
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_raw_terms(input_path: Path) -> list[str]:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    terms = sorted(data.keys(), key=str.lower)
    print(f"Loaded {len(terms):,} unique raw terms from {input_path}")
    return terms


def chunk(lst: list, size: int) -> list[list]:
    return [lst[i:i + size] for i in range(0, len(lst), size)]


def build_requests(term_chunks: list[list[str]]) -> list[dict]:
    reqs = []
    for i, terms in enumerate(term_chunks):
        terms_json = json.dumps(terms, ensure_ascii=False, indent=2)
        user_msg = USER_PROMPT_TEMPLATE.format(n=len(terms), terms_json=terms_json)
        reqs.append({
            "custom_id": f"chunk_{i:04d}",
            "params": {
                "model": MODEL,
                "max_tokens": MAX_TOKENS,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_msg}],
            },
        })
    return reqs


# ---------------------------------------------------------------------------
# Batch submission + polling
# ---------------------------------------------------------------------------

def submit_batch(client: anthropic.Anthropic, requests: list[dict], state_file: Path) -> str:
    print(f"Submitting {len(requests)} requests to Anthropic Batch API…")
    batch = client.messages.batches.create(requests=requests)
    print(f"  Batch ID: {batch.id}  (saved to {state_file})")
    state_file.write_text(json.dumps({"batch_id": batch.id}), encoding="utf-8")
    return batch.id


def poll_until_done(client: anthropic.Anthropic, batch_id: str) -> None:
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
            sys.exit(f"Timed out waiting for batch {batch_id}. Re-run with --resume {batch_id}")
        time.sleep(POLL_INTERVAL)


# ---------------------------------------------------------------------------
# Result parsing
# ---------------------------------------------------------------------------

def parse_batch_results(client: anthropic.Anthropic, batch_id: str) -> dict[str, dict]:
    """
    Returns {raw_term → {canonical, parent, is_authority}}.
    Terms whose batch request errored or produced unparseable output are omitted
    (they'll be absent from the mapping and flagged in the summary).
    """
    mapping: dict[str, dict] = {}
    errors = 0

    for result in client.messages.batches.results(batch_id):
        if result.result.type != "succeeded":
            errors += 1
            print(f"  Request {result.custom_id} failed: {result.result.type}")
            continue

        msg = result.result.message
        if msg.stop_reason == "max_tokens":
            errors += 1
            print(f"  TRUNCATED {result.custom_id}: hit max_tokens — raise MAX_TOKENS or lower BATCH_SIZE")
            continue

        raw_text = msg.content[0].text.strip()

        # Strip accidental markdown fences
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            entries = json.loads(raw_text)
        except json.JSONDecodeError as e:
            errors += 1
            print(f"  JSON parse error in {result.custom_id}: {e}")
            print(f"  Raw text (first 200 chars): {raw_text[:200]}")
            continue

        if not isinstance(entries, list):
            errors += 1
            print(f"  {result.custom_id}: expected list, got {type(entries)}")
            continue

        for entry in entries:
            raw = entry.get("raw", "").strip()
            canonical = (entry.get("canonical") or "").strip()
            if not raw or not canonical:
                continue
            mapping[raw] = {
                "canonical":    canonical,
                "parent":       entry.get("parent") or None,
                "is_authority": bool(entry.get("is_authority", False)),
            }

    print(f"Parsed {len(mapping):,} term mappings ({errors} batch errors)")
    return mapping


# ---------------------------------------------------------------------------
# Build hierarchical index
# ---------------------------------------------------------------------------

def build_index(mapping: dict[str, dict], raw_topics: dict) -> dict:
    """
    Assemble a hierarchical index:
      {
        canonical: {
          "parent": str|null,
          "is_authority": bool,
          "raw_terms": [str, ...],        # all raw terms that map here
          "daf_count": int,
          "tractate_count": int,
          "tractates": [str, ...],
          "subentries": {canonical: {...}},
          "occurrences": [{tractate, daf, timestamps}, ...],
        }
      }
    Two levels only: main entries and their subentries.
    Deeper nesting is left for human review.
    """
    # canonical → aggregated entry
    entries: dict[str, dict] = {}

    def get_or_create(canonical: str, parent: str | None, is_auth: bool) -> dict:
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
        canonical   = norm["canonical"]
        parent      = norm["parent"]
        is_auth     = norm["is_authority"]

        entry = get_or_create(canonical, parent, is_auth)
        entry["raw_terms"].append(raw_term)

        # Carry over occurrence data from the raw topics
        if raw_term in raw_topics:
            entry["occurrences"].extend(raw_topics[raw_term]["occurrences"])

        # Ensure parent entry exists
        if parent:
            get_or_create(parent, None, False)

    # Wire subentries
    for canonical, entry in entries.items():
        parent = entry["parent"]
        if parent and parent in entries:
            entries[parent]["subentries"][canonical] = entry

    # Compute aggregate stats per entry
    for entry in entries.values():
        tractates = sorted({o["tractate"] for o in entry["occurrences"]})
        entry["daf_count"]      = len(entry["occurrences"])
        entry["tractate_count"] = len(tractates)
        entry["tractates"]      = tractates

    # Top-level = entries with no parent, sorted: authorities first (alpha), then subjects (breadth → alpha)
    top_level = {
        k: v for k, v in entries.items()
        if not v["parent"] or v["parent"] not in entries
    }
    return {
        "entries":   entries,
        "top_level": top_level,
    }


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_mapping(mapping: dict, path: Path) -> None:
    path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {path}  ({len(mapping):,} entries)")


def write_index(index: dict, path: Path) -> None:
    # Write a compact version (no occurrences) for easy browsing
    def slim(entry: dict) -> dict:
        return {
            "canonical":      entry["canonical"],
            "parent":         entry["parent"],
            "is_authority":   entry["is_authority"],
            "daf_count":      entry["daf_count"],
            "tractate_count": entry["tractate_count"],
            "tractates":      entry["tractates"],
            "raw_terms":      entry["raw_terms"],
            "subentries":     {k: slim(v) for k, v in entry["subentries"].items()},
        }

    top = sorted(
        index["top_level"].values(),
        key=lambda e: (not e["is_authority"], -e["tractate_count"], -e["daf_count"], e["canonical"].lower()),
    )
    out = [slim(e) for e in top]
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {path}  ({len(out):,} top-level entries)")


def write_tsv(mapping: dict, raw_topics: dict, path: Path) -> None:
    lines = ["raw_term\tcanonical\tparent\tis_authority\tdaf_count\ttractates"]
    for raw, norm in sorted(mapping.items(), key=lambda kv: kv[1]["canonical"].lower()):
        info = raw_topics.get(raw, {})
        tractates = ", ".join(info.get("tractates", []))
        lines.append("\t".join([
            raw,
            norm["canonical"],
            norm["parent"] or "",
            "yes" if norm["is_authority"] else "",
            str(info.get("daf_count", "")),
            tractates,
        ]))
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {path}")


def print_index_stats(index: dict) -> None:
    entries   = index["entries"]
    top_level = index["top_level"]
    subentries = {k: v for k, v in entries.items() if v["parent"] and v["parent"] in entries}

    authorities = [e for e in top_level.values() if e["is_authority"]]
    subjects    = [e for e in top_level.values() if not e["is_authority"]]

    print()
    print("=" * 60)
    print("INDEX STRUCTURE SUMMARY")
    print("=" * 60)
    print(f"  Total canonical entries:  {len(entries):>6,}")
    print(f"  Top-level main entries:   {len(top_level):>6,}")
    print(f"    — Authorities:          {len(authorities):>6,}")
    print(f"    — Subject topics:       {len(subjects):>6,}")
    print(f"  Subentries:               {len(subentries):>6,}")
    print()

    shas_wide   = [e for e in subjects if e["tractate_count"] >= 10]
    multi       = [e for e in subjects if 2 <= e["tractate_count"] < 10]
    single      = [e for e in subjects if e["tractate_count"] == 1]
    print(f"  Subject main entries by tractate breadth:")
    print(f"    Shas-wide (10+):  {len(shas_wide):,}")
    print(f"    Multi (2–9):      {len(multi):,}")
    print(f"    Single-tractate:  {len(single):,}")
    print()

    print("SAMPLE TOP-LEVEL SUBJECT ENTRIES (first 20 by breadth):")
    print(f"  {'CANONICAL':<50} {'DAFS':>5}  {'TRACTATES':>5}  {'SUBS':>5}")
    print(f"  {'-'*50} {'-----':>5}  {'---------':>5}  {'----':>5}")
    shown = sorted(subjects, key=lambda e: (-e["tractate_count"], -e["daf_count"]))[:20]
    for e in shown:
        n_subs = len(e["subentries"])
        print(f"  {e['canonical'][:50]:<50} {e['daf_count']:>5}  {e['tractate_count']:>5}  {n_subs:>5}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize raw topic terms via Anthropic Batch API")
    parser.add_argument("--input", default="./topic_analysis/topics_raw.json",
                        help="Path to topics_raw.json from extract_topics.py")
    parser.add_argument("--out-dir", default="./topic_analysis")
    parser.add_argument("--resume", metavar="BATCH_ID",
                        help="Skip submission and collect results from an existing batch")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show batch plan and prompt sample; do not submit")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    state_file = out_dir / ".normalize_batch_state.json"

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("Error: ANTHROPIC_API_KEY not set (add to .env or environment)")
    client = anthropic.Anthropic(api_key=api_key)

    input_path = Path(args.input)
    if not input_path.exists():
        sys.exit(f"Input file not found: {input_path}\nRun extract_topics.py first.")

    raw_topics: dict = json.loads(input_path.read_text(encoding="utf-8"))
    terms = sorted(raw_topics.keys(), key=str.lower)
    print(f"Loaded {len(terms):,} unique raw terms")

    term_chunks = chunk(terms, BATCH_SIZE)
    print(f"Will submit {len(term_chunks)} batch requests ({BATCH_SIZE} terms each)")

    # ---- Dry run ----
    if args.dry_run:
        sample_req = build_requests([term_chunks[0]])[0]
        print("\n--- SAMPLE REQUEST (chunk 0) ---")
        print(f"  Model:      {MODEL}")
        print(f"  Max tokens: {MAX_TOKENS}")
        print(f"  Terms:      {len(term_chunks[0])}")
        print("\n--- USER PROMPT SAMPLE ---")
        print(sample_req["params"]["messages"][0]["content"][:800])
        print("…")
        print(f"\nEstimated input tokens: ~{len(terms) * 15:,}  (~${len(terms) * 15 * 0.000000025:.2f} at Haiku pricing)")
        print(f"Estimated output tokens: ~{len(terms) * 25:,}  (~${len(terms) * 25 * 0.000000125:.2f})")
        return

    # ---- Determine batch ID ----
    batch_id: str
    if args.resume:
        batch_id = args.resume
        print(f"Resuming batch {batch_id}")
    elif state_file.exists():
        saved = json.loads(state_file.read_text())
        batch_id = saved["batch_id"]
        print(f"Found existing batch state: {batch_id}")
        print("  (use --resume <id> to explicitly resume, or delete .normalize_batch_state.json to start fresh)")
    else:
        requests_list = build_requests(term_chunks)
        batch_id = submit_batch(client, requests_list, state_file)

    # ---- Poll ----
    print("Polling for completion…")
    poll_until_done(client, batch_id)

    # ---- Collect results ----
    print("Collecting results…")
    mapping = parse_batch_results(client, batch_id)

    if not mapping:
        sys.exit("No results parsed — check batch errors above.")

    unmapped = [t for t in terms if t not in mapping]
    if unmapped:
        print(f"  {len(unmapped):,} terms had no mapping (batch errors). Writing anyway.")

    # ---- Write outputs ----
    write_mapping(mapping, out_dir / "topic_mapping.json")
    write_tsv(mapping, raw_topics, out_dir / "topic_mapping.tsv")

    print("Building hierarchical index…")
    index = build_index(mapping, raw_topics)
    write_index(index, out_dir / "topic_index_draft.json")

    print_index_stats(index)

    print()
    print("Next steps:")
    print("  1. Open topic_mapping.tsv in Numbers/Excel to spot-check normalization quality")
    print("  2. Review topic_index_draft.json for the proposed hierarchy")
    print("  3. Run build_index.py (coming next) to deduplicate canonical terms across batches")
    print("     and produce the final reviewable index")


if __name__ == "__main__":
    main()
