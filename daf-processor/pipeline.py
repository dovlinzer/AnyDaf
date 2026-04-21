import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Tuple

import anthropic

from config import (
    SEGMENTATION_MODEL, REWRITE_MODEL, SOURCE_INSERTION_MODEL,
    SEGMENTATION_MAX_TOKENS, REWRITE_MAX_TOKENS, SOURCE_INSERTION_MAX_TOKENS,
    BATCH_POLL_INTERVAL, BATCH_TIMEOUT, DEFAULT_WORKERS,
)
from prompts import segmentation_prompt, rewrite_prompt, source_insertion_prompt
from sefaria import fetch_daf_text, fetch_daf_tail, fetch_daf_head, identify_daf  # noqa: F401
from srt_parser import parse_srt, srt_to_timestamped_text, srt_to_text

logger = logging.getLogger(__name__)


def _ts_to_seconds(ts: str) -> float:
    """Convert 'MM:SS' timestamp to seconds."""
    parts = re.split(r':', ts.strip())
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except (ValueError, IndexError):
        pass
    return 0.0


def _truncate_display_title(title: str, source_title: str = "") -> str:
    """Return a display_title of 25 chars or fewer."""
    dt = title or source_title
    if len(dt) > 25:
        dt = dt[:24].rstrip() + "…"
    return dt


def repair_segmentation(data: dict) -> dict:
    """
    Ensure macro and micro segments are in strict chronological order.

    Pass 1 — sort and re-anchor:
      1. Sorts micro-segments within each macro by timestamp.
      2. Re-anchors each macro's timestamp to its first micro.
      3. Sorts macro segments by corrected timestamp.

    Pass 2 — split non-contiguous macros:
      If a macro contains micros that overlap chronologically with the NEXT
      macro (i.e. Claude grouped non-contiguous audio thematically), split it
      at the boundary.  The later portion becomes a "<Title> (continued)"
      segment inserted at the correct chronological position.  Iterates until
      no overlaps remain.

    Pass 3 — enforce display_title length limit (25 chars).
    """
    macros = data.get("macro_segments", [])
    if not macros:
        return data

    # ── Pass 1: sort micros, re-anchor, sort macros ──────────────────────
    repaired = []
    for macro in macros:
        micros = macro.get("micro_segments", [])
        micros_sorted = sorted(micros, key=lambda m: _ts_to_seconds(m.get("timestamp", "0:00")))
        if micros_sorted:
            macro = dict(macro)
            macro["timestamp"] = micros_sorted[0]["timestamp"]
            macro["micro_segments"] = micros_sorted
        repaired.append(macro)

    repaired.sort(key=lambda m: _ts_to_seconds(m.get("timestamp", "0:00")))

    # ── Pass 2: iteratively split non-contiguous macros ──────────────────
    splits_made = 0
    for _ in range(20):   # safety cap — should converge in far fewer iterations
        overlap_found = False
        new_macros = []
        for i, macro in enumerate(repaired):
            micros = macro.get("micro_segments", [])
            # Determine the timestamp boundary imposed by the next macro
            if i + 1 < len(repaired):
                next_micros = repaired[i + 1].get("micro_segments", [])
                next_first_ts = _ts_to_seconds(
                    next_micros[0]["timestamp"] if next_micros
                    else repaired[i + 1].get("timestamp", "99:99")
                )
            else:
                next_first_ts = float("inf")

            # Find where this macro's micros spill past the next macro's start
            split_at = next(
                (j for j, m in enumerate(micros)
                 if _ts_to_seconds(m.get("timestamp", "0:00")) >= next_first_ts),
                None,
            )

            if split_at is not None and split_at > 0:
                # Keep the early portion; spin off the rest as a continuation
                early = micros[:split_at]
                late  = micros[split_at:]
                base_title = macro.get("title", "")
                cont_title = base_title + " (continued)"
                cont_dt    = _truncate_display_title(
                    (macro.get("display_title") or base_title)[:22].rstrip() + "…"
                )
                macro1 = {**macro, "micro_segments": early,
                          "timestamp": early[0]["timestamp"]}
                macro2 = {**macro, "title": cont_title, "display_title": cont_dt,
                          "micro_segments": late, "timestamp": late[0]["timestamp"]}
                new_macros.extend([macro1, macro2])
                overlap_found = True
                splits_made += 1
            else:
                new_macros.append(macro)

        # Re-sort after any splits
        repaired = sorted(new_macros,
                          key=lambda m: _ts_to_seconds(m.get("timestamp", "0:00")))
        if not overlap_found:
            break

    if splits_made:
        logger.info(f"  Segmentation: split {splits_made} non-contiguous macro(s) into "
                    f"'(continued)' segments to restore chronological order.")

    # ── Pass 3: enforce display_title length ─────────────────────────────
    for macro in repaired:
        macro["display_title"] = _truncate_display_title(
            macro.get("display_title") or macro.get("title", ""))
        for micro in macro.get("micro_segments", []):
            micro["display_title"] = _truncate_display_title(
                micro.get("display_title") or micro.get("title", ""))

    changed = repaired != macros
    if changed:
        logger.info("  Segmentation repaired (ordering or title length).")

    return {**data, "macro_segments": repaired}


