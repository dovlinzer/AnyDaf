"""Melakhot batches 3-4 (Shabbat 7:2, nos. 12-24: the Garment set) + 3 'modern look' comparison pictures. Kehati only (data/melakhot_kehati_notes.md).
Rules applied (STYLE_BIBLE): essence of each melakha shown; no expressions on single actions; setting changes stated; what is gone stated; complete counts;
each edit says where things end up; second stage = edit of the previous in the SAME chat."""
import sys; sys.path.insert(0, "scripts")
from graphic_novel_style import STYLE as GN
CLAY = ("Illustration for a children's and family Mishnah study site, in the style of hand-modelled plasticine clay figures with exaggerated expressive faces, fingerprint texture, "
        "soft studio lighting, 3:2 wide format. No letters or words anywhere in the image, and no numerals. Every figure has a full face with eyes, nose and mouth. "
        "Land of Israel, 1st-century setting, simple tunics, dresses and cloaks. The sky or backdrop fills the whole background; no white background. "
        "Draw ONLY the people, animals and objects named in the scene, and exactly the number named of each.")
CLAY_MODERN = CLAY.replace("Land of Israel, 1st-century setting, simple tunics, dresses and cloaks.", "Present-day setting, modern everyday clothes such as jeans, T-shirts and sweaters.")
U = "Using the previous picture as reference, everything is exactly the same except: "
W = "a woman in a rust-red dress with a white head covering"
B3 = [
 ("mel12-shearing", "12. Shearing (gozez tzemer) [FIRST of the Garment set; nos. 13-17 are edits in the SAME chat]",
  f"Scene: an open grassy hillside under a wide sky, in the morning. {W} kneels beside one white woolly sheep and cuts the wool from its side with a pair of hand shears. A thick, cream-coloured piece of fleece is coming away from the sheep's side and falls onto the grass, and the sheep's body under it is bare, smooth and pink-grey. Exactly one woman, one sheep and one pair of shears.",
  "ESSENCE: wool is cut off the animal. A bare patch on the sheep's side; the fleece falling away; shears in her hand; one woman, one sheep; no expression on the sheep."),
 ("mel13-bleaching", "13. Bleaching (melabno) [edit of 12, same chat]",
  U + "the sheep and the shears are gone, and the scene is now the yard of a house: a low mud-brick wall in the background and bare earth underfoot, with no hillside and no grass. The woman kneels beside a wide round clay basin of water, pressing a lump of wool down into the water with her two fists, and the water around the wool is cloudy grey. On the ground on her right lies a small heap of clean, bright white wool, and on her left lies a small heap of dull grey, dirty wool. Exactly one woman, one basin, one heap of clean white wool and one heap of dirty grey wool.",
  "ESSENCE: dirty wool is washed white. Grey heap (before) and white heap (after) both visible; wool in the water; no sheep, no shears, no grass."),
 ("mel14-hackling", "14. Hackling (menapetz) [edit of 13, same chat]",
  U + "the basin and the two heaps are gone. The woman sits on a low stool and holds a tangled, matted clump of white wool in her left hand, and draws a wooden comb with long iron teeth through it with her right hand. The wool that has already been combed hangs from the comb as soft, loose, fluffy, straight fibres. Exactly one woman, one stool, one clump of wool and one comb.",
  "ESSENCE: tangled wool becomes loose, fluffy, straight fibre. A matted clump (before) and combed fluffy wool (after) both visible; one comb; no basin."),
 ("mel15-dyeing", "15. Dyeing (tzove'a) [edit of 14, same chat]",
  U + "the stool and the comb are gone. The woman stands beside a large clay vat of deep blue dye and lifts a skein of wool out of it on a wooden stick; the skein is dripping and the wool is now a deep blue all through, and blue drops fall back into the vat. A second skein of undyed white wool hangs from a wooden pole beside the vat. Exactly one woman, one vat, one stick with a blue skein, and one white skein on a pole.",
  "ESSENCE: white wool becomes coloured. The blue skein (after) and the white skein (before) both visible; blue dye in the vat; no stool, no comb."),
 ("mel16-spinning", "16. Spinning (toveh) [edit of 15, same chat]",
  U + "the vat, the stick and both skeins are gone. The woman sits on a low stool and holds a bundle of loose, fluffy white wool on a stick (a distaff) in her left hand, and from it she draws out a single long, thin twisted thread, which runs down to a wooden spindle hanging from the end of the thread and spinning in the air. Exactly one woman, one stool, one distaff of wool and one spindle with its thread.",
  "ESSENCE: loose fluffy wool becomes one continuous twisted thread. The fluffy wool (before) and the thin thread to the spindle (after) both visible; no vat, no skeins."),
 ("mel17-warp", "17. Setting the warp (mesech) [edit of 16, same chat]",
  U + "the stool, the stick of wool and the spindle are gone, and the scene is now inside a plain mud-brick room, with a tall upright wooden loom frame standing in the middle of the floor. Dozens of white threads run straight down from the top bar to the bottom bar of the frame, side by side, parallel and pulled tight. The woman stands at the frame and draws one more thread taut over the top bar, gripping it in her two fists. Exactly one woman and one loom frame, with nothing woven yet: there is no cloth on the loom.",
  "ESSENCE: loose threads become a row of parallel, tight threads stretched on the frame. No cloth woven yet; one loom; no spindle, no stool."),
]
B4 = [
 ("mel18-heddles", "18. Two heddles (oseh shnei batei nirin) [edit of 17, same chat; FIRST of batch 4]. If you already ran the first version, run THIS as an edit of that result",
  U + "the two narrow heddle frames are now each filled with many thin upright cords side by side, and every cord has a tiny loop (an eye) in its middle. The white tight threads pass THROUGH these loops: the 1st, 3rd, 5th and every other odd thread passes through the loops of the front heddle frame, and the 2nd, 4th, 6th and every other even thread passes through the loops of the rear heddle frame. Each heddle frame holds half of the threads, and the threads run through the frames, not beside them. The loom is seen slightly from the side so that the front and rear heddle frames are both visible, one in front of the other. The woman is pushing one white thread through a loop of the rear heddle frame with her fingers. No cord hangs on the floor. Exactly one woman, one loom, two heddle frames.",
  "ESSENCE: the tight threads are threaded through the loops of two heddles, one half of the threads per heddle, so the halves can be lifted alternately. Threads visibly PASS THROUGH loops in the frames (not beside them); two frames one behind the other; she is threading one; no cloth yet; no loose cord on the floor."),
 ("mel18b-heddles-with-reference", "18 (ALTERNATIVE). Same, with a structure reference picture attached (use if the text-only version keeps failing)",
  U + "the two heddle frames are redrawn to match the structure shown in the second attached picture: two upright frames, each full of small loops, with alternate threads running through the loops of each frame. Use that picture for the STRUCTURE only: do not copy its style, layout, labels or any text, and keep the woman, the room and the clay look from the previous picture. Exactly one woman, one loom, two heddle frames.",
  "Attach one of your reference loom pictures as the second image. Check: our clay look and our woman; the structure matches; no text or labels from the reference."),
 ("mel19-weaving", "19. Weaving two threads (oreg shnei chutin) [edit of 18, same chat]",
  U + "the woman has just passed a thread across through the tight threads with her fingers, with the two heddle frames still in place, and at the bottom of the loom a small strip of woven cloth has begun, with exactly two cross-threads woven into it. Exactly one woman, one loom frame, two heddle frames and one small strip of cloth.",
  "ESSENCE: cross-threads are woven through the tight threads and cloth begins. Exactly two woven cross-threads visible; cross-thread passed by hand; the two heddle frames still in place."),
 ("mel20-dividing", "20. Dividing two threads (potze'a shnei chutin) [edit of 19, same chat]",
  U + "the shuttle is gone. The woman draws two cross-threads out of the strip of woven cloth with her fingers, and where they were there is now a visible gap in the cloth. The two loose threads hang from her fingers. Exactly one woman, one loom frame, one strip of cloth with a gap, and two loose threads.",
  "ESSENCE: two threads are taken out of the weave, leaving a gap. The two loose threads in her fingers; the gap visible in the cloth; nothing else in her hands."),
 ("mel21-tying", "21. Tying (koshair) [edit of 20, same chat]",
  U + "the loom frame and the strip of cloth are gone. The woman sits on a low stool with the ends of two thick threads in her hands, and has tied them together in a tight, firm knot in the middle. Exactly one woman, one stool and one tied knot joining the two threads.",
  "ESSENCE: two loose ends become one tied, firm knot. A visible knot joining two threads; no loom."),
 ("mel22-untying", "22. Untying (matir) [edit of 21, same chat]",
  U + "the knot is loose and coming undone: the woman draws the knot open with her fingers, and the two thread ends are slipping apart, with the loop of the knot open between her fingers. Exactly one woman, one stool and one loosening knot in two threads.",
  "ESSENCE: a knot becomes loose ends. The knot visibly open and the ends slipping apart; same stool."),
 ("mel23-sewing", "23. Sewing two stitches (tofer shtei tefirot) [edit of 22, same chat]",
  U + "the threads are gone. The woman sits on the stool with two flat pieces of plain cream cloth held together on her lap, and a needle with a thread passes through the cloth. Exactly two neat stitches in thread already join the two pieces along their edge, and she is drawing the needle through for the next stitch. Exactly one woman, one stool, two pieces of cloth, one needle and exactly two stitches.",
  "ESSENCE: two pieces of cloth are joined by stitches. Exactly two stitches visible joining them; needle and thread in her hand; no threads loose on the floor."),
 ("mel24-tearing", "24. Tearing in order to sew two stitches (koreah al menat litfor shtei tefirot) [edit of 23, same chat; last of the Garment set]",
  U + "the needle and the pieces of cloth are gone. The woman holds a single piece of cream cloth in her two fists, and has torn a long rip into the middle of it, with ragged edges, as she draws the cloth apart. A needle with a thread lies on her knee, ready to sew the tear closed. Exactly one woman, one stool, one torn piece of cloth and one needle with thread.",
  "ESSENCE: the cloth is torn (visible rip) in order to be sewn together again. A ripped cloth being pulled; a threaded needle ready on her knee; no stitches yet."),
]
MODERN = [
 ("mel15m-dyeing-modern", "15 (modern look). Dyeing (tzove'a): FRESH picture, not an edit",
  "Scene: a bright workshop with a plain white wall. A woman in jeans and a grey T-shirt stands beside a large steel pot of deep blue dye and lifts a skein of wool out of it on a wooden stick; the skein is dripping and the wool is a deep blue all through. A second skein of undyed white wool hangs on a pole beside the pot. Exactly one woman, one pot, one stick with a blue skein and one white skein on a pole.",
  "ESSENCE as no. 15; modern clothes and room for comparison with the 1st-century version."),
 ("mel16m-spinning-modern", "16 (modern look). Spinning (toveh): FRESH picture, not an edit",
  "Scene: a living room with a sofa in the background. A woman in jeans and a green sweater sits on a wooden chair and holds a bundle of loose, fluffy white wool in her left hand, and from it she draws out a single long, thin twisted thread, which runs down to a wooden spindle hanging from the end of the thread and spinning in the air. Exactly one woman, one chair, one bundle of wool and one spindle with its thread.",
  "ESSENCE as no. 16; modern look."),
 ("mel23m-sewing-modern", "23 (modern look). Sewing two stitches (tofer shtei tefirot): FRESH picture, not an edit",
  "Scene: a living room with a sofa in the background. A woman in jeans and a blue shirt sits in an armchair with two flat pieces of plain cream cloth held together on her lap, and a needle with a thread passes through the cloth. Exactly two neat stitches in thread already join the two pieces along their edge, and she is drawing the needle through for the next stitch. Exactly one woman, one armchair, two pieces of cloth, one needle and exactly two stitches.",
  "ESSENCE as no. 23; modern look."),
]
def write(path, style, title, pics, head, note):
    out = [f"# Melakhot of Shabbat 7:2, {head}: {title} (2026-10-14)\n",
           "Sources: the mishnah (Shabbat 7:2) and Kehati only (own paraphrase: data/melakhot_kehati_notes.md). Rules (STYLE_BIBLE): the ESSENCE of each melakha must be visible (what differs before and after); no expression is described; one moment; every edit names what is gone, what changes setting, and complete counts.\n", note + "\n",
           "Library: save each accepted picture as data/generated_originals/concepts/melakhot/<id>.jpg.\n"]
    for i, (pid, h, scene, review) in enumerate(pics):
        first = scene.startswith("Scene:")
        body = (f"GENERAL STYLE (the same for every picture):\n{style}\n\nTHE SCENE TO DRAW:\n" + scene) if first else scene
        out.append(f"## {pid}: {h}\n\nPASTE:\n```\n{body}\n```\nReview: {review}\nOverlay: none (concept picture; reuse as a miniature badge).\n")
    open(path, "w").write("\n".join(out))
n3 = "How to use: paste no. 12 into a NEW Gemini chat, then nos. 13-17 one after another into that chat. Regenerate any that is wrong before the next edit."
n4 = "How to use: continue in the chat of no. 17 (or attach picture 17 and begin 'Using the attached picture as reference, everything is exactly the same except:'), then paste nos. 18-24 in order."
nm = "How to use: each is a NEW chat (fresh picture), clay only, to compare a present-day look with the 1st-century garment set."
write("data/melakhot_prompts_b3_clay.md", CLAY, "clay", B3, "batch 3 (Making a Garment, nos. 12-17)", n3)
write("data/melakhot_prompts_b3_graphic-novel.md", GN, "graphic novel", B3, "batch 3 (Making a Garment, nos. 12-17)", n3)
write("data/melakhot_prompts_b4_clay.md", CLAY, "clay", B4, "batch 4 (Making a Garment, nos. 18-24)", n4)
write("data/melakhot_prompts_b4_graphic-novel.md", GN, "graphic novel", B4, "batch 4 (Making a Garment, nos. 18-24)", n4)
# Modern-look comparison tried and rejected by the author (2026-10-14); kept above only for the record. Not written out.
