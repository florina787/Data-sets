import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { Logo } from "../components/ui";
import { Credit } from "../components/Credit";

export const SITE_NAV = [
  { to: "/features", label: "Features" }, { to: "/demo", label: "Demo" }, { to: "/club", label: "Sisterhood" },
  { to: "/how-it-works", label: "How it works" }, { to: "/gallery", label: "Gallery" }, { to: "/pricing", label: "Pricing" }, { to: "/trust", label: "Science & trust" },
];

export function SiteLayout({ children, dark = false }: { children: ReactNode; dark?: boolean }) {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const loc = useLocation();
  useEffect(() => { setOpen(false); window.scrollTo?.(0, 0); }, [loc.pathname]);
  useEffect(() => { const on = () => setScrolled(window.scrollY > 24); on(); addEventListener("scroll", on, { passive: true }); return () => removeEventListener("scroll", on); }, []);
  const light = dark && !scrolled && !open;
  return (
    <div className="site min-h-screen bg-[#f7f4ee] text-[#17140f]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[70] focus:rounded-full focus:bg-white focus:px-4 focus:py-2">Skip to content</a>
      <header className={`fixed inset-x-0 top-0 z-50 transition-colors ${light ? "bg-[#14110e]/90 text-[#f7f1e6] backdrop-blur" : "bg-[#f7f4ee]/90 text-[#17140f] shadow-[0_1px_0_rgba(23,20,15,0.08)] backdrop-blur"}`}>
        <nav className="mx-auto flex max-w-7xl items-center gap-6 px-5 py-4" aria-label="Main">
          <Link to="/" className="flex items-center gap-2" aria-label="FEMORA Muse home"><Logo size={28} /><span className="font-display text-2xl tracking-wide">FEMORA <span className={light ? "text-[#e7cf9f]" : "text-[#7c5f2b]"}>Muse</span></span></Link>
          <ul className="ml-auto hidden items-center gap-5 text-[15px] lg:flex">{SITE_NAV.map((n) => <li key={n.to}><NavLink to={n.to} className={({ isActive }) => `py-1 ${isActive ? "border-b border-current" : "opacity-85 hover:opacity-100"}`}>{n.label}</NavLink></li>)}</ul>
          <Link to="/app" className={`ml-auto hidden rounded-full px-5 py-2.5 text-sm font-medium lg:ml-2 lg:inline-flex ${light ? "bg-[#f7f1e6] text-[#17140f]" : "bg-[#17140f] text-[#f7f1e6]"}`}>Open the app</Link>
          <button className="ml-auto lg:hidden" aria-label={open ? "Close menu" : "Open menu"} aria-expanded={open} onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</button>
        </nav>
        {open && <ul className="border-t border-black/5 bg-[#f7f4ee] px-5 pb-6 pt-2 text-lg text-[#17140f] lg:hidden">{SITE_NAV.map((n) => <li key={n.to}><NavLink to={n.to} className="block py-3">{n.label}</NavLink></li>)}
          <li className="pt-3"><Link to="/app" className="inline-flex rounded-full bg-[#17140f] px-5 py-3 text-[#f7f1e6]">Open the app</Link></li></ul>}
      </header>
      <main id="main">{children}</main>
      <footer className="border-t border-[#17140f]/10 bg-[#f4f1ea]">
        <div className="mx-auto grid max-w-7xl gap-10 px-5 py-14 md:grid-cols-[1.4fr_1fr_1fr]">
          <div><div className="flex items-center gap-2"><Logo size={26} /><span className="font-display text-2xl">FEMORA <span className="text-[#7c5f2b]">Muse</span></span></div>
            <p className="mt-3 max-w-sm text-[15px] text-[#5a544b]">A private companion for women's health, menopause and life. It supports, and never replaces, professional medical care.</p>
            <p className="mt-3 text-sm text-[#5a544b]">In an emergency, call your local emergency number.</p></div>
          <div><h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-[#7c5f2b]">Explore</h2><ul className="mt-3 space-y-2 text-[15px]">{SITE_NAV.map((n) => <li key={n.to}><Link to={n.to}>{n.label}</Link></li>)}</ul></div>
          <div><h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-[#7c5f2b]">Open source</h2><ul className="mt-3 space-y-2 text-[15px]">
            <li><a href="https://github.com/florina787/femora" rel="noopener">Source code</a></li><li><Link to="/app">Open the app</Link></li><li><Link to="/trust">Privacy & limits</Link></li></ul></div>
        </div>
        <div className="border-t border-[#17140f]/10 py-6 text-center"><Credit /></div>
      </footer>
    </div>
  );
}

export function Eyebrow({ children, light = false }: { children: ReactNode; light?: boolean }) {
  return <p className={`text-sm font-semibold uppercase tracking-[0.3em] ${light ? "text-[#e7cf9f]" : "text-[#7c5f2b]"}`}>{children}</p>;
}
export function StatusPill({ s, onDark = false }: { s: "live" | "preview" | "soon"; onDark?: boolean }) {
  const m = onDark
    ? { live: ["Available now", "bg-[#7cc79c]/20 text-[#bfe6cf]"], preview: ["Interactive preview", "bg-[#d7b57a]/20 text-[#ecd9ae]"], soon: ["Coming soon", "bg-white/15 text-[#f7f1e6]"] }[s]
    : { live: ["Available now", "bg-[#2f6a4a]/12 text-[#2f6a4a]"], preview: ["Interactive preview", "bg-[#7c5f2b]/12 text-[#6a4f22]"], soon: ["Coming soon", "bg-[#17140f]/8 text-[#4a443c]"] }[s];
  return <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wider ${m[1]}`}>{m[0]}</span>;
}
