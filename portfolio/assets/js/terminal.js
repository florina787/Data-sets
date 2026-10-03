// A tiny terminal with a fixed command table. There is no shell, eval or
// arbitrary execution: input is only matched against the keys of COMMANDS.
import { CONFIG, contactLinks } from './config.js';
import { esc } from './util.js';

const PROJECTS = [
  ['P-01', 'Enterprise Agentic AI Copilot', 'LangGraph · FastAPI · ChromaDB · Claude'],
  ['P-02', 'AI Engineering Lab (this site)', 'Vanilla JS · agent/RAG/MCP simulations'],
  ['P-03', 'Image Similarity with Siamese Networks', 'Keras · TensorFlow · metric learning'],
  ['P-04', 'Text Detection & OCR Pipelines', 'keras-ocr · TensorFlow'],
];

const AGENTIC = `
                 USER
                   │
                   ▼
            ORCHESTRATOR      intent · plan · budget
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
   RETRIEVAL   REASONING    TOOL       hybrid search · analysis · MCP
     AGENT       AGENT      AGENT
        └──────────┼──────────┘
                   ▼
              VALIDATOR       citations · grounding · PII
                   │
                   ▼
               RESPONSE`;

const RAG = `
 question → query processing → embedding
          → hybrid retrieval (BM25 + vector) → rerank
          → context builder (token budget) → LLM
          → grounded answer + citations`;

const SECTIONS = {
  approach: 'approach', agents: 'agent-lab', rag: 'rag', mcp: 'mcp', design: 'case-study', production: 'production',
  observability: 'observability', failures: 'failures', security: 'security', evaluation: 'evaluation',
  decisions: 'decisions', cost: 'cost', projects: 'projects', experience: 'experience', skills: 'skills', contact: 'contact',
};

