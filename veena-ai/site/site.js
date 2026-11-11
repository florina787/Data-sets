// VEENA.AI website behaviour. No trackers, no cookies, no third-party scripts.
(function () {
  "use strict";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Reveal sections as they enter the viewport.
  var items = document.querySelectorAll(".reveal");
  if (reduce || !("IntersectionObserver" in window)) {
    items.forEach(function (el) { el.classList.add("in"); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
    }, { rootMargin: "0px 0px -8% 0px" });
    items.forEach(function (el) { io.observe(el); });
  }

  // Reduced motion: videos stay on their poster frame.
  if (reduce) document.querySelectorAll("video[autoplay]").forEach(function (v) { v.removeAttribute("autoplay"); v.pause(); });

  // Feature page: open a demo video in a dialog.
  var dialog = document.getElementById("player");
  if (dialog) {
    var video = dialog.querySelector("video");
    document.querySelectorAll("[data-video]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        video.src = btn.getAttribute("data-video");
        video.setAttribute("aria-label", btn.getAttribute("data-label") || "VEENA demo");
        dialog.showModal();
        if (!reduce) video.play().catch(function () {});
      });
    });
    dialog.addEventListener("close", function () { video.pause(); video.removeAttribute("src"); video.load(); });
    dialog.querySelector("[data-close]").addEventListener("click", function () { dialog.close(); });
  }

  var cfg = window.VEENA_CONFIG || {};

  // Free vs paid-plan wording must match the app people can actually download.
  var plans = cfg.plansLive === true;
  document.querySelectorAll("[data-when]").forEach(function (el) { el.hidden = el.getAttribute("data-when") !== (plans ? "plans" : "free"); });

  // Community links appear only once the owner has enabled GitHub Discussions
  // (CI checks the repository's API before this can be switched on).
  var DISCUSSIONS = "https://github.com/florina787/Data-sets/discussions";
  document.querySelectorAll("[data-community]").forEach(function (a) {
    if (cfg.discussionsEnabled === true) { a.href = DISCUSSIONS; a.hidden = false; } else { a.remove(); }
  });
  var commP = document.getElementById("fb-community");
  if (commP && cfg.discussionsEnabled === true) { document.getElementById("fb-community-link").href = DISCUSSIONS; commP.hidden = false; }

  // Cloudflare Web Analytics: cookieless page-view counts, loaded only when the owner set a token.
  if (typeof cfg.cloudflareToken === "string" && /^[a-f0-9]{32}$/.test(cfg.cloudflareToken)) {
    var cf = document.createElement("script");
    cf.defer = true;
    cf.src = "https://static.cloudflareinsights.com/beacon.min.js";
    cf.setAttribute("data-cf-beacon", JSON.stringify({ token: cfg.cloudflareToken }));
    document.head.appendChild(cf);
  }

  // Campaign label from the link that brought the visitor (e.g. ?utm_campaign=linkedin-launch).
  // Only a short, plain label is kept; nothing about the visitor is read or stored.
  var campaign = (function () {
    try {
      var q = new URLSearchParams(location.search);
      var c = (q.get("utm_campaign") || q.get("ref") || "").toLowerCase();
      return /^[a-z0-9_-]{1,40}$/.test(c) ? c : "none";
    } catch (e) { return "none"; }
  })();

  // Feedback form: posts to VEENA Insights (/v1/feedback) when it is configured. No account, no
  // cookies; only what the person types. Until a server is configured it says so and offers email.
  var form = document.getElementById("fb-form");
  if (form) setupFeedback(form);

  function setupFeedback(form) {
    var url = typeof cfg.insightsUrl === "string" && /^https:\/\//.test(cfg.insightsUrl) ? cfg.insightsUrl.replace(/\/$/, "") : null;
    var started = Date.now();
    var bug = /(^|[?&])type=bug(&|$)/.test(location.search);
    var $ = function (id) { return document.getElementById(id); };
    if (bug) {
      $("fb-kind").value = "bug"; $("fb-rating-group").hidden = true; $("fb-worked-group").hidden = true; $("fb-next-group").hidden = true;
      $("fb-eyebrow").textContent = "Free public beta · Report a bug"; $("fb-title").innerHTML = 'Report a <span class="serif">bug.</span>';
      $("fb-lede").textContent = "Tell us what happened and what you expected. Include your operating system and VEENA version if you can.";
      $("fb-didnt-label").textContent = "What went wrong?"; $("fb-bug-link").textContent = "Share general feedback instead"; $("fb-bug-link").href = "feedback.html";
      $("fb-feature").value = "setup";
    }
    if (!url) { $("fb-fields").disabled = true; $("fb-pending").hidden = false; return; }
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var err = $("fb-error"); err.hidden = true;
      var rating = form.querySelector("input[name=rating]:checked");
      var body = { kind: $("fb-kind").value, feature: $("fb-feature").value, worked: $("fb-worked").value, didnt: $("fb-didnt").value, next: $("fb-next").value,
        email: $("fb-email").value.trim(), contact_ok: $("fb-contact").checked, website: $("fb-website").value, elapsed_ms: Date.now() - started };
      if (body.kind === "feedback") body.rating = rating ? Number(rating.value) : 0;
      if (!body.email) delete body.email;
      var problem = body.kind === "feedback" && !body.rating ? "Choose a rating from 1 to 5." :
        !(body.worked.trim() || body.didnt.trim() || body.next.trim()) ? "Write at least one answer." :
        body.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(body.email) ? "Check the email address, or leave it empty." : "";
      if (problem) { err.textContent = problem; err.hidden = false; return; }
      $("fb-submit").disabled = true; $("fb-submit").textContent = "Sending…";
      fetch(url + "/v1/feedback", { method: "POST", mode: "cors", credentials: "omit", referrerPolicy: "no-referrer", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })
        .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || "HTTP " + r.status); }); })
        .then(function () {
          form.innerHTML = '<div class="fb-done" role="status"><h2>Thank you.</h2><p class="fine">Your ' + (body.kind === "bug" ? "bug report" : "feedback") +
            ' reached us. It helps decide what VEENA does next.</p></div>';
        })
        .catch(function (e) {
          err.textContent = "Could not send just now (" + e.message + "). You can also write to florinaregius@yahoo.com.";
          err.hidden = false; $("fb-submit").disabled = false; $("fb-submit").textContent = "Send feedback";
        });
    });
  }

  // VEENA Insights counters: one anonymous count per page view / download click. No cookies, no
  // storage, no identifier; skipped when the browser sends Global Privacy Control or Do Not Track.
  var insights = typeof cfg.insightsUrl === "string" && /^https:\/\/[a-z0-9.-]+(\/[a-z0-9._-]*)*$/i.test(cfg.insightsUrl) ? cfg.insightsUrl.replace(/\/$/, "") : null;
  var optedOut = navigator.globalPrivacyControl === true || navigator.doNotTrack === "1";
  function count(body) {
    if (!insights || optedOut) return;
    try {
      fetch(insights + "/v1/web", { method: "POST", mode: "cors", credentials: "omit", keepalive: true, referrerPolicy: "no-referrer",
        headers: { "content-type": "application/json" }, body: JSON.stringify(body) }).catch(function () {});
    } catch (e) { /* counting must never affect the page */ }
  }
  (function () {
    var page = location.pathname.replace(/^\/Data-sets/, "") || "/";
    var ref = "";
    try { if (document.referrer) { var h = new URL(document.referrer).hostname; if (h !== location.hostname) ref = h; } } catch (e) {}
    count({ kind: "pageview", page: page, referrer: ref, campaign: campaign === "none" ? "" : campaign });
  })();

  // Download clicks: a page-local event with platform, version and campaign, for an analytics
  // tool that supports custom events if one is ever added. Today nothing leaves the page;
  // download totals come from GitHub's own per-file counts (site/tools/release_downloads.py).
  function trackDownload(os, version) {
    try { document.dispatchEvent(new CustomEvent("veena:download", { detail: { os: os, version: version, campaign: campaign } })); } catch (e) { /* old browser */ }
    count({ kind: "download_click", os: os === "mac" ? "macos" : os, campaign: campaign === "none" ? "" : campaign });
  }

  // Download: only offer files that exist in the newest PUBLISHED VEENA release.
  var title = document.getElementById("dl-title");
  if (!title) return;
  var REPO = "florina787/Data-sets";
  var RELEASES = "https://github.com/" + REPO + "/releases";
  var TAG = /^veena-ai-v(\d+)\.(\d+)\.(\d+)$/;
  var PLATFORMS = [
    { id: "windows", label: "Windows", detail: "Windows 10 and 11, 64-bit", file: "VEENA.AI-Windows-Setup.exe" },
    { id: "mac", label: "macOS", detail: "Mac with Apple Silicon (M1–M4)", file: "VEENA.AI-macOS-AppleSilicon.dmg" },
    { id: "linux", label: "Linux", detail: "x86_64 AppImage", file: "VEENA.AI-Linux-x86_64.AppImage" },
  ];
  var ua = navigator.userAgent;
  var detected = /Windows/.test(ua) ? "windows" : /Mac OS X|Macintosh/.test(ua) ? "mac" : /Linux/.test(ua) && !/Android/.test(ua) ? "linux" : null;
  var mobile = /Android|iPhone|iPad|iPod/.test(ua);
  var primary = PLATFORMS.filter(function (p) { return p.id === detected; })[0] || PLATFORMS[0];
  var btn = document.getElementById("dl-button");
  var meta = document.getElementById("dl-meta");
  var others = document.getElementById("dl-others");
  var osLine = document.getElementById("dl-os");
  var heroBtn = document.querySelector("[data-dl-primary]");

  function mb(n) { return Math.round(n / 1e6) + " MB"; }
  function link(href, text) { var a = document.createElement("a"); a.href = href; a.textContent = text; return a; }
  function span(text) { var s = document.createElement("span"); s.textContent = text; return s; }

  function comingSoon(reason) {
    osLine.textContent = mobile ? "VEENA is a desktop app" : "For " + primary.detail;
    title.textContent = "Public beta coming soon";
    meta.textContent = reason;
    btn.textContent = "Follow releases on GitHub";
    btn.href = RELEASES;
    btn.removeAttribute("aria-disabled");
    others.textContent = "";
    PLATFORMS.forEach(function (p) { others.appendChild(span(p.label + ": not yet published")); });
  }

  function newer(a, b) { for (var i = 1; i <= 3; i++) { if (+a[i] !== +b[i]) return +a[i] > +b[i]; } return false; }

  fetch("https://api.github.com/repos/" + REPO + "/releases?per_page=20", { headers: { Accept: "application/vnd.github+json" } })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(function (list) {
      var best = null, bestV = null;
      list.forEach(function (rel) {
        var m = TAG.exec(rel.tag_name || "");
        if (!m || rel.draft || rel.prerelease) return;
        if (!best || newer(m, bestV)) { best = rel; bestV = m; }
      });
      if (!best) return comingSoon("Installers for Windows, macOS and Linux are built and tested; the first public release has not been published yet.");
      var version = bestV.slice(1).join(".");
      var assets = {};
      (best.assets || []).forEach(function (a) { if (a.state === "uploaded" && a.size > 0) assets[a.name] = a; });
      var main = assets[primary.file];
      osLine.textContent = mobile ? "VEENA is a desktop app · choose your computer" : "Recommended for your computer";
      if (main) {
        title.textContent = "VEENA " + version + " for " + primary.label;
        meta.textContent = primary.detail + " · " + mb(main.size) + " · not yet code-signed (expect a one-time warning)";
        btn.textContent = "Download for " + primary.label;
        btn.href = main.browser_download_url;
        btn.removeAttribute("aria-disabled");
        btn.addEventListener("click", function () { trackDownload(primary.id, version); });
        if (heroBtn) heroBtn.href = "#download";
      } else {
        title.textContent = "VEENA " + version;
        meta.textContent = "No " + primary.label + " installer in this release yet.";
        btn.textContent = "See all files";
        btn.href = best.html_url;
        btn.removeAttribute("aria-disabled");
      }
      others.textContent = "";
      PLATFORMS.forEach(function (p) {
        if (p.id === primary.id) return;
        var a = assets[p.file];
        if (!a) return others.appendChild(span(p.label + ": not in this release"));
        var l = link(a.browser_download_url, p.label + " · " + mb(a.size));
        l.addEventListener("click", function () { trackDownload(p.id, version); });
        others.appendChild(l);
      });
      others.appendChild(link(best.html_url, "Release notes and SHA-256 checksums"));
      var sums = document.getElementById("dl-sums");
      if (sums) sums.href = best.html_url;
    })
    .catch(function () { comingSoon("Could not reach GitHub just now. Releases are listed on GitHub."); });
})();