def _repair_segmentation_text(text: str) -> str:
    """Parse, repair ordering, and re-serialise segmentation JSON text."""
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]
    try:
        data = json.loads(raw)
        data = repair_segmentation(data)
        return json.dumps(data, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        return text  # return original if unparseable; pipeline will log the error later


PASS_FILES = {
    1: '01_segmentation.json',
    2: '02_rewrite.md',
    3: '03_final.md',
}
PASS_MODELS = {
    1: SEGMENTATION_MODEL,
    2: REWRITE_MODEL,
    3: SOURCE_INSERTION_MODEL,
}
PASS_TOKENS = {
    1: SEGMENTATION_MAX_TOKENS,
    2: REWRITE_MAX_TOKENS,
    3: SOURCE_INSERTION_MAX_TOKENS,
}
PASS_NAMES = {1: 'Segmentation', 2: 'Rewrite', 3: 'Source Insertion'}


class Pipeline:
    def __init__(
        self,
        output_dir: Path,
        use_batch: bool = False,
        workers: int = DEFAULT_WORKERS,
        resume: bool = False,
        passes: str = 'all',
    ):
        self.output_dir = output_dir
        self.use_batch = use_batch
        self.workers = workers
        self.resume = resume
        self.passes = passes
        self.client = anthropic.Anthropic()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def process_files(
        self,
        srt_files: List[Path],
        masechta_override: Optional[str] = None,
        daf_override: Optional[int] = None,
        amud_override: Optional[str] = None,
    ):
        from sefaria import parse_filename  # local import to avoid circular

        jobs: List[Tuple[Path, str, int, Optional[str]]] = []
        for srt_file in srt_files:
            if masechta_override and daf_override:
                masechta, daf, amud = masechta_override, daf_override, amud_override
            else:
                result = identify_daf(srt_file)
                masechta = masechta_override or (result[0] if result else None)
                daf = daf_override or (result[1] if result else None)
                amud = amud_override if amud_override is not None else (result[2] if result else None)
            if masechta is None or daf is None:
                logger.warning(
                    f"Could not determine masechta/daf for {srt_file.name} "
                    f"(tried filename and SRT header). "
                    f"Use --masechta and --daf to override. Skipping."
                )
                continue
            jobs.append((srt_file, masechta, daf, amud))

        if not jobs:
            logger.error("No valid jobs found.")
            return

        mode = 'Batch API' if self.use_batch else f'direct API ({self.workers} workers)'
        logger.info(f"Processing {len(jobs)} daf(im) via {mode}")

        if self.use_batch:
            self._process_batch(jobs)
        else:
            self._process_direct(jobs)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _job_dir(self, masechta: str, daf: int, amud: Optional[str] = None) -> Path:
        key = f"{masechta.lower().replace(' ', '_')}_{daf}{amud or ''}"
        d = self.output_dir / key
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _is_done(self, job_dir: Path, pass_num: int) -> bool:
        return self.resume and (job_dir / PASS_FILES[pass_num]).exists()

    def _should_run(self, pass_num: int) -> bool:
        return self.passes == 'all' or self.passes == str(pass_num)

    def _get_sefaria(self, masechta: str, daf: int, job_dir: Path) -> str:
        cache = job_dir / 'sefaria.md'
        if cache.exists():
            return cache.read_text(encoding='utf-8')
        logger.info(f"  Fetching Sefaria text for {masechta} {daf}")
        text = fetch_daf_text(masechta, daf)
        cache.write_text(text, encoding='utf-8')
        return text

    def _get_sefaria_prev_tail(self, masechta: str, daf: int, job_dir: Path) -> Optional[str]:
        """Return the b-side of the preceding daf as context for pass 3."""
        prev_daf = daf - 1
        if prev_daf < 2:   # dafs start at 2; nothing before daf 2
            return None
        cache = job_dir / 'sefaria_prev.md'
        if cache.exists():
            return cache.read_text(encoding='utf-8')
        logger.info(f"  Fetching Sefaria tail for {masechta} {prev_daf} (preceding context)")
        text = fetch_daf_tail(masechta, prev_daf)
        if text:
            cache.write_text(text, encoding='utf-8')
        return text

    def _get_sefaria_next_head(self, masechta: str, daf: int, job_dir: Path) -> Optional[str]:
        """Return the a-side of the following daf as context for pass 3."""
        next_daf = daf + 1
        cache = job_dir / 'sefaria_next.md'
        if cache.exists():
            return cache.read_text(encoding='utf-8')
        logger.info(f"  Fetching Sefaria head for {masechta} {next_daf} (following context)")
        text = fetch_daf_head(masechta, next_daf)
        if text:
            cache.write_text(text, encoding='utf-8')
        return text

    def _build_prompt(
        self, srt_file: Path, masechta: str, daf: int, job_dir: Path, pass_num: int,
        amud: Optional[str] = None,
    ) -> Optional[str]:
        entries = parse_srt(srt_file.read_text(encoding='utf-8'))
        label = f"{masechta} {daf}{amud or ''}"

        if pass_num == 1:
            return segmentation_prompt(masechta, daf, srt_to_timestamped_text(entries), amud=amud)

        seg_file = job_dir / PASS_FILES[1]
        if pass_num == 2:
            if not seg_file.exists():
                logger.warning(f"  Pass 1 output missing for {label}; cannot build pass 2 prompt")
                return None
            return rewrite_prompt(masechta, daf, srt_to_text(entries),
                                  seg_file.read_text(encoding='utf-8'), amud=amud)

        rewrite_file = job_dir / PASS_FILES[2]
        if pass_num == 3:
            if not rewrite_file.exists():
                logger.warning(f"  Pass 2 output missing for {label}; cannot build pass 3 prompt")
                return None
            sefaria_text = self._get_sefaria(masechta, daf, job_dir)
            if sefaria_text.startswith('[Sefaria text not available'):
                logger.warning(f"  [{label}] Sefaria text unavailable; skipping pass 3")
                return None
            prev_tail = self._get_sefaria_prev_tail(masechta, daf, job_dir)
            next_head = self._get_sefaria_next_head(masechta, daf, job_dir)
            return source_insertion_prompt(
                masechta, daf,
                rewrite_file.read_text(encoding='utf-8'),
                sefaria_text,
                prev_daf_tail=prev_tail,
                next_daf_head=next_head,
                amud=amud,
            )

        return None

    # ------------------------------------------------------------------
    # Direct mode
    # ------------------------------------------------------------------

    def _process_direct(self, jobs: List[Tuple[Path, str, int, Optional[str]]]):
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {
                executor.submit(self._process_single, f, m, d, a): (m, d, a)
                for f, m, d, a in jobs
            }
            for future in as_completed(futures):
                masechta, daf, amud = futures[future]
                try:
                    future.result()
                except Exception as e:
                    label = f"{masechta} {daf}{amud or ''}"
                    logger.error(f"Failed {label}: {e}", exc_info=True)

    def _call_api(self, pass_num: int, prompt: str, label: str) -> Tuple[str, str]:
        """Call the API and return (text, stop_reason). Retries on overload/rate-limit and
        retries once more if pass 1 produces invalid JSON."""
        MAX_OVERLOAD_RETRIES = 5
        OVERLOAD_BACKOFF     = [10, 20, 40, 60, 120]   # seconds between retries

        max_attempts = 2 if pass_num == 1 else 1
        for attempt in range(1, max_attempts + 1):
            # Retry loop for transient API errors (overloaded, rate-limited)
            for overload_attempt in range(MAX_OVERLOAD_RETRIES):
                try:
                    with self.client.messages.stream(
                        model=PASS_MODELS[pass_num],
                        max_tokens=PASS_TOKENS[pass_num],
                        messages=[{"role": "user", "content": prompt}],
                    ) as stream:
                        text = stream.get_final_text()
                        stop_reason = stream.get_final_message().stop_reason
                    break   # success — exit the overload retry loop
                except anthropic.APIStatusError as e:
                    if e.status_code in (429, 529) and overload_attempt < MAX_OVERLOAD_RETRIES - 1:
                        wait = OVERLOAD_BACKOFF[overload_attempt]
                        logger.warning(
                            f"  [{label}] API overloaded/rate-limited "
                            f"(attempt {overload_attempt + 1}/{MAX_OVERLOAD_RETRIES}); "
                            f"retrying in {wait}s…"
                        )
                        time.sleep(wait)
                    else:
                        raise
            if pass_num == 1:
                text = _repair_segmentation_text(text)
                raw = text.strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
                try:
                    json.loads(raw)
                except json.JSONDecodeError as e:
                    if attempt < max_attempts:
                        logger.warning(
                            f"  [{label}] Pass 1 produced invalid JSON ({e}); retrying…"
                        )
                        continue
                    logger.warning(
                        f"  [{label}] Pass 1 produced invalid JSON after {max_attempts} attempt(s) — "
                        f"saved anyway. Run with --passes 1 --resume to retry later."
                    )
            return text, stop_reason
        return text, stop_reason  # unreachable but satisfies type checker

    def _process_single(self, srt_file: Path, masechta: str, daf: int, amud: Optional[str] = None):
        job_dir = self._job_dir(masechta, daf, amud)
        label = f"{masechta} {daf}{amud or ''}"
        logger.info(f"Starting {label}")

        for pass_num in (1, 2, 3):
            if not self._should_run(pass_num):
                continue
            out_file = job_dir / PASS_FILES[pass_num]
            if self._is_done(job_dir, pass_num):
                logger.info(f"  [{label}] Pass {pass_num} already done, skipping")
                continue
            prompt = self._build_prompt(srt_file, masechta, daf, job_dir, pass_num, amud=amud)
            if prompt is None:
                logger.warning(f"  [{label}] Cannot run pass {pass_num}; stopping here")
                break
            logger.info(f"  [{label}] Pass {pass_num}: {PASS_NAMES[pass_num]} ({PASS_MODELS[pass_num]})")
            text, stop_reason = self._call_api(pass_num, prompt, label)
            if stop_reason == "max_tokens":
                logger.warning(
                    f"  [{label}] Pass {pass_num} OUTPUT TRUNCATED — hit max_tokens "
                    f"({PASS_TOKENS[pass_num]}). Raise the limit in config.py."
                )
            out_file.write_text(text, encoding='utf-8')

        logger.info(f"Done: {label} → {job_dir}")

    # ------------------------------------------------------------------
    # Batch mode
    # ------------------------------------------------------------------

    def _process_batch(self, jobs: List[Tuple[Path, str, int, Optional[str]]]):
        for pass_num in (1, 2, 3):
            if not self._should_run(pass_num):
                continue
            self._run_batch_phase(jobs, pass_num)

    def _run_batch_phase(self, jobs: List[Tuple[Path, str, int, Optional[str]]], pass_num: int):
        logger.info(f"Batch phase {pass_num}: {PASS_NAMES[pass_num]}")

        # Pre-fetch Sefaria for pass 3 (needed to build prompts)
        if pass_num == 3:
            for _, masechta, daf, amud in jobs:
                job_dir = self._job_dir(masechta, daf, amud)
                self._get_sefaria(masechta, daf, job_dir)
                self._get_sefaria_prev_tail(masechta, daf, job_dir)
                self._get_sefaria_next_head(masechta, daf, job_dir)

        # Build requests
        requests_list = []
        id_to_job = {}  # custom_id → (masechta, daf, amud, job_dir)

        for srt_file, masechta, daf, amud in jobs:
            job_dir = self._job_dir(masechta, daf, amud)
            if self._is_done(job_dir, pass_num):
                label = f"{masechta} {daf}{amud or ''}"
                logger.info(f"  Skipping {label} pass {pass_num} (already done)")
                continue
            prompt = self._build_prompt(srt_file, masechta, daf, job_dir, pass_num, amud=amud)
            if prompt is None:
                continue
            custom_id = f"{masechta.lower().replace(' ', '_')}_{daf}{amud or ''}_p{pass_num}"
            requests_list.append({
                "custom_id": custom_id,
                "params": {
                    "model": PASS_MODELS[pass_num],
                    "max_tokens": PASS_TOKENS[pass_num],
                    "messages": [{"role": "user", "content": prompt}],
                },
            })
            id_to_job[custom_id] = (masechta, daf, amud, job_dir)

        if not requests_list:
            logger.info("  No jobs to submit for this phase.")
            return

        logger.info(f"  Submitting {len(requests_list)} request(s) to Batch API")
        batch = self.client.messages.batches.create(requests=requests_list)
        logger.info(f"  Batch ID: {batch.id}  (save this to resume if needed)")

        # Persist batch ID so user can recover if script is interrupted
        state_file = self.output_dir / f".batch_phase{pass_num}.json"
        state_file.write_text(
            json.dumps({"batch_id": batch.id, "jobs": {k: list(v[:3]) for k, v in id_to_job.items()}}),
            encoding='utf-8',
        )

        # Poll until done
        start = time.time()
        while True:
            batch = self.client.messages.batches.retrieve(batch.id)
            counts = batch.request_counts
            logger.info(
                f"  Status: {batch.processing_status} | "
                f"succeeded={counts.succeeded} processing={counts.processing} "
                f"errored={counts.errored}"
            )
            if batch.processing_status == 'ended':
                break
            if time.time() - start > BATCH_TIMEOUT:
                logger.error(
                    f"  Batch timed out after {BATCH_TIMEOUT}s. "
                    f"Batch ID saved to {state_file}. Rerun with --resume to pick up results."
                )
                return
            time.sleep(BATCH_POLL_INTERVAL)

        # Collect results
        succeeded = 0
        for result in self.client.messages.batches.results(batch.id):
            cid = result.custom_id
            if cid not in id_to_job:
                continue
            masechta, daf, amud, job_dir = id_to_job[cid]
            label = f"{masechta} {daf}{amud or ''}"
            if result.result.type == 'succeeded':
                out_file = job_dir / PASS_FILES[pass_num]
                msg = result.result.message
                if msg.stop_reason == "max_tokens":
                    logger.warning(
                        f"  {label} pass {pass_num} OUTPUT TRUNCATED — "
                        f"hit max_tokens ({PASS_TOKENS[pass_num]}). "
                        f"Raise the limit in config.py."
                    )
                text = msg.content[0].text
                if pass_num == 1:
                    text = _repair_segmentation_text(text)
                    raw = text.strip()
                    if raw.startswith("```"):
                        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
                    try:
                        json.loads(raw)
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"  {label} pass 1 produced invalid JSON ({e}). "
                            f"Re-run: python main.py <srt> --masechta {masechta} "
                            f"--daf {daf} --passes 1"
                        )
                out_file.write_text(text, encoding='utf-8')
                succeeded += 1
                logger.info(f"  ✓ {label}")
            else:
                logger.error(f"  ✗ {label}: {result.result.type}")

        logger.info(f"  Phase {pass_num} complete: {succeeded}/{len(requests_list)} succeeded")
