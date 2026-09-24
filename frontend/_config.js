// ── Frontend Config Loader ─────────────────────────────────────────
// The API base URL is the only value kept in code (it's not a secret).
// All keys (API key, AES key) are fetched from the backend at runtime.
(function () {
  var API_BASE = 'https://surya-hospital-website.onrender.com';

  // Start with just the base URL so early scripts can reference it
  window.APP_CONFIG = window.APP_CONFIG || {};
  window.APP_CONFIG.API_BASE_URL = API_BASE;

  // Fetch the rest (keys, profile) from the backend
  var xhr = new XMLHttpRequest();
  xhr.open('GET', API_BASE + '/_config.json', false); // synchronous so subsequent scripts see the config
  try {
    xhr.send();
    if (xhr.status === 200) {
      var cfg = JSON.parse(xhr.responseText);
      for (var k in cfg) {
        if (cfg.hasOwnProperty(k)) window.APP_CONFIG[k] = cfg[k];
      }
    }
  } catch (e) {
    // Config fetch failed — app will run with defaults (no encryption, no API key)
  }
})();
