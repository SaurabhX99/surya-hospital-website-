// ── API configuration ──────────────────────────────────────────────
// Update API_BASE_URL to your deployed backend URL before going live.
// For local development leave it as http://localhost:8000
window.APP_CONFIG = {
  API_BASE_URL: 'https://surya-hospital-website.onrender.com',
  PUBLIC_API_KEY: 'i4SF2xgEp5U4FnFPxmeA6uiu+JeadCIWR9vV75Gl4Jw=',

  // AES-256-CBC encryption key (base64-encoded 32-byte key).
  // Must match backend AES_ENCRYPTION_KEY. Leave empty to disable encryption.
  // Generate: python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
  AES_ENCRYPTION_KEY: '',

  // APP_PROFILE: 'DEV' or 'PROD'
  // PROD disables browser developer tools (inspect element, network tab, etc.)
  APP_PROFILE: 'DEV',
};
