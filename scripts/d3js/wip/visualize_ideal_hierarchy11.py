import json
import math
import webbrowser
import os

# --- CONFIGURATION ---
TOTAL_ARTICLES = 730
ARTICLES_PER_HUB = 7   
HUBS_PER_HUB = 7       
OUTPUT_FILENAME = "ideal_hierarchy_v11.html"

# --- THE SIMULATION ---
def generate_ideal_graph():
    nodes = []
    links = []
    
    article_count = 0
    hub_count = 0
    queue = []

    # 1. Create Root
    root_id = "hub_0"
    nodes.append({
        "id": root_id, 
        "group": "root", 
        "depth": 0, 
        "label": "HOMEPAGE",
        "val": 40 
    })
    queue.append((root_id, 0))
    hub_count += 1

    hub_usage = {root_id: 0}

    while article_count < TOTAL_ARTICLES and queue:
        current_hub_id, current_depth = queue.pop(0)
        
        # A. Assign Articles
        remaining = TOTAL_ARTICLES - article_count
        to_create = min(ARTICLES_PER_HUB, remaining)
        
        for _ in range(to_create):
            article_id = f"art_{article_count}"
            heat = 1.0 - (article_count / TOTAL_ARTICLES)
            
            nodes.append({
                "id": article_id,
                "group": "article",
                "depth": current_depth,
                "label": f"Art_{article_count}",
                "heat": heat,
                "val": 7,
                "parentId": current_hub_id
            })
            
            links.append({
                "source": current_hub_id,
                "target": article_id,
                "type": "article_link"
            })
            
            hub_usage[current_hub_id] = hub_usage.get(current_hub_id, 0) + 1
            article_count += 1

        # B. Create Sub-Hubs
        if article_count < TOTAL_ARTICLES:
            for i in range(HUBS_PER_HUB):
                if article_count >= TOTAL_ARTICLES: break
                    
                new_hub_id = f"hub_{hub_count}"
                hub_size = max(8, 40 - (current_depth * 15))
                
                nodes.append({
                    "id": new_hub_id,
                    "group": "hub",
                    "depth": current_depth + 1,
                    "label": "Cat",
                    "val": hub_size,
                    "parentId": current_hub_id
                })
                
                links.append({
                    "source": current_hub_id,
                    "target": new_hub_id,
                    "type": "hub_link"
                })
                
                hub_usage[new_hub_id] = 0
                queue.append((new_hub_id, current_depth + 1))
                hub_count += 1

    return {"nodes": nodes, "links": links}

