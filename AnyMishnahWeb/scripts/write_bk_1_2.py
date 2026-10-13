"""Layer 1 and chapter summaries for Bava Kamma 1 and 2 (2026-10-13). Sources: the mishnah (Sefaria), R. Kulp, Kehati (read pdf pp.1-21). No other sources."""
import json
def S(h, *items): return {"h": h, "b": [list(i) for i in items]}
L1 = {"tractate": "Bava Kamma", "chapter": 1, "status": "Draft from the mishnah, R. Kulp and Kehati (pages 1-21 of the scan).", "mishnayot": [
{"n": 1, "title": "The four primary causes of injury", "summary": "The Torah names four primary causes of injury: the ox, the pit, the crop-destroying beast and fire. Each has a feature the others lack, and what they share is that you are responsible to guard them.",
 "outline": [
  S("The four", ("The four primary causes of injury (avot nezikin) are the ox, the pit, the crop-destroying beast and fire.", "Mishnah 1:1"), ("Each comes from the Torah: the ox (Exodus 21:35-36), the pit (21:33-34), the crop-destroying beast (22:4) and fire (22:5).", "Kulp 1:1")),
  S("Why four?", ("The ox is not like the crop-destroying beast; neither is like fire, which is not alive; none of these, whose way is to go out and damage, is like the pit, whose way is not.", "Mishnah 1:1"), ("The Rabbis held that no law in the Torah is superfluous, so each case must teach something the others could not.", "Kulp 1:1")),
  S("What they share", ("It is their way to do injury, and you are responsible to guard them.", "Mishnah 1:1"), ("When one of them does injury, whoever is responsible pays from the best of his land.", "Mishnah 1:1")),
  S("Kehati's notes", ("The Gemara disputes what the four are. Rav says the mishnah names the main kinds of damage in the Torah (the ox covers horn, tooth and foot, the \"crop-destroying beast\" is a person who damages). Shmuel says it names only four kinds of property damage that are attested dangers from the start: the foot (\"ox\"), the tooth (\"crop-destroyer\", from a word meaning to bulge out), the pit and fire. Kehati explains the mishnah as Shmuel does, with Rambam and Bartenura.", "Kehati 1:1"))]},
{"n": 2, "title": "What I must guard, and for what damage I pay", "summary": "A person is liable for what he is bound to guard, even if he only partly caused the damage. Payment is only for property that is not sacred, belongs to Jews, is owned, and damaged outside the damager's own domain and the domain shared by both.",
 "outline": [
  S("The principle", ("Anything I am responsible to guard, I have rendered it possible to do injury (hichsharti).", "Mishnah 1:2"), ("If I partially rendered it possible, I pay as if I totally did.", "Mishnah 1:2"), ("Example: a pit that was already four feet deep, and a six foot pit would kill an animal; if I deepen it to six, I am liable as if I dug the whole pit.", "Kulp 1:2")),
  S("When the damager pays", ("The property damaged is not sacred (no \"sacrilege\", me'ilah), belongs to members of the covenant (Jews), and is owned.", "Mishnah 1:2"), ("The injury is done in any place other than the private domain of the damager and the domain shared by damager and damaged.", "Mishnah 1:2"), ("Payment is from the best of his land.", "Mishnah 1:2")),
  S("Kehati's notes", ("The partial case is clearer with Kehati's example: a pit of nine handbreadths that he deepened by one, to ten, so an animal that falls dies.", "Kehati 1:2"), ("The conditions: sacred property is excluded because the verse says \"his neighbour's ox\", not the Temple's; gentiles' property is covered in 4:3; ownerless property is excluded too.", "Kehati 1:2"))]},
{"n": 3, "title": "How damages are assessed", "summary": "Damages are assessed in money before a court, on the evidence of free Jewish witnesses. Women are included. The injured and the injurer can share the loss.",
 "outline": [
  S("The procedure", ("Assessment of the injury in money or things worth money is made before a court of law and by witnesses who are free and Children of the Covenant.", "Mishnah 1:3"), ("Two things are assessed: what the damaged animal was worth, and how large a piece of land the damager must give.", "Kulp 1:3")),
  S("Women", ("Women may be parties in suits concerning injury.", "Mishnah 1:3"), ("The Torah uses \"man\" in many of these verses, so one might have thought only men's damages count.", "Kulp 1:3"), ("Kehati: the Torah's law applies to women too, from the verse that follows the Sinai chapters, \"these are the laws that you shall set before them\" (Exodus 21:1).", "Kehati 1:3")),
  S("Sharing the compensation", ("The injured and the injurer may share in the compensation.", "Mishnah 1:3"), ("The clearest case is half damages: the owner of an ox not known to gore pays only half, so the injured owner bears the other half.", "Kulp 1:3")),
  S("Kehati's notes", ("The assessment is made only before a court of experts, not a lay court.", "Kehati 1:3"), ("The Gemara disputes whether the half damages of a harmless ox is money or a fine (Rav Pappa: money; Rav Huna: a fine).", "Kehati 1:3"))]},
{"n": 4, "title": "Harmless and attested dangers", "summary": "Five agents are harmless (tam) and five are attested dangers (mu'ad). A harmless one pays half damages from its own body; an attested danger pays full damages from the best property.",
 "outline": [
  S("Five harmless", ("An animal is not an attested danger to butt, push, bite, lie down or kick.", "Mishnah 1:4")),
  S("Five attested dangers", ("The tooth is an attested danger to eat what is fit for it; the leg to break as it walks; an ox that has been warned; an ox that damages in the domain of the damaged party; and human beings.", "Mishnah 1:4"), ("The wolf, lion, bear, leopard, panther and snake are attested dangers. Rabbi Eliezer: when tame they are not, but the snake always is.", "Mishnah 1:4")),
  S("The difference", ("The harmless pays half damages from its own body; the attested danger pays full damages from the best property.", "Mishnah 1:4"), ("The idea: an owner whose animal is likely to do a certain damage should guard it more carefully.", "Kulp 1:4")),
  S("Kehati's notes", ("The Torah (Exodus 21:35): \"sell the live ox and divide its price\": a harmless ox pays only from its own value. If it died or was lost, the owner pays nothing more.", "Kehati 1:4")),
  S("Halakha", ("The halakha does not follow Rabbi Eliezer.", "Kehati 1:4"))],
 "chart": {"title": "Harmless and attested dangers", "cols": ["", "What it does", "What the owner pays"], "rows": [["Harmless (tam)", "butts, pushes, bites, lies down, kicks", "half damages, from the body of the animal"], ["Attested danger (mu'ad)", "eats what it likes, breaks as it walks, a warned ox, an ox in the damaged party's domain, a person, wild beasts and the snake", "full damages, from the best property"]]}}]}
