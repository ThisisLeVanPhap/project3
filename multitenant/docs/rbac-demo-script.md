# RBAC Demo Script

Use these three short flows to demo the role-based platform behavior.

## 1. PLATFORM_ADMIN

- Login: use the platform admin account on `/login`
- Redirect: lands on `/admin`
- Visible sections: tenants, chatbots, bindings, monitoring, leads, purchase requests, statistics
- Can do: create a tenant and load global statistics
- Cannot do: use the tenant workspace as a tenant user role

Suggested line:
"As a platform admin, I land in the platform console, can manage tenants, and can see global cross-tenant stats."

## 2. TENANT_ADMIN

- Login: use a tenant admin email and password on `/login`
- Redirect: lands on `/tenant`
- Visible sections: operational tenant workspace plus the tenant admin tools panel
- Can do: load tenant chatbot and channel binding data, then work purchase requests and leads
- Cannot do: access platform admin tenant-management or global stats pages

Suggested line:
"As a tenant admin, I stay inside one tenant and can both configure tenant chatbot resources and handle day-to-day operations."

## 3. TENANT_MEMBER

- Login: use a tenant member email and password on `/login`
- Redirect: lands on `/tenant`
- Visible sections: operational tenant workspace only
- Can do: update purchase requests, reply to customers, and process lead operations for the tenant
- Cannot do: see tenant admin tools, chatbot config, or platform admin pages

Suggested line:
"As a tenant member, I can do the operational work, but I do not see tenant configuration controls or platform-wide admin features."

## Quick Close

- PLATFORM_ADMIN: platform-wide visibility and tenant management
- TENANT_ADMIN: tenant-scoped config plus tenant operations
- TENANT_MEMBER: tenant-scoped operations only
