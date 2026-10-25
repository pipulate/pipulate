# RFC 9110 (rfc9110.org): Proactive Content Negotiation for the Semantic Internet

You are reading the `text/markdown` representation of this resource, served via **RFC 9110 Section 12 (HTTP Semantics: Content Negotiation)** from the same canonical URI that serves HTML to web browsers and a Nix bootstrap script to `curl`.

Test the response headers in your terminal:

    curl -sI -H "Accept: text/markdown" rfc9110.org

Inspect the reference harness installer with `less` (scroll with `j` and `k`, quit with `q`):

    curl -fsSL rfc9110.org | less

When you are ready to run the local RFC 9110 verification lab in `~/rfc9110`:

    curl -fsSL rfc9110.org | bash

## One URL, Three Native Representations

- **Browsers (`Accept: text/html`)** — receive the visual HTML document.
- **AI Crawlers & Agents (`Accept: text/markdown`)** — receive this clean Markdown representation with `Vary: Accept, User-Agent` and zero DOM boilerplate.
- **Terminal Operators (`curl` / `wget`)** — receive the self-documenting Nix flake bootstrap script stamped to `rfc9110`.
