// node guide_test.js guide_data.json
const assert = require("assert");
const L = require("./guide_logic.js");
const data = JSON.parse(require("fs").readFileSync(process.argv[2], "utf8"));

const ch = { n: 7, letter: "A", part: 3 };
assert(L.chapterOk(ch, [7, 7, "A", 3, false]));
assert(!L.chapterOk(ch, [7, 7, "B", 0, false]));
assert(L.chapterOk(ch, [5, 5, "", 0, true]));
assert(!L.chapterOk(ch, [8, 8, "", 0, true]));
assert(L.chapterOk(ch, [4, 10, "", 0, false]));

// location 132: "Hire woodcarvers" needs Chance Meetings part 3
const owned = new Set(["Chance Meetings|3", "Venedian Path|2"]);
const party = new Set(["Osbert"]);
const open = L.openGates(data, owned, ch, party);
// matched by place and condition, not by label, so the test holds for every build language
const hire = g => g.at === "132/1" && g.conds.some(c => c[0] === "Chance Meetings" && c[1] === 3);
assert(open.some(hire), "132 woodcarvers gate");
assert(!L.openGates(data, new Set(), ch, party).some(hire));
const withHero = data.gates.find(g => g.heroes.length === 1 && g.heroes[0] === "Elgan" && !g.conds.length && !g.chapter.length);
assert(L.openGates(data, new Set(), ch, new Set(["Elgan"])).includes(withHero), "Elgan gate open for Elgan");
assert(!L.openGates(data, new Set(), ch, party).includes(withHero), "Elgan gate closed without Elgan");
assert(L.condOk(new Set(["Time Passes: Chapter 7|1"]), ch, ["Time Passes", null, true]));

// "at least two parts of Family Secrets", and a counted status without parts
assert(L.condOk(new Set(["Family Secrets|1", "Family Secrets|4"]), ch, ["Family Secrets", null, true, 2]));
assert(!L.condOk(new Set(["Family Secrets|1"]), ch, ["Family Secrets", null, true, 2]));
assert(L.condOk(new Set(["Mapping the Bog|1", "Mapping the Bog|2", "Mapping the Bog|3"]), ch, ["Mapping the Bog", null, true, 3]));

// hand-pinned lead: the Caprellida hint shows after Rumors 5 and goes away with Faint Notion 8
const capr = l => l.at === "155/9" && l.hide;
assert(L.activeLeads(data, new Set(["Rumors & Hearsay|5"])).some(capr));
assert(!L.activeLeads(data, new Set(["Rumors & Hearsay|5", "Faint Notion|8"])).some(capr));

// the senator's map quest ends with Friend of Nobility 3 (map to Culpean) or Informer 5 (map to Octavia)
const map = l => l.at === "155/8" && l.hide;
assert(L.activeLeads(data, new Set(["Bureaucracy|3"])).some(map));
assert(!L.activeLeads(data, new Set(["Bureaucracy|3", "Friend of Nobility|3"])).some(map));

// link code round-trips a full state and refuses a code from another layout
const full = { owned: ["Faint Notion|8", "Topography|3", "Mapping the Bog|1", "Mapping the Bog|2"], ch: { n: 7, letter: "B", part: 3 },
  heroes: ["Iunis", "Osbert"], onMap: [151, 157], sample: false };
const code = L.encodeState(data, full);
assert(/^[0-9a-z-]+$/.test(code), code);
const back = L.decodeState(data, code);
assert.deepStrictEqual([new Set(back.owned), back.ch, back.heroes, back.onMap], [new Set(full.owned), full.ch, full.heroes, full.onMap]);
assert.throws(() => L.decodeState(data, code.replace(/^t\w+-/, "tzzzz-")));

console.log("ok; link code", code.length, "chars;", open.length, "open gates,", L.activeLeads(data, owned).length, "leads for the sample state");
