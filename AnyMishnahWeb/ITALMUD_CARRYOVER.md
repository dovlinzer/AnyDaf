# Decisions from Illustrated Mishna (AnyMishnahWeb) to carry over to iTalmud

NOTE (author, 2026-10-30): for iTalmud MOST of this does not apply. The audience is more advanced and the amount of text is large, so there is less need for technical-term treatment in the English; iTalmud already has glossary terms underlined and linked in its outline. What still applies is marked [iTALMUD] below. Everything else is Illustrated Mishna only (kept for reference).


A running list. Add to it whenever a decision here should also hold there. Newest at the bottom of each section. Dates are when the author decided.

## 1. Sources and licensing (2026-10-28) [iTALMUD]
- Explanatory content rests on the primary text and Kehati-type commentary only; no other commentator's content or wording. Never publish a copyrighted commentator's own wording: own paraphrase with citations.
- English translation from Sefaria's William Davidson Edition (Koren/Steinsaltz), CC BY-NC 4.0, credited on the page and in the footer. Kulp removed entirely.
- Davidson gaps (Mishnah): Zeraim except Berakhot, Taharot except Niddah, plus Eduyot, Avot, Middot, Kinnim. Candidate fillers (undecided): Sefaria Community (CC0), Silverstein (CC-BY), Open Mishnah (CC-BY-SA), 1843 "Eighteen Treatises" (public domain). Danby was NOT used (US copyright likely to 2029).
- Always read the commentary closely before writing any prompt or explanation (author rule, caps).

## 2. How the English is displayed (2026-10-30: the Smoothed/Davidson toggle was removed on Illustrated Mishna; smoothed only)
- ILLUSTRATED MISHNA ONLY: two modes with a toggle in the options bar (remembered per reader): SMOOTHED (default) and full DAVIDSON. The smoothed text is a fluent rendering written by Claude from the Hebrew plus the whole Davidson passage, as close as possible to the Hebrew and the amber words; labelled a Claude draft under review (field en_smooth; scripts/make_smooth_en.py). Only the smoothed text carries the glossary-term treatment (section 3).
- iTALMUD: NO smoothing (decided 2026-10-28; the whole Talmud is planned). The English is the full Davidson text, amber for the text's own words (the mishnah's, and in the Gemara the Talmud's) and grey for the editors' connecting explanation, as in AnyDaf/AnyTorah, uniformly for mishnah and Gemara.
- Both: one-line CC BY-NC credit under each English text, fuller credit in the footer. One stable English gloss per term (Davidson varies his phrasing).
- Open question for iTalmud: how the glossary-term treatment (section 3) applies inside the Davidson text, which is not ours to reword. Options: mark term occurrences by a word list (underline only, no rewording) so a click opens the same popup, or limit the term treatment to our own outlines, bullets and glossary.

