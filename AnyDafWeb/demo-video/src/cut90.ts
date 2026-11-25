// The 90-second edit (takes L1-L6, recorded by capture/scenes90.mjs). Times are seconds of each take; the
// click and scroll times are logged beside each clip in public/clips/<take>.marks.json.
// Camera rows: [t, x, y, w] for 16:9 and [tx, ty, tw] for 9:16 (CSS pixels of the 1600x900 page).
import { Key, Scene } from "./cut";

type Row = [number, number, number, number, number, number, number];
const cam = (rows: Row[]) => ({
  wide: rows.map(([t, x, y, w]): Key => ({ t, x, y, w })),
  tall: rows.map(([t, , , , x, y, w]): Key => ({ t, x, y, w })),
});
const F = 1600;   // the whole page

export const SCENES90: Scene[] = [
  {
    clip: "L1_outline",
    kicker: "The study outline",
    caption: "Every daf, organized: a study outline from the first line to a summary at the end.",
    segs: [
      { from: 2.4, to: 9.6, rate: 1.8, note: "Each section opens to a summary, the steps of the sugya, and insights from the shiur." },
      { from: 12.3, to: 17.4, rate: 1.9, note: "Open everything at once, or one section at a time." },
      { from: 19.3, to: 27.0, rate: 1.9, note: "The daf summary gathers the takeaways and debates, each linked back to its section." },
    ],
    ...cam([
      [2.4, 800, 450, F, 300, 380, 620], [3.6, 480, 360, 980, 300, 420, 620], [10.2, 480, 360, 980, 300, 420, 620],
      [12.6, 800, 450, F, 300, 420, 620], [17.4, 800, 450, F, 300, 420, 620],
      [19.4, 800, 450, F, 300, 420, 620], [20.4, 470, 320, 980, 320, 330, 640], [24.4, 470, 320, 980, 320, 330, 640],
      [25.2, 520, 380, 1100, 320, 400, 640],
    ]),
  },
  {
    clip: "L2_visuals",
    kicker: "Charts & illustrations",
    caption: "The sugya at a glance: every case drawn, every ruling charted.",
    segs: [
      { from: 0.2, to: 10.2, rate: 1.95, note: "Charts set the cases side by side, with an icon for each ruling." },
      { from: 10.2, to: 18.5, rate: 1.95, note: "Illustrations show the case, then each opinion's ruling." },
      { from: 18.5, to: 24.0, rate: 1.95, note: "The storekeeper and the laborer: both swear and collect from the employer." },
    ],
    ...cam([
      [0.2, 470, 390, 1000, 463, 383, 870], [3.0, 470, 390, 1000, 463, 383, 870], [4.6, 650, 420, 820, 720, 400, 580],
      [8.6, 650, 420, 820, 720, 470, 580], [10.2, 470, 390, 1000, 476, 380, 750],
      [12.0, 480, 380, 900, 476, 380, 750], [15.6, 480, 420, 820, 476, 470, 620], [18.4, 480, 420, 820, 476, 470, 620],
      [20.0, 480, 400, 900, 476, 400, 750], [24.3, 480, 400, 880, 476, 400, 750],
    ]),
  },
  {
    clip: "L3_reference",
    kicker: "Terms, sages, measures",
    caption: "Every term, every sage, every measure, a tap away.",
    segs: [
      { from: 1.6, to: 6.4, rate: 1.7, note: "Tap a key term for its definition and where it comes up on the daf." },
      { from: 8.0, to: 12.9, rate: 1.9, note: "Tap a sage: who he was, his era, and where he speaks on the daf." },
      { from: 12.9, to: 30.2, rate: 2.1, note: "His teachers and students. Tap any of them and the diagram re-centres on that sage." },
      { from: 32.8, to: 39.9, rate: 1.7, note: "Weights, measures and coins, compared on one scale." },
    ],
    ...cam([
      [1.6, 600, 350, 1200, 300, 330, 600], [2.8, 560, 380, 1100, 215, 365, 440], [6.4, 560, 380, 1100, 215, 365, 440],
      [8.0, 600, 400, 1200, 300, 400, 600], [9.4, 560, 420, 1100, 305, 429, 600], [12.9, 560, 420, 1100, 305, 429, 600],
      [13.6, 800, 430, 1300, 800, 300, 720], [26.2, 800, 430, 1300, 800, 300, 720], [27.2, 800, 430, 1300, 560, 300, 640], [30.4, 800, 430, 1300, 560, 300, 640],
      [33.0, 600, 330, 1200, 480, 300, 820], [34.0, 520, 300, 1050, 480, 268, 820], [39.9, 520, 300, 1050, 480, 268, 820],
    ]),
  },
  {
    clip: "L4_games",
    kicker: "Quizzes & games",
    caption: "Quizzes and games on every daf.",
    segs: [
      { from: 1.8, to: 12.6, rate: 2.2, note: "A quiz on the daf's main points, with the reason for each answer." },
      { from: 12.6, to: 20.4, rate: 1.8, note: "Then see the answer in the outline, or on the daf itself." },
      { from: 22.0, to: 46.3, rate: 3.6, note: "Fill in the chart: drag each card to its place." },
      { from: 48.0, to: 60.4, rate: 2.2, note: "Term match: pair each term with its meaning." },
    ],
    ...cam([
      [1.8, 800, 450, F, 1380, 300, 600], [3.4, 1100, 420, 1150, 1207, 417, 680], [12.6, 1100, 420, 1150, 1207, 417, 680],
      [13.6, 800, 450, F, 330, 400, 680], [16.2, 800, 450, F, 330, 400, 680], [17.4, 900, 420, 1350, 1265, 420, 660], [20.4, 900, 420, 1350, 1265, 420, 660],
      [22.0, 700, 430, 1150, 613, 417, 680], [46.3, 700, 430, 1150, 613, 417, 680],
      [48.0, 700, 430, 1150, 613, 417, 680], [60.4, 700, 430, 1150, 613, 417, 680],
    ]),
  },
  {
    clip: "L5_sync",
    kicker: "Outline and Talmud in step",
    caption: "Outline and Talmud move together, on the text and on the daf.",
    segs: [
      { from: 2.0, to: 12.4, rate: 2.2, note: "Tap a section and the Gemara moves to it, in Hebrew, English or both." },
      { from: 13.8, to: 19.2, rate: 1.9, note: "Margin sources open in place: here the same case elsewhere in Shas." },
      { from: 19.4, to: 24.0, rate: 1.6, note: "Tap a line of Gemara and the outline moves to it." },
      { from: 23.6, to: 35.0, rate: 2.1, note: "On the daf itself, too, with the Rambam and Shulchan Arukh in the margin." },
    ],
    ...cam([
      [2.0, 800, 450, F, 300, 300, 600], [3.2, 800, 450, F, 300, 300, 600], [4.0, 800, 450, F, 1150, 450, 640], [13.4, 800, 450, F, 1150, 450, 640],
      [13.8, 800, 450, F, 1150, 450, 640], [15.4, 820, 450, 1300, 820, 420, 700], [19.4, 820, 450, 1300, 820, 420, 700],
      [20.4, 800, 450, F, 1150, 450, 640], [21.2, 800, 450, F, 330, 450, 640], [24.0, 800, 450, F, 330, 450, 640],
      [24.6, 1100, 470, 1150, 1265, 500, 660], [31.8, 1100, 470, 1150, 1265, 500, 660], [33.0, 800, 450, 1150, 800, 450, 680], [35.3, 800, 450, 1100, 800, 450, 680],
    ]),
  },
  {
    clip: "L6_words",
    kicker: "Every word",
    caption: "Tap any word for its meaning and its dictionary entry.",
    segs: [
      { from: 0.4, to: 16.0, rate: 1.95, note: "Right-click a line on the daf, then tap any word: its meaning, and Jastrow, Klein or BDB at the right sense." },
    ],
    ...cam([
      [0.4, 1100, 450, 1150, 1265, 450, 660], [3.4, 1100, 450, 1150, 1265, 450, 660], [4.4, 800, 450, 1100, 800, 330, 680],
      [6.6, 800, 450, 1100, 800, 330, 680], [7.6, 800, 520, 1000, 800, 560, 680], [16.0, 800, 520, 1000, 800, 560, 680],
    ]),
  },
];
