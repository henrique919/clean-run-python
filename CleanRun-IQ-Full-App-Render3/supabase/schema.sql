create table if not exists projects (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  address text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists subcontractors (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  trade text,
  email text,
  phone text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists items (
  id uuid primary key default gen_random_uuid(),
  code text unique not null,
  type text not null,
  status text not null default 'open',
  project text not null,
  building text,
  level text,
  unit text,
  room text,
  trade text,
  subcontractor text,
  priority text,
  due_date date,
  description text,
  raised_by text,
  created_by text,
  rejection_reason text,
  issued_at timestamptz,
  started_at timestamptz,
  ready_at timestamptz,
  inspected_at timestamptz,
  closed_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists evidence (
  id uuid primary key default gen_random_uuid(),
  item_id uuid references items(id) on delete cascade,
  evidence_type text not null,
  photo text,
  comment text,
  note text,
  role text,
  confirmation text,
  uploaded_by text,
  created_at timestamptz default now()
);

create table if not exists comments (
  id uuid primary key default gen_random_uuid(),
  item_id uuid references items(id) on delete cascade,
  text text not null,
  created_by text,
  created_at timestamptz default now()
);

create table if not exists audit_events (
  id uuid primary key default gen_random_uuid(),
  item_id uuid references items(id) on delete cascade,
  event_type text not null,
  message text not null,
  created_by text,
  created_at timestamptz default now()
);

create table if not exists cleanrun_state (
  id text primary key,
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table projects enable row level security;
alter table subcontractors enable row level security;
alter table items enable row level security;
alter table evidence enable row level security;
alter table comments enable row level security;
alter table audit_events enable row level security;
alter table cleanrun_state enable row level security;
