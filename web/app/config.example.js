/* Copy to config.js and fill only the browser-safe publishable key. */
window.CONTENTENGINE_CONFIG = Object.freeze({
  APP_NAME: "Контент ИИ Завод",
  SUPABASE_URL: "https://YOUR_PROJECT_REF.supabase.co",
  SUPABASE_PUBLISHABLE_KEY: "sb_publishable_REPLACE_ME",
  RPC_SCHEMA: "public",
  STORAGE_BUCKET: "contentengine-private",
  MOCK_ONLY: true,
  MAX_BATCH_SIZE: 50,
  MAX_UPLOAD_BYTES: 52428800,
});
