/*
 * Browser-visible configuration for GitHub Pages.
 * SUPABASE_PUBLISHABLE_KEY is intentionally public and is protected by RLS.
 * Never put sb_secret_*, service_role, database passwords, or provider keys here.
 */
window.CONTENTENGINE_CONFIG = Object.freeze({
  APP_NAME: "Контент ИИ Завод",
  SUPABASE_URL: "https://iyckwryrucqrxwlowxow.supabase.co",
  SUPABASE_PUBLISHABLE_KEY: "__SET_SUPABASE_PUBLISHABLE_KEY__",
  RPC_SCHEMA: "public",
  STORAGE_BUCKET: "contentengine-private",
  MOCK_ONLY: true,
  MAX_BATCH_SIZE: 50,
  MAX_UPLOAD_BYTES: 52428800,
});
