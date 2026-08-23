/*
 * Same-origin ESM adapter for the official @supabase/supabase-js 2.57.4 UMD
 * distribution. The immutable upstream artifact and its MIT license live next
 * to this file; provenance and integrity are recorded in the NOTICE file.
 */
import "./supabase-js-2.57.4.umd.js";

const sdk = globalThis.supabase;

if (
  !sdk
  || typeof sdk.createClient !== "function"
  || typeof sdk.processLock !== "function"
) {
  throw new Error("Vendored Supabase browser client 2.57.4 is unavailable");
}

export const createClient = (...args) => sdk.createClient(...args);
export const processLock = (...args) => sdk.processLock(...args);
export default sdk;
