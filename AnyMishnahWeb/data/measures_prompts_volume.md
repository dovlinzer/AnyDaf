# Measure photos, volume family (log, kav, se'ah, ephah, kor): prompts for the author to run
Plan: the five measures are drawn in the box as the SAME vessel at different sizes (height in proportion to the cube root of the volume), so ONE good photo is enough: the code scales it for all five, adds the number on its face and sets the labels. Run each prompt in a fresh chat; pick the best look. Pure white background so the vessel can be placed on any card.
Note: nothing in the Mishnah or Kehati fixes the SHAPE of these vessels (only their sizes); the shape below is a plain, believable measuring vessel, not a claim about a particular ancient find.

## vol01-clay: one clay measure (option A)
PASTE:
```
A realistic studio photograph of one plain, unglazed terracotta measuring vessel, with no handles, no decoration and no writing or marks of any kind. It has a wide round opening and straight sides that taper gently toward a flat base, and it is a little taller than it is wide. The rim is plain and slightly thick. The vessel is empty and stands upright in the centre of the picture, photographed from slightly above so that the round opening shows as a shallow ellipse and the inside wall is just visible. Pure white seamless background, soft even light, a very faint shadow directly under the base, sharp focus. Exactly one vessel is in the picture, and nothing else.
```
Review: one vessel only; empty; no handle; no marks or text; straight tapering sides, wide mouth; pure white background; nothing else.
Overlay: the code scales it to five sizes and writes the numbers on it.

## vol02-wood: one wooden measure (option B)
PASTE:
```
A realistic studio photograph of one plain wooden measuring vessel made of pale wooden staves held by two simple dark metal bands, with no handles, no decoration and no writing or marks of any kind. It has a wide round opening and straight sides that taper gently toward a flat base, and it is a little taller than it is wide. The vessel is empty and stands upright in the centre of the picture, photographed from slightly above so that the round opening shows as a shallow ellipse and the inside wall is just visible. Pure white seamless background, soft even light, a very faint shadow directly under the base, sharp focus. Exactly one vessel is in the picture, and nothing else.
```
Review: one vessel only; empty; staves and two bands; no handle; no marks or text; pure white background; nothing else.
Overlay: the code scales it to five sizes and writes the numbers on it.

## vol03-grain (optional, for the dry-measure view later): the same clay vessel, filled with wheat
PASTE:
```
Using the previous picture as reference, everything is exactly the same except: the vessel is now filled to its rim with golden wheat kernels, with the surface of the grain level with the rim.
```
Review: same vessel; wheat to the rim, level; nothing else changed.
Overlay: used only if we show dry and liquid measures separately.

## UPDATE 2026-10-28 (author decisions)
- Vessel look: the clay vessel made for LIQUIDS (with a small pouring lip) is the one chosen. Small measures (revi'it, log) = that vessel with WINE in it. Large measures (kav, se'ah, ephah, kor), mostly dry = the same clay vessel WITHOUT the lip, filled with wheat. The author is running these.
- The box scales one photo per kind; the numbers on the vessels are drawn by the code.

# Money photos (new): one coin per metal, scaled by the code; the metal changes as you tap from unit to unit
Facts used: perutah copper (Davidson note on Kiddushin 1:1: a small copper coin); issar and the dinar/zuz, ma'ah, sela silver; gold dinar = 25 silver dinar (Bartenura on Bava Metzia 5:1; Rashi on Ketubot 93a). The Mishnah gives no coin design: the coins below are plain, with no portraits, no letters, no dates.

## mon01-copper: one copper coin
PASTE:
```
A realistic studio photograph of one ancient copper coin: a thin, flat, slightly irregular disc, only a few millimetres thick, with a flat face and a plain, gently rounded edge. There is no raised rim and no dish shape; the surface is flat all the way to the edge, with no portrait, no letters, no numbers and no pattern. It lies flat on the table, seen from directly above, in the centre of the picture. Pure white seamless background, soft even light, a very faint shadow under the coin, sharp focus. Exactly one coin is in the picture, and nothing else.
```
Review: one coin; copper colour; blank face; white background; nothing else.

