begin;

-- PostgREST can keep the pre-migration function catalog until its schema
-- cache is refreshed. Reload it explicitly so the browser can call the new
-- generation-learning RPC immediately after deployment.
notify pgrst, 'reload schema';

commit;
