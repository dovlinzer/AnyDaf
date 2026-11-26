# Narration: the 2-minute cut (calm120)

Record each line as its own file, named by its id (`title.m4a`, `f1.m4a`, `s1.m4a` … `end.m4a`). A scene too short for its line slows down to fit, but the Features cards (the `f` lines) don't stretch: they last about 2 seconds, so say those briskly, or leave them out and the cards run silent. Read the end line slowly, a beat between the words, as they appear one by one.

- **title**: This is iTalmud: the Illustrated Talmud.
- **f1** (Features card): Study outline.
- **s1** (outline): Every daf comes with a study outline. Open a section to see its steps, and insights from the shiur.
- **s2** (summary): At the end, a summary of the whole daf, each point linked back to its section.
- **f2** (Features card): Charts and illustrations.
- **s3** (chart): Charts set the cases side by side, with an icon for every ruling.
- **s4** (illustration): Illustrations draw each case, and how each opinion rules on it.
- **f3** (Features card): Terms, sages, measures.
- **s5** (reference): Tap a key term for its definition, or a measure to see it on a scale.
- **s6** (sages): Tap a sage to meet him, and explore his teachers and students.
- **f4** (Features card): Quizzes and games.
- **s7** (quiz): Test yourself with a quiz on every daf. Each answer links to its place on the daf.
- **s8** (fill in the chart): Or rebuild a chart: drag each card to its place.
- **f5** (Features card): Hyperlinks.
- **s9** (links in the margin): Every line links to its sources: the verse in Tanakh, the parallels in Shas, the Rambam and the Shulchan Arukh. Each one opens right on the page.
- **s10** (daf page): On the daf page too, with the sources in the margin. Tap a passage, and the outline goes there.
- **f6** (Features card): Word definitions.
- **s11** (words): And every word opens to its meaning, and its dictionary entry: Jastrow for the Gemara, and for a verse, Brown-Driver-Briggs.
- **end**: The Talmud. Explicated. Annotated. Illustrated. italmud dot com.

Then:

```bash
python3 voice/import.py <folder> --edit calm120
```

```bash
npm run rendercalmv
```