## mon02-silver: one silver coin
PASTE:
```
A realistic studio photograph of one ancient silver coin: a thin, flat, slightly irregular disc, only a few millimetres thick, with a flat face and a plain, gently rounded edge. There is no raised rim and no dish shape; the surface is flat all the way to the edge, with no portrait, no letters, no numbers and no pattern. It lies flat on the table, seen from directly above, in the centre of the picture. Pure white seamless background, soft even light, a very faint shadow under the coin, sharp focus. Exactly one coin is in the picture, and nothing else.
```
Review: one coin; silver colour; blank face; white background; nothing else.

## mon03-gold: one gold coin
PASTE:
```
A realistic studio photograph of one ancient gold coin: a thin, flat, slightly irregular disc, only a few millimetres thick, with a flat face and a plain, gently rounded edge. There is no raised rim and no dish shape; the surface is flat all the way to the edge, with no portrait, no letters, no numbers and no pattern. It lies flat on the table, seen from directly above, in the centre of the picture. Pure white seamless background, soft even light, a very faint shadow under the coin, sharp focus. Exactly one coin is in the picture, and nothing else.
```
Review: one coin; gold colour; blank face; white background; nothing else.

## mon04-purse: a purse of silver coins (for the maneh = 100 dinar, a SUM of money)
PASTE:
```
A realistic studio photograph of one plain, small cloth purse of undyed linen, tied at the neck with a cord and full and heavy, with a few plain silver coins spilling out in front of it. No writing, no decoration. Pure white seamless background, soft even light, a faint shadow under it, sharp focus. Nothing else in the picture.
```
Review: one purse, tied; a few silver coins in front; no text; white background.

## REVISION 2026-10-28 (author): use real Temple-period coins as the basis
The author asked why we are not basing these on real coins. Better plan: use photographs of real coins of the period (the author has them), as either (a) the picture itself (cut out and cleaned like the vessels), or (b) a reference image for the generator: "Using the attached photograph of a real ancient coin as reference, make a studio photograph of the same coin, flat on a pure white background, seen from directly above, nothing else." Candidates, one per metal, to be confirmed by the author:
- copper: a bronze prutah of the Hasmonean or Herodian period;
- silver: a Tyrian silver coin (the shekel/tetradrachm, commonly identified with the sela, the Temple-tax coin) and a silver denarius (the dinar/zuz);
- gold: a Roman gold aureus (the gold dinar).
Rights: coins we own, or museum / Wikimedia Commons images whose licence allows reuse, with credit.

## REVISION 2026-10-28 (b): coin pictures as OUR OWN drawings based on the author's reference coins
The author's real-coin photographs are NOT used on the page (rights unclear); they were only cut out for a test and are kept in data/generated_originals/coins/ (and the cut-outs in data/generated_originals/coins/cutouts/). The page shows our own coin pictures; until they exist it falls back to simple drawn coins. Attach the named reference photograph to each prompt. Only the side WITHOUT a person's portrait.

## mon05-silver-ref: our silver coin (reference: the Tyrian silver coin, eagle side; attach 223.webp, right-hand coin)
PASTE (with the reference photograph attached):
```
Using the attached photograph of an ancient silver coin only as a reference for the general look, make a new, original studio photograph of one ancient silver coin showing just the side with the eagle. Do not copy the coin: draw your own eagle, standing upright with folded wings, in the same general style, slightly worn, on a thin, flat, slightly irregular silver disc only a few millimetres thick, with a flat face right to the edge and no raised rim. Leave out all lettering, numbers and inscriptions. The coin lies flat, seen from directly above, in the centre of the picture. Pure white seamless background, soft even light, a very faint shadow under the coin, sharp focus. Exactly one coin is in the picture, and nothing else.
```
Review: eagle side only; no letters; flat, no raised rim; silver; one coin; white background.

