// Development launcher: Vite dev server for the renderer, tsc for the main
// process, then Electron pointed at the dev server.
import { spawn, spawnSync } from "node:child_process";
import { createServer } from "vite";

const tsc = spawnSync("npx", ["tsc", "-p", "electron/tsconfig.json"], { stdio: "inherit", shell: process.platform === "win32" });
if (tsc.status !== 0) process.exit(tsc.status ?? 1);

const server = await createServer();
await server.listen();
const url = server.resolvedUrls.local[0];
console.log(`renderer dev server at ${url}`);

const electronBin = (await import("electron")).default;
const child = spawn(electronBin, ["."], { stdio: "inherit", env: { ...process.env, VITE_DEV_SERVER_URL: url } });
child.on("exit", async (code) => {
  await server.close();
  process.exit(code ?? 0);
});
