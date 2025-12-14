import json
import math
import webbrowser
import os

# --- CONFIGURATION ---
TOTAL_ARTICLES = 730
ARTICLES_PER_HUB = 7  
HUBS_PER_HUB = 7      
OUTPUT_FILENAME = "ideal_hierarchy_v4.html"

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
                "val": 8
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
                hub_size = max(20, 35 - (current_depth * 10))
                
                nodes.append({
                    "id": new_hub_id,
                    "group": "hub",
                    "depth": current_depth + 1,
                    "label": "Cat",
                    "val": hub_size
                })
                
                links.append({
                    "source": current_hub_id,
                    "target": new_hub_id,
                    "type": "hub_link"
                })
                
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
    <title>Architect Console v4 (Interactive)</title>
    <style>
        body {{ 
            margin: 0; 
            background-color: #0f0f0f; 
            color: #ccc;
            font-family: 'Courier New', monospace;
            overflow: hidden;
        }}
        #graph {{ width: 100vw; height: 100vh; }}
        #controls {{
            position: absolute;
            top: 20px; 
            left: 20px;
            background: rgba(10, 10, 10, 0.85);
            padding: 20px;
            border: 1px solid #444;
            border-radius: 8px;
            pointer-events: auto;
            z-index: 100;
            width: 250px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        }}
        h3 {{ margin: 0 0 10px 0; color: #fff; font-size: 16px; border-bottom: 1px solid #444; padding-bottom: 5px;}}
        .control-group {{ margin-bottom: 15px; }}
        label {{ display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 5px; }}
        input[type=range] {{ width: 100%; cursor: pointer; }}
        .legend-item {{ display: flex; align-items: center; margin-top: 5px; font-size: 12px; }}
        .dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 8px; }}
        #status {{ font-size: 10px; color: #888; margin-top: 10px; font-style: italic; }}
    </style>
    <script src="https://d3js.org/d3.v7.min.js"></script>
</head>
<body>
    <div id="controls">
        <h3>The Architect's Console</h3>
        
        <div class="control-group">
            <label><span>Expansion Factor</span> <span id="val-expansion">1.0</span></label>
            <input type="range" id="slider-expansion" min="0.2" max="3.0" step="0.1" value="1.0">
        </div>

        <div class="control-group">
            <div class="legend-item"><span class="dot" style="background:#ff00ff"></span>Homepage</div>
            <div class="legend-item"><span class="dot" style="background:#9d00ff"></span>Category Hub</div>
            <div class="legend-item"><span class="dot" style="background:#00ffff"></span>Article</div>
        </div>
        
        <div id="status">Physics Stabilizing...</div>
    </div>
    
    <div id="graph"></div>

    <script>
        const graph = {json_str};
        const width = window.innerWidth;
        const height = window.innerHeight;

        // Base constants for the physics
        const BASE_HUB_DIST = 350;
        const BASE_ART_DIST = 50;
        const BASE_RING_SPACING = 400;

        const zoom = d3.zoom().scaleExtent([0.05, 5]).on("zoom", (event) => {{
            g.attr("transform", event.transform);
        }});

        const svg = d3.select("#graph").append("svg")
            .attr("width", width)
            .attr("height", height)
            .call(zoom);

        const g = svg.append("g");

        // --- PHYSICS ENGINE ---
        // Initialize forces
        const linkForce = d3.forceLink(graph.links).id(d => d.id);
        const chargeForce = d3.forceManyBody().strength(-300);
        const radialForce = d3.forceRadial(d => 0, width/2, height/2).strength(0.8); // Placeholder radius
        const collideForce = d3.forceCollide().radius(d => d.val + 5).iterations(2);

        const simulation = d3.forceSimulation(graph.nodes)
            .force("link", linkForce)
            .force("charge", chargeForce)
            .force("r", radialForce)
            .force("collide", collideForce);

        // --- RENDER ---
        const link = g.append("g")
            .attr("stroke", "#444")
            .attr("stroke-opacity", 0.3)
            .selectAll("line")
            .data(graph.links)
            .join("line")
            .attr("stroke-width", d => d.type === 'hub_link' ? 2 : 0.5);

        const node = g.append("g")
            .attr("stroke", "#000")
            .attr("stroke-width", 1.5)
            .selectAll("circle")
            .data(graph.nodes)
            .join("circle")
            .attr("r", d => d.val)
            .attr("fill", d => {{
                if (d.group === 'root') return "#ff00ff";
                if (d.group === 'hub') return "#9d00ff";
                return d3.interpolateGnBu(d.heat * 0.8 + 0.2);
            }})
            .call(drag(simulation));

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

        // --- DYNAMIC PHYSICS UPDATE ---
        function updatePhysics(scaleMultiplier) {{
            // 1. Update Link Distances (Tethers)
            linkForce.distance(d => {{
                if (d.type === 'hub_link') return BASE_HUB_DIST * scaleMultiplier;
                return BASE_ART_DIST * scaleMultiplier; // Keep articles relative to hubs
            }});

            // 2. Update Radial Rings (Orbits)
            radialForce.radius(d => {{
                if (d.group === 'article') return null; // Articles float freely
                return d.depth * BASE_RING_SPACING * scaleMultiplier;
            }});

            // 3. Re-heat the simulation so nodes move to new spots
            simulation.alpha(0.3).restart();
        }}

        // Initialize with default
        updatePhysics(1.0);

        // --- SLIDER EVENT LISTENER ---
        const slider = document.getElementById("slider-expansion");
        const label = document.getElementById("val-expansion");

        slider.addEventListener("input", (e) => {{
            const val = parseFloat(e.target.value);
            label.innerText = val.toFixed(1);
            updatePhysics(val);
            document.getElementById("status").innerText = "Adjusting Geometry...";
        }});

        // --- DRAG UTILS ---
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
        
        // --- AUTO-FIT LOGIC ---
        function zoomToFit() {{
            const bounds = g.node().getBBox();
            if (bounds.width === 0 || bounds.height === 0) return;
            const fullWidth = width;
            const fullHeight = height;
            const midX = bounds.x + bounds.width / 2;
            const midY = bounds.y + bounds.height / 2;
            const scale = 0.85 / Math.max(bounds.width / fullWidth, bounds.height / fullHeight);
            const finalScale = Math.min(scale, 1); 
            const translate = [fullWidth / 2 - finalScale * midX, fullHeight / 2 - finalScale * midY];

            svg.transition().duration(1500)
               .call(zoom.transform, d3.zoomIdentity.translate(translate[0], translate[1]).scale(finalScale));
            
            document.getElementById("status").innerText = "Simulation Stabilized.";
        }}

        setTimeout(zoomToFit, 2000);

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