L2 = {"tractate": "Bava Kamma", "chapter": 2, "status": "Draft from the mishnah, R. Kulp and Kehati (pages 12-21 of the scan).", "mishnayot": [
{"n": 1, "title": "The foot: breaking as it walks", "summary": "An animal is an attested danger for breaking as it walks in its usual way. Kicking or flinging stones is unusual, so half damages.",
 "outline": [
  S("The foot", ("A beast is an attested danger only as it goes along in its usual way and breaks an object.", "Mishnah 2:1"), ("If it kicked, or small stones were tossed from under its feet and broke vessels: half damages.", "Mishnah 2:1")),
  S("Two vessels", ("If it trampled a vessel and the broken vessel fell on another and broke it: full damages for the first, half for the other.", "Mishnah 2:1")),
  S("Fowl", ("Fowl are attested dangers in their usual way. If its feet were entangled, or it was jumping and broke a vessel: half damages.", "Mishnah 2:1"), ("The rule of the chapter: damage in the usual way, the animal is an attested danger (full); in an unusual way, harmless (half).", "Kulp 2:1")),
  S("Kehati's notes", ("Kicking is not damage by the foot but a form of damage by the horn, so half damages. The second vessel is treated like damage by flung stones (tzrarot), which pays half.", "Kehati 2:1"))]},
{"n": 2, "title": "The tooth: eating", "summary": "An animal is an attested danger to eat what is fit for it (fruit and vegetables). Clothing and utensils: half damages. In the public domain: exempt, except for what it benefited.",
 "outline": [
  S("What it eats", ("A beast is an attested danger to eat fruit and vegetables.", "Mishnah 2:2"), ("If it ate clothing or utensils: half damages.", "Mishnah 2:2")),
  S("Where", ("In the domain of the damaged party the owner pays; in the public domain he is exempt.", "Mishnah 2:2"), ("If the beast benefited, he pays what it benefited.", "Mishnah 2:2")),
  S("What it benefited", ("From the middle of the marketplace: what it benefited. From the sides: the damage. In front of a store: what it benefited. Inside a store: the damage.", "Mishnah 2:2"), ("The owner of the animal is not liable if you carelessly leave your things in the public domain and his animal eats them.", "Kulp 2:2")),
  S("Kehati's notes", ("\"What it benefited\" is the value of what the animal would normally eat in its place (for example barley) at the low price, a third below market.", "Kehati 2:2"))]},
{"n": 3, "title": "Dogs, goats and a cake with an ember", "summary": "A dog or goat that jumps from a roof is an attested danger; a dog that takes a cake with an ember and burns a stack: full for the cake, half for the stack.",
 "outline": [
  S("Jumping from a roof", ("A dog or goat that jumped from a roof and broke vessels: full damages, since they are attested dangers.", "Mishnah 2:3")),
  S("The cake and the stack", ("A dog took a cake with an ember on it, went to a stack of grain, ate the cake and burned the stack: full damages for the cake, half for the stack.", "Mishnah 2:3"), ("Dogs are likely to eat cake, but unlikely to burn a stack of grain.", "Kulp 2:3")),
  S("Kehati's notes", ("The damage to the stack is unusual, since it is not a dog's way to kindle a fire.", "Kehati 2:3"))]},
{"n": 4, "title": "How an animal becomes an attested danger, and stops", "summary": "Rabbi Judah and Rabbi Meir dispute how many times an animal must damage to be an attested danger and what makes it harmless again. The halakha follows R. Judah for becoming one and R. Meir for returning to harmless.",
 "outline": [
  S("Rabbi Judah", ("An attested danger: people gave testimony about it for three days. A harmless one: it refrained from damage for three days.", "Mishnah 2:4")),
  S("Rabbi Meir", ("An attested danger: people gave testimony three times. A harmless one: children can touch it and it will not gore.", "Mishnah 2:4")),
  S("Halakha", ("The halakha follows Rabbi Judah for becoming an attested danger and Rabbi Meir for returning to harmless. Rambam: an ox does not return to harmless until children play with it and it does not gore.", "Kehati 2:4"))]},
{"n": 5, "title": "The ox that gores in the injured party's domain", "summary": "In the public domain the horn pays half damages. In the domain of the injured party Rabbi Tarfon says full damages; the Sages say half. The halakha follows the Sages.",
 "outline": [
  S("The cases", ("If it gored, pushed, bit, lay down or kicked in the public domain: half damages.", "Mishnah 2:5"), ("In the injured party's private domain: Rabbi Tarfon says full damages; the Sages say half.", "Mishnah 2:5")),
  S("Rabbi Tarfon's argument", ("If the law is lenient for tooth and foot in the public domain (exempt) and strict in the private domain of the injured (full), then horn, which is strict even in the public domain, should be full damages in the injured's domain.", "Mishnah 2:5")),
  S("The Sages' reply", ("\"It is enough if the inferred law is as strict as that from which it is inferred\" (dayo): half in the public domain, so half in the injured's domain.", "Mishnah 2:5"), ("Rabbi Tarfon: I do not derive horn from horn but horn from foot. The Sages answer with the same rule.", "Mishnah 2:5")),
  S("Halakha", ("The halakha follows the Sages.", "Kehati 2:5"))]},
{"n": 6, "title": "A person is always an attested danger", "summary": "A person who damages pays full damages, whether by accident or on purpose, awake or asleep.",
 "outline": [
  S("The rule", ("Human beings are always attested dangers, whether inadvertently or deliberately, awake or asleep. If a man blinded his fellow's eye or broke his utensils he pays full damages.", "Mishnah 2:6"), ("A person cannot claim it was accidental and so exempt himself.", "Kulp 2:6")),
  S("Kehati's notes", ("This is for damage (nezek). The other payments of one who injures (pain, healing, loss of time, shame) are in chapter 8, and he pays them only if he acted deliberately or nearly so.", "Kehati 2:6"))]}]}
