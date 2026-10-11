"""Bava Kamma 3, older audience, first-try test of the prompt lessons (2026-10-10). Scenes written from the mishnah text and R. Kulp's commentary only.
Run: python3 scripts/make_graphic_novel_prompts_bk3.py -> data/graphic-novel_prompts_bk3_v2.md"""
from graphic_novel_style import STYLE
P = [  # (id, title, kind, scene, review, overlay)
("bk3-1a", "3:1 a jug left in the road", "scene",
 "Scene: a dirt road through a small town, with stone houses on both sides. A man in a blue tunic has just tripped over a large clay jug that was standing in the road: he is sprawled on the road with one hand gripping his ankle, wincing. The jug lies cracked into three large pieces beside him, with a dark wet patch spreading across the stones. At the side of the road, a stocky woman with grey hair under a white head covering, in a brown dress and a cream apron, looks on with both hands raised to her head in dismay: she is the jug's owner. Exactly two people (a man and a woman) and one jug (broken).",
 "one man (tripper) and one woman (owner); jug in 3 pieces, only one jug; the tripper is hurt but there is no blood",
 "tripper -> pays nothing for the jug (exempt, 'notpay'); owner (the woman) -> pays for the injury ('pay')"),
("bk3-1b", "3:1 a jug breaks in the road", "scene",
 "Scene: a market lane between stone walls. A woman in a green dress with a white head covering stands holding only the handle of a broken jug; the rest of the jug lies in pieces at her feet, and water has spread across the stones in a wide puddle. A second man, in a yellow tunic, with a bald head, has slipped in the puddle and is falling backward, arms flung out, one foot in the air, with a look of alarm. Exactly two people. One jug, broken.",
 "one woman (green, owner) and one man (yellow, falling); one broken jug; the puddle is under the falling man",
 "jug owner (the woman in green) -> pays ('pay'). R. Judah's disagreement (only if on purpose) goes in the text, not the picture"),
("bk3-2a", "3:2 water poured into the street", "scene",
 "Scene: a narrow street of stone houses. A woman in a grey dress with a white head covering stands at her gate and tips a wooden bucket, so that a stream of water splashes onto the street. A passerby in a brown cloak, with a basket of bread on his head, has slipped on the wet stones: he is falling sideways, the basket tipping, his face startled. Exactly two people.",
 "one woman (pouring) and one man (passerby); water leaves the bucket and reaches the passerby's feet; one basket",
 "woman pouring -> pays ('pay')"),
("bk3-2b", "3:2 a thorn fence fallen across the path", "scene",
 "Scene: a country path beside a field. A fence made of thorn branches that ran along the edge of the field has fallen across the path, and thorns lie spread over the ground. A woman traveller in a blue cloak and a long dress has stepped into the thorns and is hopping on one foot, holding the other foot up with a pained face. The field's owner, a man in an olive tunic with a white beard, stands at the edge of his field with both hands on his head. Exactly two people.",
 "one woman (traveller) and one man (field owner); the fence is visibly down across the path (not standing); no blood",
 "field owner -> pays ('pay')"),
("bk3-3", "3:3 straw and stubble put out on the road", "scene",
 "Scene: the edge of a village road. A long low heap of straw and stubble lies along the road. A woman in a blue dress sits on the ground beside the heap, holding her sore foot with a wince. Next to him stands the man who put the heap there, in a brown tunic with a grey beard, shaking his head. A young woman in a yellow dress, smiling, is pitching straw from the heap into her own hand cart with a pitchfork. Exactly three people (one man, two women) and one hand cart.",
 "one man (owner, brown) and two women (injured, blue; young, yellow), all dressed differently; the young woman is taking the straw into HER cart; the sitting woman holds her foot",
 "owner (brown) -> pays for the injury ('pay'); young woman -> keeps the straw ('keeps')"),
("bk3-4", "3:4 two pot-sellers", "scene",
 "Scene: a path between two stone walls, seen from the side, with everyone moving toward the left of the picture. Two women pot-sellers each carry a wooden rack full of clay pots on her back. The first, ahead at the left, in a brown dress with a white head covering, has tripped and lies sprawled on the path. The second, behind her at the right, in a green dress with a red head covering, is tumbling forward over the first, arms out, her rack tipping so that pots spill. Several broken clay pots lie on the path. Exactly two women.",
 "exactly two women; the FIRST (left, brown) is on the ground and the SECOND (right, green) is falling onto her, not the other way round",
 "first woman (brown) -> pays ('pay')"),
("bk3-5s", "3:5 clause 1: the two men walk side by side (own picture, new chat; same people as 5a)", "scene",
 "Scene: a wide town street seen from the side, with both people walking toward the left of the picture, abreast of each other. The man nearer the viewer, in a brown tunic, carries a long wooden beam on his shoulder, the beam pointing forward past his shoulder. The woman beside him, farther from the viewer, in a blue dress with a white head covering, carries a large clay jar on her shoulder; the front end of the beam has knocked against the jar, which is cracking and dropping a shard. Both look surprised. Exactly one man and one woman, one beam, one jar.",
 "the man and the woman are level with each other, not one behind the other; the beam end touches the jar; same two outfits as 5a",
 "beam man -> exempt ('notpay'), the mishnah's ruling, confirmed by Kehati"),
("bk3-5a", "3:5 beam in front, jar behind: the jar breaks (FIRST of a set of three; make 5b and 5c in the SAME chat)", "scene",
 "Scene: a wide town street seen from the side, with both people walking toward the left of the picture. The first man, at the left, in a brown tunic, carries a long wooden beam horizontally on his shoulder; the rear end of the beam sticks out behind him. The second person, a woman behind him at the right, in a blue dress with a white head covering, carries a large clay jar on her shoulder and has walked into the rear end of the beam: the jar is cracking and a shard drops. The first man keeps walking, looking straight ahead, unaware. Exactly one man and one woman, one beam, one jar.",
 "beam man is AHEAD (left) and walking on; jar woman is BEHIND (right) and has walked into the beam's rear end; the jar is breaking",
 "beam man -> exempt ('notpay')"),
("bk3-5b", "3:5 the beam man stops suddenly (same chat, edit of 5a)", "edit",
 "Using the previous picture as reference, everything is exactly the same except: the first man (beam) has stopped walking, feet planted, with his head turned slightly back toward the woman with the jar in surprise and no gesture of warning; she has run into the rear end of the beam because he stopped; the jar is cracking.",
 "beam man standing still, no hand raised; same two people, same clothes",
 "beam man -> pays ('pay')"),
("bk3-5c", "3:5 the beam man stops and warns (same chat, edit of 5b)", "edit",
 "Using the previous picture as reference, everything is exactly the same except: the first man (beam) has turned back toward the woman with the jar, one hand raised, palm open, and his mouth open as if calling out a warning; the jar is still cracking.",
 "raised open palm, mouth open; no letters or words anywhere",
 "beam man -> exempt ('notpay')"),
("bk3-6", "3:6 a runner and a walker collide", "scene",
 "Scene: a town street. A woman in a purple dress who was running, her head covering loosened, and a man in a tan tunic who was walking have collided and both sit on the ground, dazed, each rubbing a sore elbow or knee. Exactly one woman and one man and nothing else on the street.",
 "one woman (purple, was running) and one man (tan, was walking), both on the ground, both hurt about equally",
 "each person -> pays nothing ('notpay'), two hotspots"),
("bk3-7", "3:7 a wood chip flies over a wall", "scene",
 "Scene: a courtyard with a low stone wall that opens onto a street. Inside the courtyard, a woman in a rust-coloured dress with rolled sleeves and a head covering has just split a log with an axe. A wooden chip has flown over the wall and struck a passerby in the street, a man in a blue cloak, who stands on the street side holding the side of his head with a pained expression. The chip lies at his feet. Exactly two people.",
 "woodcutter (a woman) inside the wall, passerby (a man) outside it; the chip is on the ground by the passerby; no blood",
 "woodcutter (the woman) -> pays ('pay')"),
("bk3-11a", "3:11 two oxen chase a third, two different owners (FIRST of a pair; make 11b in the SAME chat)", "scene",
 "Scene: an open pasture with a stone wall along one side. A small brown ox runs across the pasture, limping, with one front leg held up. A red ox and a black ox run after it, one close behind the other. Beside the wall stand three people. The owner of the red ox, a woman in a green dress with a white head covering, points at the black ox with a frown. The owner of the black ox, in a yellow tunic, with a bald head, points at the red ox with a frown. The owner of the small brown ox, a woman with grey hair in a blue dress, stands between them with open hands, puzzled. Exactly three oxen and exactly three people (two women and one man).",
 "three oxen (small brown limping, red, black), three people: woman in green, man in yellow, woman in blue; each of the two owners points at the OTHER owner's ox",
 "woman in green -> pays nothing ('notpay'); man in yellow -> pays nothing ('notpay')"),
("bk3-11b", "3:11 the same two oxen, one owner (same chat, edit of 11a)", "edit",
 "Using the previous picture as reference, everything is exactly the same except: the red ox and the black ox are now both owned by the woman in the green dress, who stands beside the wall with a worried face and one hand on her chin; the man in the yellow tunic is gone; the woman in the blue dress still stands with open hands, pointing now at the two oxen. Exactly three oxen and exactly two women.",
 "two women only (green, blue); the woman in green is next to the wall with both chasing oxen still running behind the limping one",
 "woman in green -> pays ('pay')"),
]

