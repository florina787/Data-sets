// Pricing page: tabs, plan selection, sign-in and Stripe Checkout through the VEENA Billing Worker.
// Payment status is always read back from the server: reaching the success URL proves nothing.
(function () {
  "use strict";
  var cfg = window.VEENA_CONFIG || {};
  var API = typeof cfg.billingUrl === "string" && /^https:\/\//.test(cfg.billingUrl) ? cfg.billingUrl.replace(/\/$/, "") : null;
  var $ = function (id) { return document.getElementById(id); };
  if (cfg.billingTestMode !== false && API) $("testmode").hidden = false;

  var PRICES = {
    unlimited_monthly: { label: "Get Unlimited — $74.95/month", price: "$74.95", per: "USD / month", note: "Billed monthly. Cancel anytime." },
    unlimited_annual: { label: "Get Unlimited — $299.95/year", price: "$299.95", per: "USD / year", note: "Billed yearly: about $25.00 a month. Cancel anytime." },
    credits_1: { label: "Buy 1 Credit — $19.00" }, credits_3: { label: "Buy 3 Credits — $29.50" },
    credits_8: { label: "Buy 8 Credits — $59.00" }, credits_15: { label: "Buy 15 Credits — $88.50" },
  };
  var selected = { unlimited: "unlimited_monthly", credits: "credits_3" };

  // ---- tabs (WAI-ARIA tabs pattern: arrow keys move, Enter/Space or focus selects) ----
  var tabs = [].slice.call(document.querySelectorAll('[role="tab"]'));
  function selectTab(t, focus) {
    tabs.forEach(function (x) {
      var on = x === t;
      x.setAttribute("aria-selected", String(on)); x.tabIndex = on ? 0 : -1;
      $(x.getAttribute("aria-controls")).hidden = !on;
    });
    if (focus) t.focus();
  }
  tabs.forEach(function (t, i) {
    t.addEventListener("click", function () { selectTab(t); });
    t.addEventListener("keydown", function (e) {
      var k = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (e.key === "Home") { e.preventDefault(); selectTab(tabs[0], true); }
      if (e.key === "End") { e.preventDefault(); selectTab(tabs[tabs.length - 1], true); }
      if (k) { e.preventDefault(); selectTab(tabs[(i + k + tabs.length) % tabs.length], true); }
    });
  });

  // ---- radio groups ----
  function radios(group, onPick) {
    var items = [].slice.call(group.querySelectorAll('[role="radio"]'));
    function pick(it, focus) {
      items.forEach(function (x) { var on = x === it; x.setAttribute("aria-checked", String(on)); x.tabIndex = on ? 0 : -1; });
      if (focus) it.focus();
      onPick(it.getAttribute("data-plan"));
    }
    items.forEach(function (it, i) {
      it.tabIndex = it.getAttribute("aria-checked") === "true" ? 0 : -1;
      it.addEventListener("click", function () { pick(it); });
      it.addEventListener("keydown", function (e) {
        var k = /Right|Down/.test(e.key) ? 1 : /Left|Up/.test(e.key) ? -1 : 0;
        if (k) { e.preventDefault(); pick(items[(i + k + items.length) % items.length], true); }
      });
    });
  }
  radios(document.querySelector(".seg2"), function (plan) {
    selected.unlimited = plan; var p = PRICES[plan];
    $("u-price").textContent = p.price; $("u-per").textContent = p.per; $("u-note").textContent = p.note;
    document.querySelector('[data-buy="unlimited"]').textContent = p.label;
  });
  radios(document.querySelector(".packs"), function (plan) {
    selected.credits = plan; document.querySelector('[data-buy="credits"]').textContent = PRICES[plan].label;
  });

  // ---- purchase ----
  var status = $("buy-status");
  function say(text) { status.hidden = false; status.textContent = text; }
  function token() { try { return sessionStorage.getItem("veena-billing-token"); } catch (e) { return null; } }
  function installId() {
    try { var v = sessionStorage.getItem("veena-web-install") || crypto.randomUUID(); sessionStorage.setItem("veena-web-install", v); return v; } catch (e) { return crypto.randomUUID(); }
  }
  function api(path, method, body) {
    var h = { "content-type": "application/json" }; var t = token(); if (t) h.authorization = "Bearer " + t;
    return fetch(API + path, { method: method || "GET", headers: h, body: body ? JSON.stringify(body) : undefined, credentials: "omit" })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || "HTTP " + r.status); return j; }); });
  }
  var pending = null;
  document.querySelectorAll("[data-buy]").forEach(function (b) {
    b.addEventListener("click", function () {
      var plan = selected[b.getAttribute("data-buy")];
      if (!API) { say("Payments are not open yet. Your free uses are already included in the app."); return; }
      pending = plan;
      if (!token()) { $("signin").showModal(); $("si-email").focus(); return; }
      go(plan);
    });
  });
  function go(plan) {
    say("Opening secure checkout…");
    api("/v1/checkout", "POST", { package: plan }).then(function (r) { location.assign(r.url); })
      .catch(function (e) { say("Could not start checkout: " + e.message); });
  }
  var stage = "email";
  $("si-form").addEventListener("submit", function (e) {
    if (e.submitter && e.submitter.value === "cancel") return;
    e.preventDefault();
    var err = $("si-err"); err.hidden = true;
    var email = $("si-email").value.trim();
    var p = stage === "email" ? api("/v1/auth/start", "POST", { email: email, install_id: installId() }).then(function () {
      stage = "code"; $("si-code-row").hidden = false; $("si-go").textContent = "Sign in"; $("si-code").focus();
    }) : api("/v1/auth/verify", "POST", { email: email, code: $("si-code").value.trim(), install_id: installId() }).then(function (r) {
      try { sessionStorage.setItem("veena-billing-token", r.token); } catch (x) {}
      $("signin").close(); if (pending) go(pending);
    });
    p.catch(function (x) { err.textContent = x.message; err.hidden = false; });
  });

  // ---- back from Stripe: confirm with the server, never with the URL ----
  var q = new URLSearchParams(location.search);
  if (q.get("checkout") === "cancelled") say("Checkout cancelled. You have not been charged.");
  if (q.get("checkout") === "success" && API && token()) {
    say("Confirming your payment with the server…");
    var tries = 0;
    (function poll() {
      api("/v1/me").then(function (me) {
        if (me.unlimited) return say("Payment confirmed. VEENA Unlimited (" + me.plan + ") is active.");
        if (me.credit_minutes > 0) return say("Payment confirmed. Credit balance: " + me.credit_minutes + " minutes.");
        if (++tries < 15) return setTimeout(poll, 2000);
        say("We have not received confirmation from Stripe yet. If you were charged, your balance will update shortly; nothing is unlocked until it does.");
      }).catch(function () { say("Could not check your balance just now. Please refresh in a moment."); });
    })();
  }
})();
