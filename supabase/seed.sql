insert into public.companies (id, name)
values ('00000000-0000-0000-0000-000000000001', 'CleanRun Demo')
on conflict (id) do nothing;

insert into public.projects (id, company_id, name, address)
values (
  '10000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'Jura Noosa',
  '79-83 Eumundi Noosa Rd, Noosaville'
)
on conflict (id) do nothing;
