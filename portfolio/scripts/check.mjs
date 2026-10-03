#!/usr/bin/env node
// Pre-deploy checks (no dependencies):
//   1. Secret scan: fails on anything that looks like a real credential.
//   2. Placeholder report: warns (does not fail) while contact placeholders remain.
//   3. Demo labelling: every simulated-metrics section must carry a DEMO/SIMULATED label.
//
//   node scripts/check.mjs [dir ...]     (default: the portfolio folder)
import { readdir, readFile, stat } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { CONFIG, isPlaceholder } from '../assets/js/config.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SKIP_DIRS = new Set(['.git', 'node_modules', 'dist', '.venv', '__pycache__']);
const TEXT_EXT = /\.(html?|css|m?js|json|md|txt|ya?ml|toml|py|sh|env|example|cfg|ini|xml|svg)$|^\.env/i;
const SELF = fileURLToPath(import.meta.url);

// Each rule matches a credential-looking VALUE, not merely the variable name.
const RULES = [
  ['OpenAI / Anthropic style key', /\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}/],
  ['ANTHROPIC_API_KEY with value', /ANTHROPIC_API_KEY\s*[=:]\s*["']?(?!\s|$|["']|your|<|\$\{)[^\s"'#]{8,}/],
  ['OPENAI_API_KEY with value', /OPENAI_API_KEY\s*[=:]\s*["']?(?!\s|$|["']|your|<|\$\{)[^\s"'#]{8,}/],
  ['Generic API_KEY with value', /\bAPI_KEY\s*=\s*["']?(?!\s|$|["']|your|<|\$\{)[^\s"'#]{12,}/],
  ['api_key assignment', /\bapi_key\s*[:=]\s*["'][A-Za-z0-9_\-]{16,}["']/i],
  ['AWS access key id', /\b(?:AKIA|ASIA)[0-9A-Z]{16}\b/],
  ['AWS_ACCESS_KEY with value', /AWS_ACCESS_KEY(?:_ID)?\s*[=:]\s*["']?[A-Z0-9]{16,}/],
  ['AWS_SECRET with value', /AWS_SECRET(?:_ACCESS_KEY)?\s*[=:]\s*["']?[A-Za-z0-9/+]{30,}/],
  ['GitHub token', /\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}/],
  ['Slack token', /\bxox[abprs]-[A-Za-z0-9-]{10,}/],
  ['Private key block', /-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----/],
];

async function* walk(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    if (SKIP_DIRS.has(entry.name)) continue;
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(p);
    else if (TEXT_EXT.test(entry.name)) yield p;
  }
}

async function scanSecrets(dirs) {
  const findings = [];
  let files = 0;
  for (const dir of dirs) {
    for await (const file of walk(dir)) {
      if (file === SELF) continue;
      if ((await stat(file)).size > 5_000_000) continue;
      files += 1;
      const lines = (await readFile(file, 'utf8')).split('\n');
      lines.forEach((line, i) => {
        for (const [name, re] of RULES) {
          if (re.test(line)) findings.push(`${path.relative(process.cwd(), file)}:${i + 1}  ${name}`);
        }
      });
    }
  }
  return { findings, files };
}

async function checkDemoLabels() {
  const html = await readFile(path.join(ROOT, 'index.html'), 'utf8');
  const problems = [];
  const need = { observability: /DEMO TELEMETRY/, rag: /Local simulation/i, 'agent-lab': /Local simulation/i, mcp: /Simulated/i, cost: /Illustrative/i };
  for (const [id, re] of Object.entries(need)) {
    const start = html.indexOf(`id="${id}"`);
    const section = start === -1 ? '' : html.slice(start, html.indexOf('</section>', start));
    if (!re.test(section)) problems.push(`#${id} is missing a ${re} label`);
  }
  return problems;
}

async function main() {
  const dirs = process.argv.slice(2).length ? process.argv.slice(2).map((d) => path.resolve(d)) : [ROOT];
  let failed = false;

  const { findings, files } = await scanSecrets(dirs);
  if (findings.length) {
    failed = true;
    console.error(`✗ secret scan: ${findings.length} suspicious match(es)`);
    findings.forEach((f) => console.error(`    ${f}`));
  } else {
    console.log(`✓ secret scan: ${files} files, no credential-like values found`);
  }

  const labels = await checkDemoLabels();
  if (labels.length) { failed = true; labels.forEach((l) => console.error(`✗ ${l}`)); }
  else console.log('✓ demo labelling: all simulated sections are labelled');

  const pending = ['GITHUB_USERNAME', 'LINKEDIN_URL', 'EMAIL_ADDRESS'].filter((k) => isPlaceholder(CONFIG[k]));
  if (isPlaceholder(CONFIG.SITE_URL)) pending.push('SITE_URL');
  if (pending.length) console.warn(`! placeholders still set in assets/js/config.js: ${pending.join(', ')} (links render as inert placeholders)`);
  else console.log('✓ contact placeholders configured');

  process.exit(failed ? 1 : 0);
}

main().catch((err) => { console.error(err); process.exit(1); });
