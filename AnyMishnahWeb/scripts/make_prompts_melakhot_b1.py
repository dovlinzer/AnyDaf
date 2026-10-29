"""Melakhot batch 1 (Shabbat 7:2, nos. 1-5: sowing, plowing, reaping, binding sheaves, threshing). Writes clay and graphic-novel prompt files.
Source for definitions: data/melakhot_kehati_notes.md (Kehati only). Each act after the first is an EDIT of the previous picture, in the SAME chat."""
import sys; sys.path.insert(0, "scripts")
from graphic_novel_style import STYLE as GN
CLAY = ("Illustration for a children's and family Mishnah study site, in the style of hand-modelled plasticine clay figures with exaggerated expressive faces, fingerprint texture, "
        "soft studio lighting, 3:2 wide format. No letters or words anywhere in the image, and no numerals. Every figure has a full face with eyes, nose and mouth. "
        "Land of Israel, 1st-century setting, simple tunics, dresses and cloaks. The sky or backdrop fills the whole background; no white background. "
        "Draw ONLY the people, animals and objects named in the scene, and exactly the number named of each.")
# One farmer in every picture of the Bread set.
F = "a farmer in an ochre tunic with a cloth headband"
PICS = [
 ("mel01-sowing", "1. Sowing (zore'a) [FIRST of the Bread set; nos. 2-5 are edits in the SAME chat]",
  f"Scene: the edge of a ploughed field under a wide sky, in the morning. {F}, walks across the soft brown furrows with his arm swung out wide, his open hand scattering a spray of seed that is falling onto the bare earth in front of him, a concentrating expression. A small cloth bag hangs at his hip. Exactly one farmer. The field is bare earth with no plants.",
  None, "the seed is in the air and landing on bare earth; his hand is open; bare field, no plants; one man."),
 ("mel02-plowing", "2. Plowing (choresh) [edit of 1, same chat]",
  "Using the previous picture as reference, everything is exactly the same except: the farmer now grips a wooden hoe in his fists, and the blade of the hoe is buried in the hard, unbroken ground in front of his feet, with clods of soil thrown up around it. A row of turned-over soil lies on the ground at his side. The hoe is a single piece, with its blade fixed on the end of the handle he is gripping. No seed is in the air and there is no bag at his hip. Exactly one farmer and one hoe.",
  None, "ONE hoe only, blade in the ground (no second blade or loose blade anywhere); soil thrown up; turned soil at his side; no seed, no bag."),
 ("mel03-reaping", "3. Reaping (koitzer) [edit of 2, same chat]",
  f"Using the previous picture as reference, everything is exactly the same except: the field is now full of tall ripe golden wheat, and the farmer, bent forward, holds a bundle of wheat in his left hand and draws a curved sickle through the stalks just below it with his right hand. The cut stalks are in his hand; the rest of the wheat stands uncut around him. He has a concentrating expression. There is no hoe. Exactly one farmer and one sickle.",
  None, "sickle in the stalks; stalks cut in his hand; standing wheat around; no hoe; one man."),
 ("mel04-binding", "4. Binding sheaves (me'amer) [edit of 3, same chat]",
  f"Using the previous picture as reference, everything is exactly the same except: the wheat around him is now cut and lies in rows on the ground, and the farmer kneels beside a thick armful of cut stalks, pulling a twisted strand of straw tight around the middle of it to bind it into one sheaf. He holds no sickle. Exactly one farmer and one sheaf being bound.",
  None, "one armful of cut stalks being tied round its middle with a strand of straw; cut wheat in rows; no sickle; one man."),
 ("mel05-threshing", "5. Threshing (dash) [edit of 4, same chat]",
  f"Using the previous picture as reference, everything is exactly the same except: the setting is a flat, bare circle of packed earth (a threshing floor) in the open, with open bare ground and sky all around it. No wheat is standing anywhere (the field has been reaped; only short stubble remains in the distance), and the only wheat in the picture is the spread-out stalks on the floor. The sheaf has been untied and spread out on the ground, and the farmer stands over it swinging a long wooden stick down onto the stalks. Golden kernels are springing loose and scattering across the earth around the stalks. Exactly one farmer and one stick.",
  None, "the stick comes down on spread stalks; kernels visibly loose on the floor; one man; no sheaf tied."),
]
def block(style, first):
    return f"GENERAL STYLE (the same for every picture):\n{style}\n\nTHE SCENE TO DRAW:\n" if first else ""
def write(path, style, title):
    out = [f"# Melakhot of Shabbat 7:2, batch 1 (Making Bread, nos. 1-5): {title} (2026-10-14)\n",
           "Sources: the mishnah (Shabbat 7:2) and Kehati only (own paraphrase: data/melakhot_kehati_notes.md). Rules applied (STYLE_BIBLE): one picture = one moment; the product is visible; nothing the source does not need (no animals, no extra tools); no expression is described (a single action needs none; neutral is safe); exact counts; edits in the SAME chat, each stating where things end up. Same farmer in every picture.\n",
           "How to use: paste no. 1 into a NEW Gemini chat; paste nos. 2-5 one after another into THAT chat. Review each before moving on; if one is wrong, regenerate it before the next edit.\n",
           "Library: save each accepted picture as data/generated_originals/concepts/melakhot/<id>.png (tag: *Hebrew name* (English name)).\n"]
    for i, (pid, head, scene, _, review) in enumerate(PICS):
        out.append(f"## {pid}: {head}\n\nPASTE:\n```")
        out.append((block(style, True) + scene) if i == 0 else scene)
        out.append(f"```\nReview: {review}\nOverlay: none (concept picture; reuse as a miniature badge).\n")
    open(path, "w").write("\n".join(out))
write("data/melakhot_prompts_b1_clay.md", CLAY, "clay")
write("data/melakhot_prompts_b1_graphic-novel.md", GN, "graphic novel")
