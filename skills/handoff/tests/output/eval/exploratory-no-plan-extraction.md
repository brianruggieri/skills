## Summary
Explored auth provider options for a SaaS dashboard (React frontend, Express API, Supabase database) targeting 50-100 initial users with eventual enterprise customers. Evaluated Supabase Auth, Clerk, Auth0, Lucia, and better-auth. No provider was chosen; user deferred the decision overnight. No code was written or committed.

## Decisions
- **Auth provider shortlist:** Supabase Auth or Clerk — Auth0 is viable but wasn't carried forward, Lucia and better-auth were discussed but deprioritized due to DIY SSO and maturity risks respectively. [FRAGILE]
- **No auth abstraction layer:** Code directly against the chosen provider's SDK rather than building a swappable adapter — frontend integration leaks too much for the abstraction to be practical.
- **RBAC approach:** Simple `user_roles` table with admin/member roles initially, defer granular permissions until needed.

## Do Not Retry
- Do not attempt a provider-agnostic auth abstraction layer — each provider's React SDK (hooks, session management, middleware) is too different for a clean interface, especially on the frontend.
- Do not use better-auth for enterprise-targeted SaaS — still immature (v1 mid-2024), small community, SAML support is community-contributed and not battle-tested.
- Do not store complex org hierarchies or per-resource permissions in Supabase JWT claims — JWTs over ~4KB cause issues with reverse proxies and CDNs that enforce header size limits.

## Constraints
- Provider decision is deferred — do not begin auth implementation until the user confirms Supabase Auth vs. Clerk.
- If enterprise SSO is needed within 6 months, that should tip the decision toward Clerk (SAML/OIDC built-in vs. Supabase's paid per-connection SSO).
- Multi-tenancy model (orgs/teams from day one vs. added later) must be decided before implementation begins.

## Next Steps
1. User decides between Supabase Auth and Clerk — blocking decision based on enterprise SSO timeline and preference for staying within the Supabase ecosystem.
2. Lock in RBAC granularity (admin/member vs. more granular) and whether to model orgs from day one.
3. Implement auth with the chosen provider — session/token setup, React SDK integration, Express middleware, and basic role enforcement.

## Key Files
- `src/auth/provider.ts` — auth provider implementation (to be created)
- `src/auth/session.ts` — session management (to be created)
- `src/middleware/auth.ts` — Express auth middleware (to be created)
- `package.json` — will need auth provider dependency added