# --- THE VISUALIZER ---
def create_html(graph_data):
    json_str = json.dumps(graph_data)
    
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Architect Console v11 (Spoked Core)</title>
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
            transition: background-color 0.5s, border-color 0.5s;
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

        <div id="status">Aligning Spokes...</div>
    </div>
    
    <div id="graph"></div>

    <script>
        const rawGraph = {json_str};
        const width = window.innerWidth;
        const height = window.innerHeight;

        // --- V11: HYBRID SEEDING ---
        // 1. D3 Tree for general topology
        // 2. Strict Trigonometry for the Core Ring
        
        const stratify = d3.stratify()
            .id(d => d.id)
            .parentId(d => d.parentId);

        try {{
            const root = stratify(rawGraph.nodes);
            const treeLayout = d3.cluster().size([2 * Math.PI, 2000]); 
            treeLayout(root);
            const nodeMap = new Map(root.descendants().map(d => [d.id, d]));

            // Apply general tree positions first
            rawGraph.nodes.forEach(node => {{
                const treeNode = nodeMap.get(node.id);
                if (treeNode) {{
                    const theta = treeNode.x - Math.PI / 2; 
                    const r = treeNode.y; 
                    node.x = width/2 + r * Math.cos(theta) * 0.1; 
                    node.y = height/2 + r * Math.sin(theta) * 0.1;
                }}
            }});

            // --- THE MANUAL OVERRIDE ---
            // 1. PIN THE KING (Homepage)
            const rootNode = rawGraph.nodes.find(n => n.group === 'root');
            if (rootNode) {{
                rootNode.fx = width / 2; // Fixed X
                rootNode.fy = height / 2; // Fixed Y
                rootNode.x = width / 2;
                rootNode.y = height / 2;
            }}

            // 2. DISTRIBUTE LEVEL 1 HUBS (The Spokes)
            // We force them into a perfect circle around the center.
            const spokes = rawGraph.nodes.filter(n => n.depth === 1 && n.group === 'hub');
            const angleStep = (2 * Math.PI) / spokes.length;
            const spokeRadius = 100; // Initial push-out radius

            spokes.forEach((node, i) => {{
                const angle = i * angleStep; // - Math.PI/2 to start top if desired
                node.x = width/2 + Math.cos(angle) * spokeRadius;
                node.y = height/2 + Math.sin(angle) * spokeRadius;
                // Note: We do NOT fix them (fx/fy). We just place them perfectly 
                // and let physics handle the rest.
            }});

            console.log("Hybrid Seeding Complete.");

        }} catch (e) {{
            console.warn("Seeding failed:", e);
        }}

        // --------------------------------

        const zoom = d3.zoom().scaleExtent([0.01, 10]).on("zoom", (event) => {{
            g.attr("transform", event.transform);
        }});

        const svg = d3.select("#graph").append("svg")
            .attr("width", width)
            .attr("height", height)
            .call(zoom);

        const g = svg.append("g");

        // --- PHYSICS CONFIG ---
        const BASE_RING_SPACING = 350;
        const ARTICLE_ORBIT_OFFSET = 60; 
        
        let collideMultiplier = 0.0; 
        let radialMultiplier = 2.0;

        const simulation = d3.forceSimulation(rawGraph.nodes)
            .force("link", d3.forceLink(rawGraph.links).id(d => d.id)
                .distance(d => d.type === 'hub_link' ? 150 : 30)
                .strength(d => d.type === 'hub_link' ? 0.2 : 1.5))
            .force("charge", d3.forceManyBody().strength(-200))
            .force("r", d3.forceRadial(d => {{
                // Stronger radial force for Level 1 to maintain the wheel
                if (d.depth === 1 && d.group === 'hub') return BASE_RING_SPACING * radialMultiplier * 0.8;
                
                const baseRing = d.depth * BASE_RING_SPACING * radialMultiplier;
                if (d.group === 'article') return baseRing + ARTICLE_ORBIT_OFFSET;
                return baseRing; 
            }}, width / 2, height / 2).strength(d => d.depth === 1 ? 1.0 : 0.8)) // Max strength for inner ring
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

        // --- THEME & COLOR LOGIC ---
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
                    
                    if (isLight) {{
                         return d3.interpolateBlues(d.heat * 0.8 + 0.2);
                    }} else {{
                         return d3.interpolateGnBu(d.heat * 0.8 + 0.2);
                    }}
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

        // --- INTERACTIVITY ---
        const sliderCollide = document.getElementById("slider-collide");
        const valCollide = document.getElementById("val-collide");
        const sliderRadial = document.getElementById("slider-radial");
        const valRadial = document.getElementById("val-radial");
        const sliderEdge = document.getElementById("slider-edge");
        const valEdge = document.getElementById("val-edge");
        const btnTheme = document.getElementById("btn-theme");

        function updateSimulation() {{
            simulation.force("collide").radius(d => {{
                if (d.group === 'hub' || d.group === 'root') return d.val * collideMultiplier;
                return d.val + 2; 
            }});

            simulation.force("r").radius(d => {{
                // Maintain that strong inner ring logic dynamically
                if (d.depth === 1 && d.group === 'hub') return BASE_RING_SPACING * radialMultiplier * 0.8;

                const baseRing = d.depth * BASE_RING_SPACING * radialMultiplier;
                if (d.group === 'article') return baseRing + ARTICLE_ORBIT_OFFSET;
                return baseRing;
            }});

            simulation.alpha(0.3).restart();
            document.getElementById("status").innerText = "Physics Updating...";
        }}

        sliderCollide.addEventListener("input", (e) => {{
            collideMultiplier = parseFloat(e.target.value);
            valCollide.innerText = collideMultiplier.toFixed(1);
            updateSimulation();
        }});

        sliderRadial.addEventListener("input", (e) => {{
            radialMultiplier = parseFloat(e.target.value);
            valRadial.innerText = radialMultiplier.toFixed(1);
            updateSimulation();
        }});
        
        sliderEdge.addEventListener("input", (e) => {{
            const val = parseFloat(e.target.value);
            valEdge.innerText = val.toFixed(2);
            updateColors(); 
        }});

        btnTheme.addEventListener("click", () => {{
            document.body.classList.toggle('light-mode');
            updateColors();
        }});

        updateColors();

        function drag(simulation) {{
            function dragstarted(event, d) {{
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            }}
            function dragged(event, d) {{
                d.fx = event.x;
                d.fy = event.y;
            }}
            function dragended(event, d) {{
                if (!event.active) simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            }}
            return d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended);
        }}
        
        function applyInitialZoom() {{
            const transform = d3.zoomIdentity
                .translate(width/2, height/2) 
                .scale(0.19)                  
                .translate(0, 0);              

            svg.transition().duration(1500).call(zoom.transform, transform);
            document.getElementById("status").innerText = "Sovereign View Loaded.";
        }}

        setTimeout(applyInitialZoom, 1000);

    </script>
</body>
</html>
    """
    
    with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"✅ Generated {OUTPUT_FILENAME}")
    webbrowser.open('file://' + os.path.realpath(OUTPUT_FILENAME))

if __name__ == "__main__":
    data = generate_ideal_graph()
    create_html(data)