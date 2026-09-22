// ── Frontend Environment Configuration ────────────────────────────
// This file IS the frontend's .env — there is no browser-native ENV
// for vanilla JS. Update these values per deployment environment.
//
// For PROD: set API_BASE_URL, PUBLIC_API_KEY, AES_ENCRYPTION_KEY,
//           and APP_PROFILE before deploying the frontend.
window.APP_CONFIG = {
  // Backend URL — change to your deployed backend before going live
  API_BASE_URL: 'https://surya-hospital-website.onrender.com',

  // Site API key — must match PUBLIC_API_KEY in backend .env
  // In PROD this key only works from whitelisted origins (ALLOWED_ORIGINS).
  // External callers must use a separately issued API key.
  PUBLIC_API_KEY: 'i4SF2xgEp5U4FnFPxmeA6uiu+JeadCIWR9vV75Gl4Jw=',

  // AES-256-CBC encryption key — must match backend AES_ENCRYPTION_KEY
  // Leave empty to disable encryption (all traffic will be plain JSON).
  AES_ENCRYPTION_KEY: 'IWJ1XhEdXfj4OyeYLEr/6U2p+3n3oNus5hhCL1oriEg=',

  // APP_PROFILE: 'DEV' or 'PROD'
  // PROD: disables browser dev tools, enforces strict origin checks
  APP_PROFILE: 'DEV',
};
