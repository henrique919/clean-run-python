create or replace function public.submit_access_request(
  p_id uuid,
  p_full_name text,
  p_email text,
  p_company text,
  p_role_requested text,
  p_project_site text,
  p_message text default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.access_requests (
    id,
    full_name,
    email,
    company,
    role_requested,
    project_site,
    message,
    status
  )
  values (
    p_id,
    nullif(trim(p_full_name), ''),
    lower(nullif(trim(p_email), '')),
    nullif(trim(p_company), ''),
    nullif(trim(p_role_requested), ''),
    nullif(trim(p_project_site), ''),
    nullif(trim(coalesce(p_message, '')), ''),
    'pending'
  );
end;
$$;

revoke all on function public.submit_access_request(uuid, text, text, text, text, text, text) from public;
grant execute on function public.submit_access_request(uuid, text, text, text, text, text, text) to anon, authenticated;
