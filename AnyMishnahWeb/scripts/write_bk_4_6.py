"""Layer 1 and chapter summaries for Bava Kamma 4 and 6 (2026-10-13). Sources: the mishnah (Sefaria), R. Kulp, Kehati (pdf pp.37-60 for ch.4; pp.61-70 for ch.6). No other sources."""
import json
def S(h, *items): return {"h": h, "b": [list(i) for i in items]}
L4 = {"tractate": "Bava Kamma", "chapter": 4, "status": "Draft from the mishnah, R. Kulp and Kehati.", "mishnayot": [
{"n": 1, "title": "A harmless ox that gores several oxen", "summary": "A harmless ox pays only from its own body. When it gored several oxen in turn, Rabbi Meir has the last victim paid first; Rabbi Shimon has the victims share.",
 "outline": [
  S("The case", ("An ox gored four or five oxen, one after another. The owner pays the owner of the last ox injured; if money remains, the one before; and so on. The last benefits, according to Rabbi Meir.", "Mishnah 4:1")),
  S("Rabbi Shimon", ("An ox worth 200 gored an ox worth 200 and the carcass is worth nothing: each owner gets 100. If it gores a third worth 200: the last gets 100, the previous 50. A fourth: the last 100, the previous 50, and the first two 25 each.", "Mishnah 4:1")),
  S("The two views", ("One opinion: the owner of the injured ox becomes the new owner of the harmless ox, so he is responsible for its later damage. The other: he becomes a partner in the ox.", "Kulp 4:1"), ("The Gemara: Rabbi Meir follows Rabbi Yishmael (the injured is a creditor of the damager), Rabbi Shimon follows Rabbi Akiva (the injured becomes a partner in the ox).", "Kehati 4:1"))]},
{"n": 2, "title": "An attested danger for some things only", "summary": "An ox can be an attested danger to one kind of victim and harmless to another, or on one day and not another. For the first it pays full damages, for the other half.",
 "outline": [
  S("By kind of victim", ("An ox that is an attested danger to its own kind but not to others, to people but not to beasts, to children but not to adults: for that for which it is an attested danger, full damages; for the rest, half.", "Mishnah 4:2"), ("The owner must be extra careful where the ox is known to injure.", "Kulp 4:2"), ("For example, an ox seen standing with horses and camels and not goring is not an attested danger to those.", "Kehati 4:2")),
  S("By day", ("Rabbi Judah: an ox that is an attested danger on the Sabbath but not during the week pays full damages for Sabbaths and half damages for weekdays.", "Mishnah 4:2"), ("It becomes harmless again after it refrains from injury for three Sabbath days.", "Mishnah 4:2"))]},
{"n": 3, "title": "Property of the Temple, of a gentile", "summary": "An Israelite's ox that gores a sacred ox or a gentile's ox is exempt. A gentile's ox that gores an Israelite's pays full damages, harmless or not.",
 "outline": [
  S("The cases", ("An Israelite's ox that gored an ox of the Temple, or the Temple's that gored an Israelite's: exempt, since the verse says \"his neighbour's ox\" (Exodus 21:35), not the Temple's.", "Mishnah 4:3"), ("An Israelite's ox that gored a gentile's: exempt. A gentile's ox that gored an Israelite's, harmless or not: full damages.", "Mishnah 4:3")),
  S("Why", ("The first clause is a midrash on the words \"his neighbour\".", "Kulp 4:3"), ("For the gentile cases Kehati gives reasons: the Gemara says the seven commandments of Noah were not kept by the nations, so their property was released to Israel; Rambam says it is a fine, since gentiles do not guard against damage; Meiri says it applies to nations not bound by religious norms.", "Kehati 4:3"))]},
{"n": 4, "title": "Oxen of a deaf-mute, an insane person, a minor", "summary": "The owner of a sound ox who injures the ox of a deaf-mute, insane person or minor pays. Their ox that injures a sound person's ox: exempt. The court appoints a guardian.",
 "outline": [
  S("Who pays", ("An ox of a person of sound senses that gored the ox of a deaf-mute, insane person or minor: obligated. The reverse: exempt.", "Mishnah 4:4"), ("These are people not capable of fully knowing the consequences of their actions, so they cannot be held responsible.", "Kulp 4:4")),
  S("A guardian, and becoming sound", ("If their ox gored, the court appoints a guardian, and the ox is warned in front of him.", "Mishnah 4:4"), ("If the deaf-mute becomes of sound senses, the insane person recovers, or the minor comes of age: Rabbi Meir says the ox is harmless again; Rabbi Yose says it remains as it was.", "Mishnah 4:4"), ("Rambam follows Rabbi Yose. The Gemara gives Rabbi Meir's reason: a change of owner changes the ox's status.", "Kehati 4:4")),
  S("The arena ox", ("An ox trained for the stadium is not liable to death, as it says \"when it will gore\" and not \"when others cause it to gore\".", "Mishnah 4:4"))]},
{"n": 5, "title": "An ox that kills a person", "summary": "An ox that kills a person is stoned. An attested danger's owner also pays ransom; a harmless ox's owner does not. For a slave, thirty sela.",
 "outline": [
  S("The cases", ("An ox gored a person and he died: if it was an attested danger, its owner pays the ransom (kofer); if harmless, he is exempt from it. In both cases the ox is put to death.", "Mishnah 4:5"), ("The same for a son or a daughter. For a male or female slave: its owner pays 30 sela, whether the slave was worth a maneh or not a dinar.", "Mishnah 4:5")),
  S("Background", ("The Torah's verses: Exodus 21:28-32. The ox is stoned and its meat forbidden; the owner of an attested danger could in principle deserve death, but the Torah allows him to ransom his life.", "Kulp 4:5"), ("Kofer is the value of the person killed.", "Kehati 4:5"))]},
{"n": 6, "title": "An ox that did not intend to kill", "summary": "An ox is judged by its intention. If it did not mean to kill a person, it is exempt from death.",
 "outline": [
  S("The cases", ("An ox rubbing against a wall that fell on a person; an ox that intended to kill an animal and killed a man; one that intended to kill a gentile and killed an Israelite; one that intended to kill an untimely birth and killed a viable infant: exempt from death.", "Mishnah 4:6"), ("In all of these the ox meant to kill something for which it would not be liable to death. We judge the ox by its intention, not its action.", "Kulp 4:6"))]},
{"n": 7, "title": "Oxen of those with no adult male owner", "summary": "The ox of a woman, orphans, a guardian, or a wild, Temple or convert's ownerless ox that kills is put to death. Rabbi Judah exempts the ones with no owner. The halakha does not follow him.",
 "outline": [
  S("The list", ("The ox of a woman, of orphans, of a guardian, a wild ox, an ox of the Temple, or of a convert who died without heirs: all are liable to death.", "Mishnah 4:7"), ("Rabbi Judah: a wild ox, a Temple ox and a convert's ox are exempt, since they have no owners.", "Mishnah 4:7"), ("Rabbi Judah derives this from Exodus 21:28-29: the ox is put to death only where the owners can be warned.", "Kulp 4:7")),
  S("Halakha", ("The halakha does not follow Rabbi Judah.", "Kehati 4:7"))]},
{"n": 8, "title": "Dedicating an ox that is going to be stoned", "summary": "An owner cannot dedicate or slaughter an ox once sentence is complete. Before that, his act is valid.",
 "outline": [
  S("After the sentence", ("If an ox goes out to be stoned and its owners dedicate it, it is not dedicated. If he slaughtered it, its flesh is forbidden.", "Mishnah 4:8")),
  S("Before the sentence", ("If before its sentence was complete its owner dedicated it, it is dedicated; if he slaughtered it, its flesh is permitted.", "Mishnah 4:8"), ("He tries to cheat the system by getting credit for a sacrifice or food and leather for himself.", "Kulp 4:8")),
  S("Kehati's notes", ("After the sentence the flesh is forbidden to eat and to benefit from.", "Kehati 4:8"))]},
{"n": 9, "title": "Guards, and an ox that was properly guarded", "summary": "A guard takes the owner's place. If the owner tied or locked the ox properly and it still damaged, the sages dispute: Rabbi Meir, Rabbi Judah and Rabbi Eliezer. The halakha follows Rabbi Judah.",
 "outline": [
  S("A guard takes the owner's place", ("If one handed it to an unpaid guardian, a borrower, a paid guardian or a hirer, they take the place of the owners: full damages for an attested danger, half for a harmless one.", "Mishnah 4:9")),
  S("An ox properly guarded", ("If its owner tied it with a halter or locked it up properly, but it came out and caused damage: Rabbi Meir: liable, whether an attested danger or harmless.", "Mishnah 4:9"), ("Rabbi Judah: if harmless he is liable; if an attested danger he is exempt, as it says \"and its owner did not guard it\", but this one was guarded.", "Mishnah 4:9"), ("Rabbi Eliezer: its only guarding is the knife.", "Mishnah 4:9")),
  S("Kehati's notes", ("Rabbi Judah's exemption is from the full payment: the owner still pays half damages.", "Kehati 4:9"), ("There are three views about an attested danger that was guarded: Rabbi Meir: liable if the guard was weak, exempt if strong; Rabbi Judah: exempt from the full payment even with a weak guard; Rabbi Eliezer: liable even with a strong guard.", "Kehati 4:9")),
  S("Halakha", ("The halakha follows Rabbi Judah.", "Kehati 4:9"))]}]}
