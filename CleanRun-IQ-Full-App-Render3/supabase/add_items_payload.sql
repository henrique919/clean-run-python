alter table items
add column if not exists payload jsonb;

create index if not exists items_payload_idx
on items using gin (payload);
