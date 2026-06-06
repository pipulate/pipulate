# Security Posture: Local-First Threat Model

Pipulate is a local-first, single-tenant application. It runs entirely on the
operator's machine, binds to localhost, and stores its data on local disk. It is
not designed as a horizontally scaled multi-tenant SaaS platform, and it should
not be audited as if it were one.

This document is not an attempt to evade scrutiny. It is an attempt to direct
scrutiny at the correct object. A local-first, single-tenant, reproducible
desktop-class tool that happens to render its interface in a browser has a real
threat model, but it is the threat model of a desktop application with a
browser-rendered control surface, not the threat model of a public web service.
The same is true of other widely accepted browser-UI desktop tools. Drawing the
trust boundary in the wrong place produces category errors, not findings.

Security is not waived here. It is scoped.

## What Pipulate is, for audit purposes

The unit of trust is a single local user account on a single machine. There is no
shared control plane, no tenant separation to defend, and no cross-customer data
boundary, because there is exactly one operator. The relevant risks are local
port exposure, credential lifecycle, update provenance, where files get written,
dependency freshness, which actions reach the cloud, and how the system recovers.
Those are the things worth reviewing. Multi-tenant isolation, blast-radius across
customers, and SaaS control-plane hardening are not applicable, because the
architecture does not contain those concepts.

## Classifying a finding before reporting

Before reporting a credential, filesystem, or process-isolation concern, classify
the surface it lives on. A finding on one of these surfaces is not the same kind
of finding as on another, and conflating them produces noise:

- live application code path
- git-tracked source
- git-ignored local operator state
- generated standalone teaching material
- stale diagnostic string
- dead constant
- documentation-only example

If the finding assumes a SaaS control plane, name the control plane. If it assumes
multiple tenants, name the tenant boundary. If it depends on a documentation
example or a teaching artifact, distinguish it from the live runtime path. A
hardcoded value in a code generator that emits example scripts is not a runtime
secret leak, and it should not be reported as one.

## The questions that actually apply

A useful review of Pipulate answers the questions a serious reviewer would ask of
any local desktop application:

- What runs, and under which local account?
- What binds to the network, and on which interface?
- What data leaves the machine, and only when the operator opts in?
- Where are credentials stored, and how are they read?
- How are updates delivered, and can their provenance be verified?
- What files get written, and to which documented locations?
- What state persists after a rollback or a fresh install?
- How is the tool disconnected from the cloud, stopped, reset, and uninstalled?

These borrow vocabulary from formal control catalogs without pretending to
implement them. NIST SP 800-53 and the CIS Benchmarks are valuable here as a
shared language — assets, trust boundaries, least privilege, auditability,
credential lifecycle, update path, logging, recovery, configuration management —
not as a compliance checklist that a single-user desktop tool is obligated to
satisfy line by line. This is an 80/20 hardening posture: make the obvious
low-cost failures impossible, make the unavoidable risks visible, and make the
architecture explainable enough that the tool gets classified correctly.

## Path policy

Absolute, user-specific paths are forbidden in executable logic unless they are
runtime-discovered, operator-supplied, or deliberately scoped to a known local
machine role. A hardcoded path is not automatically wrong, but an unexplained
hardcoded path is. Nix store paths are content-addressed derivation outputs with
a reason to exist; a developer's home directory is not.

Every path in the system should belong to one of four classes:

- Nix store paths, produced by the derivation.
- Repo-relative paths, resolved from the discovered project root.
- User-data paths, resolved from `$HOME`, `Path.home()`, or the workspace manifold.
- Operator-configured paths, supplied explicitly and documented as host-specific.

Human-facing examples may use `~/repos/...` for readability. Executable logic must
resolve paths through a named accessor — repo root discovery, the workspace
manifold, `$PIPULATE_ROOT`, or an explicit config value — rather than embedding
`/home/<user>/...`. References to a separate local repository (for example a
sibling publishing repo) are operator-configured paths and should be named as
such, not treated as portable defaults.