## 3. Terminology rules
- Standing terminology: שוטה is always "a person with psychosis" (never imbecile/idiot/insane); applied to the Davidson text on fetch, to our text, bullets, charts, quiz. An ox that is a shoteh: "disoriented (shoteh)".
- Fixed compact pairs (BK): mazik = "damaging party", nizak = "damaged party"; tam = "harmless", mu'ad = "attested danger"; shor/bor/mav'eh/hev'er; avot nezikin = "primary causes of injury". Consistent transliteration spelling (mu'ad not muad).
- THREE KINDS OF TERMS in the translation:
  1. CORE terms (reused across a unit, one stable gloss): marked {{key}} in OUR OWN text (outlines, bullets; not in Davidson). First use in a unit/mishnah = pair (italic term + gloss in parentheses; order follows the reader's "Terms first: English / Hebrew" setting). Later uses = the bare term or gloss with a dotted underline (a key term, click for glossary).
  2. INCIDENTAL technical terms (a real technical term elsewhere in Shas, mentioned here in passing, e.g. me'ilah, yibbum, shekhiv me'ra): marked {{key|i}} (in our own text). ALWAYS English first with the term in parentheses and underlined, in either setting, so the page does not read too technical. Clicking opens the glossary entry.
  3. NOT terms: a phrase that only describes a principle in the text's own sentence and is never reused (e.g. hichsharti): plain English, and NOT in the glossary.
- Core set is per tractate/study unit (about 15), not for all of Shas; shared terms (shomer etc.) carry over.
- Grammar: handle articles and plurals of transliterated terms (a/an follows the displayed form; plural forms tamim/mu'adim).

## 4. Glossary [iTALMUD: master list across Shas; the popup and the locus field apply]
- Entry shape: id/key, term (English + transliteration), Hebrew, definition (own words, sourced), references, optional "locus".
- In iTalmud this becomes ONE MASTER glossary across Shas. Each entry has a field "Primary discussion: [Tractate X, ch. Y-Z] [Tractate A]" (locus list). The line is HIDDEN when the reader is already in that primary location (someone learning Me'ilah does not need "discussed in Me'ilah"). Wording of the line may still be improved.
- Incidental terms point the curious reader to where the primary discussion is.
- A glossary entry must say something substantive (the halakhic import, the definition, where it comes from). If an entry would only repeat the translation (ox, pit, fire as bare words) it gets NO link and no popup: a plain term (italic first use) at most. (2026-10-30)
- The "Primary discussion" line is shown for every entry that has one and always names the tractate (never "here"): "Bava Kamma", "Bava Kamma chs. 1-5", "Tractate Me'ilah". Its purpose is to tell the reader where the idea is discussed at greater length, NOT where the word occurs, so it is chosen by hand (editorial, not computed from word counts) and approved by the author. Supporting evidence comes from scanning our own Kehati-based outlines for where the concept is discussed (scripts/term_locations.py), never from general knowledge. It need not be precise (chapter level is enough). Each entry may add a short hand-written "why" after the location (e.g. "Defined in 1:4; how an ox stops being a tam in 2:4; half damages for a tam in 3:8, 4:1 and 5:1."), each claim checkable against our outlines (2026-10-30). (2026-10-30)
- Clicking the same term again closes its popup (on/off); Esc or a click elsewhere also closes it.
- A glossary term never jumps the reader to the bottom of the page: clicking it opens a small pop-up box next to the term (term, Hebrew, definition, primary location, close button). Esc or a click elsewhere closes it; keyboard accessible.

## 5. Pictures (clay / graphic-novel prompts)
- Standing rules are in STYLE_BIBLE.md (preflight before sending; injuries visible; no expressions on single-action shots; one picture one moment; say where things flow from and to with fixed left/right; change the setting when the stage happens elsewhere; remove what an earlier stage used up; show the ESSENCE of the thing, not just the farm act; balance men and women across a set; keep the 1st-century look).
- Key categories get named labelled boxes with the Hebrew name in italics and English in parentheses; versions of one category share one box in a fixed order of the authorities.
- Pictures library tagged by concept name for reuse as miniature badges.

## 6. Site behaviour worth reusing
- Quiz mode: dragged badge must always clear (pointer cancel, missed release, Escape, window blur, tab hidden); answer keys must never pass through the translation table (broke the Hebrew quiz).
- Captions hidden in Quiz mode only on pictures that have a quiz.
- Hebrew pages: written fresh in Hebrew (not translated), with the Hebrew mishnah column kept on the right; Steinsaltz biur with its own credit; drafts until the author reviews.
- Header: YCT logo and "Illustrated Mishna" at the upper left.

## 7. Credits (2026-10-30)
- Attribution is not repeated under every mishnah. One terse footer line per page ("English: smoothed by Claude from the William Davidson Edition (Koren), via Sefaria, CC BY-NC 4.0.") plus a "Sources and credits" link (banner and footer) that opens a small box with the full credits. [iTALMUD: same idea, once per page/site.]
- Illustrated Mishna: terms are underlined and linked in the mishnah text only; the outline keeps plain italic terms (both would be too busy).

## 8. Paragraphing the text (2026-10-30) [iTALMUD: may apply to long Gemara passages]
- Long mishnayot are split into paragraphs, Hebrew and English aligned (data fields he_p / en_p; scripts/make_paragraphs.py). Break where the text moves to a new case, a new ruling block, a new speaker/dispute; a case and its ruling stay together. Guide: the divisions of the Be'eri/Kaufmann edition on Sefaria (public domain) where it has them, plus judgement; Mishnah Sedura would be the better guide but is not available to us. Nothing reworded: the paragraphs must rejoin to the original text exactly.
- Glossary entries: first paragraph = the base translation/definition; a second paragraph = the implications. No "X follows" / "Kehati follows" attributions in entries, bullets, summaries or charts (author, 2026-10-30).

## 9. Terms and prepositions (2026-10-30) [iTALMUD: glossary]
- Glossary terms are keyed and shown without leading prepositions/articles (ב ל מ ו ה כ ש): meitav ha'aretz, not be-meitav; English gloss likewise bare.
- tam = "unattested danger", mu'ad = "attested danger" (never "harmless"); first gloss form "an ox that is a tam (unattested danger)".

## Paragraph rule (author, 2026-10-28)
Start a new paragraph whenever the speaker switches or a different tanna states a position ("They said to him", "He said to them", "Rabbi X says/said", "The Sages say"), in both English and Hebrew. Paragraph spacing is .25em. scripts/split_speakers.py applies this; use it for any new text.