L6 = {"tractate": "Bava Kamma", "chapter": 6, "status": "Draft from the mishnah, R. Kulp and Kehati.", "mishnayot": [
{"n": 1, "title": "A flock that gets out of the pen", "summary": "An owner who shut his flock in properly is exempt if it still gets out. If he did not, he is liable. If the pen was broken at night or by bandits, he is not liable.",
 "outline": [
  S("Closing it in", ("If he shut the flock in properly and it went out and caused damage: exempt. If not properly: liable.", "Mishnah 6:1")),
  S("Broken through", ("If the pen was broken through at night, or bandits broke it, and the flock came out and caused damage: he is not liable. If the bandits brought out the flock, the bandits are liable.", "Mishnah 6:1"), ("This begins the laws of the crop-destroying beast, the third archetypal cause of damage.", "Kulp 6:1")),
  S("Kehati's notes", ("\"Properly\" means a door able to stand up to ordinary wind; that is enough for tooth and foot, which are attested dangers from the start.", "Kehati 6:1"), ("The exemption for a break at night is for a break he could not have prevented; if the break was by day and enough time passed for him to find out and guard, he is liable.", "Kehati 6:1"), ("If the bandits stood in front of the flock until it went out, it is as if they took it out by hand. If they only broke the pen, the damage is indirect (grama), and they are exempt.", "Kehati 6:1"))]},
{"n": 2, "title": "The flock in the sun, and in a garden", "summary": "An owner is liable if he left the flock in the sun or gave it to someone who cannot be responsible. A flock that fell into a garden pays only what it benefited; one that entered normally pays for the damage.",
 "outline": [
  S("Left in the sun, or handed over", ("If he left the flock in the sun, or delivered it to a deaf-mute, an idiot or a minor, and it came out and caused damage, he is liable. If he delivered it to a shepherd, the shepherd takes the place of the owner.", "Mishnah 6:2"), ("In the heat the animals go wild and break out, which he should have expected.", "Kulp 6:2")),
  S("In a garden", ("If the flock fell into a garden and benefited, he pays for the benefit. If it went down in its usual way and caused damage, he pays for the damage.", "Mishnah 6:2"), ("Falling in is an unavoidable accident.", "Kulp 6:2")),
  S("How the damage is assessed", ("They assess what a seah's space of ground in that field was worth before and after.", "Mishnah 6:2"), ("Rabbi Shimon: if they ate fully grown produce, he repays in fully grown produce; one seah, one seah; two, two.", "Mishnah 6:2")),
  S("Kehati's notes", ("The mishnah's shepherd who \"takes the place of the owner\" is a shepherd who handed the flock to a second shepherd under him; the second takes his place. An owner handing a flock to a guard is in 4:9.", "Kehati 6:2"), ("A seah's space is a field in which one sows a seah, 2,500 square cubits.", "Kehati 6:2")),
  S("Halakha", ("The halakha follows Rabbi Shimon.", "Kehati 6:2"))]},
{"n": 3, "title": "Sheaves stacked in a field", "summary": "The same rules as in 5:3, applied to a stack in another's field: without permission the field owner is not liable; with permission he is liable, if he accepted to guard.",
 "outline": [
  S("The cases", ("If a man stacked his sheaves in his fellow's field without permission and the field owner's beast ate them: exempt. If the beast was injured by them: the owner of the stack is liable. If he made the stack with permission: the owner of the field is liable.", "Mishnah 6:3"), ("These laws were learned in 5:3.", "Kulp 6:3")),
  S("Kehati's notes", ("\"The owner of the field is liable\" means a guard of the threshing floors there, or a field owner who accepted to guard them. Rabbi (5:3) holds that letting someone in does not make him liable unless he accepted.", "Kehati 6:3"))]},
{"n": 4, "title": "Fire", "summary": "The one who kindles a fire pays for everything it burns. The sages dispute how far the fire must spread. The halakha follows Rabbi Shimon: by the nature of the fire.",
 "outline": [
  S("Sending fire", ("If a person sends fire in the hands of a deaf-mute, an idiot or a minor, he is not liable by the laws of man but is by the laws of Heaven. If he sent it in the hands of a person of sound senses, that person is liable.", "Mishnah 6:4"), ("Kehati: a deaf-mute, idiot or minor cannot be agents. An adult agent is liable, and the sender is exempt even from heavenly law, since there is no agent for a wrong act.", "Kehati 6:4")),
  S("Several people", ("One brought the fire and another the wood: the one who brought the wood is liable. One brought the wood and another the fire: the one who brought the fire. Another fanned the flames: he is liable.", "Mishnah 6:4"), ("The last to contribute is liable for all the damage.", "Kulp 6:4"), ("If the wind fanned the flame, they are all exempt.", "Mishnah 6:4"), ("This is only for an unusual wind. If it was an ordinary wind, the last is liable, since fire spreads in an ordinary wind and he should have guarded.", "Kehati 6:4")),
  S("What it burns", ("If it consumed wood, stones or dust: he is liable, for it says \"stacked corn, standing corn, or the field\" (Exodus 22:5).", "Mishnah 6:4")),
  S("How far", ("If it passed over a fence four cubits high, or over a public way, or over a river: exempt.", "Mishnah 6:4"), ("A fire kindled in his own domain: Rabbi Eleazar ben Azariah: as if in the middle of a kor's space; Rabbi Eliezer: sixteen cubits, like a public road; Rabbi Akiva: fifty cubits; Rabbi Shimon: all by the nature of the fire.", "Mishnah 6:4")),
  S("Halakha", ("The halakha follows Rabbi Shimon: if the fire is large, he is liable even beyond those distances.", "Kehati 6:4"))]},
{"n": 5, "title": "What was in the stack", "summary": "A fire that burns a stack with utensils in it: Rabbi Judah says pay for all; the Sages, only for the grain. In a large building all agree he pays for everything in it.",
 "outline": [
  S("Utensils in the stack", ("If a man set fire to a stack and utensils in it caught fire: Rabbi Judah says he pays for what was in it; the Sages say only for a stack of wheat or barley.", "Mishnah 6:5"), ("The Sages agree with Rabbi Judah that if he burned a large building, he pays for everything in it, since it is the custom to leave goods in houses.", "Mishnah 6:5"), ("The Sages think it is not customary to leave things in stacks.", "Kulp 6:5")),
  S("A kid and a slave", ("If a kid was fastened to the stack and a slave stood near by and they were burnt: he is liable. If a slave was fastened to it and a kid stood near by and they were burnt: he is not liable.", "Mishnah 6:5"))]},
{"n": 6, "title": "Sparks, flax and the lamp", "summary": "A spark from a hammer: liable. A camel's flax that catches a shopkeeper's light: the camel's owner pays; if the lamp was outside the shop, the shopkeeper does. Rabbi Judah: not for a Hanukkah light.",
 "outline": [
  S("The spark", ("If a spark flew out from under the hammer and caused damage, he is liable.", "Mishnah 6:6"), ("Kehati: it is like one who throws a stone or an arrow.", "Kehati 6:6")),
  S("The camel and the shop", ("A camel laden with flax passed in the public domain and its flax entered a shop and caught fire from the shopkeeper's light: the owner of the camel is liable.", "Mishnah 6:6"), ("But if the shopkeeper left his light outside, the shopkeeper is liable.", "Mishnah 6:6")),
  S("Rabbi Judah", ("If it was a Hanukkah light, the shopkeeper is not liable.", "Mishnah 6:6"), ("The Hanukkah light is supposed to be placed outside, at the door.", "Kulp 6:6"), ("The halakha does not follow Rabbi Judah.", "Kehati 6:6"))]}]}
