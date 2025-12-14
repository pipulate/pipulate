import json
import math
import webbrowser
import os

# --- CONFIGURATION ---
TOTAL_ARTICLES = 730
ARTICLES_PER_HUB = 7  # The "Local Board"
HUBS_PER_HUB = 7      # The "Express Board"
OUTPUT_FILENAME = "ideal_hierarchy_v3.html"

# --- THE SIMULATION ---
def generate_ideal_graph():
    nodes = []
    links = []
    
    # Trackers
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
        "val": 50 # Big Anchor
    })
    queue.append((root_id, 0))
    hub_count += 1

    while article_count < TOTAL_ARTICLES and queue:
        current_hub_id, current_depth = queue.pop(0)
        
        # A. Assign Articles (Local Board)
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
                "val": 8  # Larger, more visible leaves
            })
            
            links.append({
                "source": current_hub_id,
                "target": article_id,
                "type": "article_link"
            })
            article_count += 1

        # B. Create Sub-Hubs (Express Board)
        if article_count < TOTAL_ARTICLES:
            for i in range(HUBS_PER_HUB):
                if article_count >= TOTAL_ARTICLES: break
                    
                new_hub_id = f"hub_{hub_count}"
                
                # Less extreme scaling. Level 1 = 30, Level 2 = 20
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
    <title>Idealized Link Graph v3 (Auto-Fit)</title>
    <style>
        body {{ 
            margin: 0; 
            background-color: #0f0f0f; 
            color: #ccc;
            font-family: 'Courier New', monospace;
            overflow: hidden;
        }}
        #graph {{ width: 100vw; height: 100vh; }}
        #legend {{
            position: absolute;
            top: 20px; 
            left: 20px;
            background: rgba(0,0,0,0.8);
            padding: 15px;
            border: 1px solid #333;
            border-radius: 4px;
            pointer-events: none;
            z-index: 10;
        }}
        button {{
            margin-top: 10px;
            pointer-events: auto;
            background: #333;
            color: #fff;
            border: 1px solid #555;
            padding: 5px 10px;
            cursor: pointer;
        }}
    </style>
    <script src="https://d3js.org/d3.v7.min.js"></script>
</head>
<body>
    <div id="legend">
        <h3>The Rule of 7 (v3)</h3>
        <p>Hubs: <span style="color:#ff00ff">●</span> Articles: <span style="color:#00ffff">●</span></p>
        <div id="status">Calculating Physics...</div>
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

        // --- PHYSICS ENGINE v3 ---
        const simulation = d3.forceSimulation(graph.nodes)
            // 1. Link Force
            // Hubs push FAR out (350px) to define rings. Articles pull CLOSE (50px).
            .force("link", d3.forceLink(graph.links).id(d => d.id)
                .distance(d => d.type === 'hub_link' ? 350 : 50)
                .strength(d => d.type === 'hub_link' ? 0.5 : 2.0))
            
            // 2. Charge
            // Strong repulsion to prevent hairballing
            .force("charge", d3.forceManyBody().strength(-300))
            
            // 3. Selective Radial Force
            // ONLY apply radial force to Hubs/Root. Let articles float freely around them.
            // This fixes the "Satellite Compression" issue.
            .force("r", d3.forceRadial(d => {{
                if (d.group === 'article') return null; // Ignore articles
                return d.depth * 400; // Hub Rings at 0, 400, 800
            }}, width / 2, height / 2).strength(d => d.group === 'article' ? 0 : 0.8))
            
            .force("collide", d3.forceCollide().radius(d => d.val + 5).iterations(2));

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
        // We wait for the "Big Bang" (initial expansion) to settle, then fit.
        function zoomToFit() {{
            const bounds = g.node().getBBox();
            
            // If bounds are invalid (0x0), wait longer
            if (bounds.width === 0 || bounds.height === 0) return;

            const fullWidth = width;
            const fullHeight = height;
            const midX = bounds.x + bounds.width / 2;
            const midY = bounds.y + bounds.height / 2;

            if (bounds.width === 0 || bounds.height === 0) return; // nothing to fit

            // Add 10% padding
            const scale = 0.9 / Math.max(bounds.width / fullWidth, bounds.height / fullHeight);
            
            // clamp scale to prevent zooming in too far on empty graphs
            const finalScale = Math.min(scale, 1); 

            const translate = [
                fullWidth / 2 - finalScale * midX,
                fullHeight / 2 - finalScale * midY
            ];

            svg.transition()
                .duration(1500) // Slow, smooth animation
                .call(zoom.transform, d3.zoomIdentity
                    .translate(translate[0], translate[1])
                    .scale(finalScale));
            
            document.getElementById("status").innerText = "Simulation Stabilized & Fitted.";
        }}

        // Trigger fit after 2 seconds (allow physics to expand the tree first)
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