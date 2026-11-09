// Enables a download button only after confirming, from GitHub's public API,
// that the installer exists in the newest published (non-draft) VEENA release.
// Until then the buttons stay disabled: no link ever points at a missing file.
(function () {
  var API = "https://api.github.com/repos/florina787/Data-sets/releases?per_page=20";
  var RELEASES = "https://github.com/florina787/Data-sets/releases";
  var TAG = /^veena-ai-v(\d+)\.(\d+)\.(\d+)$/;
  var buttons = Array.prototype.slice.call(document.querySelectorAll("#downloads .btn"));
  var ua = navigator.userAgent;
  var os = /Windows/.test(ua) ? "windows" : /Mac OS X|Macintosh/.test(ua) ? "mac" : /Linux/.test(ua) && !/Android/.test(ua) ? "linux" : null;

  function setState(btn, text) { btn.querySelector(".state").textContent = text; }
  function unavailable(reason) {
    buttons.forEach(function (b) {
      b.setAttribute("aria-disabled", "true");
      b.removeAttribute("href");
      setState(b, reason);
    });
    document.getElementById("release-line").innerHTML =
      'Installers are not published yet. Follow <a href="' + RELEASES + '">the releases page</a> for the first public beta.';
  }
  function newer(a, b) { for (var i = 1; i <= 3; i++) { if (+a[i] !== +b[i]) return +a[i] > +b[i]; } return false; }

  fetch(API, { headers: { Accept: "application/vnd.github+json" } })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(function (list) {
      var best = null, bestV = null;
      list.forEach(function (rel) {
        var m = TAG.exec(rel.tag_name || "");
        if (!m || rel.draft || rel.prerelease) return;
        if (!best || newer(m, bestV)) { best = rel; bestV = m; }
      });
      if (!best) return unavailable("Coming soon");
      var found = 0;
      buttons.forEach(function (b) {
        var asset = (best.assets || []).filter(function (a) { return a.name === b.dataset.file && a.state === "uploaded" && a.size > 0; })[0];
        if (!asset) { setState(b, "Not in this release"); return; }
        found++;
        b.href = asset.browser_download_url;
        b.removeAttribute("aria-disabled");
        setState(b, "v" + bestV.slice(1).join(".") + " · " + (asset.size / 1e6).toFixed(0) + " MB");
        if (b.dataset.os === os) b.classList.add("suggested");
      });
      document.getElementById("release-line").innerHTML =
        'Version ' + bestV.slice(1).join(".") + '. <a href="' + best.html_url + '">Release notes and SHA-256 checksums</a>. Apple Silicon Macs only for now.';
      if (!found) unavailable("Coming soon");
    })
    .catch(function () { unavailable("Unavailable right now"); document.getElementById("release-line").innerHTML = 'Could not reach GitHub. Downloads are on <a href="' + RELEASES + '">the releases page</a>.'; });
})();
