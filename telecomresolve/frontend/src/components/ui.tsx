import { ReactNode, useEffect, useRef } from "react";
import { STATUS_LABEL, TONE_ICON, Tone, statusTone } from "../format";

export function Chip({ tone, children, title }: { tone: Tone; children: ReactNode; title?: string }) {
  return (
    <span className={`chip chip-${tone}`} title={title}>
      <span aria-hidden="true" className="chip-icon">{TONE_ICON[tone]}</span>
      {children}
    </span>
  );
}

export function StatusChip({ status }: { status: string }) {
  return <Chip tone={statusTone(status)}>{STATUS_LABEL[status] ?? status}</Chip>;
}

export function Card({ title, children, actions, className = "" }:
  { title?: ReactNode; children: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-head">
          {title && <h2>{title}</h2>}
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

export function ErrorNote({ error }: { error: string | null }) {
  if (!error) return null;
  return <p role="alert" className="error-note"><span aria-hidden="true">✕ </span>{error}</p>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("keydown", onKey); prev?.focus(); };
  }, [onClose]);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title} tabIndex={-1} ref={ref}
           onClick={(e) => e.stopPropagation()}>
        <header className="card-head">
          <h2>{title}</h2>
          <button className="btn btn-ghost" onClick={onClose} aria-label="Close">Close</button>
        </header>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}
