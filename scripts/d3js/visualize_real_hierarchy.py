import json
import os
import math
import webbrowser
from collections import Counter
from pathlib import Path

# --- CONFIGURATION ---
# Path to your context JSONs
CONTEXT_DIR = Path("/home/mike/repos/MikeLev.in/_posts/_context")
OUTPUT_FILENAME = "real_hierarchy_viz.html"

# "Rule of 7" Constraints
MAX_HUBS = 7
MAX_ARTICLES_PER_HUB = 20  # Loosened for visibility, strict rule is 7

def load_shards():
    """Loads all .json context files from the directory."""
    shards = []
    if not CONTEXT_DIR.exists():
        print(f"❌ Error: Directory {CONTEXT_DIR} not found.")
        return []
        
    for filename in os.listdir(CONTEXT_DIR):
        if filename.endswith(".json"):
            try:
                with open(CONTEXT_DIR / filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    shards.append(data)
            except Exception as e:
                print(f"Skipping broken shard {filename}: {e}")
    return shards

def build_graph_from_shards(shards):
    nodes = []
    links = []
    
    # 1. Create Root
    nodes.append({
        "id": "root", 
        "group": "root", 
        "depth": 0, 
        "label": "MikeLev.in",
        "val": 40,
        "parentId": ""
    })

    # 2. Identify Hubs (The Clustering Pass)
    # Flatten all keywords from all articles
    all_keywords = []
    for shard in shards:
        all_keywords.extend([k.lower() for k in shard.get('kw', [])])
    
    # Find the top N most frequent keywords
    keyword_counts = Counter(all_keywords)
    top_keywords = [kw for kw, count in keyword_counts.most_common(MAX_HUBS)]
    
    print(f"🏆 Elected Hubs: {top_keywords}")

    # Create Hub Nodes
    hub_map = {} # kw -> hub_id
    for i, kw in enumerate(top_keywords):
        hub_id = f"hub_{i}"
        hub_map[kw] = hub_id
        nodes.append({
            "id": hub_id,
            "group": "hub",
            "depth": 1,
            "label": kw.title(),
            "val": 25,
            "parentId": "root"
        })
        links.append({"source": "root", "target": hub_id, "type": "hub_link"})

    # 3. Assign Articles (The Gravity Pass)
    # We assign an article to the *highest ranked* hub keyword it possesses.
    hub_counts = {kw: 0 for kw in top_keywords}
    
    for shard in shards:
        assigned = False
        
        # Check against our top keywords in order of their popularity (gravity)
        for kw in top_keywords:
            if kw in [k.lower() for k in shard.get('kw', [])]:
                
                # Check capacity (Loose Rule of 7)
                if hub_counts[kw] < MAX_ARTICLES_PER_HUB:
                    article_id = shard.get('id', 'unknown')
                    hub_id = hub_map[kw]
                    
                    # Simulated Heat (Just random/default for now, or based on date if parsed)
                    heat = 0.8 
                    
                    nodes.append({
                        "id": article_id,
                        "group": "article",
                        "depth": 1, # Conceptually depth 1 relative to hub
                        "label": shard.get('t', 'Untitled'),
                        "heat": heat,
                        "val": 7,
                        "parentId": hub_id
                    })
                    
                    links.append({
                        "source": hub_id,
                        "target": article_id,
                        "type": "article_link"
                    })
                    
                    hub_counts[kw] += 1
                    assigned = True
                    break # Assigned to first matching hub
        
        if not assigned:
            # Optional: Handle orphans (Misc Hub) or skip
            # For pure visualization now, we skip to keep the graph clean
            pass

    print(f"✅ Graph Built: {len(nodes)} nodes, {len(links)} links")
    return {"nodes": nodes, "links": links}

# --- THE VISUALIZER (Your Final V10 Code) ---
def create_html(graph_data):
    json_str = json.dumps(graph_data)
    
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Real Content Topology</title>
    <style>
        :root {{
            --bg-color: #050505;
            --text-color: #ccc;
            --panel-bg: rgba(10, 10, 15, 0.95);
            --panel-border: #333;
        }}
        body.light-mode {{
            --bg-color: #ffffff;
            --text-color: #111;
            --panel-bg: rgba(245, 245, 250, 0.95);
            --panel-border: #ccc;
        }}
        body {{ 
            margin: 0; 
            background-color: var(--bg-color); 
            color: var(--text-color);
            font-family: 'Courier New', monospace;
            overflow: hidden;
            transition: background-color 0.5s, color 0.5s;
        }}
        #graph {{ width: 100vw; height: 100vh; }}
        #controls {{
            position: absolute;
            top: 20px; 
            left: 20px;
            background: var(--panel-bg);
            padding: 20px;
            border: 1px solid var(--panel-border);
            border-radius: 8px;
            pointer-events: auto;
            z-index: 100;
            width: 260px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        }}
        h3 {{ margin: 0 0 12px 0; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid var(--panel-border); padding-bottom: 8px;}}
        .control-group {{ margin-bottom: 12px; }}
        label {{ display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 4px; opacity: 0.8; }}
        input[type=range] {{ width: 100%; cursor: pointer; }}
        #status {{ font-size: 10px; opacity: 0.6; margin-top: 10px; text-align: center; }}
        
        button {{
            width: 100%;
            padding: 8px;
            margin-top: 10px;
            background: transparent;
            border: 1px solid var(--panel-border);
            color: var(--text-color);
            cursor: pointer;
            border-radius: 4px;
            font-family: inherit;
            text-transform: uppercase;
            font-size: 11px;
        }}
        button:hover {{ background: rgba(128,128,128,0.1); }}
    </style>
    <script src="https://d3js.org/d3.v7.min.js"></script>
