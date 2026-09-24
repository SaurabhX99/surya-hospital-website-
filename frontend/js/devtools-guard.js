/* ============================================================
   DevTools Guard — PROD-only protection
   ============================================================
   Activates ONLY when APP_CONFIG.APP_PROFILE === 'PROD'.
   Blocks common methods of opening browser developer tools:
     - Right-click context menu
     - F12, Ctrl+Shift+I/J/C, Ctrl+U keyboard shortcuts
     - Debugger statement trap to hinder console usage

   Waits for __configReady (async config fetch) before checking
   APP_PROFILE, so it works with the dynamic config loader.
   ============================================================ */
(function () {
  'use strict';

  function activate() {
    var profile = (window.APP_CONFIG && window.APP_CONFIG.APP_PROFILE) || 'DEV';
    if (profile !== 'PROD') return;

    /* ── Disable right-click context menu ──────────────────── */
    document.addEventListener('contextmenu', function (e) {
      e.preventDefault();
    });

    /* ── Block DevTools keyboard shortcuts ─────────────────── */
    document.addEventListener('keydown', function (e) {
      if (e.key === 'F12' || e.keyCode === 123) {
        e.preventDefault(); return false;
      }
      if (e.ctrlKey && e.shiftKey && (e.key === 'I' || e.key === 'J' || e.key === 'C'
          || e.keyCode === 73 || e.keyCode === 74 || e.keyCode === 67)) {
        e.preventDefault(); return false;
      }
      if (e.ctrlKey && (e.key === 'U' || e.key === 'u' || e.keyCode === 85)) {
        e.preventDefault(); return false;
      }
      if (e.metaKey && e.altKey && (e.key === 'I' || e.key === 'J' || e.key === 'C'
          || e.keyCode === 73 || e.keyCode === 74 || e.keyCode === 67)) {
        e.preventDefault(); return false;
      }
      if (e.metaKey && (e.key === 'U' || e.key === 'u' || e.keyCode === 85)) {
        e.preventDefault(); return false;
      }
    });

    /* ── Debugger trap ─────────────────────────────────────── */
    (function _loop() {
      setTimeout(function () {
        debugger;
        _loop();
      }, 1000);
    })();

    /* ── Console warning ───────────────────────────────────── */
    if (typeof console !== 'undefined' && console.log) {
      console.log('%cStop!', 'color:red;font-size:48px;font-weight:bold;');
      console.log('%cThis browser feature is intended for developers. Do not paste or run any code here.', 'font-size:16px;');
    }
  }

  // Wait for async config, then activate if PROD
  if (window.__configReady) {
    window.__configReady.then(activate);
  } else {
    activate();
  }
})();
