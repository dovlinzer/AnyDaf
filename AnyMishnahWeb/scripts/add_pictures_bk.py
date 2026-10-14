"""Adds the clay picture lists (file, caption) to the layer1 files of Bava Kamma 1, 2, 4, 6 (2026-10-13).
Run AFTER write_bk_1_2.py, write_bk_4_6.py and add_charts_bk.py (they rewrite the layer1 files). Captions follow the mishnah/Kulp/Kehati outlines."""
import json
PICS = {1: {1: [("bk1-1a", "The ox: it drives its horn into a woman and throws her (the first of the four primary causes of injury)."),
                ("bk1-1a2", "The ox as Shmuel reads it: damage with its foot, as it walks."),
                ("bk1-1b", "The pit: an ox has fallen into a deep pit."),
                ("bk1-1c", "Fire: a fire has spread from where it was kindled into the wheat."),
                ("bk1-1d", "The crop-destroying beast (mav'eh), as Shmuel reads it: an animal that eats with its tooth."),
                ("bk1-1d2", "The mav'eh as Rav reads it: a person who damages.")],
           3: [("bk1-3", "The court: three judges, two witnesses, a woman who holds a broken jar and a man.")]},
        2: {1: [("bk2-1a", "The cow breaks the jar as it walks, with its foot: it is an attested danger and the owner pays full damages."),
                ("bk2-1b", "The cow kicks the jar: that is not the usual way, so the owner pays half damages.")],
            2: [("bk2-2a", "The cow eats fruit and vegetables: the owner pays full damages."),
                ("bk2-2b", "The cow eats a garment: the owner pays half damages."),
                ("bk2-2c", "In the public domain the owner is exempt, except for what the animal benefited.")],
            3: [("bk2-3a", "A dog that jumps from a roof and breaks jars is an attested danger: full damages."),
                ("bk2-3b", "A dog takes a cake with an ember, eats the cake and burns the stack: full damages for the cake, half for the stack.")],
            6: [("bk2-6", "A person is always an attested danger: the man who knocked over the jar in his sleep pays full damages.")]},
        4: {4: [("bk4-4a", "The ox of a boy gored the ox of a man of sound senses: exempt."),
                ("bk4-4b", "The ox of a man of sound senses gored the ox of a boy: he is obligated.")]},
        6: {1: [("bk6-1a", "The gate was properly shut and the pen was broken through at night: he is not liable."),
                ("bk6-1b", "The gate was not properly shut and the flock went out: he is liable.")],
            2: [("bk6-2a", "The flock fell into a garden: he pays only for the benefit."),
                ("bk6-2b", "The flock went down into the garden in its usual way: he pays for the damage.")],
            4: [("bk6-4a", "One brought the fire, then another added the wood: the one who added the wood is liable."),
                ("bk6-4b", "The fire grew and spread into the wheat."),
                ("bk6-4c", "One brought the wood, then another brought the fire: the one who brought the fire is liable."),
                ("bk6-4d", "The fire grew and spread into the wheat.")],
            6: [("bk6-6a", "The camel's flax caught fire from the shopkeeper's lamp inside the shop: the owner of the camel is liable."),
                ("bk6-6b", "The shopkeeper left his lamp outside: the shopkeeper is liable.")]}}
for c, byn in PICS.items():
    fn = f"data/bava_kamma_{c}_layer1.json"; d = json.load(open(fn))
    for m in d["mishnayot"]: m["pictures"] = [[f"{p}.jpg", cap] for p, cap in byn.get(m["n"], [])]
    json.dump(d, open(fn, "w"), ensure_ascii=False, indent=1); print(c, sum(len(v) for v in byn.values()))
