// Creator credit shown in every footer, at the creator's request.
export const CREATOR = { name: "Florina Regius", email: "florinaregius@yahoo.com" };

export function Credit({ className = "" }: { className?: string }) {
  return (
    <p className={`text-xs text-muted ${className}`}>
      Created by {CREATOR.name} · <a className="underline" href={`mailto:${CREATOR.email}`}>{CREATOR.email}</a>
    </p>
  );
}
