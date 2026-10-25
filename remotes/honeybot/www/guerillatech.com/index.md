# GuerillaTech (guerillatech.com): Nix vs. Docker for DIY Home-Hosting

Cloud rent and fragile Docker Compose YAML sprawl are optional. A ten-year-old laptop running declarative NixOS can serve eight domains, terminate Let's Encrypt TLS, log live AI-crawler wire telemetry into SQLite, and broadcast a 24/7 radio-style observability stream from your spare room.

Inspect the bootstrap contract through the read-only `less` window first:

    curl -fsSL guerillatech.com | less

Nothing executes while you read. Use `j` to scroll down, `k` to scroll up, and `q` to quit cleanly.

When you are ready to build your local workshop in `~/guerillatech`:

    curl -fsSL guerillatech.com | bash

## Why Nix Beats Containers for Sovereign Appliances

- **Deterministic Math Over Layered Blobs** — one `configuration.nix` and `flake.nix` file defines your OS, Nginx virtual hosts, systemd timers, and Python environment without shipping gigabytes of duplicate container userlands.
- **Unblindfolded Wire Telemetry** — observe real AI crawlers (RFC 9110 Markdown negotiation, RFC 9421 cryptographic signatures, and DOM-hydration trapdoors) directly on your own metal.
- **Atomic Rollbacks** — if an upgrade ever misbehaves, boot the previous NixOS generation in seconds.
