/* ============================================================
   AES-256-CBC Payload Encryption — transparent fetch wrapper
   ============================================================
   Load this script AFTER _config.js and BEFORE any script that
   uses fetch() for API calls.

   When APP_CONFIG.AES_ENCRYPTION_KEY is set (base64-encoded 32-byte
   key), every fetch() to an /api/ URL will:
     1. Encrypt outgoing JSON bodies  → {"_enc": "<base64(IV+CT)>"}
     2. Decrypt incoming JSON envelopes  {"_enc": "..."} → original data

   When the key is NOT set, this script is a complete no-op —
   all requests and responses pass through as plain JSON.

   Config is loaded asynchronously via __configReady, so the
   monkey-patch is installed immediately but encryption only
   activates once the key is available.
   ============================================================ */
(function () {
  'use strict';

  /* ── Base64 ↔ Uint8Array helpers ───────────────────────── */
  function b64ToBytes(b64) {
    var bin = atob(b64);
    var arr = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    return arr;
  }

  function bytesToB64(bytes) {
    var bin = '';
    var u8 = new Uint8Array(bytes);
    for (var i = 0; i < u8.length; i++) bin += String.fromCharCode(u8[i]);
    return btoa(bin);
  }

  /* ── CryptoKey cache ───────────────────────────────────── */
  var _keyPromise = null;

  function getKey() {
    if (!_keyPromise) {
      var kb = (window.APP_CONFIG && window.APP_CONFIG.AES_ENCRYPTION_KEY) || '';
      if (!kb) return null;
      _keyPromise = crypto.subtle.importKey(
        'raw', b64ToBytes(kb), { name: 'AES-CBC' }, false, ['encrypt', 'decrypt']
      );
    }
    return _keyPromise;
  }

  /* ── Encrypt / Decrypt ─────────────────────────────────── */
  async function encrypt(plaintext) {
    var key = await getKey();
    var iv = crypto.getRandomValues(new Uint8Array(16));
    var encoded = new TextEncoder().encode(plaintext);
    var ct = await crypto.subtle.encrypt({ name: 'AES-CBC', iv: iv }, key, encoded);
    var result = new Uint8Array(iv.length + ct.byteLength);
    result.set(iv);
    result.set(new Uint8Array(ct), iv.length);
    return bytesToB64(result);
  }

  async function decrypt(cipherB64) {
    var key = await getKey();
    var raw = b64ToBytes(cipherB64);
    var iv = raw.slice(0, 16);
    var ct = raw.slice(16);
    var pt = await crypto.subtle.decrypt({ name: 'AES-CBC', iv: iv }, key, ct);
    return new TextDecoder().decode(pt);
  }

  /* ── Monkey-patch window.fetch ─────────────────────────── */
  var _origFetch = window.fetch;
  // Promise that resolves once config is loaded (or immediately if no loader)
  var _ready = window.__configReady || Promise.resolve();

  window.fetch = async function (input, init) {
    var url = typeof input === 'string' ? input : (input && input.url) || '';

    // Only intercept /api/ calls
    if (url.indexOf('/api/') === -1) {
      return _origFetch.call(this, input, init);
    }

    // Wait for config to be loaded before first API call
    await _ready;

    // Check if encryption is enabled (key available after config load)
    if (!getKey()) {
      return _origFetch.call(this, input, init);
    }

    // ── Encrypt outgoing JSON body ────────────────────────
    if (init && init.body && typeof init.body === 'string') {
      var ct = '';
      var headers = init.headers || {};
      if (headers instanceof Headers) {
        ct = headers.get('Content-Type') || '';
      } else if (typeof headers === 'object' && !Array.isArray(headers)) {
        for (var k in headers) {
          if (k.toLowerCase() === 'content-type') { ct = headers[k]; break; }
        }
      }
      if (ct.indexOf('application/json') !== -1) {
        var enc = await encrypt(init.body);
        init = Object.assign({}, init, { body: JSON.stringify({ _enc: enc }) });
      }
    }

    var response = await _origFetch.call(this, input, init);

    // ── Decrypt incoming JSON response ────────────────────
    var origJson = response.json.bind(response);
    var _decrypted = null;
    var _jsonCalled = false;

    response.json = async function () {
      if (_jsonCalled) return _decrypted;
      _jsonCalled = true;
      var data = await origJson();
      if (
        response.ok &&
        data && typeof data === 'object' && !Array.isArray(data) &&
        data._enc && Object.keys(data).length === 1
      ) {
        try {
          var plain = await decrypt(data._enc);
          _decrypted = JSON.parse(plain);
          return _decrypted;
        } catch (_) {
          // Decryption failed — return raw data
        }
      }
      _decrypted = data;
      return data;
    };

    return response;
  };
})();
