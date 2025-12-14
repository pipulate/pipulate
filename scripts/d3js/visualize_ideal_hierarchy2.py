import json
import math
import webbrowser
import os

# --- CONFIGURATION ---
TOTAL_ARTICLES = 730
ARTICLES_PER_HUB = 7  # The "Local Board"
HUBS_PER_HUB = 7      # The "Express Board"
OUTPUT_FILENAME = "ideal_hierarchy_v2.html"

# --- THE SIMULATION ---
def generate_ideal_graph():
    nodes = []
    links = []
    
    # Trackers
    article_count = 0
    hub_count = 0
    
    # Queue for Breadth-First Search generation
    # Tuple: (hub_id, depth)
    queue = []

    # 1. Create Root
    root_id = "hub_0"
    nodes.append({
        "id": root_id, 
        "group": "root", 
        "depth": 0, 
        "label": "HOMEPAGE",
        "val": 30 
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
                "val": 6  # Slightly larger for visibility
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
                
                # Scale hub size down slightly by depth, but not too much
                hub_size = max(15, 30 - (current_depth * 5))
                
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
    <title>Idealized Link Graph v2 (Radial Fit)</title>
    <style>
        body {{ 
            margin: 0; 
            background-color: #0f0f0f; /* Deep Noir */
            color: #ccc;
            font-family: 'Courier New', monospace; /* Tech feel */
            overflow: hidden;
        }}
        #graph {{ width: 100vw; height: 100vh; }}
        #legend {{
            position: absolute;
            top: 20px; 
            left: 20px;
            background: rgba(0,0,0,0.7);
            padding: 15px;
            border: 1px solid #333;
            border-radius: 4px;
            pointer-events: none;
        }}
    </style>
    <script src="https://d3js.org/d3.v7.min.js"></script>
</head>
<body>
    <div id="legend">
        <h3>The Rule of 7 (Radial)</h3>
        <p>Hubs (Category): <span style="color:#ff00ff">●</span></p>
        <p>Articles (Leaf): <span style="color:#00ffff">●</span></p>
        <p style="font-size:0.8em">Scroll to Zoom. Drag to Pan.</p>
    </div>
    <div id="graph"></div>

    <script>
        const graph = {json_str};
        const width = window.innerWidth;
        const height = window.innerHeight;

        // 1. Setup SVG with Initial Zoom "Fit"
        // We start zoomed out to see the whole universe.
        const svg = d3.select("#graph").append("svg")
            .attr("width", width)
            .attr("height", height)
            .call(d3.zoom().scaleExtent([0.1, 8]).on("zoom", (event) => {{
                g.attr("transform", event.transform);
            }}));

        const g = svg.append("g");

        // Center the initial view
        // Using a manual transform to start zoomed out (0.4x scale) centered in viewport
        const initialScale = 0.4;
        const initialX = (width - width * initialScale) / 2;
        const initialY = (height - height * initialScale) / 2;
        // Note: D3 zoom identity doesn't auto-apply here without logic, 
        // but forces will center the graph at width/2, height/2 naturally.
        // We will let the forces center it, user can scroll to zoom out more.

        // --- PHYSICS ENGINE ---
        const simulation = d3.forceSimulation(graph.nodes)
            // A. Link Force: 
            // - Hubs (Express) pushed WAY out (distance 150)
            // - Articles (Local) kept VERY close (distance 25)
            .force("link", d3.forceLink(graph.links).id(d => d.id)
                .distance(d => d.type === 'hub_link' ? 180 : 25)
                .strength(d => d.type === 'hub_link' ? 0.8 : 2.0)) // Rigid articles, flexible hubs
            
            // B. ManyBody (Gravity/Repulsion):
            // - Strong global repulsion to spread the tree
            .force("charge", d3.forceManyBody().strength(-500))
            
            // C. Radial Force (The Secret Sauce):
            // - Forces nodes into rings based on their depth.
            // - Root at center (0), Level 1 at 300px, Level 2 at 600px...
            .force("r", d3.forceRadial(d => d.depth * 300, width / 2, height / 2).strength(0.8))
            
            // D. Collision: Prevent overlapping
            .force("collide", d3.forceCollide().radius(d => d.val + 10).iterations(2));

        // --- RENDER ---
        const link = g.append("g")
            .attr("stroke", "#444")
            .attr("stroke-opacity", 0.4)
            .selectAll("line")
            .data(graph.links)
            .join("line")
            .attr("stroke-width", d => d.type === 'hub_link' ? 1 : 0.5);

        const node = g.append("g")
            .selectAll("circle")
            .data(graph.nodes)
            .join("circle")
            .attr("r", d => d.val)
            .attr("fill", d => {{
                if (d.group === 'root') return "#ff00ff";
                if (d.group === 'hub') return "#9d00ff";
                // Heatmap: Cyan (Hot) -> Blue (Cold)
                return d3.interpolateGnBu(d.heat * 0.8 + 0.2);
            }})
            .attr("stroke", "#000")
            .attr("stroke-width", 1.5)
            .call(drag(simulation));

        // Labels (Only for Hubs to reduce clutter)
        const label = g.append("g")
            .selectAll("text")
            .data(graph.nodes.filter(d => d.group !== 'article' || d.depth < 2)) // Only label top layers
            .join("text")
            .attr("dx", 12)
            .attr("dy", ".35em")
            .text(d => d.group === 'root' ? "HOME" : "")
            .attr("fill", "#fff")
            .style("font-size", "10px")
            .style("pointer-events", "none");

        simulation.on("tick", () => {{
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);

            node
                .attr("cx", d => d.x)
                .attr("cy", d => d.y);
                
            label
                .attr("x", d => d.x)
                .attr("y", d => d.y);
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
        
        // Initial Zoom Out Hack
        // Wait for a few ticks then programmatically zoom out to fit
        setTimeout(() => {{
            const zoomTransform = d3.zoomIdentity.translate(width/2, height/2).scale(0.15).translate(-width/2, -height/2);
            svg.transition().duration(750).call(d3.zoom().transform, zoomTransform);
        }}, 500);

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