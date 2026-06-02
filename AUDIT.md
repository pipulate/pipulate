# Security Posture: Local-First Threat Model

Pipulate is a local-first, single-tenant application. It is not designed as a
horizontally scaled multi-tenant SaaS platform.

Audit findings are welcome, but they must preserve the deployment boundary.

Before reporting a credential, filesystem, or process-isolation concern, classify
the surface:

- live application code path
- git-tracked source
- git-ignored local operator state
- generated standalone teaching material
- stale diagnostic string
- dead constant
- documentation-only example

Secrets must not be committed to source control. Local operator secrets live in
git-ignored files such as `.env`, and live application reads should go through
canonical accessors rather than scattered ad hoc file reads.

This does not mean “local-first is automatically safe.”
It means the correct questions are different:

- Who is the attacker?
- What local account do they control?
- What file can they read?
- What process can they influence?
- What network egress exists?
- What tenant boundary is crossed?
- What state persists after rollback?

If the finding assumes a SaaS control plane, name the control plane.
If the finding assumes multiple tenants, name the tenant boundary.
If the finding depends on a documentation example, distinguish it from the live
runtime path.

Security is not waived here. It is scoped.