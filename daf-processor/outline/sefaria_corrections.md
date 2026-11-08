# Errors found in Sefaria's data, to report to Sefaria

One place for every error we find in Sefaria's texts, links and topics. Add to it as they turn up.
Our own translation choices (שוטה as "a person with psychosis", "question" for *ba'ya*) are not errors
and don't belong here.

## Topics: sages' Hebrew Wikipedia links (`heWikiLink`)

Fixed on our side in `sages_wiki.py` (`WIKI_TITLES`).

| Sefaria topic | Problem | Right page |
|---|---|---|
| rabban-gamliel / rabban-gamliel-b-rabbi-(iii) | The two links are swapped | רבן גמליאל דיבנה / רבן גמליאל ברבי |
| rabbi-mana-(i) (A2) | Linked to Rabbi Mana II's page (A5) | none found for Mana I; רבי מנא is Mana II |
| rabbi-chiyya-b-abba | Linked to the tanna R. Chiyya | רבי חייא בר אבא |

Not yet sorted: about 25 more entries in `WIKI_TITLES` (Rav Kahana I–IV, Ravin, Rav Acha, R. Ilai II and
others) were matched by hand on 2026-10-29. For each, check whether Sefaria's link is wrong or just
missing before reporting it.

## Texts

- **Nazir 33b**: empty in Sefaria's Bavli (`Nazir 33b` has no segments).

## Links (export of 2026-10-01; see `xrefs_coverage.md`)

- **Bava Kamma 3a**: the Ein Mishpat and Mesoret HaShas links are off by one line (they fit line N+1).
- **51 links** name a line past the end of their amud.
- **Sukkah**: Ein Mishpat links are labelled `ein mishpat`; every other tractate uses
  `ein mishpat / ner mitsvah`.
- **417 links** are anchored to the whole amud rather than a line. This is only a gap in precision, so
  it is low priority.

## Ein Mishpat / Mesoret HaShas / verse citations with wrong numbers

Sefaria's text (and Wikisource's) misreads Rashi-script numerals: for example ח read as א, as in
Bava Metzia 2a:2, which cites Rambam טוען ונטען 9:1 when the right reference is 9:8.
Found by `check_xrefs.py` and judged by `judge_xrefs.py` (2026-11-02). The model's first count, 1,083
references, is **not reliable**: it judged each reference against the whole Gemara line, and on lines with two
notes many "corrections" were the line's other note. Rechecked against Wikisource's Ein Mishpat notes
(`recheck_xrefs.py`), 256 of the 694 Rambam/SA ones drop out. Still to be judged again with each note's word, and
confirmed by the author; confirmed ones go in `xref_check/corrections.json`.

Separately, `xref_check/disagreements.json` lists 336 Rambam/SA references where Sefaria's number differs from
Wikisource's by a possible misreading (e.g. Bava Batra 90a: Sefaria Mekhirah 14:1, Wikisource 14:9).

Rejudged with each note's letter and marked words (`rejudge_xrefs.py`, `xref_check/rejudged.json`): of 618
Rambam/SA references, 447 judged to need the other number, 137 kept as Sefaria has them, 34 neither/unsure. Not yet
confirmed by the author (sample page https://claude.ai/artifact/8tmKdHXQKDU9KWPtR9sYP6).

Also worth telling Sefaria: their Ein Mishpat links don't record the note letter or the word it marks, so a line
with several notes can't be told apart. Wikisource has both for 24 tractates.

Also found: in a sample of references the local check couldn't confirm, about 13% don't match their line.
These look like links attached to the wrong line, or (Semag) a different edition's numbering. The size of
this across Shas is not yet known.