## mon06-gold-ref: our gold coin (reference: the gold coin with the jug on one side; attach 221.jpg, right-hand coin)
PASTE (with the reference photograph attached):
```
Using the attached photograph of an ancient gold coin only as a reference for the general look, make a new, original studio photograph of one ancient gold coin showing just the side with a tall, slender jug with a handle and a narrow neck, standing in the centre of the coin with a ring of small dots around the edge. Do not copy the coin: draw your own jug in the same general style, on a thin, flat, slightly irregular gold disc only a few millimetres thick, with a flat face right to the edge and no raised rim. Leave out all lettering, numbers and inscriptions. The coin lies flat, seen from directly above, in the centre of the picture. Pure white seamless background, soft even light, a very faint shadow under the coin, sharp focus. Exactly one coin is in the picture, and nothing else.
```
Review: jug side only; dotted ring; no letters; flat, no raised rim; gold; one coin; white background.

## mon07-copper-ref: our copper coin (reference: the bronze prutah with three ears of grain; attach 225.jpg, right-hand coin)
PASTE (with the reference photograph attached):
```
Using the attached photograph of a small ancient bronze coin only as a reference for the general look, make a new, original studio photograph of one small ancient copper coin showing just the side with three ears of grain tied together at the bottom, in the same general style. Do not copy the coin: draw your own. It is a small, thick-skinned, dark, slightly uneven and worn copper disc, thin and flat, with no raised rim. Leave out all lettering, numbers and inscriptions. The coin lies flat, seen from directly above, in the centre of the picture. Pure white seamless background, soft even light, a very faint shadow under the coin, sharp focus. Exactly one coin is in the picture, and nothing else.
```
Review: three ears of grain; no letters; flat, no raised rim; dark copper; one coin; white background.

## mon08-maneh-stack: the maneh, 25 sela
Two ways; the author chooses. (A) one picture of a stack; the generator is poor at counting, so check the layers. (B) one coin seen from the side that the code stacks 25 times, so the count is exact. (B) is recommended.

A. PASTE:
```
A realistic studio photograph of a neat, straight stack of exactly twenty-five identical ancient silver coins, one on top of another in a single upright column, seen from the side at eye level so that the thin edge of every coin shows as a separate layer, with the face of the top coin just visible from slightly above. All the coins are the same size. No lettering and no numbers. Pure white seamless background, soft even light, a very faint shadow at the base, sharp focus. Exactly one stack is in the picture, and nothing else.
```
Review: count the layers (25); one straight column; identical coins; white background.