</head>
<body class="dark-mode">
    <div id="controls">
        <h3>Graph Controls</h3>
        <div class="control-group">
            <label><span>Territory (Cluster)</span> <span id="val-collide">0.0</span></label>
            <input type="range" id="slider-collide" min="0.0" max="8.0" step="0.5" value="0.0">
        </div>
        <div class="control-group">
            <label><span>Orbit (Expansion)</span> <span id="val-radial">2.0</span></label>
            <input type="range" id="slider-radial" min="0.1" max="4.0" step="0.1" value="2.0">
        </div>
        <div class="control-group">
            <label><span>Edge Visibility</span> <span id="val-edge">1.0</span></label>
            <input type="range" id="slider-edge" min="0.0" max="1.0" step="0.05" value="1.0">
        </div>
        <button id="btn-theme">Toggle Day/Night</button>
        <div id="status">Initializing...</div>
    </div>
    
    <div id="graph"></div>

    <script>
        const rawGraph = {json_str};
        const width = window.innerWidth;
        const height = window.innerHeight;

        // --- TOPOLOGICAL SEEDING ---
        // Ensure parentId is valid or root if missing
        rawGraph.nodes.forEach(n => {{
            if (!n.parentId) n.parentId = "root";
            if (n.id === "root") n.parentId = null; 
        }});

        const stratify = d3.stratify().id(d => d.id).parentId(d => d.parentId);

        try {{
            const root = stratify(rawGraph.nodes);
            const treeLayout = d3.cluster().size([2 * Math.PI, 1500]); 
            treeLayout(root);

            const nodeMap = new Map(root.descendants().map(d => [d.id, d]));

            rawGraph.nodes.forEach(node => {{
                const treeNode = nodeMap.get(node.id);
                if (treeNode) {{
                    const theta = treeNode.x - Math.PI / 2; 
                    const r = treeNode.y; 
                    node.x = width/2 + r * Math.cos(theta) * 0.1; 
                    node.y = height/2 + r * Math.sin(theta) * 0.1;
                }}
            }});
            console.log("Topological Seeding Complete.");
        }} catch (e) {{
            console.warn("Seeding failed (graph likely not strict tree):", e);
        }}

        const zoom = d3.zoom().scaleExtent([0.01, 10]).on("zoom", (event) => {{
            g.attr("transform", event.transform);
        }});

        const svg = d3.select("#graph").append("svg")
            .attr("width", width)
            .attr("height", height)
            .call(zoom);

        const g = svg.append("g");

        // --- PHYSICS ---
        const BASE_RING_SPACING = 300;
        const ARTICLE_ORBIT_OFFSET = 80; 
        
        let collideMultiplier = 0.0; 
        let radialMultiplier = 2.0;

        const simulation = d3.forceSimulation(rawGraph.nodes)
            .force("link", d3.forceLink(rawGraph.links).id(d => d.id)
                .distance(d => d.type === 'hub_link' ? 150 : 30)
                .strength(d => d.type === 'hub_link' ? 0.2 : 1.5))
            .force("charge", d3.forceManyBody().strength(-200))
            .force("r", d3.forceRadial(d => {{
                const baseRing = d.depth * BASE_RING_SPACING * radialMultiplier;
                if (d.group === 'article') return baseRing + ARTICLE_ORBIT_OFFSET;
                return baseRing; 
            }}, width / 2, height / 2).strength(0.8)) 
            .force("collide", d3.forceCollide().radius(d => {{
                if (d.group === 'hub' || d.group === 'root') return d.val * collideMultiplier;
                return d.val + 2; 
            }}).iterations(2));

        // --- RENDER ---
        const link = g.append("g")
            .attr("class", "links")
            .selectAll("line")
            .data(rawGraph.links)
            .join("line")
            .attr("stroke-width", d => d.type === 'hub_link' ? 1.5 : 0.5)
            .attr("stroke-opacity", 1.0); 

        const node = g.append("g")
            .selectAll("circle")
            .data(rawGraph.nodes)
            .join("circle")
            .attr("r", d => d.val)
            .call(drag(simulation));
            
        // Tooltip for real titles
        node.append("title").text(d => d.label);

        // --- UPDATE & INTERACTIVITY ---
        function updateColors() {{
            const isLight = document.body.classList.contains('light-mode');
            const sliderVal = parseFloat(document.getElementById("slider-edge").value);
            
            let strokeColor;
            if (isLight) {{
                const val = Math.floor(255 - (sliderVal * 205)); 
                strokeColor = `rgb(${{val}},${{val}},${{val}})`;
            }} else {{
                const val = Math.floor(sliderVal * 170 + 10); 
                strokeColor = `rgb(${{val}},${{val}},${{val}})`;
            }}

            d3.selectAll(".links line").attr("stroke", strokeColor);
            const nodeStroke = isLight ? "#fff" : "#111";
            
            node.attr("stroke", nodeStroke)
                .attr("stroke-width", 1.0)
                .attr("fill", d => {{
                    if (d.group === 'root') return "#ff00ff";
                    if (d.group === 'hub') return isLight ? "#7b00cc" : "#bd00ff";
                    // Real data doesn't have heat calc yet, default to cold-ish
                    if (isLight) return d3.interpolateBlues(0.6);
                    return d3.interpolateGnBu(0.6);
                }});
        }}

        simulation.on("tick", () => {{
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
            node
                .attr("cx", d => d.x)
                .attr("cy", d => d.y);
        }});

        document.getElementById("slider-collide").addEventListener("input", (e) => {{
            collideMultiplier = parseFloat(e.target.value);
            simulation.force("collide").radius(d => {{
                if (d.group === 'hub' || d.group === 'root') return d.val * collideMultiplier;
                return d.val + 2; 
            }});
            simulation.alpha(0.3).restart();
        }});

        document.getElementById("slider-radial").addEventListener("input", (e) => {{
            radialMultiplier = parseFloat(e.target.value);
            simulation.force("r").radius(d => {{
                const baseRing = d.depth * BASE_RING_SPACING * radialMultiplier;
                if (d.group === 'article') return baseRing + ARTICLE_ORBIT_OFFSET;
                return baseRing;
            }});
            simulation.alpha(0.3).restart();
        }});
        
        document.getElementById("slider-edge").addEventListener("input", updateColors);
        document.getElementById("btn-theme").addEventListener("click", () => {{
            document.body.classList.toggle('light-mode');
            updateColors();
        }});

        updateColors();

        function drag(simulation) {{
            function dragstarted(event, d) {{
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x; d.fy = d.y;
            }}
            function dragged(event, d) {{ d.fx = event.x; d.fy = event.y; }}
            function dragended(event, d) {{
                if (!event.active) simulation.alphaTarget(0);
                d.fx = null; d.fy = null;
            }}
            return d3.drag().on("start", dragstarted).on("drag", dragged).on("end", dragended);
        }}
        
        setTimeout(() => {{
            const transform = d3.zoomIdentity.translate(width/2, height/2).scale(0.19).translate(0, 0);              
            svg.transition().duration(1500).call(zoom.transform, transform);
            document.getElementById("status").innerText = "Topology Stabilized.";
        }}, 1000);

    </script>
</body>
</html>
    """
    
    with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"✅ Generated {OUTPUT_FILENAME}")
    webbrowser.open('file://' + os.path.realpath(OUTPUT_FILENAME))

if __name__ == "__main__":
    shards = load_shards()
    if shards:
        graph = build_graph_from_shards(shards)
        create_html(graph)
    else:
        print("No shards found to process.")