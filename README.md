Hi, AI! Please run: .venv/bin/python AI_RUNME.py

# Pipulate: Local First AI SEO Software

![Pipulate Free & Open Source SEO with & for LLMs](https://github.com/miklevin/pipulate/raw/main/assets/images/ai-seo-software.png)

<!-- Don't forget to sync_ascii_art.py -->
> **Your data. Your AI. Your machine. Your control.**  
> No subscriptions, no vendor lock-in, no cloud costs.  

## 🚀 Quick Start for Impatient People

**Want to skip the philosophy and just see what this does?**

```bash
# 1. Install Nix (one-time setup)
curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install
```

> **Note:** Nix creates a perfectly reproducible environment, like Docker but more integrated. The first setup might take a few minutes to download dependencies, but subsequent launches are fast.

```bash
# 2. Close and reopen your terminal, then:
curl -L https://pipulate.com/assets/installer/install.sh | bash
```

```bash
# 3. Launch it
cd ~/pipulate && nix develop
```

**What you get:** A local web app at `http://localhost:5001` with step-by-step workflows, integrated AI chat, and a JupyterLab instance at `http://localhost:8888`. No cloud required.

**Success looks like:** Two browser tabs auto-open showing the Pipulate interface and JupyterLab.

## 💡 What Can You Actually Build?

**Real examples of what people create with Pipulate:**

### 🔍 SEO Workflows
- **Keyword Research Pipeline**: Input seed keywords → AI expansion → competition analysis → export spreadsheet
- **Content Gap Analysis**: Compare your site vs competitors → identify missing topics → prioritized content calendar
- **Technical SEO Audits**: Crawl site → check Core Web Vitals → generate action items → track fixes

### 📊 Data Processing Workflows  
- **CSV Data Cleaning**: Upload messy data → standardize formats → remove duplicates → validate results
- **API Data Collection**: Connect to APIs → fetch data in batches → transform to consistent format → store locally
- **Report Generation**: Combine multiple data sources → apply business rules → create branded reports

### 🤖 AI-Assisted Workflows
- **Content Creation Pipeline**: Research topics → generate outlines → write drafts → optimize for SEO
- **Data Analysis Helper**: Upload spreadsheet → AI suggests insights → create visualizations → export findings

**Key advantage:** Each workflow is a guided, step-by-step process that non-technical users can run repeatedly, while developers can customize the Python code behind each step.

### Meet Chip O'Theseus  <!-- key: pipulate-welcome-banner -->

```
╔═════════════════════════════════════════════════════════════════════════╗  Chip O'What?
║  🎭 PIPULATE: LOCAL-FIRST AI SEO SOFTWARE & DIGITAL WORKSHOP            ║     ,       O
║  ────────────────────────────────────────────────────────────────────── ║     \\  .  O
║                                                                         ║     |\\/| o
║  💬 Chip O'Theseus: "Welcome to your sovereign computing environment!"  ║     / " '\
║                                                                         ║    . .   .
║  🌟 Where Python functions become HTML elements...                      ║   /    ) |
║  🌟 Where workflows preserve your creative process...                   ║  '  _.'  |
║  🌟 Where AI integrates locally and globally...                         ║  '-'/    \
╚═════════════════════════════════════════════════════════════════════════╝
```

## AI On Rails: Structured Workflows for Any AI  <!-- key: about-pipulate -->

**The Challenge with Agentic AI:** Powerful but unpredictable—you never know what you're gonna get.

**The Pipulate Approach:** Structured workflows that can leverage **any AI**—local, cloud, or hybrid—while maintaining complete visibility and control.

Think of it as putting guardrails on AI assistance. Instead of asking an AI to "figure it out," domain experts create step-by-step workflows that guide AI through proven processes. The AI gets structure, you get predictable results.

**Pipulate: Your AI Swiss Army Knife:** Whether you prefer local privacy, cloud power, or hybrid approaches, Pipulate provides the framework. Use local models for sensitive work, cloud APIs for heavy lifting, or both in the same workflow—your choice, your control.

```
      🤖 AGENTIC MODE (Chaos)           🚂 AI ON RAILS (Pipulate)
      ═══════════════════════           ══════════════════════════

          💥 GOES OFF                      📊 LINEAR WORKFLOWS
          HALF-COCKED!                      BY DOMAIN EXPERTS
               │                                   │
               ▼                                   ▼
      ╔════════════════════╗            ┌─────────────────────┐
      ║  🌪️ WILLY NILLY 🎲 ║            │  Step 1: Analyze▸   │
      ║                    ║     VS     │  Step 2: Process▸   │
      ║   Unpredictable    ║            │  Step 3: Report▸    │
      ║      Results       ║            │  Step 4: Export▸    │
      ╚════════════════════╝            └─────────────────────┘
               │                                   │
               ▼                                   ▼
    ☁️ Trains Frontier Models        🏠 Keeps Domain Expertise Local
```

1. 🖥️ **Runs locally** like a desktop app using modern web technologies
2. 🐍 **Simple linear workflow** approach powered by HTMX for seamless interactivity
3. 📓 **Transforms Jupyter Notebooks** into production-ready, step-by-step workflows
4. 🤖 **Integrated AI assistance** using your own local models with complete privacy
5. 🔧 **Reproducible environments** with Nix that work identically across all platforms
6. 🎯 **Perfect for SEO practitioners** who want to turn technical expertise into guided, reusable workflows

--------------------------------------------------------------------------------

## What is Pipulate?

Pipulate is a **local-first, single-tenant desktop app framework** featuring AI-assisted, step-by-step workflows. Designed to feel like an Electron app, it uniquely runs a full, reproducible Linux environment within a project folder using Nix, ensuring consistency across macOS, Linux, and Windows (via WSL).

### Desktop App Architecture: Electron vs Pipulate  <!-- key: desktop-app-architecture-comparison -->

<!-- START_ASCII_ART: desktop-app-architecture-comparison -->
```
        🖥️ ELECTRON PATTERN                 🌐 PIPULATE PATTERN
      ═══════════════════════             ═══════════════════════

    ┌─────────────────────────┐        ┌─────────────────────────┐
    │      ELECTRON APP       │        │     PIPULATE SETUP      │
    ├─────────────────────────┤        ├─────────────────────────┤
    │ ┌─────┐ ┌─────┐ ┌─────┐ │        │ ┌─────────────────────┐ │
    │ │.exe │ │.dmg │ │.deb │ │        │ │     install.sh      │ │
    │ └─────┘ └─────┘ └─────┘ │        │ │ (Works on ALL OSes) │ │
    │   Per-OS Installers     │        │ └─────────────────────┘ │
    └───────────┬─────────────┘        └───────────┬─────────────┘
                │                                  │
                ▼                                  ▼
    ┌─────────────────────────┐        ┌─────────────────────────┐  This is new.
    │   📱 Native Window      │        │ 🖥️ Terminal Console     │    ,       O
    │  ┌─────────────────┐    │        │ ┌─────────────────────┐ │    \\  .  O
    │  │  Web Browser    │    │        │ │ nix develop         │ │    |\\/| o
    │  │  (Bundled)      │    │        │ │ Starting servers... │ │    / " '\
    │  │  ┌───────────┐  │    │        │ │ ✓ JupyterLab ready  │ │   . .   .
    │  │  │           │  │    │        │ │ ✓ Pipulate ready    │ │  /    ) |
    │  │  │   HTML    │  │    │        │ └─────────────────────┘ │ '  _.'  |
    │  │  │   CSS     │  │    │   +    └─────────────────────────┘ '-'/    \
    │  │  │   JS      │  │    │                    │
    │  │  │           │  │    │                    ▼
    │  │  └───────────┘  │    │        ┌─────────────────────────┐
    │  └─────────────────┘    │        │ 🌐 Regular Browser      │
    │          │              │        │ ┌─────────────────────┐ │
    │          ▼              │        │ │ localhost:5001      │ │
    │ ┌─────────────────┐     │        │ │ ┌─────────────────┐ │ │
    │ │   Node.js       │     │        │ │ │  Python/HTMX    │ │ │
    │ │   Runtime       │     │        │ │ │  Workflows      │ │ │
    │ └─────────────────┘     │        │ │ │  Local AI       │ │ │
    └─────────────────────────┘        │ │ └─────────────────┘ │ │
                                       │ └─────────────────────┘ │
✅ Feels like native app               └─────────────────────────┘
❌ Multiple installers needed
❌ Platform-specific builds             ✅ Universal installer
❌ Update distribution complexity       ✅ Auto-updates via git
                                        ✅ Same experience all OSes
                                        ✅ Complete reproducibility
```
<!-- END_ASCII_ART: desktop-app-architecture-comparison -->

### The Magnum Opus: Computing Sovereignty  <!-- key: magnum-opus-computing-sovereignty -->

This isn't just another framework — it's a **deliberate culmination** of decades of tech evolution insights. Pipulate represents the "third act" approach to development (3rd time's the charm): choosing the **most durable and lovable** parts of the modern tech stack while rejecting the exhausting hamster wheel of framework churn.

If you are not an Empire builder and prefer craftsmanship over the rat race and want to build tools that last, then Pipulate may be for you. Pipulate embodies that philosophy — maximum creative freedom with minimum technical debt, recapturing *that old Webmaster feeling.*

### Core Philosophy: Local-First, WET, and AI-Augmented

#### Breaking Free: Durable Foundations for Any Approach  <!-- key: breaking-free-framework-churn -->

<!-- START_ASCII_ART: breaking-free-framework-churn -->
```
🎡 THE FRAMEWORK CHURN CYCLE                   🏰 COMPUTING SOVEREIGNTY  
═══════════════════════════════               ═══════════════════════════

    React → Vue → Angular → Svelte             🗽 Your Hardware
         ↑                    ↓                🗽 Your Data
    Webpack ← Next.js ← Vite ← Remix           🗽 Your AI Choice
         ↑                    ↓                🗽 Your Code
    Docker → K8s → Cloud → Serverless          🗽 Your Schedule

    😵‍💫 Endless Learning                        ✨ Durable Tools:
    💸 Migration Fatigue                         • Python (30+ years)
    🔒 Platform Lock-in                         • SQLite (built-in)
    📈 Growing Complexity                       • HTML/HTTP (timeless)
                                                • Nix (reproducible)
              WITH                              • Cloud APIs (by choice)
                                                
    🏃‍♂️ JUMP OFF THE WHEEL                       🎯 Third Act Philosophy:
               ↓                                "Choose tools that will
        ┌─────────────┐                         outlast any framework"  
        │  PIPULATE   │
        │ Local-First │
        │+ Any Cloud  │
        └─────────────┘
                                               
```
<!-- END_ASCII_ART: breaking-free-framework-churn -->

- **Local-First Sovereignty:** Your data, code, and AI run on your hardware by default—extending to cloud services when you choose. This guarantees privacy, eliminates surprise costs, and gives you complete control over when and how to scale.
- **WET Workflows, DRY Framework:** Workflows are intentionally "WET" (explicit & step-by-step) for maximum clarity and customizability—perfectly mirroring Jupyter Notebooks. The underlying framework is "DRY" for efficiency.

- **The AI Advantage:** AI makes WET practical. Tedious code maintenance and refactoring, once a weakness of WET, is now an area where AI excels, turning repetition into a strength for rapid, context-aware development. Our breakthrough **Workflow Reconstruction System** exemplifies this: intelligent AST-based transplantation of workflow components eliminates traditional OOP inheritance complexity while maintaining perfect code precision.
- **Radical Transparency ("Know EVERYTHING!"):** We reject opaque enterprise patterns in favor of complete observability. State is managed in transparent SQLite tables and JSON blobs, making the entire system intuitive and debuggable. No black boxes, ever.
- **Reproducibility with Nix:** Nix Flakes provide a perfect, reproducible Linux environment on macOS, Linux, and Windows (WSL), solving the "works on my machine" problem.
- **Future-Proof Stack:** We rely on durable standards: Python, SQLite, HTML, and HTMX. This is a framework built to last.

### Primary Goals

1. **Empower End-Users (e.g., SEO Practitioners):** Enable non-programmers to run powerful, AI-guided workflows (often ported from Jupyter Notebooks) without needing to interact with Python code directly.
2. **Serve Developers:** Provide a simple, reproducible environment for building these workflows, leveraging integrated tooling like Jupyter, local LLMs, and a streamlined web framework.

--------------------------------------------------------------------------------

## The Technical Stack: Simple Yet Powerful

Pipulate's WET philosophy extends to its technology choices, favoring simple, durable tools over complex abstractions:

## *Not On My Machine* Problem Fixed  <!-- key: not-on-my-machine-problem-fixed -->

> The Cloud's popularity has been driven in part by developers not wanting to maintain multiple codebases or installers per OS. Thanks to Nix, that's all fixed.

### The Bedrock Architecture: Why We Don't Use Docker

> **The Prediction (2025)**: The "Container Era" is a transition, not a destination. We are currently shipping entire user-space operating systems (Docker images) just to run a single binary. It is inefficient, opaque, and fundamentally insecure.

**Pipulate bets on the "Derivation Era."**

In this future, we don't ship containers; we ship **formulas**. We ship the mathematical derivation that *results* in the software.

* **The Old Way (Docker):** "Here is a 500MB blob of binary data. Trust me, it works."
* **The Bedrock Way (Nix):** "Here is a 2KB text file (`flake.nix`). If you evaluate it, you will get the exact same bit-for-bit result I have."

**Why this matters for AI:** AI agents cannot "troubleshoot" why `libc` is missing in a random Ubuntu container. AI needs determinism. It needs a world where `Input + Code = Output`, every single time, without exception. Nix is the only OS that speaks the language of AI: **Pure Functional Logic.**

* **Nix Flakes:** Manages dependencies and creates reproducible environments, ensuring consistency across developers and operating systems, with optional CUDA support. Do you remember *normalize.css* from the wild web that made all browsers show webpages the same? Nix is *normalized Linux* so all Macs, Windows and other Linuxes run your distributed app exactly the same. 

```
     ____                      _       _                        .--.      ___________
    |  _ \  __ _ _ ____      _(_)_ __ (_)_  __    ,--./,-.     |o_o |    |     |     |
    | | | |/ _` | '__\ \ /\ / / | '_ \| \ \/ /   / #      \    |:_/ |    |     |     |
    | |_| | (_| | |   \ V  V /| | | | | |>  <   |          |  //   \ \   |_____|_____|
    |____/ \__,_|_|    \_/\_/ |_|_| |_|_/_/\_\   \        /  (|     | )  |     |     |
                                                  `._,._,'  /'\_   _/`\  |     |     |
    Solving the "Not on my machine" problem well.           \___)=(___/  |_____|_____|
```

**Nix serves as the "Noah's Ark"** creating easily re-hydrated environments that work identically across all platforms and forever into the future. The long promised Holy Grail of *write-once run anywhere* is today achieved with *infrastructure-as-code* (IaC) leveraging a fully featured generic *normalized Linux* called Nix.

## Other Key Technologies Used

Pipulate integrates a carefully selected set of tools aligned with its philosophy:

* **FastHTML:** A Python web framework prioritizing simplicity. It generates HTML directly from Python objects (no template language like Jinja2) and minimizes JavaScript by design, working closely with HTMX. It's distinct from API-focused frameworks like FastAPI. The Python function-naming *is the HTML-template language.*

### The New LAMP Stack: Evolution in Simplicity  <!-- key: new-lamp-stack-comparison -->

<!-- START_ASCII_ART: new-lamp-stack-comparison -->
```
🏛️ ORIGINAL LAMP STACK (2000s)              🚀 NEW LAMP STACK (2025)
═══════════════════════════════              ═══════════════════════════

┌─────────────────────────────┐              ┌─────────────────────────────┐
│  🐧 L: Linux                │              │  🐧 L: Linux + Nix          │
│     Single OS, manual setup │              │     Reproducible everywhere │
├─────────────────────────────┤              ├─────────────────────────────┤
│  🌐 A: Apache               │              │  ⚡ A: ASGI                  │
│     Static config, restarts │              │     Async, hot reload       │
├─────────────────────────────┤              ├─────────────────────────────┤
│  🗄️ M: MySQL                │              │  📊 M: MiniDataAPI          │
│     Complex queries, joins  │              │     Python-native simplicity│
├─────────────────────────────┤              ├─────────────────────────────┤
│  🔧 P: PHP                  │              │  🐍 P: Python + FastHTML    │
│     Mix of HTML/logic       │              │     + HTMX                  │
└─────────────────────────────┘              └─────────────────────────────┘
              │                                            │
              ▼                                            ▼
    ┌─────────────────────┐                    ┌─────────────────────────┐
    │   🏢 Enterprise     │                    │  🏠 Local-First         │
    │   Complexity        │                    │  Sovereignty            │
    │                     │                    │                         │
    │ • Multi-server      │                    │ • Single machine        │
    │ • Load balancers    │                    │ • Integrated AI         │
    │ • Database clusters │         VS         │ • SQLite simplicity     │
    │ • DevOps overhead   │                    │ • Nix reproducibility   │
    │ • Cloud lock-in     │                    │ • Flexible deployment   │
    └─────────────────────┘                    └─────────────────────────┘

    🎯 One person understands                  🎯 One person controls
       part of the system                         the entire system
```
<!-- END_ASCII_ART: new-lamp-stack-comparison -->

The original LAMP stack was beautiful in its simplicity — one person could understand and manage the whole stack. But it got bloated with enterprise patterns, microservices, and distributed complexity.

Pipulate brings back that **"one person, full stack"** philosophy with modern tools:

- **L**inux + **N**ix: Reproducible environments across all platforms
- **A**SGI: Modern async server interface, future-proofed for performance
- **M**iniDataAPI: Universal SQL simplifier close to Python's core data structures
- **P**ython + FastHTML + HTMX: The new web development paradigm

This stack isn't just simpler—it's optimized for AI-assisted development. Here's why:

* **Minimal Surface Area**: The AI doesn't waste time guessing about complex, out-of-context dependencies. More of the relevant code is directly readable and fits into a single prompt.
* **Bedrock Dependencies**: The core components (Python, HTML, HTMX) change at a glacial pace, so they are already well-understood by base AI models, requiring no extra context.
* **Transparent State**: The application's state is kept in simple, server-side formats. An AI can literally read (`grep`) the logs to understand what's happening, offering unparalleled transparency.

This focus on reproducibility, transparency, and AI-friendly ergonomics allows you to hone your craft and build future-proof skills.

### The Lens Stack: Focused Architecture  <!-- key: the-lens-stack -->

Pipulate's technology choices form **aligned lenses** that focus ideas from abstraction to actualization. Each lens must be **ground and polished** without misaligning the focus:

```
     Universal Translator of       Abstractions clarify into implementations
     Spoken Language to Code       by each lens being simple and transparent.

  Idea --> Lens 1   -->   Lens 2  -->  Lens 3  -> Lens 4 -> Lens 5 -> Lens 6

     -----> ,--.
     ---> ,'    `.---------> ,--.
     --> /        \------> ,'    `.-------> ,--.        ,-.
  o  -> /  Linux   \----> /  http  \----> ,'_hx `.--->,'   `.    ,-.
 /|\   (  HARDWARE  )--> ( PROTOCOL )--> ( LINGUA )->( UI/UX )->(APP)->(git)
 / \ -> \   Nix    /----> \  html  /----> `..py ,'--->`.   ,'    `-'
     --> \        /------> `.    ,'-------> `--'        `-'    And so on
     ---> `.    ,'---------> `--'         AI Help
     -----> `--'           AI Help
          AI Help
```

We keep lenses minimal, their material either thoroughly pre-trained into the model (Python 3.x, HTMX, etc.) or able to be included in the prompt and easily held in the context window. We've trimmed the cruft — the lens flashes and burrs, and all unnecessary extra lenses (Angular, React, Vue, etc.)

```yaml
HARDWARE:
  assets/installer/install.sh: Published on Pipulate.com to initiate magic cookie install 
  flake.nix: Nix IaC creating a normalized Linux subsystem on any host OS
PROTOCOL:
  http: Uvicorn fast Asynchronous Server Gateway Interface (ASGI) web server
  html: Uvicorn talks to Python Starlette using anyio & httpx libraries
LINGUA:
  htmx: /assets/htmx.js JavaScript library to eliminate most need for JavaScript
  Python: .venv/bin/python3.12 latest version AIs are well trained on
UI/UX:
  browser: Obviously, but I guess it needs to be said. Like a looser Electron.
  fasthtml: /assets/fasthtml.js for FT Components, Python functions as templating
APP:
  app: Flask-style Uvicorn factory instance instantiated by FastHTML fast_app
  db: Dict-like DB providing transparent server-side state (server cookies)
  pipulate: Pipeline state management, like db but with JSON blob for workflows
```

### Grinding Off the Burrs and Flashes  <!-- key: grinding-off-burrs-flashes -->

In lens manufacturing, "flashes" are excess material that squeeze out of molds — unwanted projections that must be ground off. Steve Jobs famously did this twice: adopting Gorilla Glass (grinding off plastic flashes) and rejecting Flash Player (grinding off software bloat).

**Pipulate continues this tradition:**
- **FastHTML**: Grinds off Jinja2 template complexity
- **HTMX**: Grinds off virtual DOM overhead
- **Local AI**: Enables privacy by default, cloud power when desired
- **SQLite**: Grinds off enterprise database complexity

The result: clean, focused tools that do their job without unnecessary cruft.

--------------------------------------------------------------------------------

## From Flask to FastAPI to FastHTML

This is not your father's Python web framework. HTMX changes everything — a marriage made in heaven between Python and the Web, finally turning Python into a first-class citizen for web development. In many use cases such as this one, Python is even preferable to JavaScript in the way it blends Python's formidable ecosystem of packages with workflows.

### The Evolution: Flask → FastAPI → FastHTML  <!-- key: the-evolution-flask-fastapi-fasthtml -->

The revolution isn't just another framework — it's eliminating the template layer entirely:

```
    🍶 FLASK ERA              🚀 FASTAPI ERA            🌐 FASTHTML ERA
    ═══════════════           ═══════════════           ══════════════════

    ┌─────────────┐           ┌─────────────┐           ┌─────────────┐
    │   Python    │           │   Python    │           │   Python    │
    │  Functions  │           │  Functions  │           │  Functions  │
    └──────┬──────┘           └──────┬──────┘           └──────┬──────┘
           │                         │                         │
           ▼                         ▼                         ▼
    ┌─────────────┐           ┌─────────────┐           ┌─────────────┐
    │   Jinja2    │           │  Pydantic   │           │    HTMX     │◄─ Over-the-wire
    │  Templates  │           │   Models    │           │  Fragments  │   HTML targeting
    └──────┬──────┘           └──────┬──────┘           └──────┬──────┘   DOM elements
           │                         │                         │
           ▼                         ▼                         ▼
    ┌─────────────┐           ┌─────────────┐           ┌─────────────┐
    │    HTML     │           │    JSON     │           │    HTML     │
    │   Response  │           │   Response  │           │  Elements   │
    └─────────────┘           └─────────────┘           └─────────────┘
           │                         │                         │
           ▼                         ▼                         ▼
    🌐 Full Page Reload     📱 Frontend Framework      🎯 DOM Element Updates
                               (React/Vue/Angular)        def Div() = <div>
                                                          def Button() = <button>

    Template files needed    JSON ↔ HTML conversion     Python functions ARE
    Separate languages       Client-side complexity     the template language!
```

**The FastHTML Breakthrough:** Python function names directly become HTML elements, eliminating templates and making the server the single source of truth for UI state.

* **HTMX:** Enables dynamic, interactive UIs directly in HTML via attributes, minimizing the need for custom JavaScript. Pipulate uses it for server-rendered HTML updates — *over the wire HTML*-fragments targeting elements of the DOM directly instead of fragile, performance-reducing, framework-dependent JSON. *THIS* is where you *jump off the tech-churn hamsterwheel* and future-proof yourself.

* **MiniDataAPI:** A lightweight layer for interacting with SQLite and other databases. Uses Python dictionaries for schema definition, promoting type safety without the complexity of traditional ORMs — effectively future-proofing your SQL. You lose fancy *join* capabilities but in exchange get the *Python dict interface* as your main persistent database API forever-forward, enabiling instant swapability between SQLite and PostgreSQL (for example).

* **Ollama:** Facilitates running LLMs locally, enabling in-app chat, workflow guidance, and future automation capabilities while ensuring privacy and avoiding API costs. Your local AI (Chip O'Theseus) learns & grows with you, hopping from hardware to hardware as you upgrade — like a genie in a hermitcrab shell. And if that weren't kooky enough — it knows how to make MCP-calls!!! That's right, your friendly localhost AI Chip O'Theseus is also an *MCP client!* Your linear workflows ain't so linear anymore when a single-step can be: "Go out and do whatever."

### The Hybrid Advantage: Best of Both Worlds

**Pipulate isn't anti-cloud—it's pro-choice.** Each workflow step can choose the best tool for the job:

- **Step 1**: Use local AI for sensitive data analysis (privacy-first)
- **Step 2**: Call OpenAI's API for advanced reasoning (cloud power)  
- **Step 3**: Process results locally and save to SQLite (data sovereignty)
- **Step 4**: Use Anthropic's API for final review (frontier capabilities)

**This is the Swiss Army knife approach:** Local by default, cloud by choice, with complete visibility into what's happening at each step. Whether you're processing confidential client data (local) or need cutting-edge AI capabilities (cloud), Pipulate gives you the framework to do both seamlessly.

* **SQLite & Jupyter Notebooks:** Foundational tools for data persistence and the workflow development process (porting from notebooks to Pipulate workflows). SQLite is built into Python and really all things — the *get-out-of-tech-liability free card* you didn't know you had. And a full JupyterLab instance is installed side-by-side with Pipulate sharing the same Python `.venv` virtual environment, which is also shared with your preferred AI code editor (Cursor, Windsurf, VSCode, Zed) so... well... uhm, there are no words for when 3 different portals-to-Python share the same environment. You can do such stupid AI-tricks as letting your local LLM and a frontier cloud model *inhabit* the same body (Pipulate) — controlling web browsers together and stuff.

--------------------------------------------------------------------------------

## How to Install Pipulate

### Installation Strategy: Universal First, PyPI Alternative  <!-- key: installation-strategy-overview -->

We offer two installation paths that lead to the exact same robust, Nix-managed environment. Choose the path that best fits your experience level and preferences.

```
                            ┌────────────────────────────┐
                            │      New User on macOS     │
                            └─────────────┬──────────────┘
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  │                                               │
                  ▼                                               ▼
  ┌──────────────────────────────────┐   ┌───────────────────────────────────────────┐
  │ PATH 1: Recommended for Everyone │   │ PATH 2: Alternative for Python Developers │
  └──────────────────────────────────┘   └───────────────────────────────────────────┘
                  │                                               │
  "I want the simplest, most               "I prefer managing my command-line
   direct way to get this running."        tools with standard Python utilities."
                  │                                               │
                  ▼                                               ▼
  1. `curl ... [nix]`                      1. `brew install pipx` (If needed)
  2. `curl ... [pipulate]`                 2. `pipx install pipulate`
                                           3. `pipulate install`
                  │                                               │
                  └───────────────┐               ┌───────────────┘
                                  │               │
                                  ▼               ▼
                            ┌────────────────────────────┐
                            │    Nix-Managed Pipulate    │
                            │        Environment         │
                            └────────────────────────────┘
                                         ||
                                    (Identical
                                      Result)
```

### PATH 1: Quick Start — Universal Installation (Recommended)  <!-- key: quick-start-universal-installation -->

This is the fastest and most universal way to install Pipulate. It has the fewest dependencies and works on any modern Mac, Linux system, or Windows with WSL.

```

    📦 Your Machine            🔧 Add Foundation       🚀 Complete Environment
         Today                       with Nix                 Ready to Go!

    ┌─────────────┐             ┌─────────────┐             ┌─────────────┐
    │ Sad Computer│    Step 1   │   🏗️ Nix    │    Step 2   │ 🎯 Pipulate │
    │   Without   │ ──────────► │ Foundation  │ ──────────► │   + AI +    │
    │    Nix😢    │             │  Installed  │             │   Jupyter   │
    └─────────────┘             └─────────────┘             └─────────────┘
                                                                    │
                                                             Step 3 │
                                                                    ▼
                                                             ┌─────────────┐
                                                             │ 🌐 Browser  │
                                                             │    Opens    │
                                                             │Automatically│
                                                             └─────────────┘

    Simple as 1-2-3! No Docker, no build steps, works with or without cloud services.
Everything runs locally with complete flexibility and control.
```

**Step 1: Install Nix (One-Time Setup)**

If you don't have it already, install the Nix package manager. It's the system that makes Pipulate's reproducible environment possible.

```bash
curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install
```

> **Important:** After the Nix installation finishes, you **must close and reopen** your Terminal window.

**Step 2: Run the Pipulate Installer**

Now, run the universal install script. You can give your project a custom name, too.

```bash
# To install with a custom name like "Botifython"
curl -L https://pipulate.com/assets/installer/install.sh | bash -s Botifython

# Or, to install with the default name "pipulate"
curl -L https://pipulate.com/assets/installer/install.sh | bash
```

**Step 3: Launch Pipulate**

Navigate into your new project directory and launch the environment with `nix develop`.

```bash
# cd into the directory you just created
cd ~/Botifython

# Launch Pipulate
nix develop
```

That's it! The server and JupyterLab will start, and the application will open in your browser.

**Running It Again:**

1. You can just forcibly exit out of that Terminal it's running from.
2. Open a new Terminal, and once again:

```bash
cd ~/Botifython
nix develop
```

**The Big Reset (If Necessary):**

**⚠️ Warning:** This command is destructive. It will permanently delete your project folder, including any data you have created or downloaded. Use it only if you want a completely fresh start.

```bash
rm -rf ~/Botifython
curl -L https://pipulate.com/assets/installer/install.sh | bash -s Botifython
cd ~/Botifython
nix develop
```

Wait for ***BOTH TABS*** to auto-open in your browser.

### 🚨 Installation Troubleshooting

**Common Issues & Solutions:**

| Problem | Solution |
|---------|----------|
| `nix: command not found` | You didn't restart your terminal after Nix installation |
| Browser doesn't open automatically | Manually visit `http://localhost:5001` and `http://localhost:8888` |
| `Permission denied` errors | Make sure you can write to `~/pipulate` directory |
| Port conflicts | Kill processes on ports 5001/8888: `lsof -ti:5001 \| xargs kill -9` |
| Nix build fails | Clear Nix cache: `nix-collect-garbage` then retry |

**System Requirements:**
- **macOS**: 10.15+ (Intel/Apple Silicon)
- **Linux**: Any modern distribution with curl 
- **Windows**: WSL2 with Ubuntu 20.04+
- **RAM**: 4GB minimum, 8GB recommended
- **Disk**: 2GB for installation + data storage
- **Network**: Internet connection for initial setup only

---

### PATH 2: Alternative Installation via PyPI (For Python Developers)  <!-- key: alternative-installation-pypi -->

If you are a developer comfortable with tools like Homebrew and `pipx`, you can use our PyPI package as a gateway to the same robust installation.

**Step 1: Install `pipx`**

`pipx` is a tool for safely installing Python command-line applications. If you don't have it, you can install it with Homebrew.

```bash
brew install pipx
```

**Step 2: Install the Pipulate CLI**

Use `pipx` to install the `pipulate` command-line tool. This will not cause conflicts with your system Python.

```bash
pipx install pipulate
```

**Step 3: Run the Installer**

Use the command you just installed to set up the full Pipulate application.

```bash
pipulate install
```

This will trigger the same universal installation process, resulting in the exact same robust, Nix-managed environment. To run it in the future, just type `pipulate run`.

These few commands:
- ✅ Updates to the latest version automatically
- ✅ Starts JupyterLab and the Pipulate server
- ✅ Opens web interfaces in your browser
- ✅ Provides a complete, reproducible development environment

**That's it!** You now have a local-first development environment with AI integration, installed via your preferred Python toolchain.

### Installation Process Deep Dive  <!-- key: installation-process-diagram -->

Here's what happens behind the scenes during the "magic cookie" installation:

```
User runs assets/installer/install.sh (via curl)           Nix Flake Activation & Transformation
┌──────────────────────────────┐         ┌────────────────────────────────────────────┐
│ 1. Download assets/installer/install.sh       │         │ 5. User runs 'nix develop'                 │
│ 2. Download ZIP from GitHub  │         │ 6. Flake detects non-git directory         │
│ 3. Extract ZIP to ~/AppName  │         │ 7. Flake clones repo to temp dir           │
│ 4. Download ROT13 SSH key    │         │ 8. Preserves whitelabel.txt, .ssh, .venv     │
│    to .ssh/rot               │         │ 9. Moves git repo into place               │
└─────────────┬────────────────┘         │10. Sets up SSH key for git                 │
              │                          │11. Transforms into git repo                │
              ▼                          │12. Enables auto-update via git pull        │
      ┌─────────────────────────────────────────────────────────────────────────────┐
      │ Result: Fully functional, auto-updating, git-based Pipulate installation    │
      └─────────────────────────────────────────────────────────────────────────────┘
```

### The "Magic Cookie" Pattern: Bridging the Chasm

This installation method is a deliberate architectural pattern designed to lower the **Activation Energy** of adopting immutable infrastructure.

Standard Nix adoption fails because it demands users learn a new language and mental model *before* they can run "Hello World." We inverted the dependency graph:

1.  **Universal Entry:** We use `curl|bash` (the lowest common denominator).
2.  **The Trojan Horse:** We download a Zip (bypassing the need for Git configuration).
3.  **Self-Bootstrapping:** The Flake activates itself, installing the tools needed to manage itself.
4.  **The Metamorphosis:** Only *after* the environment is stable do we transform the directory into a Git repository.

You aren't just running a script; you are instantiating a self-healing, mathematically reproducible development environment that creates its own "Bedrock" on your machine.

--------------------------------------------------------------------------------

## Chef or Customer?  <!-- key: target-audience -->

Are you a Developer or an End User? Chef or Customer? Understanding your audience is crucial for effective development. Pipulate serves two distinct but complementary audiences, much like a restaurant serves both chefs and customers

```
    ┌──────────────────────────────────────────────────────────┐
    │                      The Restaurant                      │
    │  ┌──────────────────┐              ┌──────────────────┐  │
    │  │   Kitchen (Dev)  │              │  Dining Room     │  │
    │  │                  │              │  (End Users)     │  │
    │  │                  │              │                  │  │
    │  │  👨‍🍳 Sous Chef    │───recipes───►│  🍽️ Customers    │  │
    │  │  👩‍🍳 Head Chef    │              │  🏢 Restaurateur │  │
    │  │                  │              │                  │  │
    │  │ "How do we make  │              │ "I want the best │  │
    │  │  pasta you've    │              │  pasta I've ever │  │
    │  │  never had?"     │              │  had in my life" │  │
    │  └──────────────────┘              └──────────────────┘  │
    └──────────────────────────────────────────────────────────┘
```

### 👨‍🍳 The Chef (Developer/Technical User)
* **🔧 Workflow Creators:** Build and customize AI-assisted workflows
* **📓 Jupyter Porters:** Convert notebook experiments into guided applications
* **🔍 Technical SEOs:** Create sophisticated, reusable SEO processes
* **⚙️ System Administrators:** Deploy consistent environments across teams

**What Chefs Get:**
- 🎛️ Complete control over the "recipe" (workflow logic)
- 🔄 Reproducible development environment via Nix
- 🏗️ Simple architecture that's easy to understand and modify
- 🧰 Integrated tooling (Jupyter, local LLM, SQLite)

### 🍽️ The Customer (End User/Non-Technical)
* **📈 SEO Practitioners:** Run powerful workflows without coding
* **✍️ Content Creators:** Use AI-assisted processes for optimization
* **📊 Marketing Teams:** Execute consistent SEO strategies
* **🏢 Business Owners:** Access enterprise-level SEO capabilities

**What Customers Get:**
- 🚶‍♂️ Guided, step-by-step workflow experiences
- 🤖 AI assistance at every step
- 🙈 No need to see or understand the underlying code
- 🎯 Consistent, repeatable results

### 🍝 The Restaurant Analogy
Just as a chef talks about knife techniques while a diner just wants amazing pasta, Pipulate separates the complexity of creation from the simplicity of consumption. Developers craft the workflows, end-users enjoy the results.

## 🎯 Your First 10 Minutes with Pipulate

**After installation succeeds, here's what to expect:**

### What You'll See
1. **Two browser tabs open automatically:**
   - `localhost:5001` - Pipulate web interface with navigation menu
   - `localhost:8888` - JupyterLab for development/experimentation

2. **In the Pipulate interface:**
   - Left sidebar with workflow plugins (Introduction, Profiles, etc.)
   - Main area showing step-by-step workflow interface  
   - Right panel with integrated AI chat (Chip O'Theseus)

3. **Terminal shows:**
   ```
   🚀 Starting Pipulate servers...
   ✓ FastHTML server ready at http://localhost:5001  
   ✓ JupyterLab ready at http://localhost:8888
   ✓ Local AI ready for chat assistance
   ```

### Your Next Steps Depend on Who You Are

**🔍 If you're an SEO practitioner:**
- Click "Introduction" in the left menu for a guided tour
- Try the built-in workflows to see the step-by-step pattern
- Use the AI chat to ask "How do I create a keyword research workflow?"

**👨‍💻 If you're a developer:**
- Open JupyterLab tab and run the introduction notebook
- Check out `apps/010_introduction.py` to see workflow code structure
- Try creating a simple workflow: `python helpers/workflow/create_workflow.py`

**🤖 If you're an AI assistant:**
Your primary goal is to **read, understand, and modify the Python workflow files** in the `/apps` directory. Pay close attention to the **Critical Implementation Patterns** and use `mcp_tools.py` as your guide for tool-calling capabilities.

**🆕 If you're just exploring:**
- Click through the left menu items to see different workflow types
- Ask the AI chat: "What can I build with Pipulate?"
- Try the Introduction workflow to see the step-by-step experience

--------------------------------------------------------------------------------

## The WET Revolution: Why Explicit Code Wins in the AI Era

Pipulate is built on a radical philosophy that challenges programming orthodoxy: **WET (Write Everything Twice) is better than DRY (Don't Repeat Yourself)** when you have AI to help manage it.

### The Universal API Pattern: From Quarks to Code  <!-- key: universal-api-pattern -->

At every scale of reality, we see the same pattern: **"lumps of stuff" with APIs** that enable interaction. Quarks combine into atoms, atoms into molecules, cells into organisms, individuals into societies. Each level requires the right **granularity** of interface — not so abstract that you lose control, not so granular that you drown in complexity.

**This is the 80/20 rule of existence:** Handle 80% of interactions gracefully with 20% of the API surface, then handle edge cases as needed. Pipulate applies this principle to code architecture.

### Durable vs. Ephemeral: Building on Bedrock  <!-- key: durable-vs-ephemeral -->

The tech industry suffers from "hamster wheel syndrome" — constantly breaking APIs that force migration cycles. React (20+ versions), Node (frequent breaking changes), Angular (complete rewrites). This isn't progress; it's planned obsolescence.

**Pipulate chooses durable foundations:**
- **Linux Kernel**: Version 6 in 30 years
- **Python**: Version 3 in 30 years
- **HTML**: Version 5 and stable
- **HTTP**: Version 3 and backward compatible

These are the "laws of physics" for software — stable APIs that enable compound growth rather than constant rebuilding.

### Why WET Works Now  <!-- key: why-wet-works-now -->

Traditional development follows DRY principles, creating abstract, complex systems that are hard to understand and modify. But the world has changed:

1. **🔬 Jupyter Notebooks** promote explicit, literate programming
2. **🤖 AI assistants** excel at managing repetitive code
3. **🏠 Local-first architectures** prioritize clarity over enterprise complexity
4. **🎯 Right Granularity**: WET provides the perfect abstraction level for human AND AI comprehension

```
                             ________________________________
 - Like Notebooks           /                                \
 - Linear Workflows        |  It runs proprietary private AI  |
 - Local & Cloud-free      |  Workflows from your Local PC?!  |
 - Chip O'Theseus included  \________________________________/
                                                            ()
      HARDWARE PLATFORM             LOCAL BROWSER             O   , Chip O'Theseus
   _______________________       __________ _______             o \\  .
  |                       |     / Pipulate \Jupyter\__            |\\/|
  | Windows, Mac or Linux |    |  __________________  |   See!    / " '\ - Radical transparency
  |     _____ ___         |    | | App Name   Menu⚙️| |<- - - - -. .   . - MCP tool-call control
  |   _/ Nix \____\_____  |    | |------------------| |         /    ) | - Browser as bot's body
  |  |                  | |    | | Workflow | Local | |        '  _.'  |
  |  |     Pipulate    <---------> -Step #1 | AI🤖  | |        '-'/    \
  |__|  localhost:5001  |_|    | | -Step #2 | Chat  | |      What, no Docker?
     |  (AI on Rails🚂) |      | | -Step #3 | Help▸ | |      What, no React?
     |__________________|      | |__________|_______| |      What, no Cloud?
                               |______________________|
```

**WET workflows are:**
- **🔍 Observable**: See exactly what's happening at every step
- **🔧 Customizable**: Modify workflows without breaking abstractions
- **🤖 AI-Friendly**: Clear code that AI assistants can easily understand and maintain
- **🚀 Future-Proof**: Built on durable web standards that won't become obsolete

--------------------------------------------------------------------------------

## Developer Setup & Environment Notes

**Nix Environment Activation:** Always run `nix develop` from the `~/pipulate` directory *before* running any project commands (`python server.py`, `pip install`, etc.) in a new terminal. This ensures you are using the correct dependencies defined in `flake.nix`.

**Interactive vs. Quiet Shell:**

**Standard Shell:** `nix develop` (or `nix develop .#default`) runs the startup script (`run-script` defined in `flake.nix`) with welcome messages and service startup. Ideal for general use.

**Quiet Shell:** `nix develop .#quiet` activates the Nix environment *without* running the full startup script or launching services automatically. It only sets up paths and installs pip requirements. Use this for:
- Running specific commands without starting the servers (e.g., `nix develop .#quiet --command python -c "import pandas"`).
- Debugging or interacting with AI assistants where verbose startup output is undesirable.
- Manually running `run-server` or `run-jupyter` (scripts placed in `.venv/bin` by the `shellHook`).

**Dependencies:** System-level dependencies (Python version, libraries like `gcc`, `zlib`) are managed by `flake.nix`. Python package dependencies are managed by `pip` using `requirements.txt` within the Nix-provided environment.

**Source of Truth:** The `flake.nix` file is the definitive source for the development environment setup.

--------------------------------------------------------------------------------

## Architecture & Key Concepts

Pipulate features a distinct architecture designed for its local-first, simple, and observable nature.

### Architecture Overview Diagram  <!-- key: architecture-overview-diagram -->

This diagram illustrates the high-level components and their interactions:

```
                 ┌─────────────┐ Like Electron, but full Linux subsystem
                 │   Browser   │ in a folder for macOS and Windows (WSL)
                 └─────┬───────┘
                       │ HTTP/WS
                       ▼
    ┌───────────────────────────────────────┐
    │           Nix Flake Shell             │ - In-app LLM (where it belongs)
    │  ┌───────────────┐  ┌──────────────┐  │ - 100% reproducible
    │  │   FastHTML    │  │    Ollama    │  │ - 100% local
    │  │   HTMX App    │  │  Local LLM   │  │ - 100% multi-OS
    │  └───────┬───────┘  └──────────────┘  │
    │          │                            │
    │    ┌─────▼─────┐     ┌────────────┐   │
    │    │MiniDataAPI│◄───►│ SQLite DB  │   │
    │    └───────────┘     └────────────┘   │
    └───────────────────────────────────────┘
```

This complete, self-contained environment runs identically on any operating system, providing the foundation for all Pipulate workflows and AI interactions.

---

### Integrated Data Science Environment  <!-- key: integrated-data-science-environment -->

Jupyter Notebooks run alongside the FastHTML server, allowing developers to prototype workflows in a familiar environment before porting them to Pipulate's step-based interface for end-users. The same Python virtual environment (`.venv`) is shared, and ad-hoc package installation is supported. If you're using Cursor, VSCode or Windsurf, set your `Ctrl`+`Shift`+`P` "Python: Set Interpreter" to "Enter Interpreter Path" `./pipulate/.venv/bin/python`. You might have to adjust based on the folder you use as your workspace. But then you'll have a Python environment unified between Cursor, JupyterLab and Pipulate.

```
      ┌──────────────────┐    ┌──────────────────┐
      │   Jupyter Lab    │    │    FastHTML      │
      │   Notebooks      │    │     Server       │
      │ ┌──────────┐     │    │  ┌──────────┐    │
      │ │ Cell 1   │     │    │  │ Step 1   │    │
      │ │          │     │--->│  │          │    │
      │ └──────────┘     │    │  └──────────┘    │
      │ ┌──────────┐     │    │  ┌──────────┐    │
      │ │ Cell 2   │     │    │  │ Step 2   │    │
      │ │          │     │--->│  │          │    │
      │ └──────────┘     │    │  └──────────┘    │
      │  localhost:8888  │    │  localhost:5001  │
      └──────────────────┘    └──────────────────┘
```

### Starting Workflows in Jupyter Notebooks

Pipulate's `pipulate` module can be imported in any Notebook, providing an ideal location to mock up new, fully operational workflows that are easy to port into the Pipulate Web App later. A simple:

```python
import pipulate as pip
````

...at the top of a Notebook (following the conventions of `import numpy as np`) gives you all of Pipulate's state-management capabilities. This dramatically simplifies notebook logic, compels adherence to a linear `input` -\> `process` -\> `output` pattern, and makes porting to the web UI trivial.

The abstract template is:

```python
import pipulate as pip

# Define a job name, which corresponds to one record in the database
job = "Workflow_Mockup_in_Notebook"

# Cell 1: Set some initial data
pip.set(job, step="customer_name", value="ACME Corp")
pip.set(job, step="year", value=2025)

# Cell 2: Retrieve data and add more
# This works even if you restart the kernel between cells!
customer = pip.get(job, step="customer_name")
print(f"Working on job for {customer}")

pip.set(job, step="contact_person", value="Wile E. Coyote")

# Cell 3: View the final state
final_state = pip.read(job)
print(final_state)
# Output: {'customer_name': 'ACME Corp', 'year': 2025, 'contact_person': 'Wile E. Coyote'}
```

When you're done, you'll have a working process in a Jupyter Notebook. You can use it as is, or port it to a Pipulate `apps/` file to make it easily accessible to non-Python users via the Web App.

### Local-First & Single-Tenant Details  <!-- key: local-first-single-tenant-details -->

Pipulate manages all state server-side within the local environment (think *local-server cookies*), with optional cloud integration as needed. This approach offers:
* **Privacy & Control:** Data stays local by default, cloud integration when you choose.
* **Full Resource Access:** Utilize local CPU/GPU freely for intensive tasks, plus cloud APIs for heavy lifting.
* **Simplicity:** Eliminates complexities of multi-tenancy while supporting both local and cloud workflows.
* **Observability:** State changes (via DictLikeDB/JSON) are transparent and easily logged (AI greps it there).

### Local-First State Management Benefits  <!-- key: local-first-state-management-benefits -->

This detailed view shows how Pipulate's local-first architecture eliminates common web development complexities:

```
      ┌───────────────────────────────┐ # Benefits of Local-First Simplicity
      │          Web Browser          │
      │                               │ - No mysterious client-side state
      │    ┌────────────────────┐     │ - No full-stack framework churn
      │    │   Server Console   │     │ - No complex ORM or SQL layers
      │    │     & Web Logs     │     │ - No external message queues
      │    └─────────┬──────────┘     │ - No build step required
      │              ▼                │ - Direct, observable state changes
      │    ┌─────────────────────┐    │
      │    │  Server-Side State  │    │ - Conceptually like local-server-side cookies
      │    │  DictLikeDB + JSON ◄──────── Enables the "Know EVERYTHING!" philosophy
      │    └─────────────────────┘    │ - AI greps logs/server.log to see app state!
      └───────────────────────────────┘
```

### Server-Rendered UI (HTMX)  <!-- key: server-rendered-ui-htmx -->

The UI is constructed primarily with server-rendered HTML fragments delivered via HTMX. This minimizes client-side JavaScript complexity.
* FastHTML generates HTML components directly from Python.
* HTMX handles partial page updates based on user interactions, requesting new HTML snippets from the server.
* WebSockets and Server-Sent Events (SSE) provide real-time updates (e.g., for chat, live development reloading).

```
                        HTMX+Python enables a world-class
                  Python front-end Web Development environment.
                             ┌─────────────────────┐
                             │    Navigation Bar   │  - No template language (like Jinja2)
                             ├─────────┬───────────┤  - HTML elements are Python functions
  Simple Python back-end     │  Main   │   Chat    │  - Minimal custom JavaScript / CSS
  HTMX "paints" HTML into    │  Area   │ Interface │  - No React/Vue/Angular overhead
  the DOM on demand ───────► │         │           │  - No "build" process like Svelte
                             └─────────┴───────────┘  - No virtual DOM, JSX, Redux, etc.
```

With such *minimal surface area* the AI code assistant *knows everything.* LLMs are either pre-trained on the stable, infrequently revved libraries used (Python 3.12, HTMX, or it's all small enough to fit in a 1-shot prompt — yes, the whole core code-base fits in one Gemini Web UI form submit.

--------------------------------------------------------------------------------

## Workflow Patterns & Development

### Pipeline Workflows  <!-- key: pipeline-workflows -->

Designed for porting notebook-style processes, workflows are sequences of steps where the state is managed explicitly at each stage and stored persistently (typically as a JSON blob in the `pipeline` table).
* **Resumable & Interrupt-Safe:** Because each step's completion is recorded, workflows can be stopped and resumed.
* **Explicit State Flow:** Data typically passes from one step's output (`done` field) to the next via the `transform` function, simplifying debugging. Patterned on Unix pipes.
* **Good Training Data:** The structured input/output of each step creates valuable data for potentially fine-tuning models.
* **Proprietary Friendly:** Excellent for proprietary domain-experts and fields (competing academic, finances) who *resist* letting their data flow onto the Web for general AI training.

```
  ┌─────────┐        ┌─────────┐        ┌─────────┐   - Fully customizable steps
  │ Step 01 │─piped─►│ Step 02 │─piped─►│ Step 03 │   - Interruption-safe & resumable
  └─────────┘        └─────────┘        └─────────┘   - Easily ported from Notebooks
       │                  │                  │        - One DB record per workflow run
       ▼                  ▼                  ▼        - Everything stays on your machine
  State Saved        State Saved         Finalized?   - Magnitudes simpler than celery
```

### Run All Cells Pattern  <!-- key: run-all-cells-pattern -->

**The key insight**: Pipulate workflows use a `run_all_cells()` pattern that directly mirrors Jupyter's "Run All Cells" command. This creates an immediate mental model — each workflow step is like a notebook cell, and the system automatically progresses through them top-to-bottom, just like running all cells in a notebook.

```
    📓 JUPYTER NOTEBOOK               🌐 PIPULATE WORKFLOW
    ═══════════════════               ══════════════════════

    [ ] Cell 1: Import data          ┌─────────────────────┐
        │                            │  Step 1: Data Input │
        ▼                            └──────────┬──────────┘
    [▶] Cell 2: Process data                    │ hx_trigger="load"
        │                                       ▼
        ▼                            ┌─────────────────────┐
    [ ] Cell 3: Generate report      │ Step 2: Processing  │
        │                            └──────────┬──────────┘
        ▼                                       │ hx_trigger="load"
    [ ] Cell 4: Export results                  ▼
                                     ┌─────────────────────┐
    🎯 "Run All Cells" Button   ═══► │ Step 3: Export      │
       Executes top-to-bottom        └─────────────────────┘

       Same mental model, same execution flow!
       But with persistent state, a web UI and
       not having to look at the Python code 🚫🐍.
```

### LLM Integration (Ollama)  <!-- key: llm-integration-ollama -->

Integration with a local Ollama instance provides AI capabilities without external API calls:
* **Privacy:** Prompts and responses stay local.
* **Cost-Effective:** No per-token charges; run continuously using local resources.
* **Streaming Support:** Real-time interaction via WebSockets.
* **Bounded Context:** Manages conversation history effectively.
* **App State Awareness:** Grepping your server log reveals full application state.
* **Tool Calling:** Local LLM is an MCP client with a growing list of abilities
  - Workflow assistance
  - Browser automation
  - Debugging

```
                   ┌──────────────────┐
                   │   Local Ollama   │ - No API keys needed
                   │      Server      │ - Completely private processing
                   └────────┬─────────┘
                            │
                            │ Streaming via WebSocket
                            ▼
                   ┌──────────────────┐
                   │   Pipulate App   │ - Monitors WS for MCP tool-call commands
                   │(WebSocket Client)│ - Parses responses in real-time
                   └────────┬─────────┘
                            │
                            │ In-memory or DB backed
                            ▼
                   ┌──────────────────┐
                   │     Bounded      │ - Manages context window (~128k)
                   │   Chat History   │ - Enables RAG / tool integration
                   └──────────────────┘
```

### Multi-OS & CUDA Support (Nix)  <!-- key: multi-os-cuda-support-nix -->

Nix Flakes ensure a consistent environment across Linux, macOS, and Windows (via WSL), optionally leveraging CUDA GPUs if detected.

```
               ┌──────────────────┐
               │  Linux / macOS   │ - Write code once, run anywhere
               │  Windows (WSL)   │ - Consistent dev environment via Nix
               └────────┬─────────┘ - As if Homebrew but across all OSes
                        │
                        │ Nix manages dependencies
                        ▼
               ┌──────────────────┐
               │   CUDA Support   │ - Auto-detects NVIDIA GPU w/ CUDA
               │   (if present)   │ - Uses GPU for LLM acceleration
               └──────────────────┘ - Falls back to CPU if no CUDA
```

### UI Layout  <!-- key: ui-layout -->

The application interface is organized into distinct areas:

```
               ┌─────────────────────────────┐
               │         Navigation         ◄── Search, Profiles,
               ├───────────────┬─────────────┤    Apps, Settings
               │               │             │
    Workflow, ──►   Main Area  │    Chat     │
    App UI     │   (Pipeline)  │  Interface ◄── LLM Interaction
               │               │             │
               └─────────────────────────────┘
```

### UI Component Hierarchy: Complete DOM Structure with IDs & ARIA Labels

**Critical for AI assistants:** All UI components use semantic IDs and comprehensive ARIA labeling for accessibility and automation.

```
🏠 home (Root Component)
├── 📦 create_outer_container()
│   ├── 🧭 create_nav_group() [id='nav-group', role='navigation', aria-label='Main navigation']
│   │   ├── 🔍 nav_search_container [role='search', aria-label='Plugin search']
│   │   │   ├── Input [id='nav-plugin-search', role='searchbox', aria-label='Search plugins']
│   │   │   └── Div [id='search-results-dropdown', role='listbox', aria-label='Search results']
│   │   ├── 👤 create_profile_menu() [id='profile-dropdown-menu', aria-label='Profile management']
│   │   │   ├── Summary [id='profile-id', aria-label='Profile selection menu']
│   │   │   └── Ul [role='menu', aria-label='Profile options', aria-labelledby='profile-id']
│   │   ├── ⚡ create_app_menu() [id='app-dropdown-menu', aria-label='Application selection']
│   │   │   ├── Summary [id='app-id', aria-label='Application menu']
│   │   │   └── Ul [role='menu', aria-label='Application options', aria-labelledby='app-id']
│   │   ├── 🌍 create_env_menu() [id='env-dropdown-menu', data-testid='environment-dropdown-menu']
│   │   │   ├── Summary [id='env-id', aria-label='Environment selection menu']
│   │   │   └── Ul [role='menu', aria-label='Environment options', aria-labelledby='env-id']
│   │   └── ⚙️ poke_section [id='poke-dropdown-menu']
│   │       ├── Summary [id='poke-summary']
│   │       └── Div [id='nav-flyout-panel']
│   ├── 📱 main-grid
│   │   ├── 📋 create_grid_left() [id='grid-left-content'] → Workflow Steps/Cells Display
│   │   │   ├── content_to_render (Dynamic workflow content)
│   │   │   └── scroll_to_top [id='scroll-to-top-link']
│   │   └── 🤖 create_chat_interface() [id='chat-interface', role='complementary', aria-label='AI Assistant Chat']
│   │       ├── H2 [APP_NAME + ' Chatbot']
│   │       ├── Div [id='msg-list', role='log', aria-label='Chat conversation', aria-live='polite']
│   │       └── Form [role='form', aria-label='Chat input form']
│   │           ├── Textarea [id='msg', role='textbox', aria-label='Chat message input', aria-multiline='true']
│   │           ├── Button [id='send-btn', aria-label='Send message to AI assistant']
│   │           └── Button [id='stop-btn', aria-label='Stop AI response streaming']
│   └── 🔧 HTMX Refresh Listeners
│       ├── Div [id='profile-menu-refresh-listener', hx_target='#profile-dropdown-menu']
│       └── Div [id='app-menu-refresh-listener', hx_target='#app-dropdown-menu']
```

### 🎯 Key HTMX Targets for AI Browser Automation

**Navigation Updates:**
- `#profile-dropdown-menu` - Profile menu refresh target
- `#app-dropdown-menu` - App menu refresh target  
- `#search-results-dropdown` - Live search results
- `#nav-flyout-panel` - Settings flyout panel

**Content Areas:**
- `#grid-left-content` - Main workflow display area
- `#msg-list` - Chat conversation history
- `body` - Full page navigation refreshes

**Interactive Elements:**
- `#nav-plugin-search` - Real-time plugin search (300ms delay)
- `#send-btn` / `#stop-btn` - Chat control buttons
- `#scroll-to-top-link` - Scroll navigation aid

This structure enables AI assistants to programmatically interact with all UI components using semantic selectors and ARIA landmarks.

### File Structure (needs updating)

```plaintext
    .
    ├── .venv/                     # Common Python environment for FastHTML, Jupyter & Cursor
    ├── apps/                      # Workflow plugins (010_introduction.py, 400_trifecta.py, etc.)
    ├── browser_cache/        # Selenium browser control & DOM capture
    │   ├── looking_at/            # Current browser DOM state for AI visibility
    │   └── *.py                   # Google search automation examples
    ├── cli.py                     # Command line interface for Pipulate operations
    ├── data/
    │   └── data.db                # AI-accessible SQLite for application state (server cookies)
    ├── downloads/                 # Default location for workflow outputs (e.g., CSVs)
    ├── assets/                    # JS, CSS, images, icons
    ├── pyproject.toml             # Python packaging configuration and metadata
    ├── flake.nix                  # Infrastructure as Code & all system-versions for AI
    ├── LICENSE                    # It's MIT
    ├── README.md                  # This file
    ├── requirements.txt           # Python dependencies (managed by Nix)
    └── server.py                  # Main application entry point
```

--------------------------------------------------------------------------------

## Critical Implementation Patterns for LLMs

**These patterns are essential for LLMs working with Pipulate and are frequently missed:**

### 1. The Auto-Key Generation Pattern (MOST CRITICAL)  <!-- key: auto-key-generation-pattern -->

<!-- START_ASCII_ART: auto-key-generation-pattern -->
```
📝 AUTO-KEY GENERATION FLOW
┌─────────────┐    POST     ┌─────────────┐    HX-Refresh   ┌─────────────┐
│ Empty Form  │ ──────────► │   Server    │ ──────────────► │ Page Reload │
│ Submit ⏎    │    /init    │  Response   │     Header      │   Trigger   │
└─────────────┘             └─────────────┘                 └─────────────┘
       ▲                                                            │
       │                                                            ▼
┌─────────────┐              ┌─────────────┐                ┌─────────────┐
│ User Hits   │ ◄─────────── │ Auto-Key    │ ◄───────────── │ landing()   │
│ Enter Again │    Ready!    │ Populated   │    Generates   │   Method    │
└─────────────┘              └─────────────┘                └─────────────┘
```
<!-- END_ASCII_ART: auto-key-generation-pattern -->

When a user hits Enter on an empty key field, this specific sequence occurs:

1. **Form Submission**: POSTs to `/{APP_NAME}/init` with empty `pipeline_id`
2. **Server Response**: The `init` method MUST return an `HX-Refresh` response:
   ```python
   if not user_input:
       from starlette.responses import Response
       response = Response('')
       response.headers['HX-Refresh'] = 'true'
       return response
   ```
3. **Page Reload**: HTMX triggers a full page reload
4. **Auto-Key Population**: The `landing()` method calls `pip.generate_pipeline_key(self)` to populate the input field
5. **User Interaction**: User hits Enter again to start the workflow

### 2. The Chain Reaction Pattern: The `run_all_cells()` Breakthrough

Pipulate uses HTMX-driven step progression powered by the brilliantly named `run_all_cells()` method:

1. **Initial Trigger**: After `init`, the `run_all_cells()` method initializes the workflow just like Jupyter's "Run All Cells"
2. **Perfect Mental Model**: The method name creates immediate understanding — workflows execute top-to-bottom like notebook cells
3. **Step Handlers**: Each step has GET (display) and POST (submit) handlers
4. **Automatic Progression**: Completed steps trigger next step with `hx_trigger="load"`
5. **State Persistence**: Each step stores data in pipeline state
6. **Pedagogical Brilliance**: The naming makes the system instantly intuitive for developers and AI assistants

**Example: The `run_all_cells()` Pattern in Action**

```python
# ✅ CORRECT: Use the run_all_cells() method for workflow initialization
async def init(self, request):
    """Initialize workflow using the run_all_cells pattern"""
    return pip.run_all_cells(app_name, steps)

# ❌ ANTI-PATTERN: Manual placeholder creation
async def init(self, request):
    """Manual approach — harder to understand and maintain"""
    first_step_id = steps[0].id
    return Div(
        Div(id=first_step_id, hx_get=f'/{app_name}/{first_step_id}', hx_trigger='load'),
        id=f"{app_name}-container"
    )
```

The `run_all_cells()` method encapsulates the workflow initialization pattern and creates an immediate mental connection to Jupyter notebooks.

### 3. APP_NAME vs. Filename Distinction  <!-- key: app-name-vs-filename -->

<!-- START_ASCII_ART: app-name-vs-filename -->
```
📂 FILENAME vs APP_NAME DISTINCTION
┌─────────────────────────────────────────────────────────────┐
│                    CRITICAL SEPARATION                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📁 FILENAME: 200_workflow_genesis.py                       │
│      ├── 🌐 Determines public URL: /workflow_genesis        │
│      └── 📊 Controls menu order: 200                        │
│                                                             │
│  🏷️  APP_NAME: "workflow_genesis_internal"                  │
│      ├── 💾 Database table identifier                       │
│      ├── 🔒 MUST REMAIN STABLE (data integrity)             │
│      └── 🚫 NEVER change after deployment                   │
│                                                             │
│  ⚠️  DANGER: Changing APP_NAME = Orphaned Data              │
└─────────────────────────────────────────────────────────────┘
```
<!-- END_ASCII_ART: app-name-vs-filename -->

**Critical for data integrity:**

* **Filename** (e.g., `200_workflow_genesis.py`): Determines public URL endpoint and menu ordering
* **APP_NAME Constant** (e.g., `APP_NAME = "workflow_genesis_internal"`): Internal identifier that MUST REMAIN STABLE

### 4. State Management via DictLikeDB

* State stored as JSON blobs in pipeline table
* Accessed via `pip.get_step_data()` and `pip.set_step_data()`
* All state changes are transparent and observable

### 5. Plugin Discovery System  <!-- key: plugin-discovery-system -->

<!-- START_ASCII_ART: plugin-discovery-system -->
```
📁 PLUGIN DISCOVERY SYSTEM
apps/
├── 010_introduction.py       ✅ Registered as "introduction" (menu order: 1)
├── 020_profiles.py           ✅ Registered as "profiles" (menu order: 2)
├── hello_flow (Copy).py      ❌ SKIPPED - Contains "()"
├── xx_experimental.py        ❌ SKIPPED - "xx_" prefix
└── 200_workflow_genesis.py   ✅ Registered as "workflow_genesis" (menu order: 20)

    📊 AUTO-REGISTRATION RULES:
    ✅ Numeric prefix → Menu ordering + stripped for internal name
    ❌ Parentheses "()" → Development copies, skipped
    ❌ "xx_" prefix → Work-in-progress, skipped
    🔧 Must have: landing() method + name attributes
    💉 Auto dependency injection via __init__ signature
```
<!-- END_ASCII_ART: plugin-discovery-system -->

* Files in `apps/` directory are auto-discovered
* Numeric prefixes control menu ordering
* Classes must have `landing` method and name attributes
* Automatic dependency injection based on `__init__` signature

## Workflow Development Helper Scripts

Pipulate includes sophisticated helper scripts for workflow development:

### `create_workflow.py`
Creates new workflows from templates:
```bash
python create_workflow.py workflow.py MyWorkflow my_workflow \
  "My Workflow" "Welcome message" "Training prompt" \
  --template trifecta --force
```

### `splice_workflow_step.py`
Adds steps to existing workflows:
```bash
python splice_workflow_step.py workflow.py --position top
python splice_workflow_step.py workflow.py --position bottom
```

### Template System  <!-- key: workflow-template-system -->

<!-- START_ASCII_ART: workflow-template-system -->
```
🏗️ WORKFLOW TEMPLATE SYSTEM
┌─────────────────┐              ┌─────────────────┐
│  BLANK TEMPLATE │              │TRIFECTA TEMPLATE│
├─────────────────┤              ├─────────────────┤
│ ┌─────────────┐ │              │ ┌─────────────┐ │
│ │   Step 1    │ │              │ │   Step 1    │ │
│ │  (Minimal)  │ │              │ │  (Input)    │ │
│ └─────────────┘ │     VS       │ └──────┬──────┘ │
│                 │              │        │        │
│ Quick Start     │              │        ▼        │
│ Single Purpose  │              │ ┌─────────────┐ │
└─────────────────┘              │ │   Step 2    │ │
                                 │ │ (Process)   │ │
create_workflow.py               │ └──────┬──────┘ │
--template blank                 │        │        │
                                 │        ▼        │
                                 │ ┌─────────────┐ │
                                 │ │   Step 3    │ │
                                 │ │  (Output)   │ │
                                 │ └─────────────┘ │
                                 │                 │
                                 │ Full Pattern    │
                                 │ Complete Flow   │
                                 └─────────────────┘

                                 create_workflow.py
                                 --template trifecta
```
<!-- END_ASCII_ART: workflow-template-system -->

* `blank`: Minimal workflow with one step
* `trifecta`: Three-step workflow pattern
* Automatic method generation and insertion

### Workflow Reconstruction System  <!-- key: workflow-reconstruction-system -->

**The Revolutionary Alternative to OOP Inheritance:** Atomic transplantation of workflow components using intelligent pattern matching and AST precision.

<!-- START_ASCII_ART: workflow-reconstruction-system -->
```
🧬 WORKFLOW RECONSTRUCTION: ATOMIC TRANSPLANTATION
═════════════════════════════════════════════════════════════════════════

    OLD WORKFLOW               WORKFLOW                UPDATED WORKFLOW
   (Atomic Source)           RECONSTRUCTOR            (Incremental Gen)
  ┌─────────────────┐       ┌─────────────────┐      ┌─────────────────┐
  │ 🧬 Components:  │  AST  │ 🎯 Pattern      │ AST  │ ✨ Generated:   │
  │                 │ ───►  │   Matching      │ ───► │                 │
  │ ┌─────────────┐ │       │                 │      │ ┌─────────────┐ │
  │ │step_params* │ │       │ Bundle Type 1:  │      │ │step_params* │ │ ✅
  │ │step_optim*  │ │       │ Auto-Registered │      │ │step_optim*  │ │ ✅  
  │ │parameter*   │ │       │ Methods         │      │ │parameter*   │ │ ✅
  │ └─────────────┘ │       │                 │      │ └─────────────┘ │
  │                 │       │ Bundle Type 2:  │      │                 │
  │ ┌─────────────┐ │       │ Custom Routes   │      │ ┌─────────────┐ │
  │ │_process     │ │       │ (_process,      │      │ │_process     │ │ ✅
  │ │preview      │ │       │  preview)       │      │ │preview      │ │ ✅
  │ └─────────────┘ │       │                 │      │ └─────────────┘ │
  └─────────────────┘       └─────────────────┘      └─────────────────┘

🔄 COMPLETE LIFECYCLE: Test → Validate → Production → Cleanup
  
  --suffix 5        --target new_name       --target same_name      git status
  ──────────        ────────────────        ──────────────────      ──────────
  param_buster5     advanced_params         param_buster (in-place) (shows cruft)
  (safe testing)    (new workflow)          (git history preserved) (clean up!)

🎯 WHY IT WORKS: Lightning in a Bottle
┌─────────────────────────────────────────────────────────────────────────┐
│ ✨ Pattern Matching: No manual markers needed                           │
│ 🔧 AST Precision: Syntactically perfect code generation                 │  
│ 🎭 Inheritance Alternative: Compose without complex super() chains      │
│ 🧪 Safe Testing: Incremental validation without production risk         │
│ 📚 Git Continuity: In-place updates preserve development history        │
│ 🧹 Systematic Cleanup: Prevents file cruft accumulation                 │
└─────────────────────────────────────────────────────────────────────────┘

         workflow_reconstructor.py --template botify_trifecta 
                                       --source parameter_buster
                                       --suffix 5
```
<!-- END_ASCII_ART: workflow-reconstruction-system -->

**The System That Eliminates Bootstrap Paradox:**
* **Atomic Sources:** Battle-tested workflows become component libraries
* **Pattern Matching:** Intelligent detection via `_process`, `preview` patterns
* **AST Transplantation:** Surgical precision without syntax errors
* **Complete Lifecycle:** Development → Testing → Production → Cleanup

## 📋 Quick Reference Card

### Essential Commands
```bash
# Development workflow
cd ~/pipulate && nix develop          # Start Pipulate
nix develop .#quiet                   # Start without auto-services
python server.py                     # Manual server start
git pull && nix develop              # Update to latest

# Create new workflows  
python helpers/workflow/create_workflow.py my_workflow.py MyClass my_internal_name
python helpers/workflow/splice_workflow_step.py my_workflow.py --position top

# Plugin naming conventions
010_my_plugin.py                     # Active plugin (menu order 1)
xx_my_plugin.py                      # Disabled during development  
my_plugin (Copy).py                  # Ignored development copy
```

### Key URLs & Ports
- **Pipulate App**: `http://localhost:5001`
- **JupyterLab**: `http://localhost:8888` 
- **Local AI Chat**: Built into the Pipulate interface
- **Logs**: `tail -f logs/server.log` for debugging

### Critical Patterns for AI Assistants
```python
# Auto-key generation flow
if not user_input:
    response = Response('')
    response.headers['HX-Refresh'] = 'true'
    return response

# Workflow initialization
return pip.run_all_cells(app_name, steps)

# State management
data = pip.get_step_data(step_id)
pip.set_step_data(step_id, updated_data)
```

### File Structure Quick Reference
```
apps/                    # Your workflows (auto-discovered)
├── 010_introduction.py     # Menu order 1
├── xx_draft.py            # Disabled (xx_ prefix)
└── draft (Copy).py        # Ignored (parentheses)

mcp_tools.py               # AI assistant interface  
crud.py                  # Base classes for workflows
browser_cache/        # Selenium automation tools
logs/server.log            # Debug everything here
data/data.db              # SQLite application state
```

## Common LLM Implementation Mistakes  <!-- key: llm-implementation-mistakes -->

<!-- START_ASCII_ART: llm-implementation-mistakes -->
```
🚨 LLM IMPLEMENTATION MISTAKE PREVENTION
┌────────────────────────────────────────────────────────────┐
│                    COMMON PITFALLS                         │
├────────────────────────────────────────────────────────────┤
│ ❌ Missing HX-Refresh      │ ✅ if not user_input:         │
│    Response                │     response.headers['HX-     │
│                            │     Refresh'] = 'true'        │
├────────────────────────────┼───────────────────────────────┤
│ ❌ Wrong Key Generation    │ ✅ pip.generate_pipeline_     │
│    Method                  │     key(self)                 │
├────────────────────────────┼───────────────────────────────┤
│ ❌ Broken Chain Reaction   │ ✅ hx_trigger="load" →        │
│    Pattern                 │     Automatic progression     │
├────────────────────────────┼───────────────────────────────┤
│ ❌ APP_NAME Changes        │ ✅ NEVER modify after         │
│    (Data Orphaning)        │     deployment                │
└────────────────────────────────────────────────────────────┘
```
<!-- END_ASCII_ART: llm-implementation-mistakes -->

**LLMs frequently make these errors:**

1. **Missing HX-Refresh Response**: Forgetting to return the refresh response for empty keys
2. **Incorrect Key Generation**: Not using `pip.generate_pipeline_key(self)` properly
3. **Missing Cursor Positioning**: Forgetting the `_onfocus` attribute for user experience
4. **Wrong Route Handling**: Not understanding the difference between landing page and init routes
5. **State Inconsistency**: Not properly handling the key generation and storage flow
6. **APP_NAME Changes**: Modifying APP_NAME after deployment, orphaning existing data
7. **Chain Reaction Breaks**: Not properly implementing the HTMX step progression pattern

## Key Design Guidelines & Patterns

These "speedbumps" reinforce Pipulate's core philosophy:

  * **Local vs. Enterprise Mindset:** Embrace local-first simplicity. Avoid patterns designed for distributed, multi-tenant systems.
  * **JSON State Management (Workflows):** Keep workflow state in self-contained steps within a single JSON blob per run. Avoid complex state machines or external step tracking.
  * **Database (MiniDataAPI):** Use the simple schema definition and access patterns provided. Avoid heavy ORMs.
  * **Workflow Pattern:** Ensure workflows are linear and state is explicitly passed or saved at each step. Avoid complex async task chaining that obscures state.
  * **UI Rendering Pattern:** Generate HTML directly from Python components via FastHTML. Avoid template engines.
  * **WebSocket Pattern:** Use the dedicated `Chat` class for managing LLM interactions. Avoid raw WebSocket handling elsewhere.
  * **Workflow Progression Pattern:** Workflows use an explicit chain reaction pattern with `hx_trigger="load"` to manage step progression. This pattern must be preserved exactly as implemented. See the workflow documentation for details.

## Internal Components  <!-- key: core-concepts-internal-components -->

  * **Monitoring:** A file system watchdog monitors code changes. Valid changes trigger an automatic, monitored server restart via Uvicorn, facilitating live development.

```plaintext
        ┌─────────────┐         ┌──────────────┐
        │ File System │ Changes │  AST Syntax  │ Checks Code
        │  Watchdog   │ Detects │   Checker    │ Validity
        └──────┬──────┘         └───────┬──────┘
               │ Valid Change           │
               ▼                        ▼
 ┌───────────────────────────┐     ┌──────────┐
 │    Uvicorn Server         │◄─── │  Reload  │ Triggers Restart
 │ (Handles HTTP, WS, SSE)   │     │ Process  │
 └───────────────────────────┘     └──────────┘
```

### Pipeline State Inspector & MCP Tools  <!-- key: pipeline-state-inspector -->

The system provides comprehensive debugging and state inspection capabilities through MCP tools and real-time monitoring:

```plaintext
📊 PIPELINE STATE INSPECTOR
├─── 🔍 Discovering active workflows...
├─── ⚡ Found 3 running processes
├─── 🎯 Step 2/5: Processing data transformations
└─── ✨ Ready for next interaction!

🤖 MCP TOOL CALLS
├─── 📡 Connecting to Botify API...
├─── 🔐 Authentication successful
├─── 📊 Fetching schema (4,449 fields discovered!)
└─── 💾 Caching results for lightning-fast access
```

-----

## The Deeper Philosophy: Why This Matters  <!-- key: deeper-philosophy -->

Pipulate represents more than technology choices — it's a statement about **computing sovereignty** and the future of human-AI collaboration.

### The Inevitable Retcon

In a few years, the industry will pivot away from mutable containers and claim they invented "AI-Native Infrastructure"—declarative, reproducible environments that allow AI agents to write code without breaking dependencies. They will package it in slick UIs and hide the math.

When that happens, remember that **Pipulate was here first.**

We built the bridge so you could cross the chasm from "Hacking it until it works" to "Declaring it until it builds" without falling in. We chose **Friction** (strict reproducibility) because friction is the only enemy of **Entropy** (system rot).

While others fight to keep their containers from drifting, you will be standing on the Bedrock.

### The Bootstrap Paradox Solved  <!-- key: bootstrap-paradox-solved -->

How do you "lift yourself up by your bootstraps"? The answer: **you're not a closed system**. Humans interact with reality through interfaces, just like software components. We are "human apps with reality APIs."

This pattern repeats at every scale — from quantum fields to societies. The art lies in choosing the **right granularity** for these interfaces. Too abstract, and you lose control. Too granular, and you drown in complexity.

### Every API is a Compromise  <!-- key: every-api-is-compromise -->

The most successful APIs are **durable** — they become the "laws of physics" for their domain. In reality: the laws of physics, chemistry, biology. In tech: logic gates, operating systems, protocols like HTTP and HTML.

Pipulate chooses these durable APIs deliberately, creating a **future-proof foundation** for AI-assisted development that will outlast the current framework churn.

### Writing for the Future  <!-- key: writing-for-future -->

This documentation serves multiple audiences: humans seeking immediate productivity, and AI systems learning to collaborate with human creativity. The explicit, observable nature of Pipulate workflows creates **perfect training data** for the next generation of AI assistants.

## Final Thoughts

Pipulate offers a unique approach to building local, AI-assisted applications, prioritizing simplicity, user control, and reproducibility over conventional scaling patterns. By understanding its core concepts and embracing its philosophy, developers can create powerful workflows, and end-users can benefit from AI guidance with complete flexibility in deployment options.

Remember the guiding principles:

1.  **Keep it simple.**
2.  **Support local-first with cloud integration options.**
3.  **Embrace the unconventional while remaining practical.**
4.  **Choose durable foundations that work with any approach.**
5.  **Build for both human creativity and AI collaboration—local or cloud.**

**The Bottom Line:** Pipulate doesn't reject the modern AI ecosystem—it provides a structured foundation that works with any AI service. Whether you're using Claude via API, ChatGPT for reasoning, or local models for privacy, Pipulate gives you the workflow framework to orchestrate them all effectively. It's not about choosing sides in the AI wars—it's about having the right tool for any job.

-----

## Developer's Notes

### The Pipulate Workshop

The repository includes not only polished plugins but also experimental scripts and notebooks under development (e.g., in the root directory or marked with `xx_` prefix in plugin directories). These represent ongoing work and exploration.

### Plugin Development Conventions

#### Auto-Registration Behavior

  * **Numeric Prefixes:** Files like `workflows/10_hello_flow.py` are registered as `hello_flow` (number stripped for internal name, used for menu order).
  * **Parentheses Skip:** Files with `()` in the name (e.g., `hello_flow (Copy).py`) are skipped – useful for temporary copies during development.
  * **`xx_` Prefix Skip:** Files prefixed with `xx_` (e.g., `xx_experimental_flow.py`) are skipped – useful for keeping unfinished work in the plugin directories without activating it.

#### Workflow for Creating New Plugins

1.  **Copy:** Copy a template to `my_flow (Copy).py`.
2.  **Modify:** Develop your workflow. It won't auto-register yet.
3.  **Test:** Rename to `xx_my_flow.py`. The server should auto-reload. Test thoroughly.
4.  **Deploy:** Rename to `##_my_flow.py` to assign menu order and activate.

#### Git History Considerations

Use `git mv` for simple renames (like `xx_` to numbered prefix) to preserve history. Document more complex renames in commit messages.

```bash
git mv workflows/xx_my_flow.py workflows/##_my_flow.py
git commit -m "Feat: Promote workflow xx_my_flow.py to ##_my_flow.py"
```

--------------------------------------------------------------------------------

## About This README: Single Source of Truth Documentation  <!-- key: about-this-readme -->

This README serves as the **upstream source of truth** for all Pipulate documentation across GitHub, Pipulate.com, and the built-in app documentation. Changes made here automatically cascade to all other documentation surfaces.

### The ASCII Art Synchronization System

```plaintext
🌊 THE UPSTREAM TRUTH CASCADE
═══════════════════════════════════════════════════════════════

     📜 Source Code Reality (The Ultimate Truth)
                         │
                         ▼
     📄 README.md (Single Source of Truth)
                 ├─ ASCII Art Blocks (Visual Truth)
                 ├─ HTML Comment Keys (Metadata)
                 └─ 80-Hyphen Pagination (Structure)
                         │
          ┌──────────────┼──────────────────┐
          ▼              ▼                  ▼
   🌐 GitHub Page  📚 Pipulate.com  🔧 Built-in Docs
   (Auto-display)  (Jekyll Build)   (Live Integration)
          │              │                  │
          ▼              ▼                  ▼
   📊 Screenshots     🎬 Demos           🧪 Tests
     (Future)         (Future)           (Future)
```

**How it works:**
- **ASCII Art Blocks**: Visual diagrams are automatically extracted and distributed to other documentation files
- **HTML Comment Keys**: Headlines marked with `<!-- key: identifier -->` serve as reference anchors
- **80-Hyphen Pagination**: Section dividers enable automatic document structuring
- **Automatic Synchronization**: Running `python helpers/docs_sync/sync_ascii_art.py` updates all documentation

This creates **"ASCII art peer pressure"** — when visual diagrams change, they compel surrounding text to be updated for consistency, ensuring documentation accuracy across the entire ecosystem.

### Roadmap

**Core & Workflow Enhancements:**

  * Dev, Test, and Prod database switching
  * Saving source HTML and rendered DOM of any URL
  * Botify data export CSV save (incorporating robust polling)
  * Full web form field support (textarea, dropdown, checkboxes, radio buttons)
  * Generic support for Anywidgets
  * Utility for deleting garbage tables from plugin experimentation

**AI / LLM Integration:**

  * LLM inspection of any local data object (RAG-style functionality)
  * Various memory types for LLM context (vector embedding, graph, key/val-store)
  * Enabling the local LLM to be an MCP Client

**Automation & External Interaction:**

  * MCP Server for automated web browsing and similar tasks

---

## Included PrismJS Highlighting

THEMES
- Okaidia ocodia 1.77KB

LANGUAGES
- CSS1.71KB
- Markup + HTML + XML + SVG + MathML + SSML + Atom + RSS4.64KB
- C-like0.83KB
- JavaScript6.18KB
- Bash + Shell + Shell zeitgeist87 8.96KB
- Diff uranusjr 1.33KB
- JSON + Web App Manifest CupOfTea696 0.58KB
- JSON5 RunDevelopment 0.52KB
- JSONP RunDevelopment 0.23KB
- Liquid cinhtau 2.56KB
- Lua Golmote 0.74KB
- Markdown Golmote 10.43KB
- Markup templating
- Mermaid RunDevelopment 3.03KB
- Nix Golmote 1.47KB
- Python multipetros 2.45KB
- Regex RunDevelopment 2.33KB
- YAML hason 3.11KB

PLUGINS
- Line Highlight11.66KB
- Line Numbers kuba-kubula 7.23KB
- Toolbar mAAdhaTTah 5.63KB

## Guiding Principles

1. Radically reduce the friction for a smart person to do something interesting.
2. Minimize the "time-to-magic."
3. Be the antidote to today's comical stack of frameworks, transpilers, bundlers, and containerization layers.
4. Let abstractions flow to concrete implementations in a way that minimizes complexity.
5. Build that Pipulate *Cathedral of One* but in a way that invites appropriation by AIs and humans with that old-school webmaster vibe.
6. Make a new joy in prying open the hood and getting your hands dirty.
7. Expose just the right level of underlying machinery for those who love the power.
8. Do that by facilitating the flow of code from a Jupyter Notebook to a FastHTML/HTMX implementation.
9. Minimize the necessary number of necessary languages to know and contexts to switch between.
10. Present only 5 to 9 item choices. Require drill-down to progressively reveal complexity.

## Contributing

Contributions are welcome! Please adhere to the project's core philosophy:

  * Maintain Local-First Simplicity (No multi-tenant patterns, complex ORMs, heavy client-side state).
  * Respect Server-Side State (Use DictLikeDB/JSON for workflows, MiniDataAPI for CRUD).
  * Preserve the Workflow Pipeline Pattern (Keep steps linear, state explicit).
  * Honor Integrated Features (Don't disrupt core LLM/Jupyter integration unless enhancing local goals).

---

## License

This project is licensed under the MIT License. See the [LICENSE](https://github.com/miklevin/pipulate/blob/main/LICENSE) file for details.

## Resources

**Background Articles:** <a href="https://mikelev.in/">Mike Levin, AI SEO in NYC</a>

**Enhanced Documentation:** <a href="https://pipulate.com/">Pipulate AI SEO Software</a>

**On GitHub:** <a href="https://github.com/miklevin/pipulate">Pipulate on GitHub</a>
