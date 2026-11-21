import logging
import time

from fastcore.xml import *
from fasthtml.common import *

ROLES = ['Tutorial']

logger = logging.getLogger(__name__)


class RoadmapPlugin:
    NAME = "roadmap"
    DISPLAY_NAME = "Roadmap 🗺️"
    ENDPOINT_MESSAGE = "Displaying project roadmap..."

    # Define the Mermaid diagram as a class property
    ROADMAP_DIAGRAM = """
    gantt
        title Pipulate Development Roadmap
        dateFormat YYYY-MM-DD
        axisFormat %b %d

        section Core Infrastructure
        Nix Environment         :done, nix1, 2024-01-01, 60d
        Magic Cookie System     :done, nix2, after nix1, 30d
        Dev/Test/Prod DB        :active, db1, 2024-03-15, 30d

        section AI Capabilities
        LLM Integration        :done, ai1, 2024-01-15, 45d
        Chat Interface        :done, ai2, after ai1, 30d
        Vector Memory         :ai3, 2024-05-15, 28d
        Graph Memory          :ai4, after ai3, 24d

        section UI & Controls
        HTMX Integration      :done, ui1, 2024-01-01, 45d
        FastHTML Components   :done, ui2, after ui1, 30d
        Web Form Fields       :ui3, 2024-06-01, 32d
        Anywidgets Support    :ui4, after ui3, 30d

        section Automation
        MCP Server            :auto1, 2024-07-01, 35d
        LLM as MCP Client     :auto2, after auto1, 30d
    """

    def __init__(self, app, pipulate, pipeline, db):
        logger.debug(f"RoadmapPlugin initialized with NAME: {self.NAME}")
        self.pipulate = pipulate
        self._has_streamed = False  # Flag to track if we've already streamed

    def _render_metric_card(self, label: str, n_vals: list[int], p_vals: list[int]):
        if self.pipulate is not None and hasattr(self.pipulate, "sparkline_card"):
            return self.pipulate.sparkline_card(label, n_vals, unique_values=p_vals)
        from imports import ascii_displays as aa
        st = aa.compute_ols_velocity(n_vals)
        stroke = "#34d399" if st["slope"] > 0.02 else ("#f87171" if st["slope"] < -0.02 else "#60a5fa")
        meta = f"N={int(round(st['total']))} · P={sum(int(x) for x in p_vals)} IPs · last={int(round(st['latest']))} · R²={st['r2']:.2f}"
        svg = NotStr(aa.render_sparkline_svg(n_vals, width=136, height=30, stroke=stroke, show_ols=True))
        return Article(
            Div(
                Div(Strong(label), Small(meta, style="display:block;opacity:0.78;font-family:monospace;font-size:0.78rem;")),
                Div(svg, Span(f"{st['arrow']} {st['slope']:+.2f}/d", style=f"font-family:monospace;font-weight:700;font-size:0.86rem;color:{stroke};white-space:nowrap;"), style="display:flex;align-items:center;gap:0.65rem;"),
                style="display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap;",
            ),
            style="padding:0.7rem 0.95rem;margin-bottom:0.65rem;",
        )

    def build_velocity_deck(self, days: int = 14):
        """Render a 2-column grid of 14-day (N, P) directional velocity sparklines."""
        import json
        import os
        import subprocess
        import sys
        from pathlib import Path
        from scripts import markov as mk
        db_ov = os.environ.get("PIPULATE_HONEYBOT_DB", "").strip()
        cache_p = Path.home() / ".config" / "pipulate" / "funnel_cache.json"
        snap = None
        if not db_ov and cache_p.is_file() and (time.time() - cache_p.stat().st_mtime) < 300:
            try:
                snap = json.loads(cache_p.read_text(encoding="utf-8"))
            except Exception:
                snap = None
        if snap is None:
            cmd = [sys.executable, "-", str(int(days)), db_ov] if (db_ov and Path(db_ov).is_file()) else ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=2", os.environ.get("PIPULATE_HONEYBOT_HOST", "honeybot"), "python3", "-", str(int(days))]
            try:
                res = subprocess.run(cmd, input=mk._REMOTE_FUNNEL_PY, capture_output=True, text=True, timeout=3, check=False)
                if res.returncode == 0 and (res.stdout or "").strip():
                    snap = json.loads(res.stdout.strip())
                    if not db_ov and snap.get("status") in ("live_metrics", "live_derived"):
                        cache_p.parent.mkdir(parents=True, exist_ok=True)
                        cache_p.write_text(json.dumps(snap), encoding="utf-8")
            except Exception:
                snap = None
        m_map = (snap or {}).get("metrics") or {}
        n_d = len((snap or {}).get("span") or []) or max(2, int(days))
        def _np(k: str) -> tuple[list[int], list[int]]:
            arr = m_map.get(k) or [[0, 0] for _ in range(n_d)]
            return [int(x[0]) for x in arr], [int(x[1]) for x in arr]
        air_n, air_p = _np("curl_airlock")
        exe_n, exe_p = _np("curl_exec")
        less_n, less_p = [max(0, a - e) for a, e in zip(air_n, exe_n)], [max(0, a - e) for a, e in zip(air_p, exe_p)]
        rows = [("📦 brain.zip Downloads", *_np("archive_dl")), ("🔍 Sun Pug curl | less", less_n, less_p), ("⚡ Sun Pug curl | bash", exe_n, exe_p), ("📺 YouTube -> Web Humans", *_np("yt_referral_human")), ("🧠 RFC 9110 Markdown", *_np("md_negotiated")), ("🏴‍☠️ Pirate 4xx/418 IDS", *_np("ids_pirate"))]
        status_s = (snap or {}).get("status", "offline")
        return Div(
            Small(f"14-Day Kaizen Directional Velocity (OLS y=mx+b · self-erasing 24h P IPs · source={status_s})", style="display:block;margin-bottom:0.6rem;font-family:monospace;opacity:0.8;"),
            Div(*[self._render_metric_card(lbl, nv, pv) for lbl, nv, pv in rows], style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:0.65rem;margin-bottom:1.25rem;"),
            id="kaizen-velocity-deck",
        )

    async def landing(self, render_items=None):
        """Always appears in create_grid_left."""
        # Generate unique IDs
        unique_id = f"mermaid-{int(time.time() * 1000)}"

        # Send the diagram to the conversation history, but only once per session
        if self.pipulate is not None and not self._has_streamed:
            try:
                # First, send the verbatim redirect message
                await self.pipulate.stream(
                    self.ENDPOINT_MESSAGE,
                    verbatim=True,
                    role="system",
                    spaces_before=1,
                    spaces_after=1
                )

                # Then append the roadmap info to history without displaying
                diagram_message = f"```mermaid\n{self.ROADMAP_DIAGRAM}\n```"
                self.pipulate.append_to_history(  # Remove await since it's not async
                    "[WIDGET CONTENT] Project Roadmap\n" + diagram_message,
                    role="system"
                )

                self._has_streamed = True  # Set flag to prevent repeated streaming
                logger.debug("Roadmap appended to conversation history")
            except Exception as e:
                logger.error(f"Error in roadmap plugin: {str(e)}")
                # Continue even if messaging fails - the diagram will still show

        # Create the mermaid diagram container - leave empty for now
        mermaid_diagram = Div(
            id=unique_id,
            style="width: 100%; padding: 10px; background-color: #f9f9f9; border-radius: 5px; margin: 15px 0;"
        )

        # Create a script that loads Mermaid.js from CDN and renders the diagram
        load_script = Script(
            f"""
            (function() {{
                var diagramEl = document.getElementById("{unique_id}");
                if (!diagramEl) return;

                // Use the diagram from class property
                var diagram = `{self.ROADMAP_DIAGRAM}`;

                // Load Mermaid.js from local static file
                var script = document.createElement('script');
                script.src = "/assets/js/mermaid.min.js";
                script.onload = function() {{
                    console.log("Mermaid loaded from local static");

                    // Create a wrapper div with mermaid class
                    var mermaidWrapper = document.createElement('div');
                    mermaidWrapper.className = 'mermaid';
                    mermaidWrapper.textContent = diagram;

                    // Add to our container
                    diagramEl.appendChild(mermaidWrapper);

                    // Initialize mermaid
                    mermaid.initialize({{
                        startOnLoad: true,
                        theme: 'default',
                        securityLevel: 'loose',
                        gantt: {{
                            titleTopMargin: 30,
                            barHeight: 35,
                            barGap: 10,
                            topPadding: 75,
                            bottomPadding: 50,
                            leftPadding: 145,
                            gridLineStartPadding: 35,
                            fontSize: 14,
                            fontFamily: "Arial, sans-serif",
                            numberSectionStyles: 5,
                            axisFormat: '%m/%d',
                            sectionHeight: 45,
                            useWidth: 1200
                        }}
                    }});

                    // Render the diagram
                    setTimeout(function() {{
                        try {{
                            mermaid.init(undefined, mermaidWrapper);
                        }} catch(e) {{
                            console.error("Mermaid rendering error:", e);
                            mermaidWrapper.innerHTML = '<p style="color: red;">Error rendering diagram. See console for details.</p>';
                        }}
                    }}, 100);
                }};

                document.head.appendChild(script);
            }})();
            """,
            type="text/javascript"
        )

        return Div(
            H2("Project Roadmap & Kaizen Velocity"),
            self.build_velocity_deck(days=14),
            H3("Development Horizon"),
            P("Planned development timeline for Pipulate features:"),
            mermaid_diagram,
            load_script
        )

# Don't register here - let the discovery process handle it
