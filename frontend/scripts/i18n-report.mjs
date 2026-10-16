/**
 * Two jobs, both planning aids rather than gates — this always exits 0 unless
 * it finds a leaked key (see below). Enforcement of hard-coded copy lives in
 * eslint.config.js, scoped to the files already migrated.
 *
 *   1. Lists the public components still holding hard-coded German copy,
 *      busiest first, so the next extraction tranche can be picked by weight
 *      instead of by guesswork.
 *   2. Flags *leaked keys*: a catalogue key that reaches the DOM as literal
 *      text instead of being resolved. TypeScript cannot see this class of bug
 *      — the key is a valid string in a `string` slot — and it happened for
 *      real: the style/water label lists in MeinSetup carried catalogue keys
 *      while their render sites still printed the raw value, so the page would
 *      have shown "setup.styles.freeride".
 *
 * Counted as user-visible: JSX child text, and literals in the attributes that
 * actually reach a reader (label/aria-label/placeholder/title/alt). Admin files
 * are skipped — the back office stays German by decision, not by omission.
 *
 * Usage: node scripts/i18n-report.mjs [--limit N]
 */
import { readdir, readFile } from "node:fs/promises";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const SRC = fileURLToPath(new URL("../src/", import.meta.url));
const CATALOGUE = fileURLToPath(new URL("../src/lib/i18n/locales/de.ts", import.meta.url));
const limitFlag = process.argv.indexOf("--limit");
const LIMIT = limitFlag === -1 ? 25 : Number(process.argv[limitFlag + 1]);

/** Files the lint guard already covers; mirrored from eslint.config.js. */
const MIGRATED = new Set([
  "main.tsx",
  "components/Footer.tsx",
  "components/Header.tsx",
  "components/AccountMenu.tsx",
  "components/SpotCommunity.tsx",
  "pages/account/AccountLayout.tsx",
  "pages/account/Einstellungen.tsx",
  "pages/account/MeinSetup.tsx",
]);

const LETTERS = "A-Za-z\\u00C0-\\u024F";
// JSX child text: between > and <, no braces (those are expressions, not copy).
const JSX_TEXT = new RegExp(`>\\s*([${LETTERS}][^<>{}]*[${LETTERS}])\\s*<`, "g");
const ATTR = new RegExp(`(?:aria-label|placeholder|label|title|alt)="([^"]*[${LETTERS}]{2}[^"]*)"`, "g");

/** Leaf key paths of the catalogue, e.g. "setup.styles.freeride". */
async function catalogueKeys() {
  const source = await readFile(CATALOGUE, "utf8");
  const keys = new Set();
  const stack = [];
  for (const raw of source.split("\n")) {
    const line = raw.trim();
    const opens = /^([A-Za-z_][A-Za-z0-9_]*):\s*\{$/.exec(line);
    if (opens) {
      stack.push(opens[1]);
      continue;
    }
    if (line.startsWith("}")) {
      stack.pop();
      continue;
    }
    // `name: "value"` on one line, or `name:` with the string on the next.
    const leaf = /^([A-Za-z_][A-Za-z0-9_]*):\s*(?:"|$)/.exec(line);
    if (leaf && stack.length) keys.add([...stack, leaf[1]].join("."));
  }
  return keys;
}

async function* walk(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "__tests__" || entry.name === "admin") continue;
      yield* walk(full);
    } else if (/\.tsx?$/.test(entry.name)) {
      yield full;
    }
  }
}

const keys = await catalogueKeys();
const rows = [];
const leaks = [];

for await (const file of walk(SRC)) {
  const rel = relative(SRC, file).replaceAll("\\", "/");
  if (/admin/i.test(rel) || rel.startsWith("lib/i18n/")) continue;
  const source = await readFile(file, "utf8");
  // Strip comments first: a prose comment is not shipped copy.
  const code = source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

  // (2) Leaked keys: a key printed as JSX text, or sitting in a user-visible
  // attribute, means it was never passed through t().
  for (const [, text] of code.matchAll(JSX_TEXT)) {
    if (keys.has(text.trim())) leaks.push({ rel, key: text.trim(), where: "JSX-Text" });
  }
  for (const [, text] of code.matchAll(ATTR)) {
    if (keys.has(text.trim())) leaks.push({ rel, key: text.trim(), where: "Attribut" });
  }

  if (!rel.endsWith(".tsx") || MIGRATED.has(rel)) continue;
  const hits = new Set();
  for (const [, text] of code.matchAll(JSX_TEXT)) hits.add(text.trim());
  for (const [, text] of code.matchAll(ATTR)) hits.add(text.trim());
  if (hits.size) rows.push({ rel, count: hits.size });
}

rows.sort((a, b) => b.count - a.count || a.rel.localeCompare(b.rel));
const total = rows.reduce((sum, row) => sum + row.count, 0);

console.log(`${keys.size} catalogue keys. ${MIGRATED.size} files migrated.`);
console.log(`${total} hard-coded strings across ${rows.length} public files.\n`);
for (const { rel, count } of rows.slice(0, LIMIT)) {
  console.log(`${String(count).padStart(4)}  ${rel}`);
}
if (rows.length > LIMIT) console.log(`\n… and ${rows.length - LIMIT} more files (--limit ${rows.length} for all).`);

if (leaks.length) {
  console.error(`\nLeaked keys — these render as literal text, not as copy:`);
  for (const { rel, key, where } of leaks) console.error(`  ${rel}: ${key} (${where})`);
  process.exit(1);
}
console.log("\nNo leaked catalogue keys.");