export function initTerminal(ctx) {
  const body = document.getElementById('term-body');
  const out = document.getElementById('term-out');
  const input = document.getElementById('term-input');
  if (!out || !input) return;

  const history = [];
  let hIndex = 0;

  const print = (text, cls = '') => {
    const p = document.createElement('p');
    p.className = `term-line ${cls}`.trim();
    p.textContent = text;
    out.append(p);
    return p;
  };
  const printHtml = (html, cls = '') => {
    const p = document.createElement('p');
    p.className = `term-line ${cls}`.trim();
    p.innerHTML = html;
    out.append(p);
  };

  const COMMANDS = {
    help: {
      desc: 'list available commands',
      run: () => {
        print('Available commands:', 'acc');
        Object.entries(COMMANDS).forEach(([name, c]) => print(`  ${name.padEnd(24)} ${c.desc}`));
      },
    },
    whoami: {
      desc: 'who is Florina',
      run: () => {
        print(CONFIG.name, 'ok');
        print(`${CONFIG.title} | ${CONFIG.roles.slice(0, 2).join(' | ')}`);
        print(CONFIG.tagline, 'dim');
      },
    },
    'skills --core': {
      desc: 'core skills',
      run: () => ['Agentic AI', 'RAG', 'LLM Engineering', 'Enterprise AI Architecture', 'Python', 'AWS'].forEach((s) => print(`  ▸ ${s}`)),
    },
    skills: {
      desc: 'full skills map',
      run: () => {
        const map = {
          'core ai': 'Generative AI, Agentic AI, RAG, LLM Engineering, Prompt Engineering, ML',
          orchestration: 'LangChain, LangGraph, AutoGen, CrewAI, LlamaIndex',
          cloud: 'AWS, Azure, AWS Bedrock, SageMaker, Databricks',
          retrieval: 'FAISS, Chroma, Vector Search, Hybrid Search, Embeddings, Reranking',
          engineering: 'Python, FastAPI, REST, Docker, Kubernetes, Git, CI/CD',
          enterprise: 'MCP, OAuth, JWT, RBAC, Jira, Confluence, SharePoint, GitHub',
        };
        Object.entries(map).forEach(([k, v]) => print(`  ${k.padEnd(14)} ${v}`));
      },
    },
    'architecture --agentic': { desc: 'compact multi-agent architecture', run: () => print(AGENTIC, 'acc') },
    'architecture --rag': { desc: 'RAG pipeline', run: () => print(RAG, 'acc') },
    projects: {
      desc: 'featured projects',
      run: () => {
        PROJECTS.forEach(([id, name, stack]) => print(`  ${id}  ${name.padEnd(40)} ${stack}`));
        print('  → goto projects  for full case studies', 'dim');
      },
    },
    contact: {
      desc: 'contact links',
      run: () => {
        Object.values(contactLinks()).forEach((c) => {
          if (c.href) {
            const ext = c.href.startsWith('mailto:') ? '' : ' target="_blank" rel="noopener noreferrer"';
            printHtml(`  ${esc(c.label.padEnd(10))} <a href="${esc(c.href)}"${ext}>${esc(c.display)}</a>`);
          } else {
            print(`  ${c.label.padEnd(10)} ${c.display}  (placeholder: set in config.js)`, 'dim');
          }
        });
      },
    },
    'mode recruiter': { desc: 'switch to recruiter mode', run: () => { ctx.setView('recruiter', { announce: true }); print('view → recruiter', 'ok'); } },
    'mode engineer': { desc: 'switch to engineer mode', run: () => { ctx.setView('engineer', { announce: true }); print('view → engineer', 'ok'); } },
    'goto <section>': {
      desc: `jump to: ${Object.keys(SECTIONS).join(', ')}`,
      run: () => print('usage: goto <section>   e.g. goto rag', 'dim'),
    },
    clear: { desc: 'clear the screen', run: () => { out.innerHTML = ''; } },
  };

  function execute(raw) {
    const line = raw.trim().replace(/\s+/g, ' ');
    print(`$ ${line}`, 'cmd');
    if (!line) return;
    const lower = line.toLowerCase();
    if (lower === 'sudo' || lower.startsWith('sudo ')) { print('Nice try. This shell only runs predefined commands.', 'err'); return; }
    const go = lower.match(/^goto (\S+)$/);
    if (go) {
      const id = SECTIONS[go[1]];
      if (id && ctx.navigate(id)) print(`→ #${id}`, 'ok');
      else print(`unknown section "${go[1]}". Try: ${Object.keys(SECTIONS).join(', ')}`, 'err');
      return;
    }
    const cmd = COMMANDS[lower];
    if (cmd && !lower.includes('<')) cmd.run();
    else print(`command not found: ${line}. Type "help".`, 'err');
  }

  function submit(value) {
    execute(value);
    if (value.trim()) history.push(value.trim());
    hIndex = history.length;
    input.value = '';
    body.scrollTop = body.scrollHeight;
  }

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); submit(input.value); }
    else if (e.key === 'ArrowUp') { if (hIndex > 0) { hIndex -= 1; input.value = history[hIndex]; } e.preventDefault(); }
    else if (e.key === 'ArrowDown') { if (hIndex < history.length) { hIndex += 1; input.value = history[hIndex] ?? ''; } e.preventDefault(); }
    else if (e.key === 'Tab' && input.value.trim()) {
      const v = input.value.trim().toLowerCase();
      const names = [...Object.keys(COMMANDS).filter((n) => !n.includes('<')), ...Object.keys(SECTIONS).map((s) => `goto ${s}`)];
      const match = names.filter((n) => n.startsWith(v));
      if (match.length === 1) { e.preventDefault(); input.value = match[0]; }
      else if (match.length > 1) { e.preventDefault(); print(match.join('   '), 'dim'); body.scrollTop = body.scrollHeight; }
    } else if (e.key === 'l' && e.ctrlKey) { e.preventDefault(); out.innerHTML = ''; }
  });

  body.addEventListener('click', (e) => {
    if (!e.target.closest('a') && !window.getSelection()?.toString()) input.focus({ preventScroll: true });
  });
  document.querySelectorAll('.term-chips [data-cmd]').forEach((b) => b.addEventListener('click', () => submit(b.dataset.cmd)));

  // Greet with `whoami` so the first impression is informative even without interaction.
  submit('whoami');
}
