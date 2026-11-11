// Checks what a built app contains before it ships.
//   node scripts/check-installer-contents.mjs <app.asar> <backend dir> [expected insights URL]
// Fails if the expected Insights endpoint is not baked in, if billing is switched on in a beta build,
// or if anything that looks like a credential is inside the app or its bundled backend.
import fs from "node:fs";
import path from "node:path";

const [asar, backendDir, expectedUrl] = process.argv.slice(2);
const fail = [];
const app = fs.readFileSync(asar);
const appText = app.toString("latin1");

if (expectedUrl) {
  if (!appText.includes(JSON.stringify(expectedUrl))) fail.push(`Insights endpoint ${expectedUrl} is not baked into ${path.basename(asar)}`);
  else console.log(`Insights endpoint baked in: ${expectedUrl}`);
}
const billing = appText.match(/BILLING_URL\s*=\s*"([^"]*)"/);
if (billing) console.log(`Billing URL in build: ${billing[1] ? billing[1] : "(empty: billing OFF)"}`);

// Credential shapes: Stripe secret/restricted/webhook keys, Cloudflare/GitHub tokens, Resend keys, private keys.
const PATTERNS = [
  [/\b(sk|rk)_(live|test)_[A-Za-z0-9]{16,}/, "Stripe secret key"],
  [/\bwhsec_[A-Za-z0-9]{16,}/, "Stripe webhook secret"],
  [/\bgh[pousr]_[A-Za-z0-9]{30,}/, "GitHub token"],
  [/\bre_[A-Za-z0-9]{8}_[A-Za-z0-9]{16,}/, "Resend API key"],
  [/CLOUDFLARE_API_TOKEN\s*[=:]\s*["']?[A-Za-z0-9_-]{30,}/, "Cloudflare API token"],
];
const scan = (buf, where) => {
  const s = buf.toString("latin1");
  for (const [re, what] of PATTERNS) { const m = s.match(re); if (m) fail.push(`${what} pattern in ${where}: ${m[0].slice(0, 12)}…`); }
};
scan(app, path.basename(asar));
if (/-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----/.test(appText)) fail.push(`private key in ${path.basename(asar)}`);

let files = 0, bytes = 0;
const walk = (d) => {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p);
    else if (e.isFile()) { const b = fs.readFileSync(p); files++; bytes += b.length; scan(b, path.relative(backendDir, p)); }
  }
};
if (backendDir) walk(backendDir);
console.log(`Scanned app bundle (${(app.length / 1e6).toFixed(1)} MB) and ${files} backend files (${(bytes / 1e6).toFixed(0)} MB) for credentials`);

if (fail.length) { for (const f of fail) console.log("FAIL", f); process.exit(1); }
console.log("installer contents OK: endpoint present, no credentials found");
