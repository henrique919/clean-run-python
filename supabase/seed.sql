insert into public.projects (id, name, address)
values ('10000000-0000-0000-0000-000000000001', 'Jura Noosa', '79-83 Eumundi Noosa Rd, Noosaville')
on conflict (id) do nothing;
