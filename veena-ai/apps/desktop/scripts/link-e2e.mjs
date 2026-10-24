// Lets the Playwright specs in ../../tests/e2e resolve @playwright/test from
// this package's node_modules (a junction on Windows, a symlink elsewhere).
import fs from "node:fs";
import path from "node:path";

const target = path.resolve(import.meta.dirname, "..", "node_modules");
const link = path.resolve(import.meta.dirname, "..", "..", "..", "tests", "node_modules");
try {
  fs.lstatSync(link);
} catch {
  fs.symlinkSync(target, link, process.platform === "win32" ? "junction" : "dir");
}
