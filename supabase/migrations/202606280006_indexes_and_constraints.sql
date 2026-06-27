-- Explicit indexes for every foreign key plus high-cardinality register filters.

create index if not exists profiles_role_idx on public.profiles(role);

create index if not exists projects_created_by_idx on public.projects(created_by);
create index if not exists projects_name_idx on public.projects(name);

create index if not exists project_members_project_id_idx on public.project_members(project_id);
create index if not exists project_members_user_id_idx on public.project_members(user_id);
create index if not exists project_members_project_role_idx on public.project_members(project_id, role);

create index if not exists subcontractors_project_id_idx on public.subcontractors(project_id);
create index if not exists subcontractors_trade_idx on public.subcontractors(trade);

create index if not exists items_project_id_idx on public.items(project_id);
create index if not exists items_project_name_idx on public.items(project);
create index if not exists items_subcontractor_id_idx on public.items(subcontractor_id);
create index if not exists items_status_idx on public.items(status);
create index if not exists items_type_idx on public.items(type);
create index if not exists items_due_date_idx on public.items(due_date);
create index if not exists items_updated_at_idx on public.items(updated_at desc);
create index if not exists items_payload_idx on public.items using gin(payload);

create index if not exists evidence_item_id_idx on public.evidence(item_id);
create index if not exists evidence_uploaded_by_idx on public.evidence(uploaded_by);
create index if not exists evidence_type_idx on public.evidence(evidence_type);

create index if not exists comments_item_id_idx on public.comments(item_id);
create index if not exists comments_created_by_idx on public.comments(created_by);

create index if not exists audit_events_item_id_idx on public.audit_events(item_id);
create index if not exists audit_events_created_by_idx on public.audit_events(created_by);
create index if not exists audit_events_created_at_idx on public.audit_events(created_at desc);

create index if not exists app_settings_project_id_idx on public.app_settings(project_id);
