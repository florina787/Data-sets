import React, { useCallback, useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import "./index.css";

type Problem = { status: number; error: string; message: string; details?: any };

const money = (cents: number) => `$${(cents / 100).toFixed(2)}`;

function storage(key: string, value?: string | null): string | null {
  try {
    if (value === undefined) return localStorage.getItem(key);
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* private mode: cart lasts for this page only */
  }
  return null;
}

async function call(path: string, customer: string | null, init: RequestInit = {}) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (customer) headers["X-Demo-Customer"] = customer;
  const response = await fetch(path, { ...init, headers });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw { status: response.status, error: body.error ?? "error", message: body.message ?? (response.status >= 500 ? "The store hit an unexpected server error." : response.statusText), details: body.details } as Problem;
  }
  return body;
}

function App() {
  const [meta, setMeta] = useState<any>(null);
  const [catalog, setCatalog] = useState<any>(null);
  const [customers, setCustomers] = useState<any[]>([]);
  const [campaign, setCampaign] = useState<any>(null);
  const [customer, setCustomer] = useState<string | null>(storage("fs.customer"));
  const [cart, setCart] = useState<any>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [order, setOrder] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [code, setCode] = useState("");
  const [freeSku, setFreeSku] = useState("FS-ORANGE-355");
  const [card, setCard] = useState("tok_demo_ok");
  const [down, setDown] = useState(false);

  const cartKey = `fs.cart.${customer ?? "guest"}`;

  const load = useCallback(async () => {
    try {
      const [m, c, cu] = await Promise.all([call("/api/meta", null), call("/api/catalog", null), call("/api/customers", null)]);
      setMeta(m); setCatalog(c); setCustomers(cu.customers); setDown(false);
      setCampaign(m.features.campaign ? await call("/api/campaign", null) : null);
    } catch {
      setDown(true);
    }
  }, []);

  const ensureCart = useCallback(async () => {
    const saved = storage(cartKey);
    if (saved) {
      try {
        const existing = await call(`/api/carts/${saved}`, customer);
        if (existing.status === "open") { setCart(existing); return; }
      } catch { /* start a new cart */ }
    }
    const created = await call("/api/carts", customer, { method: "POST" });
    storage(cartKey, created.cart_id);
    setCart(created);
  }, [cartKey, customer]);

  useEffect(() => { load(); const id = setInterval(load, 10000); return () => clearInterval(id); }, [load]);
  useEffect(() => { if (meta) ensureCart().catch((e) => setProblem(e)); }, [meta?.revision, customer]);

  const act = async (fn: () => Promise<any>, success?: string) => {
    setBusy(true); setProblem(null); setNotice(null);
    try {
      const result = await fn();
      if (result?.quote) setCart(result);
      if (success) setNotice(success);
      return result;
    } catch (e) {
      setProblem(e as Problem);
      if (cart) call(`/api/carts/${cart.cart_id}`, customer).then(setCart).catch(() => undefined);
    } finally {
      setBusy(false);
    }
  };

  const q = cart?.quote;
  const qty = (sku: string) => q?.lines.find((l: any) => l.sku === sku && !l.is_free)?.qty ?? 0;
  const setQty = (sku: string, n: number) => act(() => call(`/api/carts/${cart.cart_id}/lines/${sku}`, customer, { method: "PUT", body: JSON.stringify({ qty: Math.max(0, n) }) }));
  const promo = q?.promotion;

  if (down) {
    return <div className="mx-auto max-w-xl p-8"><div className="card"><h1 className="text-xl font-semibold">Store unavailable</h1><p className="mt-2 text-sm">The storefront API is not answering. It may be restarting during a deployment. This page retries every 10 seconds.</p></div></div>;
  }

  return (
    <div>
      <div className="bg-amber-100 px-4 py-1 text-center text-xs font-semibold text-amber-700" role="note">DEMO STORE: synthetic products and customers, mock payments only. Nothing is charged or shipped.</div>
      <header className="bg-leaf-700 px-4 py-3 text-cream-50">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3">
          <div><div className="text-xl font-bold">FreshSip</div><div className="text-xs text-leaf-100">Food Beverage Food Care (fictional) online store</div></div>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <label htmlFor="cust" className="text-xs">Customer fixture</label>
            <select id="cust" className="rounded border border-leaf-500 bg-leaf-600 px-2 py-1" value={customer ?? ""} onChange={(e) => { const v = e.target.value || null; storage("fs.customer", v); setCustomer(v); setOrder(null); setProblem(null); }}>
              <option value="">Guest (not signed in)</option>
              {customers.map((c) => <option key={c.id} value={c.token}>{c.display_name}</option>)}
            </select>
          </div>
        </div>
        <div className="mx-auto mt-1 max-w-6xl text-[11px] text-leaf-100">
          Release {meta?.release_id} · revision <span className="font-mono">{meta?.revision?.slice(0, 10)}</span> · code v{meta?.code_version} · demo clock {meta?.clock?.now}{meta?.clock?.fixed ? " (fixed)" : ""}
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl gap-4 p-4 lg:grid-cols-3">
        <section className="space-y-4 lg:col-span-2" aria-label="Products">
          {campaign ? (
            <div className="card border-leaf-500 bg-leaf-100">
              <h2 className="text-lg font-semibold text-leaf-700">{campaign.name}</h2>
              <p className="text-sm">Buy 2 FreshSip Mango, Orange or Apple, get 1 free. Ontario shipping only. Signed-in customers only, once per campaign. Cannot be combined with discount codes. While stock lasts.</p>
              <p className="mt-1 text-xs text-navy-700">Runs {campaign.start_local.replace("T", " ")} to {campaign.end_local_exclusive.replace("T", " ")} (end exclusive) {campaign.timezone} · UTC {campaign.window_utc.join(" → ")} · {campaign.active_now ? "active now" : "not active now"}</p>
            </div>
          ) : (
            <div className="card text-sm text-navy-700">No campaign in this release.</div>
          )}
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {catalog?.products.map((p: any) => (
              <article key={p.sku} className="card flex flex-col">
                <div className="text-xs text-navy-600">{p.brand} · {p.size}</div>
                <h3 className="font-semibold">{p.name}</h3>
                <div className="font-mono text-xs text-navy-600">{p.sku}</div>
                {campaign?.eligible_skus.includes(p.sku) && <span className="mt-1 w-fit rounded bg-leaf-100 px-1.5 text-[11px] font-semibold text-leaf-700">Campaign eligible</span>}
                <div className="mt-auto flex items-center justify-between pt-3">
                  <span className="text-lg font-semibold">{money(p.price_cents)}</span>
                  <div className="flex items-center gap-1">
                    <button className="btn-ghost" aria-label={`Remove one ${p.name}`} disabled={busy || !cart || qty(p.sku) === 0} onClick={() => setQty(p.sku, qty(p.sku) - 1)}>−</button>
                    <span className="w-6 text-center" aria-label={`${p.name} quantity`}>{qty(p.sku)}</span>
                    <button className="btn-green" aria-label={`Add one ${p.name}`} disabled={busy || !cart} onClick={() => setQty(p.sku, qty(p.sku) + 1)}>+</button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>

        <aside className="space-y-4" aria-label="Cart">
          <div className="card">
            <h2 className="text-lg font-semibold">Cart</h2>
            {!q ? <p className="text-sm">Loading cart…</p> : (
              <>
                {q.lines.length === 0 ? <p className="text-sm text-navy-600">Your cart is empty.</p> : (
                  <ul className="mt-2 space-y-1 text-sm">
                    {q.lines.map((l: any) => (
                      <li key={`${l.sku}-${l.is_free}`} className="flex justify-between gap-2">
                        <span>{l.qty} × {l.name}{l.is_free && <span className="ml-1 rounded bg-leaf-100 px-1 text-[11px] font-semibold text-leaf-700">FREE</span>}</span>
                        <span className="font-mono">{money(l.line_total_cents)}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {q.messages.map((m: string) => <p key={m} role="status" className="mt-2 rounded bg-amber-100 px-2 py-1 text-xs text-amber-700">{m}</p>)}
                <div className="mt-3 space-y-2 text-sm">
                  <label className="flex items-center justify-between gap-2">Ship to province
                    <select className="rounded border border-cream-300 px-1 py-1" value={q.province ?? ""} disabled={busy}
                      onChange={(e) => act(() => call(`/api/carts/${cart.cart_id}/shipping`, customer, { method: "PUT", body: JSON.stringify({ province: e.target.value || null }) }))}>
                      <option value="">Select…</option>
                      {catalog?.provinces.map((p: string) => <option key={p}>{p}</option>)}
                    </select>
                  </label>
                  {promo && (
                    <div className="rounded-lg border border-cream-300 bg-cream-50 p-2">
                      <div className="text-xs font-semibold">Buy 2, get 1 free: {promo.entitled ? <span className="text-leaf-700">eligible</span> : promo.free_unit_in_cart ? <span className="text-leaf-700">free unit in cart</span> : <span className="text-navy-600">not eligible yet</span>}</div>
                      {promo.reason_text.length > 0 && <ul className="list-disc pl-4 text-xs text-navy-700">{promo.reason_text.map((t: string) => <li key={t}>{t}</li>)}</ul>}
                      {!promo.free_unit_in_cart ? (
                        <div className="mt-1 flex items-center gap-1">
                          <label htmlFor="free" className="sr-only">Free flavour</label>
                          <select id="free" className="rounded border border-cream-300 px-1 py-0.5 text-xs" value={freeSku} onChange={(e) => setFreeSku(e.target.value)}>
                            {promo.eligible_skus.map((s: string) => <option key={s} value={s}>{s}</option>)}
                          </select>
                          <button className="btn-green" disabled={busy || !promo.entitled} onClick={() => act(() => call(`/api/carts/${cart.cart_id}/free-unit`, customer, { method: "POST", body: JSON.stringify({ sku: freeSku }) }), "Free unit added.")}>Add free unit</button>
                        </div>
                      ) : (
                        <button className="btn-ghost mt-1" disabled={busy} onClick={() => act(() => call(`/api/carts/${cart.cart_id}/free-unit`, customer, { method: "DELETE" }))}>Remove free unit</button>
                      )}
                    </div>
                  )}
                  <form className="flex gap-1" onSubmit={(e) => { e.preventDefault(); act(() => call(`/api/carts/${cart.cart_id}/discount`, customer, { method: "PUT", body: JSON.stringify({ code }) })); }}>
                    <label htmlFor="code" className="sr-only">Discount code</label>
                    <input id="code" placeholder="Discount code (try WELCOME10)" className="min-w-0 flex-1 rounded border border-cream-300 px-2 py-1 text-xs" value={code} onChange={(e) => setCode(e.target.value)} />
                    <button className="btn-ghost" disabled={busy || !code}>Apply</button>
                    {q.discount_code && <button type="button" className="btn-ghost" disabled={busy} onClick={() => act(() => call(`/api/carts/${cart.cart_id}/discount`, customer, { method: "DELETE" }))}>Remove {q.discount_code}</button>}
                  </form>
                  <div className="border-t border-cream-300 pt-2">
                    <div className="flex justify-between"><span>Subtotal</span><span className="font-mono">{money(q.subtotal_cents)}</span></div>
                    {q.discount_cents > 0 && <div className="flex justify-between"><span>Discount ({q.discount_code})</span><span className="font-mono">−{money(q.discount_cents)}</span></div>}
                    <div className="flex justify-between text-base font-semibold"><span>Total</span><span className="font-mono">{money(q.total_cents)}</span></div>
                    <p className="text-[11px] text-navy-600">Taxes and shipping are not modelled in this demo.</p>
                  </div>
                  <label className="flex items-center justify-between gap-2 text-xs">Mock card
                    <select className="rounded border border-cream-300 px-1 py-1" value={card} onChange={(e) => setCard(e.target.value)}>
                      <option value="tok_demo_ok">Approves (tok_demo_ok)</option>
                      <option value="tok_demo_decline">Declines (tok_demo_decline)</option>
                    </select>
                  </label>
                  <button className="btn-primary w-full" disabled={busy || q.lines.length === 0}
                    onClick={async () => {
                      const result = await act(() => call(`/api/carts/${cart.cart_id}/checkout`, customer, { method: "POST", body: JSON.stringify({ payment_token: card, idempotency_key: `ui-${cart.cart_id}-${Date.now()}` }) }));
                      if (result?.order) { setOrder(result.order); storage(cartKey, null); await ensureCart(); }
                    }}>
                    {busy ? "Working…" : "Place order (mock payment)"}
                  </button>
                </div>
              </>
            )}
            {problem && (
              <div role="alert" className="mt-3 rounded-lg border border-brick-700/30 bg-brick-100 p-2 text-sm text-brick-700">
                <b>{problem.status === 503 ? "Checkout temporarily unavailable" : `Error ${problem.status}`}</b>: {problem.message}
                {problem.details?.reason_text && <ul className="list-disc pl-4 text-xs">{problem.details.reason_text.map((t: string) => <li key={t}>{t}</li>)}</ul>}
              </div>
            )}
            {notice && <p role="status" className="mt-2 text-xs text-leaf-700">{notice}</p>}
          </div>

          {order && <OrderCard order={order} customer={customer} onChange={setOrder} />}
        </aside>
      </main>
    </div>
  );
}

function OrderCard({ order, customer, onChange }: { order: any; customer: string | null; onChange: (o: any) => void }) {
  const [problem, setProblem] = useState<string | null>(null);
  const act = (fn: () => Promise<any>) => fn().then((r) => { onChange(r.order); setProblem(null); }).catch((e) => setProblem(e.message));
  const returnable = order.units.filter((u: any) => !u.returned);
  return (
    <div className="card" aria-label="Order result">
      <h2 className="text-lg font-semibold">Order {order.id}</h2>
      <div className="text-sm">Status: <b>{order.status}</b> · total {money(order.total_cents)} · refunded {money(order.refunded_cents)}</div>
      <div className="font-mono text-[11px] text-navy-600">{order.payment_ref ?? "no payment"} · reservation {order.reservation_id}</div>
      <table className="mt-2 w-full text-xs">
        <thead><tr className="text-left"><th>Unit</th><th>Paid (allocated)</th><th /></tr></thead>
        <tbody>
          {order.units.map((u: any) => (
            <tr key={u.unit_index} className={u.returned ? "text-navy-600 line-through" : ""}>
              <td>{u.sku}{u.is_free ? " (free)" : ""}{u.in_promo_group ? " · promo group" : ""}</td>
              <td className="font-mono">{money(u.paid_cents)} <span className="text-navy-600">of {money(u.list_price_cents)}</span></td>
              <td />
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-2 flex flex-wrap gap-2">
        <button className="btn-ghost" disabled={order.status !== "paid"} onClick={() => act(() => call(`/api/orders/${order.id}/cancel`, customer, { method: "POST" }))}>Cancel order</button>
        {returnable.length > 0 && ["paid", "partially_returned"].includes(order.status) && (
          <button className="btn-ghost" onClick={() => act(() => call(`/api/orders/${order.id}/returns`, customer, { method: "POST", body: JSON.stringify({ items: { [returnable[0].sku]: 1 } }) }))}>
            Return one {returnable[0].sku}
          </button>
        )}
      </div>
      {order.refunds.length > 0 && <ul className="mt-2 text-xs">{order.refunds.map((r: any) => <li key={r.id}>{r.kind}: {money(r.amount_cents)}</li>)}</ul>}
      {problem && <p role="alert" className="mt-2 text-xs text-brick-700">{problem}</p>}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
