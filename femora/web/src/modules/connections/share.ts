// Real, consent-first sharing: every channel opens the user's own app with a pre-filled message; nothing is sent
// automatically and no data leaves the browser until she presses send there.
export interface Contact { id: string; name: string; phone?: string; email?: string; role: string }

export const digits = (p?: string) => (p ?? "").replace(/[^\d]/g, "");
export const whatsappUrl = (text: string, phone?: string) => `https://wa.me/${digits(phone)}?text=${encodeURIComponent(text)}`;
export const emailUrl = (to: string | undefined, subject: string, body: string) => `mailto:${encodeURIComponent(to ?? "")}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
export const smsUrl = (phone: string | undefined, body: string) => `sms:${digits(phone)}?&body=${encodeURIComponent(body)}`;

export async function nativeShare(title: string, text: string): Promise<boolean> {
  if (!navigator.share) return false;
  try { await navigator.share({ title, text }); return true; } catch { return false; }
}

/** Contact Picker API (Chrome on Android). Returns [] when unsupported or cancelled. */
export async function pickContacts(): Promise<{ name: string; phone?: string; email?: string }[]> {
  const nav = navigator as Navigator & { contacts?: { select: (props: string[], opts: { multiple: boolean }) => Promise<{ name?: string[]; tel?: string[]; email?: string[] }[]> } };
  if (!nav.contacts?.select) return [];
  try {
    const res = await nav.contacts.select(["name", "tel", "email"], { multiple: true });
    return res.map((c) => ({ name: c.name?.[0] ?? "Contact", phone: c.tel?.[0], email: c.email?.[0] }));
  } catch { return []; }
}
export const contactPickerSupported = () => "contacts" in navigator && "ContactsManager" in window;
