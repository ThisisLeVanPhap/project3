# Demo seed data for UI screenshots

This document describes the manual demo data used to make UI pages non-empty for screenshots in the graduation project report.

Important: this data is only for UI illustration. Do not use it as experiment data, benchmark results, chatbot quality evidence, market price evidence, or real customer data.

## Files

- `scripts/seed_demo_data.sql`: inserts deterministic demo tenants, users, chatbots, conversations, messages, purchase requests, and KB rebuild status.
- `scripts/delete_demo_data.sql`: removes the demo rows created by the seed script.
- `chatbot/kb/demo_caco/raw_urls.txt`: sample KB source URLs for the CaCo demo tenant.
- `chatbot/kb/demo_moho/raw_urls.txt`: sample KB source URLs for the MOHO demo tenant.

The seed is not a Flyway migration and is not required for normal application startup.

## What Is Demo Data

The seed creates:

- Tenant `datn_demo_caco`: `DEMO - Nội Thất CaCo Demo`
- Tenant `datn_demo_moho`: `DEMO - MOHO Demo`
- Tenant admin/member accounts for both tenants
- One `tenant_sales` chatbot for each demo tenant
- One `general_compare` demo chatbot with `provider=claude`
- One `market_price` demo chatbot with `provider=claude`
- Sample conversations and messages
- Four sample purchase requests with statuses `NEW`, `CONTACTED`, and `COMPLETED`
- Sample KB rebuild status rows
- Sample KB source URL files

All names, phone numbers, addresses, notes, and messages are marked `DEMO` or `DEMO/SAMPLE`. Phone numbers such as `0900000001` are fake. Addresses are fake. No personal data is used.

## What Is Not Seeded

- No real Claude key is inserted.
- No Anthropic secret value is inserted.
- No `.env` value is inserted or modified.
- No product catalog is fabricated.
- No reference catalog or market price catalog is fabricated.
- No chatbot test result, latency, pass count, or benchmark result is created.

Product/reference catalog data should come from the real data pipeline/crawl process when needed.

## Run Seed

From the repository root, with Docker Compose Postgres running:

```powershell
Get-Content .\scripts\seed_demo_data.sql | docker compose exec -T postgres psql -U postgres -d global_admin
```

If your database name/user differ from the defaults, replace `global_admin` and `postgres` with the values from your environment.

For a local PostgreSQL installation:

```powershell
psql -U postgres -d global_admin -f .\scripts\seed_demo_data.sql
```

## Delete Demo Data

From the repository root, with Docker Compose Postgres running:

```powershell
Get-Content .\scripts\delete_demo_data.sql | docker compose exec -T postgres psql -U postgres -d global_admin
```

For a local PostgreSQL installation:

```powershell
psql -U postgres -d global_admin -f .\scripts\delete_demo_data.sql
```

## Demo Login Accounts

Platform admin is the built-in account:

| Role | Account | Password |
| --- | --- | --- |
| Platform admin | `admin` | `admin123` |

Tenant accounts created by the seed:

| Tenant code | Role | Email | Password |
| --- | --- | --- | --- |
| `datn_demo_caco` | Tenant admin | `caco.admin@demo.local` | `demo123` |
| `datn_demo_caco` | Tenant member | `caco.member@demo.local` | `demo123` |
| `datn_demo_moho` | Tenant admin | `moho.admin@demo.local` | `demo123` |
| `datn_demo_moho` | Tenant member | `moho.member@demo.local` | `demo123` |

Use `/login`, enter the email, password, and tenant code for tenant accounts.

## Suggested UI Pages To Capture

- `/login`
- `/admin`
- `/tenant`
- `/tenant/purchase-requests`
- `/chat`
- `/chat/general`
- `/price-check`

For tenant chat screenshots, use one of the seeded chatbot ids or select a seeded chatbot from the UI:

- CaCo tenant sales bot: `20000000-0000-4000-8000-000000000101`
- MOHO tenant sales bot: `20000000-0000-4000-8000-000000000102`

## Verification Checklist

After running the seed, verify:

```powershell
rg -n "s[k]-ant|ANTHROPIC_[A-Z_]+=|CLAUDE_[A-Z_]+=" scripts docs/DEMO_DATA.md chatbot/kb/demo_caco chatbot/kb/demo_moho
git diff -- .env
```

Expected:

- No real Claude/API key appears.
- `.env` has no diff.
- Seeded chatbot rows have `api_key`, `api_model`, and `api_base_url` as `NULL`.