SUM = {
 1: {"status": "Draft from the mishnah, R. Kulp and Kehati. Chapters 1-6 form a unit about damage caused by one's property or act.", "principles": [
   {"t": "Four primary causes of injury: the ox, the pit, the crop-destroying beast and fire. Each is in the Torah, and each has a feature the others lack.", "m": [1], "src": "Mishnah 1:1; Kulp 1:1"},
   {"t": "What I am bound to guard, if I did not guard it, I have prepared (hichsharti) its damage, even if only partly.", "m": [2], "src": "Mishnah 1:2"},
   {"t": "Damages are paid only for property that is not sacred, belongs to Jews, is owned, and is damaged outside the damager's own domain and the domain shared by both.", "m": [2], "src": "Mishnah 1:2"},
   {"t": "Damages are assessed in money before a court of experts on the evidence of free Jewish witnesses. Women are included.", "m": [3], "src": "Mishnah 1:3; Kehati 1:3"},
   {"t": "A harmless animal (tam) pays half damages from its own body; an attested danger (mu'ad) pays full damages from the best property.", "m": [4], "src": "Mishnah 1:4"}],
  "terms": [
   {"term": "primary causes of injury (avot nezikin)", "he": "אבות נזיקין", "def": "The four basic categories of damage in the Torah: ox, pit, crop-destroying beast and fire.", "m": [1], "src": "Mishnah 1:1"},
   {"term": "harmless (tam)", "he": "תם", "def": "An animal not yet an attested danger for a given damage. Its owner pays half damages from the animal's own value.", "m": [4], "src": "Mishnah 1:4"},
   {"term": "attested danger (mu'ad)", "he": "מועד", "def": "An agent (or an animal that has been warned) whose way is to damage. Its owner pays full damages from the best property. A human being is always one.", "m": [4], "src": "Mishnah 1:4"},
   {"term": "from the best of his land", "he": "מיטב הארץ", "def": "The payment for full damages comes from the best of the payer's land.", "m": [1, 2], "src": "Mishnah 1:1-1:2"}],
  "debates": [
   {"m": 1, "title": "What are the four primary causes?", "a": "Rav: the mishnah names the main kinds of damage in the Torah.", "b": "Shmuel: it names only four kinds of property damage that are attested dangers from the start (foot, tooth, pit, fire). Kehati follows Shmuel.", "src": "Kehati 1:1"},
   {"m": 4, "title": "Do tame wild animals count as attested dangers?", "a": "The first view: the wolf, lion, bear, leopard, panther and snake are attested dangers.", "b": "Rabbi Eliezer: tame ones are not, but the snake always is. The halakha does not follow him.", "src": "Mishnah 1:4; Kehati 1:4"}]},
 2: {"status": "Draft from the mishnah, R. Kulp and Kehati.", "principles": [
   {"t": "An animal is an attested danger for what is its way (breaking as it walks, eating what it likes). In an unusual way it is harmless and the owner pays half.", "m": [1, 2, 3], "src": "Mishnah 2:1-2:3; Kulp 2:1"},
   {"t": "For tooth and foot, the owner is exempt in the public domain (except for what the animal benefited) and pays in the domain of the damaged party.", "m": [2], "src": "Mishnah 2:2"},
   {"t": "An animal becomes an attested danger by repeated damage with testimony, and returns to harmless when it is safe with children.", "m": [4], "src": "Mishnah 2:4; Kehati 2:4"},
   {"t": "A conclusion drawn by reasoning cannot be stricter than the law it is drawn from (dayo): half damages for horn in the injured party's domain.", "m": [5], "src": "Mishnah 2:5"},
   {"t": "A person is always an attested danger: full damages for damage, accident or not, awake or asleep.", "m": [6], "src": "Mishnah 2:6"}],
  "terms": [
   {"term": "foot (regel)", "he": "רגל", "def": "Damage by an animal's trampling as it walks. An attested danger in its usual way.", "m": [1], "src": "Mishnah 2:1"},
   {"term": "tooth (shen)", "he": "שן", "def": "Damage by an animal's eating. An attested danger to eat what is fit for it.", "m": [2], "src": "Mishnah 2:2"},
   {"term": "horn (keren)", "he": "קרן", "def": "Damage by goring and similar unusual damage. Harmless unless the animal has become an attested danger.", "m": [5], "src": "Mishnah 2:5"},
   {"term": "it is enough (dayo)", "he": "דיו", "def": "The rule that a conclusion from reasoning is not stricter than its source.", "m": [5], "src": "Mishnah 2:5"}],
  "debates": [
   {"m": 4, "title": "How does an ox become an attested danger?", "a": "Rabbi Judah: testimony on three days; harmless again after three days without damage.", "b": "Rabbi Meir: testimony three times; harmless again when children can touch it. Halakha: R. Judah for becoming, R. Meir for returning.", "src": "Mishnah 2:4; Kehati 2:4"},
   {"m": 5, "title": "How much does a harmless ox pay in the injured party's domain?", "a": "Rabbi Tarfon: full damages, by an argument from tooth and foot.", "b": "The Sages: half damages, since the conclusion may not exceed its source (dayo). Halakha: the Sages.", "src": "Mishnah 2:5; Kehati 2:5"}]}}
for c, L in ((1, L1), (2, L2)):
    json.dump(L, open(f"data/bava_kamma_{c}_layer1.json", "w"), ensure_ascii=False, indent=1)
    json.dump(SUM[c], open(f"data/bava_kamma_{c}_summary.json", "w"), ensure_ascii=False, indent=1)
print("ok")
