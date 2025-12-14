import json
import math
import webbrowser
import os

# --- CONFIGURATION ---
TOTAL_ARTICLES = 730
ARTICLES_PER_HUB = 7  # The "Local Board"
HUBS_PER_HUB = 7      # The "Express Board"
OUTPUT_FILENAME = "ideal_hierarchy.html"

# --- THE SIMULATION ---
def generate_ideal_graph():
    nodes = []
    links = []
    
    # Trackers
    article_count = 0
    hub_count = 0
    
    # Queue for Breadth-First Search generation (ensures balanced tree)
    # Tuple: (hub_id, depth)
    queue = []

    # 1. Create Root
    root_id = "hub_0"
    nodes.append({
        "id": root_id, 
        "group": "root", 
        "depth": 0, 
        "label": "HOMEPAGE",
        "val": 40 # Size
    })
    queue.append((root_id, 0))
    hub_count += 1

    while article_count < TOTAL_ARTICLES and queue:
        current_hub_id, current_depth = queue.pop(0)
        
        # A. Assign Articles to this Hub (The "Local Board")
        # We calculate "Heat" based on the order of creation. 
        # Early articles = Higher GSC Potential = Hotter Color
        remaining_articles = TOTAL_ARTICLES - article_count
        to_create = min(ARTICLES_PER_HUB, remaining_articles)
        
        for _ in range(to_create):
            article_id = f"art_{article_count}"
            
            # Simulated GSC "Heat" (0.0 to 1.0)
            # Articles closer to the center (lower count) are "hotter"
            heat = 1.0 - (article_count / TOTAL_ARTICLES)
            
            nodes.append({
                "id": article_id,
                "group": "article",
                "depth": current_depth,
                "label": f"Article {article_count}",
                "heat": heat,
                "val": 5
            })
            
            links.append({
                "source": current_hub_id,
                "target": article_id,
                "type": "article_link"
            })
            article_count += 1

        # B. Create Sub-Hubs (The "Express Board")
        # Only create sub-hubs if we still have articles left to place
        if article_count < TOTAL_ARTICLES:
            # We determine how many sub-hubs we need roughly based on remaining items
            # But strictly following Rule of 7, we just max it out until we run out of "future" slots
            # For this simulation, we just spawn the standard amount to keep the tree balanced.
            
            for i in range(HUBS_PER_HUB):
                # Don't spawn empty hubs if we are near the end
                if article_count >= TOTAL_ARTICLES: 
                    break
                    
                new_hub_id = f"hub_{hub_count}"
                nodes.append({
                    "id": new_hub_id,
                    "group": "hub",
                    "depth": current_depth + 1,
                    "label": "Category",
                    "val": 20
                })
                
                links.append({
                    "source": current_hub_id,
                    "target": new_hub_id,
                    "type": "hub_link"
                })
                
                queue.append((new_hub_id, current_depth + 1))
                hub_count += 1

    return {"nodes": nodes, "links": links}

# --- THE VISUALIZER (HTML/D3 GENERATOR) ---
def create_html(graph_data):
    json_str = json.dumps(graph_data)
    
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>The Idealized Link Graph (Rule of 7)</title>
    <style>
        body {{ 
            margin: 0; 
            background-color: #111; /* Noir Mode */
            color: #ddd;
            font-family: sans-serif;
            overflow: hidden;
        }}
        #graph {{ width: 100vw; height: 100vh; }}
        .tooltip {{
            position: absolute;
            background: rgba(0,0,0,0.8);
            padding: 5px;
            border-radius: 4px;
            pointer-events: none;
            font-size: 12px;
            border: 1px solid #555;
        }}
        #legend {{
            position: absolute;
            top: 20px;
            left: 20px;
            background: rgba(0,0,0,0.5);
            padding: 10px;
            border-radius: 8px;
        }}
    </style>
    <script src="https://d3js.org/d3.v7.min.js"></script>
</head>
<body>
    <div id="legend">
        <h3>The Rule of 7 Hierarchy</h3>
        <p>Total Articles: {TOTAL_ARTICLES}</p>
        <p>Hubs (Categories): <span style="color:#ff00ff">●</span></p>
        <p>Articles (Content): <span style="color:#00ffff">●</span></p>
        <p><em>Color intensity indicates SEO Value (Heat)</em></p>
    </div>
    <div id="graph"></div>

    <script>
        const graph = {json_str};

        const width = window.innerWidth;
        const height = window.innerHeight;

        const svg = d3.select("#graph").append("svg")
            .attr("width", width)
            .attr("height", height)
            .call(d3.zoom().on("zoom", (event) => {{
                g.attr("transform", event.transform);
            }}))
            .append("g");

        const g = svg.append("g");

        // --- FORCES ---
        // 1. Link Force: Hubs push further apart, Articles stick close to parent
        const simulation = d3.forceSimulation(graph.nodes)
            .force("link", d3.forceLink(graph.links).id(d => d.id)
                .distance(d => d.type === 'hub_link' ? 100 : 30)) 
            .force("charge", d3.forceManyBody().strength(d => d.group === 'root' ? -1000 : -300))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collide", d3.forceCollide().radius(d => d.val + 2).iterations(2));

        // --- RENDER LINKS ---
        const link = g.append("g")
            .attr("stroke", "#555")
            .attr("stroke-opacity", 0.6)
            .selectAll("line")
            .data(graph.links)
            .join("line")
            .attr("stroke-width", d => d.type === 'hub_link' ? 1.5 : 0.5);

        // --- RENDER NODES ---
        const node = g.append("g")
            .attr("stroke", "#fff")
            .attr("stroke-width", 0.5)
            .selectAll("circle")
            .data(graph.nodes)
            .join("circle")
            .attr("r", d => d.val)
            .attr("fill", d => {{
                if (d.group === 'root') return "#ff00ff"; // Magenta Root
                if (d.group === 'hub') return "#9d00ff";  // Purple Hubs
                
                // Heatmap for articles (Cyan to Dark Blue)
                // Hotter (closer to 1.0) = Bright Cyan
                return d3.interpolateBlues(d.heat * 0.8 + 0.2); 
            }})
            .call(drag(simulation));

        node.append("title")
            .text(d => d.group === 'article' ? d.label + " (Heat: " + d.heat.toFixed(2) + ")" : d.label);

        // --- TICK FUNCTION ---
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
    </script>
</body>
</html>
    """
    
    with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"✅ Generated {OUTPUT_FILENAME}")
    print(f"   Nodes: {len(graph_data['nodes'])}")
    print(f"   Links: {len(graph_data['links'])}")
    
    # Auto-open
    webbrowser.open('file://' + os.path.realpath(OUTPUT_FILENAME))

if __name__ == "__main__":
    data = generate_ideal_graph()
    create_html(data)