SUM = {
 4: {"status": "Draft from the mishnah, R. Kulp and Kehati.", "principles": [
   {"t": "A harmless ox pays only from its own body; the injured owner is either a new owner or a partner in it (Rabbi Meir and Rabbi Shimon).", "m": [1], "src": "Mishnah 4:1; Kehati 4:1"},
   {"t": "An ox can be an attested danger for one kind of victim or one day, and harmless for others: full damages for the one, half for the other.", "m": [2], "src": "Mishnah 4:2"},
   {"t": "An Israelite's ox is exempt for damage to Temple property and to a gentile's ox; a gentile's ox pays full damages to an Israelite.", "m": [3], "src": "Mishnah 4:3"},
   {"t": "An ox that kills a person is stoned; the owner of an attested danger pays ransom (kofer), the owner of a harmless one does not.", "m": [5], "src": "Mishnah 4:5"},
   {"t": "An ox is judged by its intention: it is exempt from death if it did not intend to kill a person.", "m": [6], "src": "Mishnah 4:6"},
   {"t": "A guard takes the owner's place; an owner who tied or locked his ox properly: the sages dispute, and the halakha follows Rabbi Judah.", "m": [9], "src": "Mishnah 4:9; Kehati 4:9"}],
  "terms": [
   {"term": "ransom (kofer)", "he": "כופר", "def": "The payment an owner of an attested danger makes to ransom his life when his ox kills a person. It is the value of the person killed.", "m": [5], "src": "Mishnah 4:5; Kehati 4:5"},
   {"term": "guardian (apotropos)", "he": "אפוטרופוס", "def": "A person the court appoints to watch the ox of a deaf-mute, insane person or minor.", "m": [4], "src": "Mishnah 4:4"},
   {"term": "paid guardian, borrower, hirer", "he": "שומר שכר, שואל, שוכר", "def": "People to whom an ox is handed; they take the owner's place for its damage.", "m": [9], "src": "Mishnah 4:9"}],
  "debates": [
   {"m": 1, "title": "What does the injured owner become?", "a": "Rabbi Meir: a creditor, paid first from the last victim backward.", "b": "Rabbi Shimon: a partner in the ox, so the victims share.", "src": "Mishnah 4:1; Kehati 4:1"},
   {"m": 4, "title": "Is the ox harmless again when its owner recovers?", "a": "Rabbi Meir: harmless again.", "b": "Rabbi Yose: it remains as it was. Rambam follows Rabbi Yose.", "src": "Mishnah 4:4; Kehati 4:4"},
   {"m": 9, "title": "A properly guarded ox that still damages", "a": "Rabbi Meir: liable, harmless or not. Rabbi Judah: harmless, liable; attested danger, exempt from the full payment.", "b": "Rabbi Eliezer: its only guarding is the knife. The halakha follows Rabbi Judah.", "src": "Mishnah 4:9; Kehati 4:9"}]},
 6: {"status": "Draft from the mishnah, R. Kulp and Kehati.", "principles": [
   {"t": "An owner who guarded his flock properly is exempt if it escapes through no fault; one who did not is liable.", "m": [1, 2], "src": "Mishnah 6:1-6:2"},
   {"t": "A flock that falls into a garden pays what it benefited; one that enters normally pays the damage, assessed by the value of a seah's space.", "m": [2], "src": "Mishnah 6:2"},
   {"t": "Whoever kindles a fire pays for everything it burns. When several contribute, the last one is liable; a wind frees all only if it was unusual.", "m": [4], "src": "Mishnah 6:4; Kehati 6:4"},
   {"t": "The distance a fire must travel to be exempt is disputed; the halakha follows Rabbi Shimon, by the nature of the fire.", "m": [4], "src": "Mishnah 6:4; Kehati 6:4"},
   {"t": "The Sages: goods are paid for only where it is customary to keep them (a building, not a stack of hay); Rabbi Judah: he pays for all that was in it.", "m": [5], "src": "Mishnah 6:5; Kulp 6:5"}],
  "terms": [
   {"term": "fire (esh)", "he": "אש", "def": "The fourth archetypal cause of damage: the one who kindles a fire pays for the damage it does.", "m": [4], "src": "Mishnah 6:4"},
   {"term": "indirect cause (grama)", "he": "גרמא", "def": "Damage caused indirectly, such as bandits who break a pen and the flock then leaves. Not liable in human law.", "m": [1], "src": "Kehati 6:1"},
   {"term": "laws of man and of Heaven", "he": "דיני אדם ודיני שמים", "def": "A wrong that cannot be prosecuted in court but for which the person is still accountable.", "m": [4], "src": "Mishnah 6:4; Kulp 6:4"}],
  "debates": [
   {"m": 4, "title": "How far must the fire spread?", "a": "Rabbi Eleazar ben Azariah: like the middle of a kor's space; Rabbi Eliezer: 16 cubits; Rabbi Akiva: 50.", "b": "Rabbi Shimon: all by the nature of the fire. The halakha follows Rabbi Shimon.", "src": "Mishnah 6:4; Kehati 6:4"},
   {"m": 5, "title": "Utensils inside a stack that burned", "a": "Rabbi Judah: he pays for what was in it.", "b": "The Sages: only for the wheat or barley. In a large building all agree he pays for the contents.", "src": "Mishnah 6:5"},
   {"m": 6, "title": "The Hanukkah light outside the shop", "a": "The first view: the shopkeeper who left his light outside is liable.", "b": "Rabbi Judah: not liable for a Hanukkah light. The halakha does not follow him.", "src": "Mishnah 6:6; Kehati 6:6"}]}}
for c, L in ((4, L4), (6, L6)):
    json.dump(L, open(f"data/bava_kamma_{c}_layer1.json", "w"), ensure_ascii=False, indent=1)
    json.dump(SUM[c], open(f"data/bava_kamma_{c}_summary.json", "w"), ensure_ascii=False, indent=1)
print("ok")
