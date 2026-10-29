# Global glossary — plan (draft, 2026-10-18)

The goal: one glossary for all of Shas. Every legal category or principle has a single entry, with
one reviewed definition, and every mention of it on any daf links to that entry, whatever daf's
list it came from. Each daf adds a line on how the term is used there. The glossary becomes a
browsable index of Talmudic concepts in its own right: each entry lists the dafim where the concept
matters.

## Where we are

- Each outline lists its own key terms (now 6–12 per daf). A term links only once per daf, at its
  first mention.
- Since 2026-10-18 the site also links terms from the tractate's other dafim (`SHARED_TERMS` in
  `build_prototype.py`). This is a stopgap: it matches spellings exactly, has no sense control, and
  each daf's own draft definition is what the reader sees.
- `daf-processor/build_master_glossary.py` already clusters per-daf terms into a draft master list
  (`outline/glossary/master_draft.json`). It groups spellings by Hebrew skeleton and a folded
  transliteration, splits senses, and keeps every candidate definition with its daf.
- The schema for `glossary_entries` is sketched in `DESIGN.md`. The AskAnyDaf taxonomy (1,222
  entries) and the 28,982 canonical corpus terms are available as a seed.

## Data model

**`glossary_entries`**: one row per concept *in one sense* (`chatzer_acquisition` and
`chatzer_courtyard` are two entries).

| Field | Use |
|---|---|
| `id` | stable slug, e.g. `derara_demamona` |
| `term`, `hebrew` | standard transliteration (by the transliteration standard) and Hebrew |
| `variants` | every spelling seen (derara / drara de'mamona), for linking and search |
| `sense` | one line saying which meaning, when the word has several |
| `short` | one line for the hover / first glance |
| `definition` | the core definition: author-reviewed, or marked as a draft |
| `opposite`, `related` | ids (*mitztamek ve'yafeh lo* ↔ *ve'ra lo*; *bari* ↔ *shema*) |
| `taxonomy_id` | the AskAnyDaf topic, when confirmed |
| `he_term`, `he_short`, `he_definition` | for the Hebrew outlines |
| `status` | `draft` / `reviewed` / `published` |

**`daf_terms`**: one row per daf per entry. Fields: `daf_key`, `entry_id`, `on_this_daf` (how it
is used here), `sections`, and `listed` (true if the daf's own list chose it; false if it is only
mentioned there). The index of where a concept appears comes from these rows.

## How a term gets its entry

1. **Bootstrap (local, no API).** Cluster the terms of every outline we have into the master draft
   (the existing script, extended to newer outlines, which carry `key_terms` inside). For each
   entry, choose the best candidate definition as the draft. Seed from the taxonomy where it
   matches.
2. **In the outline pass.** The prompt gets a compact list of the master entries that matter for
   this daf: the tractate's entries, plus the most common core concepts across Shas (a few hundred
   lines of `id · term · sense`, cached). For each key term the model either reuses an entry's
   `id`, or proposes a new one (`"id": null`, with its definition). It always writes the daf-specific
   `on_this_daf` line. This keeps spelling and sense consistent from the start, instead of repairing
   them afterwards.
3. **After each batch,** the new terms are clustered against the master list. Exact or near
   matches attach automatically. Anything uncertain (a possible new sense of an existing word, two
   entries that may be one) goes on a review list for the author. This is the same rhythm as the
   tag questions.
4. **One small cleanup pass, when needed:** a cheap Sonnet batch that compares candidate merges
   ("are these the same concept in the same sense?") so the author reviews decisions, not raw lists.

## On the site

- **Linking.** Every mention of any master entry's variants links, on every daf. It still links
  once per daf, and never right after a negation. Homographs are the exception: a word with several
  senses (*chatzer*, *yad*) links only where the daf's own terms say which sense, so a reader
  never gets the wrong definition.
- **The definition shown** is the reviewed core definition, with "On this daf" underneath. An
  unreviewed entry shows its draft and says so.
- **A glossary page:** A–Z, by category (taxonomy), and search. Each entry lists the dafim where it
  matters and links to them. Later, it becomes the bridge to AskAnyDaf's topic browsing.
- **Hebrew outlines** use the same entries, with the Hebrew fields.

## Review (the author's part)

- Definitions are halakhic statements, so the author reviews the core ones. Order of review: by
  how often an entry appears. A few hundred entries probably cover most mentions in Shas; rarer
  entries can ship marked as drafts.
- A review page lists entries with their candidate definitions side by side, the dafim they came
  from, and Approve / Edit / Merge / Split. Decisions are saved to the database, not to files.

## Scale and cost (estimates)

- Shas at about 9 terms per daf is roughly 24,000 daf-term rows, which would collapse to perhaps
  2,500–4,000 entries.
- Linking in the outline pass adds only prompt tokens, a cached list of about 10–15K tokens, so a
  few cents per daf at most.
- Merge checks: a Sonnet batch, probably tens of dollars for all of Shas, run in pieces as batches
  come in.
- Hebrew definitions: one translation pass over reviewed entries only.

## Phases

1. **Bootstrap**: master draft from all current outlines, and a glossary page on the preview site
   reading it, with linking from it in place of `SHARED_TERMS`. Local, no API.
2. **Database**: `glossary_entries` + `daf_terms` in Supabase (DDL run by the author), loaded from
   the draft.
3. **Outline pass**: the master list goes into the prompt, and terms come back with ids. Test it in
   the next test run.
4. **Review tooling**: the review page above.
   Chapter glossaries with conceptual groups (see Decisions) come after the database.
5. **Full run**: the outline pass assigns ids as it goes, and each batch ends with the review list.

## Decisions (author, 2026-10-18)

- **Drafts may show**, marked as drafts. The author reviews the most common entries first.
- **Each daf's list stays its own** (the 6–12 terms the daf turns on). Other glossary terms link
  quietly where the daf mentions them, but stay off the list.
- **Words with several senses: one dictionary-style headword with numbered senses**, each opening
  with a short context label: *chatzer* (act of acquiring): …; *chatzer* (domain): … with its
  Eruvin and Bava Kamma implications (a cow entering my domain and eating my fruit). In both
  cases the word means courtyard; what differs is its legal import. Each daf links to the sense
  it uses. (Data model: `glossary_entries` stays one row per sense, sharing a `headword`; the page
  shows them together.)
- **No A–Z list of all of Shas** ("too overwhelming, and an A-to-Z list does no one any good").
  Instead, a **chapter glossary**: all the terms in one chapter, arranged in **conceptual groups**
  (Types of sanctity: *bedek ha'bayit*, *kedushat ha'guf*, *kedushat damim*…; Acts of taking
  possession: *kinyanim*…). Further on, **broader groupings across chapters** (e.g. the relevant
  terms of Bava Kamma 1–6 under "Nizkei Mamon"), not tied to a chapter range: major and minor
  divisions found by looking across all the terms. A project of its own; the taxonomy's
  categories may help seed the groups.
- **Possibly an A–Z sort as an option** (author, 2026-10-29): the conceptual groups stay the
  default, with a switch to show the same entries alphabetically, as the daf glossary's
  "As they appear / A–Z" switch does now.
