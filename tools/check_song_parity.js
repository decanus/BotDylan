/*
 * check_song_parity.js — songs/*.json must match the copies inside the
 * simulator.
 *
 * The simulator has to keep its own embedded copy of every song: it is meant
 * to run straight from file://, where fetching a local JSON file is blocked.
 * So the songs exist twice, and duplication drifts unless something checks.
 * This is that something.
 *
 *   node tools/check_song_parity.js
 *
 * Exits non-zero on any difference. Run it after editing either copy.
 */
"use strict";
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
const html = fs.readFileSync(path.join(root, "tools/simulator.html"), "utf8");

const start = html.indexOf("/* ---- Songs");
const end = html.indexOf("function stopSong");
if (start < 0 || end < 0) {
  console.error("could not find the song block in simulator.html");
  process.exit(2);
}
// `const` inside eval is scoped to the eval, so hand the bindings back out.
const S = eval(html.slice(start, end) + ";({AMAZING_GRACE, ODE_TO_JOY})");

const PAIRS = [
  ["songs/amazing_grace.json", S.AMAZING_GRACE],
  ["songs/ode_to_joy.json", S.ODE_TO_JOY],
];

let failures = 0;

for (const [file, sim] of PAIRS) {
  const json = JSON.parse(fs.readFileSync(path.join(root, file), "utf8"));

  if (json.quarterMs !== sim.q) {
    console.error(`${file}: quarterMs ${json.quarterMs} != simulator q ${sim.q}`);
    failures++;
  }
  if (json.notes.length !== sim.notes.length) {
    console.error(`${file}: ${json.notes.length} notes != simulator ${sim.notes.length}`);
    failures++;
    continue;
  }

  json.notes.forEach((n, i) => {
    const [s, a, b, beats, vowelCC, syllable, velocity, glide] = sim.notes[i];
    const want = { sop: s, alto: a, bass: b, beats, vowelCC, syllable, velocity, glide };
    for (const k of Object.keys(want)) {
      if (n[k] !== want[k]) {
        console.error(
          `${file}: note ${i} field ${k}: json ${JSON.stringify(n[k])} != simulator ${JSON.stringify(want[k])}`
        );
        failures++;
      }
    }
  });

  console.log(`${file}: ${json.notes.length} notes match the simulator`);
}

if (failures) {
  console.error(`SONG PARITY FAILED (${failures} difference${failures === 1 ? "" : "s"})`);
  process.exit(1);
}
console.log("SONG PARITY OK");
