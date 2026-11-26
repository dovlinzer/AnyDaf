# iTalmud demo video

A 45-second demo of the Illustrated Talmud website (Bava Metzia 3, the example outline), in 16:9 and 9:16.

1. `node capture/scenes.mjs [1 2 3 4 5]` records the takes from the live site with Playwright (system Chrome,
   1600x900 at 2x, DevTools screencast -> `public/clips/s*.mp4`). A cursor is drawn into the page.
2. `src/cut.ts` is the edit: which stretches of each take play and how fast, the camera keyframes for each
   format (in the page's CSS pixels), and the captions. `src/Demo.tsx` draws it (title card, scenes, end card).
3. `npm run render:wide` / `npm run render:tall` -> `out/`. `npm run studio` to preview.

The 9:16 version is reframed from the same web takes (no phone recording). `capture/phone.mjs` records the
phone layout, unused. Takes, renders and stills are gitignored; re-record if the site changes.

## 90-second version
`node capture/scenes90.mjs [1-6]` records takes L1-L6 (L6 is Hullin 88a's word lookups); each take's click and scroll times go to `public/clips/<take>.marks.json`. The edit is `src/cut90.ts` (captions per segment); render with `npm run render90:wide` / `npm run render90:tall`.

## Narration
Script: `voice/SCRIPT.md` (from `voice/script.json`). The draft track is the Mac's voice; `python3 voice/import.py <folder>` brings in recordings named title, s1..s6, end (trims silence, evens loudness). `npm run render90v:wide` / `render90v:tall`; a scene too short for its line slows to fit (`fitToVoice` in src/cut.ts).

## Calm cuts (90 s, 60 s, three 30 s)

The first cuts played the takes at up to 3.6x. The calm cuts use one short take per feature, recorded slowly
(`capture/beats.mjs`: outline, summary, chart, illustration, reference, sages, quiz, fillchart, textsync,
linesync, dafpage, words) and played at 1.05x–1.25x, with one caption per feature.

    npm run beats          # record the takes, then gather their timings into src/beats.gen.json
    npm run rendercalm     # calm90, calm60, calm30study, calm30reference, calm30practice, each 16:9 and 9:16

Each take logs where the camera should look (`L.focus(...)`, saved as `<clip>.cam.json`); `src/calm.ts` turns
that into the camera (16:9 zooms in only on a small target; 9:16 stays at most 620 px wide so the text is
readable on a phone). The cuts are lists of beat names in `CALM` (`name@from-to` plays part of a take), so a
new cut is one line.

Narration for calm90: `voice/calm90/SCRIPT.md`. Record title, s1 … s10, end, then
`python3 voice/import.py <folder> --edit calm90` and `npm run rendercalmv`.
