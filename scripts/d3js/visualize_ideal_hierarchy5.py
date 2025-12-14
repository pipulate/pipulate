import json
import math
import webbrowser
import os

# --- CONFIGURATION ---
TOTAL_ARTICLES = 730
ARTICLES_PER_HUB = 7  
HUBS_PER_HUB = 7      
OUTPUT_FILENAME = "ideal_hierarchy_v5.html"

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
                "val": 6
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
                hub_size = max(15, 30 - (current_depth * 8))
                
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
    <title>Architect Console v5 (The Broccoli Effect)</title>
    <style>
        body {{ 
            margin: 0; 
            background-color: #050505; 
            color: #ccc;
            font-family: 'Courier New', monospace;
            overflow: hidden;
        }}
        #graph {{ width: 100vw; height: 100vh; }}
        #controls {{
            position: absolute;
            top: 20px; 
            left: 20px;
            background: rgba(15, 15, 20, 0.9);
            padding: 20px;
            border: 1px solid #444;
            border-radius: 8px;
            pointer-events: auto;
            z-index: 100;
            width: 280px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.6);
        }}
        h3 {{ margin: 0 0 10px 0; color: #fff; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid #444; padding-bottom: 8px;}}
        .control-group {{ margin-bottom: 15px; }}
        label {{ display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 5px; color: #aaa; }}
        input[type=range] {{ width: 100%; cursor: pointer; }}
        #status {{ font-size: 10px; color: #666; margin-top: 10px; text-align: center; }}
    </style>
    <script src="https://d3js.org/d3.v7.min.js"></script>
</head>
<body>
    <div id="controls">
        <h3>Graph Physics</h3>
        
        <div class="control-group">
            <label><span>Territory Size (Clustering)</span> <span id="val-collide">3.0</span></label>
            <input type="range" id="slider-collide" min="0.0" max="4.0" step="0.5" value="3.0">
        </div>

        <div id="status">Initializing Simulation...</div>
    </div>
    
    <div id="graph"></div>

    <script>
        const graph = {json_str};
        const width = window.innerWidth;
        const height = window.innerHeight;

        const zoom = d3.zoom().scaleExtent([0.05, 5]).on("zoom", (event) => {{
            g.attr("transform", event.transform);
        }});

        const svg = d3.select("#graph").append("svg")
            .attr("width", width)
            .attr("height", height)
            .call(zoom);

        const g = svg.append("g");

        // --- PHYSICS CONFIG ---
        // Base sizes for forces
        const HUB_LINK_DIST = 200;
        const ART_LINK_DIST = 40; 
        
        // This is the variable radius function.
        // It creates the "Invisible Bubble" that forces the broccoli shape.
        let collideMultiplier = 3.0; 

        const simulation = d3.forceSimulation(graph.nodes)
            // 1. Link Force: Rigid structure
            .force("link", d3.forceLink(graph.links).id(d => d.id)
                .distance(d => d.type === 'hub_link' ? HUB_LINK_DIST : ART_LINK_DIST)
                .strength(d => d.type === 'hub_link' ? 0.3 : 1.5)) // Hubs flexible, Articles strict
            
            // 2. Global Repulsion
            .force("charge", d3.forceManyBody().strength(-200))
            
            // 3. Radial Force (Weak)
            // We weaken this significantly so it doesn't crush the clusters into rings
            .force("r", d3.forceRadial(d => {{
                if (d.group === 'article') return null; 
                return d.depth * 350; 
            }}, width / 2, height / 2).strength(0.4))
            
            // 4. Collision (The Main Actor)
            // Note: We initialize with the default multiplier
            .force("collide", d3.forceCollide().radius(d => {{
                // Hubs get MASSIVE territory based on the multiplier
                if (d.group === 'hub' || d.group === 'root') return d.val * collideMultiplier;
                // Articles just need not to overlap
                return d.val + 2; 
            }}).iterations(3));

        // --- RENDER ---
        const link = g.append("g")
            .attr("stroke", "#444")
            .attr("stroke-opacity", 0.3)
            .selectAll("line")
            .data(graph.links)
            .join("line")
            .attr("stroke-width", d => d.type === 'hub_link' ? 1.5 : 0.5);

        const node = g.append("g")
            .attr("stroke", "#111")
            .attr("stroke-width", 1.0)
            .selectAll("circle")
            .data(graph.nodes)
            .join("circle")
            .attr("r", d => d.val)
            .attr("fill", d => {{
                if (d.group === 'root') return "#ff00ff";
                if (d.group === 'hub') return "#bd00ff";
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

        // --- INTERACTIVITY ---
        const sliderCollide = document.getElementById("slider-collide");
        const labelCollide = document.getElementById("val-collide");

        sliderCollide.addEventListener("input", (e) => {{
            collideMultiplier = parseFloat(e.target.value);
            labelCollide.innerText = collideMultiplier.toFixed(1);
            
            // Update the collision radius dynamically
            simulation.force("collide").radius(d => {{
                if (d.group === 'hub' || d.group === 'root') return d.val * collideMultiplier;
                return d.val + 2;
            }});
            
            simulation.alpha(0.5).restart();
            document.getElementById("status").innerText = "Adjusting Territory...";
        }});

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
        
        // --- AUTO-FIT ---
        function zoomToFit() {{
            const bounds = g.node().getBBox();
            if (bounds.width === 0) return;
            
            const fullWidth = width;
            const fullHeight = height;
            const midX = bounds.x + bounds.width / 2;
            const midY = bounds.y + bounds.height / 2;
            const scale = 0.85 / Math.max(bounds.width / fullWidth, bounds.height / fullHeight);
            const finalScale = Math.min(scale, 1); 

            svg.transition().duration(2000)
               .call(zoom.transform, d3.zoomIdentity
                    .translate(fullWidth / 2 - finalScale * midX, fullHeight / 2 - finalScale * midY)
                    .scale(finalScale));
            
            document.getElementById("status").innerText = "Simulation Stabilized.";
        }}

        setTimeout(zoomToFit, 2500);

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
