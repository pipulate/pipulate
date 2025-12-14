import json
import math
import webbrowser
import os

# --- CONFIGURATION ---
TOTAL_ARTICLES = 730
ARTICLES_PER_HUB = 7   
HUBS_PER_HUB = 7       
OUTPUT_FILENAME = "ideal_hierarchy_v14.html"

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
        "val": 50 
    })
    queue.append((root_id, 0))
    hub_count += 1

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
                "val": 6,
                "parentId": current_hub_id 
            })
            
            links.append({
                "source": current_hub_id,
                "target": article_id,
                "type": "article_link"
            })
            article_count += 1

        # B. Create Sub-Hubs
        if article_count < TOTAL_ARTICLES:
            for i in range(HUBS_PER_HUB):
                if article_count >= TOTAL_ARTICLES: break
                    
                new_hub_id = f"hub_{hub_count}"
                hub_size = max(10, 35 - (current_depth * 10))
                
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
                
                queue.append((new_hub_id, current_depth + 1))
                hub_count += 1

    # Note: We removed the "rim_link" logic here because the 
    # Geometric Locking in JS is far superior for multi-level rings.

    return {"nodes": nodes, "links": links}

# --- THE VISUALIZER ---
def create_html(graph_data):
    json_str = json.dumps(graph_data)
    
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Architect Console v14 (The Frozen Skeleton)</title>
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
        <button id="btn-unfreeze">Unfreeze Skeleton</button>

        <div id="status">Applying Frozen Skeleton...</div>
    </div>
    
    <div id="graph"></div>

    <script>
        const rawGraph = {json_str};
        const width = window.innerWidth;
        const height = window.innerHeight;

        const stratify = d3.stratify()
            .id(d => d.id)
            .parentId(d => d.parentId);

        // --- V14: THE FROZEN SKELETON ---
        // We calculate the exact angle for every Hub node and LOCK IT (fx, fy).
        // This guarantees a perfect wheel. 
        // Only articles remain free (group 'article') to cluster organically.

        try {{
            const root = stratify(rawGraph.nodes);
            
            // Recursive function to assign slice angles AND FIX POSITIONS
            function assignFixedPositions(node, startAngle, endAngle) {{
                const totalSlice = endAngle - startAngle;
                const myAngle = startAngle + (totalSlice / 2);
                
                // Expansion Radius: 
                // Level 1 at 250px
                // Level 2 at 550px
                // Level 3 (Articles) will float around 600px+
                const myRadius = node.depth * 280; 
                
                // Map to Cartesian (Rotate -90 to start top)
                const finalAngle = myAngle - Math.PI / 2;
                
                // THE LOCK:
                // We save these calculated coords as `fx` and `fy`.
                // D3 respects these as immovable anchors.
                // We only do this for HUBS and ROOT. Articles are left floating.
                if (node.data.group === 'root' || node.data.group === 'hub') {{
                    node.data.fx = width/2 + myRadius * Math.cos(finalAngle);
                    node.data.fy = height/2 + myRadius * Math.sin(finalAngle);
                    node.data.x = node.data.fx;
                    node.data.y = node.data.fy;
                }}

                if (node.children) {{
                    // Filter children to find only HUBS for the angle calculation
                    // We don't want articles taking up "Slice" space in the Skeleton
                    const hubChildren = node.children.filter(c => c.data.group === 'hub');
                    
                    if (hubChildren.length > 0) {{
                        const step = totalSlice / hubChildren.length;
                        hubChildren.forEach((child, i) => {{
                            const childStart = startAngle + (i * step);
                            const childEnd = startAngle + ((i + 1) * step);
                            assignFixedPositions(child, childStart, childEnd);
                        }});
                    }}
                }}
            }}

            // Start Recursion
            assignFixedPositions(root, 0, 2 * Math.PI);
            console.log("Skeleton Locked.");

        }} catch (e) {{
            console.warn("Seeding logic error:", e);
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
            // We still keep radial force to guide the floating articles
            .force("r", d3.forceRadial(d => {{
                if (d.group === 'article') {{
                     // Articles go to their parent's ring + offset
                     // Note: We access the parent's fixed position to find the ring radius
                     // simplified: depth * spacing
                     return (d.depth * 280) + ARTICLE_ORBIT_OFFSET;
                }}
                return 0; // Hubs are locked, force doesn't matter for them
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
                    if (isLight) return d3.interpolateBlues(d.heat * 0.8 + 0.2);
                    return d3.interpolateGnBu(d.heat * 0.8 + 0.2);
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
        const btnUnfreeze = document.getElementById("btn-unfreeze");

        function updateSimulation() {{
            simulation.force("collide").radius(d => {{
                if (d.group === 'hub' || d.group === 'root') return d.val * collideMultiplier;
                return d.val + 2; 
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
            // Note: Radial slider has less effect on locked nodes, 
            // but will push the article rings in/out
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

        // UNFREEZE: Allow the user to "melt" the skeleton if they want
        btnUnfreeze.addEventListener("click", () => {{
            rawGraph.nodes.forEach(n => {{
                n.fx = null;
                n.fy = null;
            }});
            // Keep root pinned though
            const root = rawGraph.nodes.find(n => n.group === 'root');
            if(root) {{ root.fx = width/2; root.fy = height/2; }}
            
            simulation.alpha(1).restart();
            document.getElementById("status").innerText = "Skeleton Melted. Physics Active.";
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
                // V14: Keep the lock if it was already locked by our skeleton logic
                // If it's an article, release it.
                if (d.group === 'article') {{
                    d.fx = null;
                    d.fy = null;
                }}
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
            document.getElementById("status").innerText = "Frozen Skeleton Active.";
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