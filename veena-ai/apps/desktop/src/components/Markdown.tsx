import { Check, Copy } from "lucide-react";
import { memo, useEffect, useId, useRef, useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

function textOf(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  if (node && typeof node === "object" && "props" in node) return textOf((node as { props: { children?: ReactNode } }).props.children);
  return "";
}

export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setDone(true);
        setTimeout(() => setDone(false), 1500);
      }}
      className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-sand hover:bg-bark hover:text-white"
      aria-label={label}
    >
      {done ? <Check size={13} /> : <Copy size={13} />}
      {done ? "Copied" : label}
    </button>
  );
}

let mermaidReady: Promise<typeof import("mermaid").default> | null = null;
function loadMermaid() {
  mermaidReady ??= import("mermaid").then((m) => {
    m.default.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: "base",
      fontFamily: "Inter Variable, Inter, sans-serif",
      themeVariables: {
        background: "#FFFFFF",
        primaryColor: "#F7F1E9",
        primaryBorderColor: "#99613E",
        primaryTextColor: "#2C1A12",
        secondaryColor: "#EFE2D2",
        tertiaryColor: "#FCFAF7",
        lineColor: "#75462D",
        textColor: "#4A2C1C",
        noteBkgColor: "#EFE2D2",
        noteTextColor: "#4A2C1C",
        noteBorderColor: "#B87848",
        actorBkg: "#F7F1E9",
        actorBorder: "#99613E",
        signalColor: "#75462D",
        clusterBkg: "#FCFAF7",
        clusterBorder: "#D6B79B",
      },
    });
    return m.default;
  });
  return mermaidReady;
}

function Mermaid({ code }: { code: string }) {
  const id = useId().replace(/[^a-zA-Z0-9]/g, "");
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    loadMermaid()
      .then((m) => m.render(`mmd-${id}`, code))
      .then(({ svg }) => {
        if (alive && ref.current) ref.current.innerHTML = svg;
      })
      .catch((e) => alive && setError(String(e?.message ?? e)));
    return () => {
      alive = false;
    };
  }, [code, id]);
  if (error) return <pre className="rounded-xl bg-espresso p-4 text-xs text-cream">{code}</pre>;
  return <div ref={ref} className="my-2 overflow-x-auto rounded-xl border border-cream bg-white p-3" aria-label="Diagram" />;
}

export const Markdown = memo(function Markdown({ text, streaming }: { text: string; streaming?: boolean }) {
  return (
    <div className="prose-veena">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
        components={{
          a: ({ href, children }) => (
            <a
              href={href}
              onClick={(e) => {
                e.preventDefault();
                if (href?.startsWith("https://")) void window.veena?.openExternal(href);
              }}
            >
              {children}
            </a>
          ),
          pre: ({ children }) => {
            const child = Array.isArray(children) ? children[0] : children;
            const cls = (child as { props?: { className?: string } })?.props?.className ?? "";
            const lang = /language-(\w+)/.exec(cls)?.[1];
            const code = textOf(children).replace(/\n$/, "");
            if (lang === "mermaid" && !streaming) return <Mermaid code={code} />;
            return (
              <div className="group my-3 overflow-hidden rounded-xl bg-espresso">
                <div className="flex items-center justify-between border-b border-bark px-3 py-1.5">
                  <span className="font-mono text-[11px] uppercase tracking-wide text-sand">{lang ?? "code"}</span>
                  <CopyButton text={code} />
                </div>
                <pre className="overflow-x-auto p-4 font-mono text-[13px] leading-relaxed">{children}</pre>
              </div>
            );
          },
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
});
