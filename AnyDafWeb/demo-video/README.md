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