B. PASTE:
```
A realistic studio photograph of one ancient silver coin standing on its edge and seen exactly from the side, so that it shows only as a thin, slightly irregular horizontal band, flat and straight, with a slightly rounded edge, a little worn. Seen at eye level, centred. Pure white seamless background, soft even light, no shadow, sharp focus. Exactly one coin is in the picture, and nothing else.
```
Review: a single thin horizontal band; silver; nothing else. (The code repeats it 25 times, with the top coin's face from the silver coin picture.)

# LENGTH AND AREA (added 2026-10-28)
The length and area boxes are live with simple drawn pictures (rulers; plowed squares). Photos to replace them:

## len01-forearm: one forearm and hand, for the amah, zeret, tefach and etzba
Plan: ONE photo of a bare forearm and open hand laid flat on white, elbow to fingertip. The code draws brackets on it for the etzba (one finger's width), the tefach (four fingers' width, the palm), the zeret (the span of the spread hand, thumb tip to little-finger tip) and the amah (elbow to the tip of the middle finger), at the proportions 1 : 4 : 12 : 24. Because the marks need exact positions, send the photo and I will place them.
PASTE:
```
A realistic studio photograph, seen from directly above, of a person's bare right forearm and hand laid flat and straight on a pure white surface, from the elbow to the fingertips, with the fingers together and straight and the palm facing down. Plain skin, no jewellery, no watch, no sleeve, no tattoo, no writing and no marks on the skin. The whole forearm and hand are in the picture and lie horizontally across the middle of it, with white space all around. Pure white seamless background, soft even light, a very faint shadow. Exactly one forearm and hand are in the picture, and nothing else.
```
Review: whole arm elbow to fingertips visible; fingers together; no jewellery or marks; one arm; white background.

## len02-spread-hand: the same hand with the fingers spread (the zeret)
PASTE (same chat as len01):
```
Using the previous picture as reference, everything is exactly the same except: the hand is now opened wide, with the thumb and little finger spread as far apart as they will go and the other fingers spread between them, palm still facing down.
```
Review: same arm and light; hand spread wide; one arm; white background.

## area01-plowed: a plowed field, to texture the squares of the beit se'ah and beit kor
PASTE:
```
A realistic photograph taken straight down from above of freshly plowed brown earth, with straight, parallel, evenly spaced furrows running from left to right across the whole picture. Dry, rich brown soil, a few small clods, no plants, no stones, no people, no animals, no tools, no fence, no edge of the field, no horizon. The furrows fill the whole picture right to its edges. Soft even daylight.
```
Review: furrows straight and parallel across the whole picture; only soil; no edges of the field; no objects.

## HAND ILLUSTRATION (optional, 2026-10-28): if our own simple drawn hands are not good enough
The page now draws the two hands itself as simple flat illustrations (no photograph). If you want a nicer illustration, run these and send them back (the brackets need exact positions, so I will place them):

## ill01-hand-closed
PASTE:
```
A simple, clean, flat illustration in the style of a friendly educational diagram: a bare right hand with the fingers held straight together and the thumb tucked alongside, seen from above with the palm facing up. The whole forearm is shown, running horizontally from the elbow at the far left, with the elbow fully inside the picture and a little white space to its left, to the fingertips at the right. Soft peach skin tone with two simple shading tones, a thin warm-brown outline, a few simple crease lines on the palm and finger joints. No jewellery, no watch, no sleeve, no text, no numbers. Plain white background, nothing else.
```
Review: fingers together and straight; thumb alongside; the whole forearm with the elbow visible at the left; flat illustration, not a photograph; white background. (With the elbow in the picture I can also bracket the amah.)

## ill02-hand-spread
PASTE (same chat):
```
Using the previous picture as reference, the same illustration style, skin tones and outline, except: the hand is opened wide with the thumb and the little finger spread as far apart as they will go and the other three fingers spread between them, palm facing down, still on the same whole forearm, elbow at the left.
```
Review: same style as the first; fingers and thumb fully spread; no extra items; white background.

# WEIGHTS AND DISTANCES: picture prompts (2026-10-28)

## wt01-weight: one ancient weight (the weight chart scales it for the dinar, sela and maneh)
PASTE:
```
A realistic studio photograph of one simple ancient stone weight: a smooth, slightly irregular, dome-shaped block of grey-brown limestone with a flat base and a small rounded knob on top for lifting. It is plain and unmarked: no letters, no numbers, no symbols and no engraving. It stands upright on its flat base in the centre of the picture, seen from the front at eye level so that its whole outline shows. Pure white seamless background, soft even light, a very faint shadow directly under the base, sharp focus. Exactly one weight is in the picture, and nothing else.
```
Review: one weight only; dome with a small knob; plain stone; no marks; flat base; white background.

## wt02-weight-bronze (alternative): the same weight in bronze
PASTE:
```
A realistic studio photograph of one simple ancient bronze weight: a smooth, slightly worn, dome-shaped metal block with a flat base and a small rounded knob on top. Dark golden-brown bronze with a soft green tint in the worn places. It is plain and unmarked: no letters, no numbers, no symbols and no engraving. It stands upright on its flat base in the centre of the picture, seen from the front at eye level. Pure white seamless background, soft even light, a very faint shadow directly under the base, sharp focus. Exactly one weight is in the picture, and nothing else.
```
Review: as above, in bronze.

## dist01-road: a road strip for the distance bars (mil and parsah; the code stretches it to length and repeats it)
PASTE:
```
A simple, clean, flat illustration in the same friendly educational style as a children's atlas, seen from straight above: one long, straight, even strip of packed light-brown earth road running left to right across the whole picture, filling its full width and about a third of its height, with a thin darker edge line along the top and the bottom of the road and a few small pebbles and wheel ruts. Nothing above or below the road strip except plain white. No people, no animals, no buildings, no signs, no text, no numbers.
```
Review: one straight horizontal road strip; even width; pebbles and ruts; plain white above and below; flat illustration.

## dist02-walker: a traveller, for the walking-time line
PASTE:
```
A simple, clean, flat illustration in the same friendly educational style as a children's atlas: one adult traveller seen from the side, walking to the right at an ordinary pace, wearing a plain tunic, a cloak and sandals and carrying a walking staff and a small bundle on one shoulder. Soft earth colours, a thin warm-brown outline. No text, no numbers. Plain white background, nothing else.
```
Review: one walker, side view, walking right; plain tunic; staff and bundle; flat illustration; white background.

# EATING SIZES: photo prompts (2026-10-28; real foods, so photographs)
The Eating sizes tab currently draws simple coloured shapes. Photos to replace them (the code scales each by its volume; only the shape matters). Pure white background, one item, no shadow patch.

## eat01-olive: one olive (zayit)
PASTE:
```
A realistic studio photograph of one single ripe green olive with a short piece of stem, lying on its side in the centre of the picture. No pit showing, no leaves, no oil, no bowl. Pure white seamless background, soft even light, a very faint shadow under it, sharp focus. Exactly one olive is in the picture, and nothing else.
```
Review: one olive; whole; plain white background.

## eat02-egg: one egg (beitzah)
PASTE:
```
A realistic studio photograph of one single plain white hen's egg standing upright on its wider end in the centre of the picture. No cracks, no carton, no basket, no straw. Pure white seamless background, soft even light, a very faint shadow under it, sharp focus. Exactly one egg is in the picture, and nothing else.
```
Review: one egg; upright; plain white background.

## eat03-fig: one dried fig (grogeret)
PASTE:
```
A realistic studio photograph of one single dried fig, flattened and wrinkled, light brown with a pale bloom on its skin and a small stem, lying in the centre of the picture. No bowl, no leaves, no other fruit. Pure white seamless background, soft even light, a very faint shadow under it, sharp focus. Exactly one dried fig is in the picture, and nothing else.
```
Review: one dried fig; wrinkled; white background.

## eat04-bread: a piece of bread (peras)
PASTE:
```
A realistic studio photograph of one single thick slice of plain round rustic bread, a wedge cut from a round loaf, golden-brown crust and soft crumb showing at the cut face, lying in the centre of the picture. No butter, no plate, no board, no knife. Pure white seamless background, soft even light, a very faint shadow under it, sharp focus. Exactly one piece of bread is in the picture, and nothing else.
```
Review: one piece of bread; crust and crumb; white background.

## ruler01-length: a plain ruler (Length tab bars)
Use: the bars for etzba, tefach, zeret and amah become pieces of this ruler, cut to length, so it must look right when stretched or cut anywhere along its length. No numbers, no labels; I draw the tick marks myself.
PASTE:
```
A realistic studio photograph of a plain straight wooden ruler lying flat, seen from directly above, perfectly horizontal, filling the picture from the left edge to the right edge so that both ends run off the frame. Light natural beech wood with fine straight grain, smooth edges, a thin darker line along its top edge. Completely blank: no numbers, no letters, no tick marks, no brand, no holes, no metal edge. Pure white seamless background, soft even light, no shadow at all, sharp focus. Exactly one ruler is in the picture, and nothing else.
```
Review: one blank wooden ruler; horizontal; runs off both sides; no marks; white background.

## eat05-kotevet: one large date (kotevet)
Use: the kotevet, the Yom Kippur eating amount; a large date, somewhat less than an egg. Cut out like the other eating photos.
PASTE:
```
A realistic studio photograph of one single large plump Medjool date, dark glossy brown with a lightly wrinkled skin and a small dry cap at the stem end, lying on its side in the centre of the picture. No pit showing, no bowl, no leaves, no other fruit. Pure white seamless background, soft even light, a very faint shadow under it, sharp focus. Exactly one date is in the picture, and nothing else.
```
Review: one large date; whole; plain white background.

## TO REVIEW (author, 2026-10-28): kotevet (a large date, somewhat less than an egg), grogeret, melo lugmav. Kotevet is not in the chart yet: it needs a size and a source.
