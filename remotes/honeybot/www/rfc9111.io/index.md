# RFC 9111 (rfc9111.io): Retiring Wasteful Pre-Render Solutions with HTTP Caching

Paying thousands of dollars a month to run headless Chromium clusters that pre-render JavaScript into disposable HTML snapshots for bots is an architectural tax on a solved problem. **RFC 9111 Section 4.1 (Calculating Secondary Keys with `Vary`)** lets your CDN cache both human HTML and agent-ready Markdown at the network edge from one origin URL.

Inspect the reference harness in `less` first (scroll with `j` and `k`, quit with `q`):

    curl -fsSL rfc9111.io | less

When you are ready to launch the local edge-caching audit workbench in `~/rfc9111`:

    curl -fsSL rfc9111.io | bash

## Why Bimodal Edge Caching Beats Dynamic Pre-Rendering

- **Zero Headless-Browser Compute Tax** — static HTML and static Markdown sit side-by-side in edge RAM, partitioned cleanly by `Vary: Accept, User-Agent`.
- **Zero Cloaking Liability** — every representation is declared openly in standard HTTP response headers rather than hiding behind brittle user-agent sniffing middleware.
- **Instant Time-to-First-Byte for AI Grounding** — RAG and search agents receive compact Markdown in milliseconds instead of waiting for a headless browser spin-up.
