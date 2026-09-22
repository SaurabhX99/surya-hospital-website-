/* ============================================================
   DevTools Guard — PROD-only protection
   ============================================================
   Activates ONLY when APP_CONFIG.APP_PROFILE === 'PROD'.
   Blocks common methods of opening browser developer tools:
     - Right-click context menu
     - F12, Ctrl+Shift+I/J/C, Ctrl+U keyboard shortcuts
     - Debugger statement trap to hinder console usage
   ============================================================ */
(function () {
  'use strict';

  var profile = (window.APP_CONFIG && window.APP_CONFIG.APP_PROFILE) || 'DEV';
  if (profile !== 'PROD') return;

  /* ── Disable right-click context menu ──────────────────── */
  document.addEventListener('contextmenu', function (e) {
    e.preventDefault();
  });

  /* ── Block DevTools keyboard shortcuts ─────────────────── */
  document.addEventListener('keydown', function (e) {
    // F12
    if (e.key === 'F12' || e.keyCode === 123) {
      e.preventDefault();
      return false;
    }
    // Ctrl+Shift+I  (Inspect)
    // Ctrl+Shift+J  (Console)
    // Ctrl+Shift+C  (Element picker)
    if (e.ctrlKey && e.shiftKey && (e.key === 'I' || e.key === 'J' || e.key === 'C'
        || e.keyCode === 73 || e.keyCode === 74 || e.keyCode === 67)) {
      e.preventDefault();
      return false;
    }
    // Ctrl+U  (View source)
    if (e.ctrlKey && (e.key === 'U' || e.key === 'u' || e.keyCode === 85)) {
      e.preventDefault();
      return false;
    }
    // Cmd variants for macOS
    if (e.metaKey && e.altKey && (e.key === 'I' || e.key === 'J' || e.key === 'C'
        || e.keyCode === 73 || e.keyCode === 74 || e.keyCode === 67)) {
      e.preventDefault();
      return false;
    }
    if (e.metaKey && (e.key === 'U' || e.key === 'u' || e.keyCode === 85)) {
      e.preventDefault();
      return false;
    }
  });

  /* ── Debugger trap ─────────────────────────────────────── */
  /* When DevTools is open the debugger statement pauses execution,
     making the Network and Elements tabs very difficult to use.   */
  (function _loop() {
    setTimeout(function () {
      // eslint-disable-next-line no-debugger
      debugger;
      _loop();
    }, 1000);
  })();

  /* ── Console warning ───────────────────────────────────── */
  if (typeof console !== 'undefined' && console.log) {
    console.log(
      '%cStop!',
      'color:red;font-size:48px;font-weight:bold;'
    );
    console.log(
      '%cThis browser feature is intended for developers. Do not paste or run any code here.',
      'font-size:16px;'
    );
  }
})();