FIXES = [  # edits to send in the SAME chat as the picture they fix (first run of v2, 2026-10-11)
("bk3-11b", "fix: the limping small ox was dropped from 11b", "Using the previous picture as reference, everything is exactly the same except: add back the small brown ox. It runs across the pasture at the front, limping, with one front leg held up, and the red ox and the black ox run after it. The two women stand at the wall as before. Exactly three oxen (small brown, red, black) and exactly two women."),
("bk3-5s", "fix: the beam must touch the jar", "Using the previous picture as reference, everything is exactly the same except: the front tip of the beam presses against the neck of the jar, and the jar is cracking at that spot with shards falling."),
]
out = ["# Bava Kamma 3, graphic novel: first-try prompts v2 (men and women mixed on purpose) (2026-10-10)\n",
"Purpose: test whether the lessons from BK 5 / BM 1 give good pictures on the first try. Written from the mishnah text and R. Kulp's commentary only. Scenes: 3:1 to 3:7 and 3:11 (3:8, 3:9, 3:10 are about amounts and comparisons, left for a decision).\n",
"How to use: paste the block under PASTE into a new Gemini chat. Where it says 'same chat, edit', paste it into the chat that made the previous picture. 'Review' lists what to check before accepting; 'Overlay' says what we add in code.\n",
"CHANGE from v1: gender is now chosen on purpose in each scene (about half the main figures are women, in varied roles: pot-sellers, woodcutter, pourer, owners). Prompts that changed: 3:1a, 3:1b, 3:2a, 3:2b, 3:3, 3:4, 3:5 (all four), 3:6, 3:7, 3:11a, 3:11b; none is unchanged except the edit lines that never named a person.\n",
"Lessons applied: style block names no objects and carries a palette sentence; no standing negatives; the scene says what IS there (cracked into three pieces, hopping on one foot) not what is not; counts stated; every person has their own clothes; sets that change one fact are edits in the same chat; any left/right order is stated against a fixed direction of travel; no picture carries a quantity.\n",
"SOURCE NOTE: 3:5 clause 1 (side by side): R. Kulp's explanation says the beam owner is liable, which contradicts the mishnah text; the author checked and Kehati confirms the mishnah: he is EXEMPT. R. Kulp was wrong here. Kehati outranks R. Kulp wherever they differ.\n"]
for pid, title, kind, scene, review, overlay in P:
    full = ("GENERAL STYLE (the same for every picture):\n" + STYLE + "\n\nTHE SCENE TO DRAW:\n" + scene) if kind == "scene" else scene
    out.append(f"\n## {pid}: {title}\n\nPASTE:\n```\n{full}\n```\nReview: {review}.\nOverlay: {overlay}.\n")
out.append("\n# Fixes after the first run (send each as an edit in the SAME chat as the picture it fixes)\n")
for pid, title, text in FIXES: out.append(f"\n## {pid}: {title}\n\nPASTE:\n```\n{text}\n```\n")
open("data/graphic-novel_prompts_bk3_v2.md", "w").write("".join(out)); print(len(P), "prompts")
