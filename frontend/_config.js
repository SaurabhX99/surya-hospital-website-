// ── Frontend Config Loader ─────────────────────────────────────────
// The API base URL is the only value kept in code (it's not a secret).
// All keys (API key, AES key) are fetched from the backend at runtime.
//
// Sets window.APP_CONFIG immediately with the base URL, then fetches
// the rest asynchronously. window.__configReady is a Promise that
// resolves once the full config is loaded.
(function () {
  var API_BASE = 'https://surya-hospital-website.onrender.com';

  window.APP_CONFIG = { API_BASE_URL: API_BASE };

  window.__configReady = fetch(API_BASE + '/_config.json')
    .then(function (r) { return r.json(); })
    .then(function (cfg) {
      for (var k in cfg) {
        if (cfg.hasOwnProperty(k)) window.APP_CONFIG[k] = cfg[k];
      }
    })
    .catch(function () {
      // Config fetch failed — app runs with defaults (no encryption, no API key)
    });
})();
