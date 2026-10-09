# Picture brief template (draft 2026-10-09)

One brief per mishnah. The picture is chosen to carry as much of the mishnah's teaching as one
image can, not to decorate. All words are added later as live text over the picture; the image
itself must contain NO text.

| Field | What goes in it |
|---|---|
| `teaching` | The mishnah's core teaching in one sentence (from Kulp; Kehati for layer 2). |
| `kind` | `case` (people in a situation), `sequence` (events in order), `object` (static things) or `list` (no scene). |
| `render` | `raster` (generated illustration), `svg` (diagram/table/timeline we draw), `both` (raster scene with SVG overlay), or `none`. |
| `scene` | Who is there, where, what is happening, time of day, mood. Names the cast members by their cast-sheet ID. |
| `stake` | What is in doubt or being decided, and how the picture shows it (side-by-side alternatives, a thought bubble with a "?", a ✓/✗ pair). Say what the image shows, not the words. |
| `must_show` | Elements that must be recognizable. |
| `avoid` | Anything that would mislead (wrong season, wrong garment, a detail the mishnah doesn't support). |
| `overlay` | The text labels to put on top, in English and Hebrew. |
| `source` | Where the content comes from (Kulp section, Kehati page). Anything not from a source is flagged. |

Style and cast come from `STYLE_BIBLE.md` (to be written after the pilot picks a direction).

## Rule: be specific, soften by style (added 2026-10-09)
The `scene` must state the facts the mishnah's case depends on: what happened, who is where, what state things are in (e.g. the cow was gored, the calf is dead). Specific prompts steer the image model better, and a scene that leaves out the case's facts cannot show the stake. Make it gentle through how things are drawn (closed eyes, stillness, no gore, smoke from a nostril), not by omission. Use `scene_teen` for a more graphic version where appropriate (e.g. a small red mark on the horns).

## Rule: check every detail for unintended causation (added 2026-10-09)
Before approving a scene, ask of each prop and pose: does it suggest a different cause or party than the mishnah says? (Example: a dropped basket would make the potter, not the cow, the cause of the broken pots in BK 5:2.)

## Rule: plain language (added 2026-10-09)
Every label, caption, symbol legend and outline line must use words a young reader would know; gloss or rephrase specialist terms (postscript, lien, libations, susceptible to impurity, defiles the hands). See STYLE_BIBLE.md.
