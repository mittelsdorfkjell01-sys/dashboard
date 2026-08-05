import { readdir, stat } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const directory = fileURLToPath(new URL("../dist/assets/", import.meta.url));
const files = (await readdir(directory)).filter((name) => name.endsWith(".js"));
const sizes = await Promise.all(
  files.map(async (name) => ({ name, bytes: (await stat(join(directory, name))).size }))
);
const tooLarge = sizes.filter(({ bytes }) => bytes > 1_000_000);
const isAdminBuild = process.env.VITE_INCLUDE_ADMIN === "true";
const hasAdminChunk = files.some((name) => /admin/i.test(name));
if (!isAdminBuild && hasAdminChunk) {
  console.error("Public build contains an admin chunk.");
  process.exit(1);
}
if (isAdminBuild && !hasAdminChunk) {
  console.error("Admin build is missing its admin chunks.");
  process.exit(1);
}
if (tooLarge.length) {
  console.error(`Bundle budget exceeded: ${tooLarge.map(({ name, bytes }) => `${name} (${bytes} B)`).join(", ")}`);
  process.exit(1);
}
console.log(`Bundle budget ok. Largest chunk: ${Math.max(0, ...sizes.map(({ bytes }) => bytes))} B.`);
