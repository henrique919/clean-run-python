-- CleanRun IQ baseline extensions and private application schema.
create extension if not exists pgcrypto;

create schema if not exists app;

comment on schema app is
  'Private helper schema for security-definer functions and non-client implementation details.';
