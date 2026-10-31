// Advice from owned status parts; inlined into the page by guide.py and tested by guide_test.js.
// owned: Set of "Status|part"; a status without numbered parts is counted as "Status|1".."Status|n"
// ch: {n, letter, part}

function count(owned, s) {
  let n = 0;
  for (const k of owned) if (k.startsWith(s + "|")) n++;
  return n;
}

function has(owned, s, p) {
  return p != null ? owned.has(s + "|" + p) : count(owned, s) > 0;
}

function condOk(owned, ch, [s, p, want, min]) {
  // "Time Passes" with no chapter means the part for the chapter being played
  if (s === "Time Passes") s = "Time Passes: Chapter " + ch.n;
  return (min ? count(owned, s) >= min : has(owned, s, p)) === want;
}

function chapterOk(ch, [a, b, letter, part, further]) {
  const sameStep = (!letter || letter === ch.letter);
  if (further) return ch.n > a || (ch.n === a && sameStep && (!part || ch.part >= part));
  return ch.n >= a && ch.n <= b && sameStep && (!part || ch.part === part);
}

// heroes: Set of character names in the party; a gate naming several needs any one of them
function openGates(data, owned, ch, heroes) {
  return data.gates.filter(g =>
    g.conds.every(c => condOk(owned, ch, c)) &&
    (!g.heroes.length || g.heroes.some(h => heroes.has(h))) &&
    (!g.chapter.length || g.chapter.some(c => chapterOk(ch, c))) &&
    g.reach.some(([s, p]) => !owned.has(s + "|" + p)));
}

// a lead stays relevant while its thread has not moved past the part gained next to it
function activeLeads(data, owned) {
  const top = {};
  for (const k of owned) {
    const [s, p] = k.split("|");
    top[s] = Math.max(top[s] || 0, +p || 0);
  }
  return data.leads.filter(l => l.hide
    ? l.keys.some(([s, p]) => has(owned, s, p)) && !l.hide.some(([s, p]) => has(owned, s, p))
    : l.keys.some(([s, p]) => owned.has(s + "|" + p) && top[s] === p));
}


// Compact state for a link: one bit per sheet box, packed into base36 with a layout version.
// Only letters, digits and "-" survive in an artifact link's #hash, so the code uses nothing else.
const COUNT_BITS = 3;  // tallies of statuses without numbered parts go up to 7
const HEROES_ALL = ["Elgan", "Gerdwyn", "Iunis", "Osbert"];

function layout(data) {
  const statuses = Object.keys(data.max_part).filter(s => s !== "Time Passes").sort();
  const locs = Object.keys(data.loc_names).map(Number).sort((a, b) => a - b);
  let h = 2166136261;  // FNV-1a over the layout: a link from another data build is refused, not misread
  for (const c of JSON.stringify([statuses.map(s => [s, data.max_part[s]]), locs])) h = Math.imul(h ^ c.charCodeAt(0), 16777619) >>> 0;
  return { statuses, locs, ver: h.toString(36).slice(0, 4) };
}

function encodeState(data, state) {
  const { statuses, locs, ver } = layout(data);
  const owned = new Set(state.owned), bits = [];
  const put = (v, n) => { for (let i = n - 1; i >= 0; i--) bits.push((v >> i) & 1); };
  for (const s of statuses) {
    if (data.max_part[s]) for (let p = 1; p <= data.max_part[s]; p++) bits.push(owned.has(s + "|" + p) ? 1 : 0);
    else put(Math.min(count(owned, s), 2 ** COUNT_BITS - 1), COUNT_BITS);
  }
  put(state.ch.n, 4); put(["", "A", "B"].indexOf(state.ch.letter), 2); put(state.ch.part, 3);
  for (const h of HEROES_ALL) bits.push(state.heroes.includes(h) ? 1 : 0);
  for (const l of locs) bits.push(state.onMap.includes(l) ? 1 : 0);
  return "t" + ver + "-" + BigInt("0b1" + bits.join("")).toString(36);  // leading 1 keeps leading zeros
}

function decodeState(data, code) {
  const m = /^t([0-9a-z]{1,4})-([0-9a-z]+)$/.exec(code);
  if (!m) throw new Error("format");
  const { statuses, locs, ver } = layout(data);
  if (m[1] !== ver) throw new Error("version");
  let n = 0n;
  for (const c of m[2]) n = n * 36n + BigInt(parseInt(c, 36));
  const bits = n.toString(2).slice(1);
  let i = 0;
  const take = k => { let v = 0; for (let j = 0; j < k; j++) v = v * 2 + +(bits[i++] === "1"); return v; };
  const owned = [];
  for (const s of statuses) {
    if (data.max_part[s]) { for (let p = 1; p <= data.max_part[s]; p++) if (take(1)) owned.push(s + "|" + p); }
    else for (let p = 1, c = take(COUNT_BITS); p <= c; p++) owned.push(s + "|" + p);
  }
  const ch = { n: take(4), letter: ["", "A", "B", ""][take(2)], part: take(3) };
  const heroes = HEROES_ALL.filter(() => take(1));
  const onMap = locs.filter(() => take(1));
  if (i !== bits.length) throw new Error("length");
  return { owned, ch, heroes, onMap, sample: false };
}

if (typeof module !== "undefined") module.exports = { encodeState, decodeState, count, has, condOk, chapterOk, openGates, activeLeads };