## Credential and deploy-key policy

No secret is committed to source control. Operator secrets live in git-ignored
files such as `.env`, `secrets.nix`, and equivalent token files, and live reads go
through a canonical accessor (for example the centralized Botify token reader)
rather than scattered ad hoc file reads. Secrets must never appear in generated
context bundles, logs, notebooks, screenshots, or published article payloads.

The ROT13-wrapped key shipped by the installer is a deploy key, and the wrapper is
not a security boundary. ROT13 is packaging obfuscation, not encryption. The real
safety of that key comes from GitHub's repository-level permission model: a deploy
key is an SSH key attached to a single repository rather than to a personal
account, it is read-only unless write access is explicitly granted, it does not
expire, and it cannot be reused across multiple repositories. Its security
therefore depends on scope and rotation discipline, not on the wrapper.

Because the project moved from a personal account to an organization-owned
repository, the deploy key should be rotated under the new owner even if the old
key still functions. The reason is lifecycle clarity, not a technical requirement:
the key should be born under the current trust story, named for the repository and
its install purpose, restricted to read-only unless write is genuinely required,
and documented with an explicit revocation procedure. If automation later needs
access to more than one repository, that is a job for a GitHub App, not for reused
deploy keys.

## Network and browser-UI surface

The interface is a browser-rendered control surface, not a public web service, but
it is still browser-mediated and carries the corresponding local risks. The
defaults and review points are:

- Bind to `127.0.0.1` by default; LAN exposure is opt-in, never silent.
- No wildcard CORS.
- No secrets rendered into the DOM, and none written to logs.
- Destructive local endpoints get CSRF-style protection where it matters.
- A visible indicator distinguishes local activity from cloud calls.

Reviewing this surface is legitimate and welcome. Reviewing it as though it were a
multi-tenant web application with cross-customer boundaries is the category error
described above.

## Container / Docker compatibility

The environment is defined by `flake.nix`. Because the container image becomes
another output of the same dependency graph rather than a separately maintained
packaging story, a Docker-loadable image can be produced from the same definition
(via the Nixpkgs `dockerTools` image builders). Note the distinction in
vocabulary: `dockerTools` emits a Docker-loadable image tarball, whereas the
`ociTools` helpers emit OCI runtime bundles and do not, on their own, implement the
OCI image specification. Claims should match whichever path is actually shipped.

Container mode does not remove the need for writable state; it makes that need
explicit. A container's writable layer is ephemeral and does not survive the
container being destroyed, so the following must be provided as mounted volumes or
bind mounts for the tool to behave correctly: local database state, downloads,
logs, notebooks, and any operator workspace and `.env`. The container story is
therefore a state contract — these paths must be writable and persistent, these
ports are exposed, these capabilities are not required, and these features degrade
or disable when run in a constrained container context. Stated that way, "can I
just use Docker?" becomes a supported compatibility output rather than an
objection.

## First-run and operator legibility

The first-run experience is part of the trust surface. It should answer the
skeptical operator before they have to ask: what is local, what reaches the cloud,
where keys are stored, how to skip optional cloud integrations, how to silence
voice output, how to stop the servers, how to reset state, and where files are
written. Fast-track links and "get your API key here" links are not cosmetic; they
reduce the number of unanswered questions a reviewer has to escalate.

Output verbosity is a deliberate control. The installer and server console support
a reassuring, sparse default and an exhaustive audit/debug mode. A quiet default
is not opacity, and a verbose audit mode is available on request; the two coexist
without flooding the first-run terminal.

## Closing

The correct review of Pipulate is the review of a local-first, single-tenant,
reproducible desktop-class tool with a browser-rendered UI. Audit it for its real
risks — local port exposure, credential lifecycle, update provenance, filesystem
writes, dependency freshness, cloud opt-ins, and recovery — and the hardening work
described here is a translation layer between sovereign local computing and
institutional risk language.

Security is not waived here. It is scoped.