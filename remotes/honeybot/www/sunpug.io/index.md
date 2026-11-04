# Sun Pug (sunpug.io): The Software Von Neumann Probe & True WORA

Good engineering governance never pipes an uninspected script into a shell. Before provisioning anything, audit the entire bootstrap contract in your terminal pager.

Look through the glass first with `less`:

    curl -fsSL sunpug.io | less

Nothing runs. Nothing touches your disk. Put your right hand on the home row: press `j` to scroll down, `k` to scroll up, and `q` to step back out to your command line.

When you have verified the contract and are ready to provision the workspace:

    curl -fsSL sunpug.io | bash

## What Is a Software Von Neumann Probe? (SVNPvg -> SUNPug)

John von Neumann described a self-contained probe engineered to land on raw substrate and build a complete operational facility from local resources. A **Software Von Neumann Probe** (`SVNP`) does the same on any host machine: a single auditable text script that bootstraps a reproducible engineering workbench on the durable four-letter bedrock of **Nix, Python, vim, and git** (`NPvg`). Overlap the shared `NP` (`SVNP` + `NPvg` -> `SVNPvg`) and vocalize the Classical Latin `V`s as `U`s to get **SUNPug** (`sunpug.io`).

## The Tech Industry That Cried "WORA"—And Why It Is Finally True

For decades, the software industry cried **"Write Once, Run Anywhere" (WORA)**. From 1990s bytecode VMs to heavyweight container layers and fragile virtual environments, every wave promised portability while quietly breaking on host OS drift, C-library ABI mismatches, and dependency rot. After ages of false alarms, C-Suite leaders and principal engineers were desensitized—conditioned to treat true cross-platform reproducibility as a myth.

**Nix flakes** solved the underlying physics. By cryptographically pinning the entire dependency graph down to system libraries across Linux, macOS, and Windows WSL, *Write Once, Run Anywhere* is functionally true for the first time—which is why a real Software Von Neumann Probe is finally possible now.

## The Engineering Value Proposition: Portable Plain-Text AI Context

Cloud chat tabs are ephemeral silos that lose institutional context the moment a browser window closes. Sun Pug moves human-AI collaboration onto your local disk as checkable, version-controlled plain text:

- `x` (`context`) — list the exact files and live `!` commands the model should see.
- `p` (`prompt`) — capture your question from the clipboard.
- `c` (`compile`) — bundle your files, live receipts, and discussion history into your clipboard while sealing a verifiable SHA-256 archive deed on disk.

Paste that compiled payload into any model—Claude, Gemini, ChatGPT, or a local LLM—and own your transcript for life.
