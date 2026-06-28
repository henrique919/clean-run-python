# CleanRun IQ Supabase

This folder is the source of truth for the database and storage contract.

Use the Supabase CLI local-first workflow:

```powershell
supabase start
supabase db reset
supabase gen types typescript --local > supabase/types/database.types.ts
```

Production deploy:

```powershell
supabase link --project-ref <project-ref>
supabase db push
supabase gen types typescript --project-id <project-ref> > supabase/types/database.types.ts
```

Rules:

- Do not configure schema, policies, or buckets manually in the Supabase UI.
- Do not expose `service_role` keys to browser or static app code.
- Keep every schema change as an ordered SQL migration in `supabase/migrations`.
- Regenerate `supabase/types/database.types.ts` after every migration.
