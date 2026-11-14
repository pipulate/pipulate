import asyncio
import hashlib
import json
import os
import zipfile
import html as html_lib
import math
import re
from pathlib import Path
from urllib.parse import urlparse, quote, urljoin
from bs4 import BeautifulSoup

from fasthtml.common import *
from loguru import logger
from starlette.responses import FileResponse, Response

from imports.crud import Step
from tools.scraper_tools import selenium_automation, generate_optics_subprocess

_GENERIC_DIV_CLASSES = frozenset({
    "wrapper", "container", "page-content", "content", "inner", "row", "col", "main", "layout",
})
_SEMANTIC_LANDMARKS = ("nav", "header", "aside", "footer", "section", "form")


def _normalize_graph_href(base_url: str, raw_href: str, origin_host: str, origin_path: str) -> str | None:
    s = str(raw_href or "").strip()
    if not s or s.lower().startswith(("javascript:", "mailto:", "tel:", "data:", "blob:")):
        return None
    resolved = urljoin(base_url, s)
    parsed = urlparse(resolved)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    same_page = (
        parsed.netloc.lower() == origin_host
        and (parsed.path or "/") == (origin_path or "/")
        and bool(parsed.fragment)
    )
    if same_page:
        return resolved
    return parsed._replace(fragment="").geturl()


def _resolve_dom_cluster_label(a_tag) -> str:
    nearest_div = None
    fallback_landmark = None
    for anc in a_tag.parents:
        t = (getattr(anc, "name", "") or "").lower()
        if not t or t in ("body", "html", "[document]"):
            break
        el_id = re.sub(r"[^A-Za-z0-9_-]+", "", str(anc.get("id") or "").strip())[:28]
        raw_classes = anc.get("class") or []
        cls_list = [
            re.sub(r"[^A-Za-z0-9_-]+", "", str(c))
            for c in raw_classes
            if c and str(c).lower() not in _GENERIC_DIV_CLASSES
        ]
        if t in _SEMANTIC_LANDMARKS:
            if el_id:
                return f"{t}#{el_id}"
            if cls_list:
                return f"{t}.{cls_list[0][:28]}"
            return t
        if t == "div" and nearest_div is None:
            if el_id:
                nearest_div = f"div#{el_id}"
            elif cls_list:
                nearest_div = f"div.{cls_list[0][:28]}"
        if t in ("article", "main") and fallback_landmark is None:
            fallback_landmark = f"{t}#{el_id}" if el_id else t
    return nearest_div or fallback_landmark or "body"


def _clean_anchor_label(a_tag, target_url: str) -> str:
    txt = re.sub(r"\s+", " ", (a_tag.get_text(" ", strip=True) or "")).strip()
    if not txt:
        txt = str(a_tag.get("aria-label") or a_tag.get("title") or "").strip()
    if not txt:
        img = a_tag.find("img")
        if img:
            txt = str(img.get("alt") or "").strip()
    if not txt:
        p = urlparse(target_url)
        txt = (f"#{p.fragment}" if p.fragment else p.path) or p.netloc
    return txt[:64] + ("…" if len(txt) > 64 else "")


def build_dom_link_graph(target_url: str, source_html: str, hydrated_html: str, max_leaves: int = 140) -> dict:
    """Build a 1-page radial DOM link-graph comparing raw wire HTML vs. hydrated DOM."""
    base_url = str(target_url or "").strip() or ("https:" + "//example.com/")
    parsed_origin = urlparse(base_url)
    origin_host = parsed_origin.netloc.lower()
    origin_path = parsed_origin.path or "/"
    origin_label = parsed_origin.netloc + (origin_path if origin_path != "/" else "/")

    soup_Name = "lxml"
    try:
        soup_src = BeautifulSoup(source_html or "", soup_Name)
    except Exception:
        soup_Name = "html.parser"
        soup_src = BeautifulSoup(source_html or "", soup_Name)

    wire_urls = set()
    for a_el in soup_src.find_all("a", href=True):
        u = _normalize_graph_href(base_url, a_el.get("href", ""), origin_host, origin_path)
        if u:
            wire_urls.add(u)

    soup_hyd = BeautifulSoup(hydrated_html or source_html or "", soup_Name)
    raw_anchors = 0
    by_cluster: dict[str, dict[str, dict]] = {}
    for a_el in soup_hyd.find_all("a", href=True):
        u = _normalize_graph_href(base_url, a_el.get("href", ""), origin_host, origin_path)
        if not u:
            continue
        raw_anchors += 1
        c_label = _resolve_dom_cluster_label(a_el)
        bucket = by_cluster.setdefault(c_label, {})
        if u in bucket:
            bucket[u]["count"] += 1
            continue
        is_internal = urlparse(u).netloc.lower() == origin_host
        in_wire = u in wire_urls
        status = (
            "wire_internal" if (in_wire and is_internal)
            else "wire_external" if in_wire
            else "js_internal" if is_internal
            else "js_external"
        )
        bucket[u] = {
            "url": u,
            "label": _clean_anchor_label(a_el, u),
            "cluster": c_label,
            "internal": is_internal,
            "in_wire": in_wire,
            "js_only": not in_wire,
            "status": status,
            "count": 1,
        }

    if len(by_cluster) > 14:
        ranked = sorted(by_cluster.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        kept = dict(ranked[:13])
        overflow: dict[str, dict] = {}
        for _, items in ranked[13:]:
            for u, rec in items.items():
                cp = dict(rec, cluster="div.other-dom")
                if u in overflow:
                    overflow[u]["count"] += cp["count"]
                else:
                    overflow[u] = cp
        if overflow:
            kept["div.other-dom"] = overflow
        by_cluster = kept

    all_items = [rec for bucket in by_cluster.values() for rec in bucket.values()]
    stats = {
        "total_anchors": raw_anchors,
        "unique_links": len(all_items),
        "wire_links": sum(1 for r in all_items if r["in_wire"]),
        "js_only_links": sum(1 for r in all_items if r["js_only"]),
        "internal_links": sum(1 for r in all_items if r["internal"]),
        "external_links": sum(1 for r in all_items if not r["internal"]),
        "cluster_count": len(by_cluster),
    }

    cx, cy = 390.0, 235.0
    nodes = [{
        "id": "origin",
        "label": origin_label[:42],
        "url": base_url,
        "group": "origin",
        "status": "origin",
        "cluster": "origin",
        "depth": 0,
        "count": len(all_items),
        "x": cx,
        "y": cy,
    }]
    links = []
    cluster_names = list(by_cluster.keys())
    n_clusters = max(1, len(cluster_names))
    total_unique = max(1, len(all_items))

    for idx, c_name in enumerate(cluster_names):
        ang = (2.0 * math.pi * idx / n_clusters) - (math.pi / 2.0)
        c_id = f"cluster_{idx}"
        c_items = list(by_cluster[c_name].values())
        js_in_c = sum(1 for r in c_items if r["js_only"])
        nodes.append({
            "id": c_id,
            "label": c_name,
            "url": base_url,
            "group": "cluster",
            "status": "cluster_js" if js_in_c > 0 else "cluster",
            "cluster": c_name,
            "depth": 1,
            "count": len(c_items),
            "js_count": js_in_c,
            "x": round(cx + math.cos(ang) * 112.0, 1),
            "y": round(cy + math.sin(ang) * 112.0, 1),
        })
        links.append({"source": "origin", "target": c_id, "kind": "dom_branch"})

        quota = max(2, int(round((len(c_items) / total_unique) * max_leaves)))
        # Prioritize JS-only links first so hidden client-rendered links are never sampled out
        chosen = sorted(c_items, key=lambda r: (not r["js_only"], -r["count"], r["url"]))[:quota]
        span = min(0.75, max(0.16, (2.0 * math.pi / n_clusters) * 0.78))
        m = len(chosen)
        for j, rec in enumerate(chosen):
            offset = 0.0 if m == 1 else ((j / (m - 1)) - 0.5) * span
            leaf_ang = ang + offset
            rad = 196.0 if (j % 2 == 0) else 222.0
            leaf_id = f"leaf_{idx}_{j}"
            nodes.append({
                "id": leaf_id,
                "label": rec["label"],
                "url": rec["url"],
                "group": "link",
                "status": rec["status"],
                "cluster": c_name,
                "internal": rec["internal"],
                "js_only": rec["js_only"],
                "depth": 2,
                "count": rec["count"],
                "x": round(cx + math.cos(leaf_ang) * rad, 1),
                "y": round(cy + math.sin(leaf_ang) * rad, 1),
            })
            links.append({
                "source": c_id,
                "target": leaf_id,
                "kind": "js_link" if rec["js_only"] else "wire_link",
            })

    return {
        "target_url": base_url,
        "origin_host": origin_host,
        "stats": stats,
        "clusters": [
            {
                "name": k,
                "total": len(v),
                "wire": sum(1 for r in v.values() if r["in_wire"]),
                "js_only": sum(1 for r in v.values() if r["js_only"]),
            }
            for k, v in by_cluster.items()
        ],
        "nodes": nodes,
        "links": links,
    }


def _radial_graph_client_js(mount_id: str, data_id: str) -> str:
    d3_fallback = "https:" + "//mikelev.in/assets/js/d3.v7.min.js"
    return f"""
(function() {{
  const root = document.getElementById({json.dumps(mount_id)});
  const dataEl = document.getElementById({json.dumps(data_id)});
  if (!root || !dataEl || root.dataset.mounted === '1') return;
  root.dataset.mounted = '1';
  let graph;
  try {{ graph = JSON.parse(dataEl.textContent || '{{}}'); }} catch (e) {{ return; }}
  const svgEl = root.querySelector('.optics-rg-svg');
  const tipEl = root.querySelector('.optics-rg-tip');
  const inspEl = root.querySelector('.optics-rg-insp');
  const searchEl = root.querySelector('.optics-rg-search');
  let filterMode = 'all';
  let activeCluster = '';
  let query = '';

  function colorFor(n) {{
    if (n.group === 'origin') return '#f8fafc';
    if (n.group === 'cluster') return n.js_count > 0 ? '#c084fc' : '#818cf8';
    if (n.status === 'js_internal' || n.status === 'js_external') return '#f59e0b';
    return n.internal ? '#10b981' : '#06b6d4';
  }}

  function radiusFor(n) {{
    if (n.group === 'origin') return 12;
    if (n.group === 'cluster') return Math.min(10.5, 6 + Math.sqrt(n.count || 1) * 0.7);
    return n.js_only ? 5.2 : 4.2;
  }}

  function visibleSet() {{
    const keep = {{ origin: true }};
    const ql = query.toLowerCase();
    (graph.nodes || []).forEach(function(n) {{
      if (n.group === 'cluster') {{
        if (!activeCluster || activeCluster === n.cluster) keep[n.id] = true;
      }}
    }});
    const activeClustersWithLeaves = {{}};
    (graph.nodes || []).forEach(function(n) {{
      if (n.group !== 'link') return;
      if (activeCluster && n.cluster !== activeCluster) return;
      if (filterMode === 'js' && !n.js_only) return;
      if (filterMode === 'internal' && !n.internal) return;
      if (filterMode === 'external' && n.internal) return;
      if (ql && (n.label || '').toLowerCase().indexOf(ql) === -1 && (n.url || '').toLowerCase().indexOf(ql) === -1 && (n.cluster || '').toLowerCase().indexOf(ql) === -1) return;
      keep[n.id] = true;
      activeClustersWithLeaves[n.cluster] = true;
    }});
    if (filterMode !== 'all' || ql) {{
      (graph.nodes || []).forEach(function(n) {{
        if (n.group === 'cluster' && !activeClustersWithLeaves[n.cluster]) delete keep[n.id];
      }});
    }}
    return keep;
  }}

  function esc(s) {{
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }}

  function renderInspector(keep) {{
    const leaves = (graph.nodes || []).filter(function(n) {{ return n.group === 'link' && keep[n.id]; }});
    const pills = (graph.clusters || []).map(function(c) {{
      const isAct = activeCluster === c.name ? 'border-color:#22d3ee;background:rgba(34,211,238,0.2);color:#fff;' : '';
      const jsTag = c.js_only > 0 ? ' · ⚡' + c.js_only + ' JS' : '';
      return '<button type="button" data-cluster="' + esc(c.name) + '" style="padding:0.16rem 0.5rem;border-radius:999px;border:1px solid rgba(129,140,248,0.45);background:rgba(99,102,241,0.14);color:#c7d2fe;font-size:0.72rem;cursor:pointer;' + isAct + '">' + esc(c.name) + ' (' + c.total + jsTag + ')</button>';
    }}).join(' ');
    const rows = leaves.slice(0, 24).map(function(n) {{
      const badge = n.js_only ? '<span style="color:#fbbf24;font-weight:700;">[⚡ JS-ONLY]</span> ' : '<span style="color:#34d399;">[WIRE]</span> ';
      return '<a href="' + esc(n.url) + '" target="_blank" rel="noopener" style="display:block;padding:0.3rem 0.5rem;border-radius:5px;background:rgba(255,255,255,0.035);border:1px solid rgba(255,255,255,0.08);color:#79c0ff;font-size:0.74rem;text-decoration:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"><span style="color:#8b949e;font-family:monospace;">' + esc(n.cluster) + '</span> · ' + badge + esc(n.label) + '</a>';
    }}).join('');
    const clrBtn = activeCluster ? ' <button type="button" data-cluster="" style="padding:0.14rem 0.48rem;border-radius:999px;border:1px solid rgba(255,255,255,0.25);background:transparent;color:#e6edf3;font-size:0.7rem;cursor:pointer;">✕ All Landmarks</button>' : '';
    inspEl.innerHTML = '<div style="display:flex;flex-wrap:wrap;gap:0.35rem;margin-bottom:0.5rem;align-items:center;"><strong style="font-size:0.75rem;color:#f0f6fc;">DOM Landmarks:</strong> ' + pills + clrBtn + '</div>' +
      '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:0.35rem;max-height:150px;overflow-y:auto;">' + (rows || '<span style="font-size:0.75rem;color:#8b949e;">No matching links in current filter.</span>') + '</div>';
  }}

  function renderStaticFallback() {{
    const keep = visibleSet();
    const nMap = {{}};
    (graph.nodes || []).forEach(function(n) {{ if (keep[n.id]) nMap[n.id] = n; }});
    let parts = ['<g class="rg-viewport">'];
    (graph.links || []).forEach(function(l) {{
      const s = nMap[typeof l.source === 'object' ? l.source.id : l.source];
      const t = nMap[typeof l.target === 'object' ? l.target.id : l.target];
      if (!s || !t) return;
      const stroke = l.kind === 'js_link' ? 'rgba(245,158,11,0.55)' : (l.kind === 'dom_branch' ? 'rgba(129,140,248,0.42)' : 'rgba(52,211,153,0.3)');
      parts.push('<line x1="' + s.x + '" y1="' + s.y + '" x2="' + t.x + '" y2="' + t.y + '" stroke="' + stroke + '" stroke-width="' + (l.kind === 'dom_branch' ? 1.6 : 1.0) + '"/>');
    }});
    Object.values(nMap).forEach(function(n) {{
      parts.push('<circle data-nid="' + esc(n.id) + '" cx="' + n.x + '" cy="' + n.y + '" r="' + radiusFor(n) + '" fill="' + colorFor(n) + '" stroke="#090d12" stroke-width="1.2" style="cursor:pointer;"><title>' + esc(n.cluster + ' — ' + n.label + ' (' + n.url + ')') + '</title></circle>');
      if (n.group !== 'link') {{
        parts.push('<text x="' + n.x + '" y="' + (n.y - radiusFor(n) - 4) + '" text-anchor="middle" fill="#e6edf3" font-size="10" font-weight="600" style="pointer-events:none;">' + esc(n.label) + '</text>');
      }}
    }});
    parts.push('</g>');
    svgEl.setAttribute('viewBox', '0 0 780 470');
    svgEl.innerHTML = parts.join('');
    renderInspector(keep);
  }}

  let d3Sim = null;
  function renderD3() {{
    if (!window.d3) {{ renderStaticFallback(); return; }}
    const d3 = window.d3;
    const keep = visibleSet();
    const vNodes = (graph.nodes || []).filter(function(n) {{ return keep[n.id]; }}).map(function(n) {{
      const cp = Object.assign({{}}, n);
      if (cp.group === 'origin') {{ cp.fx = 390; cp.fy = 235; }}
      return cp;
    }});
    const vMap = {{}};
    vNodes.forEach(function(n) {{ vMap[n.id] = n; }});
    const vLinks = [];
    (graph.links || []).forEach(function(l) {{
      const s = typeof l.source === 'object' ? l.source.id : l.source;
      const t = typeof l.target === 'object' ? l.target.id : l.target;
      if (vMap[s] && vMap[t]) vLinks.push({{ source: s, target: t, kind: l.kind }});
    }});
    if (d3Sim) d3Sim.stop();
    const svg = d3.select(svgEl).attr('viewBox', '0 0 780 470');
    svg.selectAll('*').remove();
    const g = svg.append('g');
    const zoom = d3.zoom().scaleExtent([0.35, 4.0]).on('zoom', function(ev) {{ g.attr('transform', ev.transform); }});
    svg.call(zoom);
    root._resetZoom = function() {{ svg.transition().duration(220).call(zoom.transform, d3.zoomIdentity); }};

    const linkSel = g.append('g').selectAll('line').data(vLinks).join('line')
      .attr('stroke', function(d) {{ return d.kind === 'js_link' ? 'rgba(245,158,11,0.6)' : (d.kind === 'dom_branch' ? 'rgba(129,140,248,0.45)' : 'rgba(52,211,153,0.3)'); }})
      .attr('stroke-width', function(d) {{ return d.kind === 'dom_branch' ? 1.6 : 1.0; }});

    const nodeSel = g.append('g').selectAll('circle').data(vNodes).join('circle')
      .attr('r', radiusFor)
      .attr('fill', colorFor)
      .attr('stroke', function(d) {{ return d.cluster === activeCluster && activeCluster ? '#ffffff' : '#090d12'; }})
      .attr('stroke-width', function(d) {{ return d.cluster === activeCluster && activeCluster ? 2.2 : 1.2; }})
      .style('cursor', 'pointer')
      .on('mouseenter', function(ev, d) {{
        const modeTag = d.group === 'link' ? (d.js_only ? '⚡ JS-Only Hydrated Link' : (d.internal ? '🟢 Wire HTML Internal' : '🔵 Wire HTML External')) : (d.group === 'cluster' ? ('DOM Container · ' + d.count + ' links') : 'Crawled Origin URL');
        tipEl.innerHTML = '<strong>' + esc(d.label) + '</strong><br><span style="color:#79c0ff;">' + esc(d.url) + '</span><br><span style="color:#c9d1d9;">' + esc(d.cluster) + ' · ' + modeTag + '</span>';
        tipEl.hidden = false;
      }})
      .on('mousemove', function(ev) {{
        const b = svgEl.getBoundingClientRect();
        tipEl.style.left = Math.min(Math.max(8, ev.clientX - b.left + 12), Math.max(20, b.width - 260)) + 'px';
        tipEl.style.top = Math.max(8, ev.clientY - b.top - 10) + 'px';
      }})
      .on('mouseleave', function() {{ tipEl.hidden = true; }})
      .on('click', function(ev, d) {{
        if (d.group === 'cluster') {{
          activeCluster = activeCluster === d.cluster ? '' : d.cluster;
          renderD3();
        }} else if (d.url) {{
          window.open(d.url, '_blank', 'noopener');
        }}
      }});

    const lblSel = g.append('g').selectAll('text').data(vNodes.filter(function(d) {{ return d.group !== 'link'; }})).join('text')
      .text(function(d) {{ return d.label; }})
      .attr('font-size', function(d) {{ return d.group === 'origin' ? '11px' : '9.5px'; }})
      .attr('font-weight', '600')
      .attr('fill', function(d) {{ return d.group === 'origin' ? '#ffffff' : '#e0e7ff'; }})
      .attr('text-anchor', 'middle')
      .attr('dy', function(d) {{ return -(radiusFor(d) + 5); }})
      .style('pointer-events', 'none')
      .style('paint-order', 'stroke')
      .attr('stroke', '#090d12')
      .attr('stroke-width', 3);

    d3Sim = d3.forceSimulation(vNodes)
      .alpha(0.55)
      .alphaDecay(0.06)
      .force('link', d3.forceLink(vLinks).id(function(d) {{ return d.id; }}).distance(function(l) {{ return l.kind === 'dom_branch' ? 96 : 68; }}).strength(0.75))
      .force('charge', d3.forceManyBody().strength(function(d) {{ return d.group === 'link' ? -26 : -180; }}))
      .force('radial', d3.forceRadial(function(d) {{ return d.depth === 0 ? 0 : (d.depth === 1 ? 112 : 208); }}, 390, 235).strength(0.65))
      .force('collide', d3.forceCollide().radius(function(d) {{ return radiusFor(d) + (d.group === 'link' ? 2.5 : 10); }}))
      .on('tick', function() {{
        linkSel.attr('x1', function(d) {{ return d.source.x; }}).attr('y1', function(d) {{ return d.source.y; }}).attr('x2', function(d) {{ return d.target.x; }}).attr('y2', function(d) {{ return d.target.y; }});
        nodeSel.attr('cx', function(d) {{ return d.x; }}).attr('cy', function(d) {{ return d.y; }});
        lblSel.attr('x', function(d) {{ return d.x; }}).attr('y', function(d) {{ return d.y; }});
      }});
    renderInspector(keep);
  }}

  renderStaticFallback();
  root.addEventListener('click', function(ev) {{
    const fBtn = ev.target.closest('[data-rg-filter]');
    if (fBtn) {{
      filterMode = fBtn.getAttribute('data-rg-filter') || 'all';
      root.querySelectorAll('[data-rg-filter]').forEach(function(b) {{
        b.style.borderColor = b === fBtn ? '#22d3ee' : 'rgba(255,255,255,0.18)';
        b.style.color = b === fBtn ? '#ffffff' : '#c9d1d9';
      }});
      renderD3();
      return;
    }}
    const cBtn = ev.target.closest('[data-cluster]');
    if (cBtn) {{
      const picked = cBtn.getAttribute('data-cluster') || '';
      activeCluster = (picked && activeCluster === picked) ? '' : picked;
      renderD3();
      return;
    }}
    const rst = ev.target.closest('[data-rg-reset]');
    if (rst) {{
      activeCluster = '';
      filterMode = 'all';
      query = '';
      if (searchEl) searchEl.value = '';
      renderD3();
      if (root._resetZoom) root._resetZoom();
    }}
  }});
  if (searchEl) {{
    searchEl.addEventListener('input', function() {{
      query = searchEl.value.trim();
      renderD3();
    }});
  }}
  if (window.d3) {{
    renderD3();
  }} else {{
    const s = document.createElement('script');
    s.src = '/optics/d3.v7.min.js';
    s.onload = renderD3;
    s.onerror = function() {{
      const s2 = document.createElement('script');
      s2.src = {json.dumps(d3_fallback)};
      s2.onload = renderD3;
      document.head.appendChild(s2);
    }};
    document.head.appendChild(s);
  }}
}})();
"""


def render_standalone_dom_graph_html(graph_data: dict) -> str:
    """Render a self-contained dark-mode HTML radial DOM link-graph for optics_deed.zip."""
    target = html_lib.escape(str(graph_data.get("target_url") or ""))
    st = graph_data.get("stats") or {}
    safe_json = json.dumps(graph_data).replace("</", "<\\/")
    js_code = _radial_graph_client_js("standalone-rg-root", "standalone-rg-data")
    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        f"<title>911 LLM Optics — Radial DOM Link-Graph ({target})</title>"
        "<style>body{margin:0;padding:1.2rem;background:#090d12;color:#e6edf3;font-family:system-ui,sans-serif;}"
        ".card{max-width:1120px;margin:0 auto;border:1px solid rgba(34,211,238,0.38);border-radius:10px;background:#0d1117;overflow:hidden;}"
        ".bar{display:flex;flex-wrap:wrap;gap:0.45rem;align-items:center;padding:0.65rem 0.9rem;background:#161b22;border-bottom:1px solid rgba(255,255,255,0.1);}"
        ".btn{padding:0.28rem 0.6rem;border-radius:6px;border:1px solid rgba(255,255,255,0.18);background:rgba(255,255,255,0.05);color:#c9d1d9;font-size:0.75rem;cursor:pointer;}"
        "</style></head><body>"
        "<div class='card' id='standalone-rg-root'>"
        "<div class='bar'>"
        f"<strong style='color:#fff;font-size:0.86rem;'>🕸️ 911 LLM Optics Radial DOM Link-Graph: {target}</strong>"
        "<input type='search' class='optics-rg-search' placeholder='Filter DOM landmarks or URLs...' style='flex:1 1 180px;padding:0.32rem 0.6rem;border-radius:6px;border:1px solid #30363d;background:#06090d;color:#f0f6fc;font-size:0.78rem;'>"
        "<button type='button' class='btn' data-rg-filter='all' style='border-color:#22d3ee;color:#fff;'>All (" + str(st.get("unique_links", 0)) + ")</button>"
        "<button type='button' class='btn' data-rg-filter='js'>⚡ JS-Only (" + str(st.get("js_only_links", 0)) + ")</button>"
        "<button type='button' class='btn' data-rg-filter='internal'>🟢 Internal (" + str(st.get("internal_links", 0)) + ")</button>"
        "<button type='button' class='btn' data-rg-filter='external'>🔵 External (" + str(st.get("external_links", 0)) + ")</button>"
        "<button type='button' class='btn' data-rg-reset='1'>⌖ Reset</button>"
        "</div>"
        "<div style='position:relative;height:470px;background:radial-gradient(circle at center,#101926 0%,#070a0f 78%);'>"
        "<svg class='optics-rg-svg' style='width:100%;height:100%;display:block;'></svg>"
        "<div class='optics-rg-tip' hidden style='position:absolute;pointer-events:none;max-width:320px;padding:0.4rem 0.6rem;border-radius:6px;background:rgba(9,13,18,0.95);border:1px solid #22d3ee;color:#f0f6fc;font-size:0.74rem;z-index:10;'></div>"
        "</div>"
        "<div style='padding:0.4rem 0.9rem;font-size:0.73rem;color:#8b949e;border-top:1px solid rgba(255,255,255,0.08);background:#090d12;'>"
        "⚪ Crawled URL · 🟣 Parent DOM Landmark / &lt;div&gt; · 🟢 Wire HTML Internal · 🔵 Wire HTML External · 🟠 JS-Only Hydrated Link (invisible to non-JS crawlers)"
        "</div>"
        "<div class='optics-rg-insp' style='padding:0.75rem 0.9rem;border-top:1px solid rgba(255,255,255,0.1);background:#0b1017;'></div>"
        f"<script type='application/json' id='standalone-rg-data'>{safe_json}</script>"
        f"<script>{js_code}</script>"
        "</div></body></html>\n"
    )

ROLES = ['Core', 'SEO']


class OpticsWorkflow:
    """
    911 LLM Optics Workflow: Zero-credential optical diffraction engine.
    Exposes RFC 9110 wire truth vs. hydrated DOM, structural diffs, and Link Lens
    in a verifiable 3-step FastHTML pipeline with sealed deed export.
    """
    APP_NAME = 'optics'
    DISPLAY_NAME = '911 LLM Optics 👁️'
    ENDPOINT_MESSAGE = 'Inspect DOM diffs, Link Lens, and RFC 9110 wire truth. Press Enter...'

    def __init__(self, app, pipulate, pipeline, db, app_name=APP_NAME):
        self.pipulate = pipulate
        self.app = app
        self.app_name = app_name
        self.wand = pipulate
        wand = self.wand

        self.pipeline = pipeline
        self.steps_indices = {}
        self.message_queue = self.wand.get_message_queue()
        self.ui = self.wand.get_ui_constants()

        self.steps = [
            Step(
                id='step_01',
                done='url',
                show='Target URL',
                refill=True
            ),
            Step(
                id='step_02',
                done='captured',
                show='Capture & SIFT',
                refill=False
            ),
            Step(
                id='step_03',
                done='inspected',
                show='Optical Analysis',
                refill=False
            ),
            Step(id='finalize', done='finalized', show='Finalize & Deed', refill=False)
        ]

        self.steps_indices = {step.id: i for i, step in enumerate(self.steps)}
        pipulate.register_workflow_routes(self)

        self.step_messages = {
            'finalize': {
                'ready': f'{self.ui["EMOJIS"]["SUCCESS"]} All steps complete. Ready to finalize and seal the optics deed.',
                'complete': f'{self.ui["EMOJIS"]["COMPLETION"]} Workflow finalized. Verified deed ready for export.'
            }
        }
        for step in self.steps:
            if step.id != 'finalize':
                self.step_messages[step.id] = {
                    'input': f'{self.ui["EMOJIS"]["INPUT_FORM"]} {self.wand.fmt(step.id)}: Please enter {step.show}.',
                    'complete': f'{self.ui["EMOJIS"]["SUCCESS"]} {step.show} complete. Proceed to next step.'
                }

        @self.app.get('/optics')
        async def redirect_optics_alias(request):
            from starlette.responses import RedirectResponse
            qs = f"?{request.url.query}" if request.url.query else ""
            return RedirectResponse(url=f'/optics_workflow{qs}', status_code=302)

        @self.app.get('/optics/d3.v7.min.js')
        async def serve_local_d3():
            for cand in (
                Path("assets/js/d3.v7.min.js"),
                Path.home() / "repos" / "trimnoir" / "assets" / "js" / "d3.v7.min.js",
            ):
                if cand.is_file():
                    return FileResponse(str(cand), media_type="application/javascript")
            return Response("// local d3 bundle not present; client falls back", status_code=404)

        # Dedicated route for downloading verified ZIP deed
        @self.app.get(f'/{self.app_name}/download/{{pipeline_id}}')
        async def download_deed(pipeline_id: str):
            state = self.wand.read_state(pipeline_id)
            out_dir_str = state.get('step_02', {}).get('captured', '')
            if not out_dir_str:
                return Response("Artifact directory not found", status_code=404)
            zip_path = Path(out_dir_str) / "optics_deed.zip"
            if zip_path.exists():
                return FileResponse(
                    str(zip_path),
                    filename=f"optics_deed_{pipeline_id}.zip",
                    media_type="application/zip"
                )
            return Response("Deed file not found", status_code=404)

    def _is_scripted_demo_run(self, pipeline_id: str) -> bool:
        """True when Ghost Driver (optics_test.json -> live-{{timestamp}}) owns narration for this run."""
        pid = str(pipeline_id or "")
        return pid.startswith("live-") or "-optics-live-" in pid

    def _speak_step_cue(self, pipeline_id: str, text: str) -> None:
        """Speak interactive workflow cue unless Ghost Driver's scripted narration is driving."""
        if not self._is_scripted_demo_run(pipeline_id):
            self.wand.speak(text, wait=False)

    def _ensure_dom_link_graph(self, out_dir: Path, target_url: str) -> dict:
        """Materialize dom_link_graph.json and dom_link_graph.html in out_dir."""
        if not out_dir or not out_dir.exists():
            return {}
        json_path = out_dir / "dom_link_graph.json"
        html_path = out_dir / "dom_link_graph.html"
        if json_path.is_file() and html_path.is_file():
            try:
                return json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        src_html = (out_dir / "source.html").read_text(encoding="utf-8", errors="replace") if (out_dir / "source.html").is_file() else ""
        hyd_html = (out_dir / "hydrated_dom.html").read_text(encoding="utf-8", errors="replace") if (out_dir / "hydrated_dom.html").is_file() else src_html
        graph_data = build_dom_link_graph(target_url, src_html, hyd_html)
        json_path.write_text(json.dumps(graph_data, indent=2), encoding="utf-8")
        html_path.write_text(render_standalone_dom_graph_html(graph_data), encoding="utf-8")
        return graph_data

    def _render_radial_dom_graph(self, graph_data: dict, scope_id: str):
        if not graph_data or not graph_data.get("nodes"):
            return P("No crawlable anchor links detected on page.", cls="text-muted")
        st = graph_data.get("stats") or {}
        mount_id = f"{scope_id}_rg_root"
        data_id = f"{scope_id}_rg_data"
        safe_json = json.dumps(graph_data).replace("</", "<\\/")
        btn_style = "padding:0.26rem 0.58rem;border-radius:6px;border:1px solid rgba(255,255,255,0.18);background:rgba(255,255,255,0.05);color:#c9d1d9;font-size:0.74rem;font-weight:600;cursor:pointer;margin:0;"
        return Div(
            Div(
                Strong("🕸️ 1-Page Radial DOM Link-Graph", style="font-size:0.82rem;color:#ffffff;"),
                Input(
                    type="search",
                    placeholder="Filter DOM landmarks or link URLs...",
                    cls="optics-rg-search",
                    style="flex:1 1 180px;margin:0;padding:0.3rem 0.6rem;height:auto;border-radius:6px;border:1px solid rgba(88,166,255,0.35);background:#06090d;color:#f0f6fc;font-size:0.78rem;",
                ),
                Button(f"All ({st.get('unique_links', 0)})", type="button", data_rg_filter="all", style=btn_style + "border-color:#22d3ee;color:#ffffff;"),
                Button(f"⚡ JS-Only ({st.get('js_only_links', 0)})", type="button", data_rg_filter="js", style=btn_style),
                Button(f"🟢 Internal ({st.get('internal_links', 0)})", type="button", data_rg_filter="internal", style=btn_style),
                Button(f"🔵 External ({st.get('external_links', 0)})", type="button", data_rg_filter="external", style=btn_style),
                Button("⌖ Reset", type="button", data_rg_reset="1", style=btn_style),
                style="display:flex;flex-wrap:wrap;align-items:center;gap:0.45rem;padding:0.6rem 0.8rem;background:rgba(255,255,255,0.03);border-bottom:1px solid rgba(255,255,255,0.09);",
            ),
            Div(
                NotStr('<svg class="optics-rg-svg" style="width:100%;height:100%;display:block;cursor:grab;"></svg>'),
                Div(cls="optics-rg-tip", hidden=True, style="position:absolute;pointer-events:none;max-width:300px;padding:0.38rem 0.58rem;border-radius:6px;background:rgba(9,13,18,0.95);border:1px solid rgba(34,211,238,0.55);color:#f0f6fc;font-size:0.73rem;line-height:1.35;z-index:10;"),
                style="position:relative;width:100%;height:430px;background:radial-gradient(circle at center,#101926 0%,#070a0f 76%);",
            ),
            Div(
                "⚪ Origin URL · 🟣 Parent DOM Landmark / <div> (click to isolate) · 🟢 Wire HTML Internal · 🔵 Wire HTML External · 🟠 JS-Only Hydrated Link",
                style="padding:0.36rem 0.8rem;font-size:0.72rem;color:#8b949e;border-top:1px solid rgba(255,255,255,0.07);background:rgba(0,0,0,0.28);",
            ),
            Div(cls="optics-rg-insp", style="padding:0.65rem 0.8rem;border-top:1px solid rgba(255,255,255,0.1);background:#0b1017;"),
            Script(NotStr(safe_json), type="application/json", id=data_id),
            Script(NotStr(_radial_graph_client_js(mount_id, data_id))),
            id=mount_id,
            style="margin-bottom:1rem;border:1px solid rgba(34,211,238,0.35);border-radius:10px;background:#090d12;color:#e6edf3;overflow:hidden;",
        )

    async def landing(self, request):
        return self.wand.create_standard_landing_page(self)

    async def init(self, request):
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        form = await request.form()
        user_input = form.get('pipeline_id', '').strip()
        if not user_input:
            response = Response('')
            response.headers['HX-Refresh'] = 'true'
            return response

        context = wand.get_plugin_context(self)
        profile_name = context.get('profile_name') or 'default'
        profile_part = profile_name.replace(' ', '_')
        plugin_part = app_name.replace(' ', '_')
        expected_prefix = f'{profile_part}-{plugin_part}-'
        if user_input.startswith(expected_prefix):
            pipeline_id = user_input
        else:
            _, prefix, user_provided_id = wand.generate_pipeline_key(self, user_input)
            pipeline_id = f'{prefix}{user_provided_id}'

        wand.db['pipeline_id'] = pipeline_id
        state, error = wand.initialize_if_missing(pipeline_id, {'app_name': app_name})
        if error:
            return error

        all_steps_complete = all((step.id in state and step.done in state[step.id] for step in steps[:-1]))
        is_finalized = 'finalize' in state and 'finalized' in state['finalize']

        await self.message_queue.add(wand, f'{self.ui["EMOJIS"]["WORKFLOW"]} Optics Run ID: {pipeline_id}', verbatim=True, spaces_before=0)
        await self.message_queue.add(wand, f"{self.ui['EMOJIS']['KEY']} Access this audit anytime using '{pipeline_id}'.", verbatim=True, spaces_before=0)

        if all_steps_complete:
            if is_finalized:
                status_msg = f'{self.ui["EMOJIS"]["LOCKED"]} Optics audit is complete and finalized. Download deed below.'
            else:
                status_msg = f'{self.ui["EMOJIS"]["SUCCESS"]} Optics analysis ready. Finalize to seal the deed.'
            await self.message_queue.add(wand, status_msg, verbatim=True)
            self.wand.speak("Optics audit recovered.", wait=False)
        elif not any((step.id in state for step in self.steps)):
            await self.message_queue.add(wand, f'{self.ui["EMOJIS"]["INPUT_FORM"]} Step 1: Provide target URL to begin optical diffraction.', verbatim=True)
            self._speak_step_cue(pipeline_id, "Optics workflow initialized. Enter target URL to begin.")

        parsed = wand.parse_pipeline_key(pipeline_id)
        prefix = f"{parsed['profile_part']}-{parsed['plugin_part']}-"
        self.pipeline.xtra(app_name=app_name)
        matching_records = [record.pkey for record in self.pipeline() if record.pkey.startswith(prefix)]
        if pipeline_id not in matching_records:
            matching_records.append(pipeline_id)
        wand.update_datalist('pipeline-ids', options=matching_records)
        return wand.run_all_cells(app_name, steps)

    async def finalize(self, request):
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        finalize_step = steps[-1]
        finalize_data = wand.get_step_data(pipeline_id, finalize_step.id, {})

        if request.method == 'GET':
            if finalize_step.done in finalize_data:
                state = wand.read_state(pipeline_id)
                out_dir_str = state.get('step_02', {}).get('captured', '')
                zip_path = Path(out_dir_str) / "optics_deed.zip" if out_dir_str else None
                hash_str = "Unknown"
                if zip_path and zip_path.exists():
                    hash_str = hashlib.sha256(zip_path.read_bytes()).hexdigest()[:16]

                target_url_Done = state.get('step_01', {}).get('url', 'https://example.com/')
                mail_subj = quote(f"911 LLM Optics AI-Readiness Audit: {target_url_Done}")
                mail_body = quote(
                    f"Attached is the 911 LLM Optics single-page AI-readiness deed (optics_deed_{pipeline_id}.zip) for {target_url_Done}.\n\n"
                    f"- Sealed SHA-256 Digest (first 16): {hash_str}\n"
                    f"- Inspect audit_report.md, rfc9110_probe.json, and the Monokai DOM diff lenses inside the ZIP.\n"
                    f"- Run your own audit locally: curl -fsSL https://sunpug.io | less\n"
                )
                return Article(
                    H3(f'{self.ui["EMOJIS"]["LOCKED"]} Optical Deed Sealed'),
                    P(f"SHA-256 Digest: {hash_str}", cls='text-muted'),
                    Div(
                        A("📥 Download Verified Optics Deed (ZIP)", href=f'/{app_name}/download/{pipeline_id}', cls=self.ui['BUTTON_STYLES']['PRIMARY'], role='button', id='optics-download-deed-btn', style='margin-right: 0.75rem;'),
                        A("📧 Email / Share Audit Deed", href=f"mailto:?subject={mail_subj}&body={mail_body}", cls=self.ui['BUTTON_STYLES']['OUTLINE'], role='button', id='optics-email-deed-btn'),
                        style='margin-bottom: 1rem;'
                    ),
                    Form(
                        Button(self.ui['BUTTON_LABELS']['UNLOCK'], type='submit', cls=self.ui['BUTTON_STYLES']['OUTLINE'], id='optics-unlock-btn'),
                        hx_post=f'/{app_name}/unfinalize',
                        hx_target=f'#{app_name}-container',
                        hx_swap='outerHTML',
                        id='optics-unlock-form'
                    ),
                    id=finalize_step.id,
                    role='region'
                )
            else:
                all_steps_complete = all((wand.get_step_data(pipeline_id, step.id, {}).get(step.done) for step in steps[:-1]))
                if all_steps_complete:
                    return Article(
                        H3(f'{self.ui["EMOJIS"]["SUCCESS"]} Optical Analysis Complete. Seal Deed?'),
                        P("Finalizing will compile the ZIP deed, stamp the cryptographic hash, and lock the run.", cls='text-muted'),
                        Form(
                            Button(self.ui['BUTTON_LABELS']['FINALIZE'], type='submit', cls=self.ui['BUTTON_STYLES']['PRIMARY'], id='optics-finalize-btn'),
                            hx_post=f'/{app_name}/finalize',
                            hx_target=f'#{app_name}-container',
                            hx_swap='outerHTML',
                            id='optics-finalize-form'
                        ),
                        id=finalize_step.id,
                        role='region'
                    )
                else:
                    return Div(id=finalize_step.id)
        else:
            # POST: Finalize workflow, build sealed ZIP
            state = wand.read_state(pipeline_id)
            out_dir_str = state.get('step_02', {}).get('captured', '')
            if out_dir_str and os.path.isdir(out_dir_str):
                out_dir = Path(out_dir_str)
                zip_path = out_dir / "optics_deed.zip"
                self._ensure_dom_link_graph(out_dir, state.get('step_01', {}).get('url', ''))
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for fname in [
                        "audit_report.md", "rfc9110_probe.json", "origin_markdown.md",
                        "dom_link_graph.json", "dom_link_graph.html",
                        "headers.json", "source.html", "hydrated_dom.html",
                        "diff_simple_dom.txt", "diff_simple_dom.html",
                        "diff_hierarchy.txt", "diff_hierarchy.html",
                        "diff_boxes.txt", "diff_boxes.html",
                        "source_dom_hierarchy.txt", "source_dom_hierarchy.html",
                        "hydrated_dom_hierarchy.txt", "hydrated_dom_hierarchy.html",
                        "source_dom_layout_boxes.txt", "source_dom_layout_boxes.html",
                        "hydrated_dom_layout_boxes.txt", "hydrated_dom_layout_boxes.html",
                        "links.md", "seo.md"
                    ]:
                        fpath = out_dir / fname
                        if fpath.exists():
                            zf.write(fpath, arcname=fname)

            await wand.finalize_workflow(pipeline_id)
            await self.message_queue.add(wand, self.step_messages['finalize']['complete'], verbatim=True)
            self._speak_step_cue(pipeline_id, "The optics deed is now locked and sealed.")
            return wand.run_all_cells(app_name, steps)

    async def unfinalize(self, request):
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        await wand.unfinalize_workflow(pipeline_id)
        await self.message_queue.add(wand, f'{self.ui["EMOJIS"]["UNLOCKED"]} Workflow unfinalized.', verbatim=True)
        self.wand.speak("Workflow unlocked.", wait=False)
        return wand.run_all_cells(app_name, steps)

    async def handle_revert(self, request):
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        form = await request.form()
        step_id = form.get('step_id')
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        if not step_id:
            return P('Error: No step specified', cls='text-invalid')
        await wand.clear_steps_from(pipeline_id, step_id, steps)
        state = wand.read_state(pipeline_id)
        state['_revert_target'] = step_id
        wand.write_state(pipeline_id, state)
        message = await wand.get_state_message(pipeline_id, steps, self.step_messages)
        await self.message_queue.add(wand, f'{self.ui["EMOJIS"]["WARNING"]} Reverted to {step_id}. {message}', verbatim=True)
        return wand.run_all_cells(app_name, steps)

    async def get_suggestion(self, step_id, state):
        return ''

    def _render_rich_html_lens(self, html_doc: str, fallback_text: str, scope_id: str):
        import re
        if not html_doc:
            return Pre(
                fallback_text,
                style='max-height: 340px; overflow-y: auto; overflow-x: auto; background: #111; color: #f8f8f2; padding: 0.75rem; border-radius: 4px; font-size: 0.75rem; line-height: 1.3;'
            )
        style_match = re.search(r'<style[^>]*>(.*?)</style>', html_doc, flags=re.DOTALL | re.IGNORECASE)
        pre_match = re.search(r'<pre[^>]*>.*?</pre>', html_doc, flags=re.DOTALL | re.IGNORECASE)
        if not pre_match:
            return Pre(
                fallback_text,
                style='max-height: 340px; overflow-y: auto; overflow-x: auto; background: #111; color: #f8f8f2; padding: 0.75rem; border-radius: 4px; font-size: 0.75rem; line-height: 1.3;'
            )
        pre_html = pre_match.group(0)
        style_css = ""
        if style_match:
            raw_css = style_match.group(1)
            rule_lines = [
                re.sub(r'\.r(\d+)\b', f'.{scope_id}_r\\1', ln.strip())
                for ln in raw_css.splitlines()
                if ln.strip().startswith('.r')
            ]
            if rule_lines:
                style_css = f"<style>{' '.join(rule_lines)}</style>"
            pre_html = re.sub(r'class="r(\d+)"', f'class="{scope_id}_r\\1"', pre_html)
        return Div(
            NotStr(style_css + pre_html),
            style='max-height: 360px; overflow-y: auto; overflow-x: auto; background: #111; color: #f8f8f2; padding: 0.75rem; border-radius: 4px; font-size: 0.75rem; line-height: 1.3; border: 1px solid #2a3140;'
        )

    def _render_colored_diff(self, diff_text: str):
        lines = []
        for raw_line in diff_text.splitlines():
            if raw_line.startswith('+++') or raw_line.startswith('---'):
                lines.append(Div(raw_line, style='color: #bd93f9; font-weight: bold; white-space: pre;'))
            elif raw_line.startswith('@@'):
                lines.append(Div(raw_line, style='color: #8be9fd; background: rgba(139, 233, 253, 0.08); white-space: pre;'))
            elif raw_line.startswith('+'):
                lines.append(Div(raw_line, style='color: #50fa7b; background: rgba(80, 250, 123, 0.12); white-space: pre;'))
            elif raw_line.startswith('-'):
                lines.append(Div(raw_line, style='color: #ff5555; background: rgba(255, 85, 85, 0.12); white-space: pre;'))
            else:
                lines.append(Div(raw_line or ' ', style='color: #f8f8f2; white-space: pre;'))
        return Pre(
            *lines,
            style='max-height: 280px; overflow-y: auto; overflow-x: auto; background: #111; padding: 0.75rem; border-radius: 4px; font-size: 0.78rem; line-height: 1.35;'
        )

    def _render_markdown_lens(self, md_text: str, widget_id: str):
        return Div(
            Pre(
                md_text,
                id=f'{widget_id}_source',
                style='display: none; white-space: pre-wrap;'
            ),
            Div(
                id=f'{widget_id}_rendered',
                cls='markdown-body',
                style='max-height: 320px; overflow-y: auto; background: #111; color: #f8f8f2; padding: 1rem; border-radius: 4px; font-size: 0.84rem; border: 1px solid #2a3140;'
            ),
            Details(
                Summary('View Raw Link Lens Markdown', style='font-size: 0.78rem; margin-top: 0.4rem; cursor: pointer; color: #8be9fd;'),
                Pre(
                    Code(md_text, cls='language-markdown'),
                    style='max-height: 200px; overflow-y: auto; font-size: 0.75rem; margin-top: 0.4rem;'
                )
            ),
            Script(f"""
                (function() {{
                    const src = document.getElementById('{widget_id}_source');
                    const out = document.getElementById('{widget_id}_rendered');
                    if (src && out) {{
                        const raw = src.textContent || '';
                        if (typeof marked !== 'undefined') {{
                            out.innerHTML = marked.parse(raw);
                        }} else {{
                            out.textContent = raw;
                        }}
                    }}
                    const stepEl = document.getElementById('step_03');
                    if (stepEl && typeof Prism !== 'undefined') {{
                        Prism.highlightAllUnder(stepEl);
                    }}
                }})();
            """),
            id=widget_id
        )

    # --- STEP 01: TARGET URL ---
    async def step_01(self, request):
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        user_val = step_data.get(step.done, '')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})

        if 'finalized' in finalize_data:
            return Div(
                Article(
                    H3(f'{self.ui["EMOJIS"]["LOCKED"]} {step.show}: {user_val}'),
                    role='region'
                ),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )
        elif user_val and state.get('_revert_target') != step_id:
            return Div(
                wand.display_revert_header(
                    step_id=step_id,
                    app_name=app_name,
                    message=f'{self.ui["EMOJIS"]["USER_INPUT"]} {step.show}: {user_val}',
                    steps=steps
                ),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )
        else:
            explanation = "Provide an HTTP/HTTPS URL to observe wire truth vs. hydrated DOM."
            return Div(
                Article(
                    H3(f'{self.ui["EMOJIS"]["USER_INPUT"]} {self.wand.fmt(step.id)}: Enter {step.show}'),
                    P(explanation, cls='text-muted'),
                    Label('Target URL:', _for='optics-step01-url-input'),
                    Form(
                        wand.wrap_with_inline_button(
                            Input(
                                type='url',
                                name=step.done,
                                value=user_val or 'https://mikelev.in/',
                                placeholder='https://example.com/',
                                required=True,
                                autofocus=True,
                                id='optics-step01-url-input',
                                aria_label='Target URL to inspect'
                            ),
                            button_label=self.ui['BUTTON_LABELS']['NEXT_STEP']
                        ),
                        hx_post=f'/{app_name}/{step_id}_submit',
                        hx_target=f'#{step_id}',
                        id='optics-step01-form'
                    ),
                    role='region'
                ),
                Div(id=next_step_id),
                id=step_id
            )

    async def step_01_submit(self, request):
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        step_id = 'step_01'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        pipeline_id = wand.db.get("pipeline_id", "unknown")

        form = await request.form()
        user_val = form.get(step.done, "").strip()
        if not user_val:
            error_msg = f'{self.ui["EMOJIS"]["ERROR"]} Please enter a valid URL'
            await self.message_queue.add(wand, error_msg, verbatim=True)
            return P(error_msg, cls='text-invalid')

        if not user_val.startswith(('http://', 'https://')):
            user_val = f'https://{user_val}'

        await wand.set_step_data(pipeline_id, step_id, user_val, steps)
        await self.message_queue.add(wand, f'{self.ui["EMOJIS"]["SUCCESS"]} Target set: {user_val}', verbatim=True)
        self._speak_step_cue(pipeline_id, "Target URL set. Ready for optical capture.")
        self.wand.append_to_history(f"[WIDGET CONTENT] {step.show}:\n{user_val}")
        return wand.chain_reverter(step_id, step_index, steps, app_name, user_val)

    # --- STEP 02: CAPTURE & SIFT ---
    async def step_02(self, request):
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        step_id = 'step_02'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        user_val = step_data.get(step.done, '')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})

        target_url = wand.get_step_data(pipeline_id, 'step_01', {}).get('url', '')

        if 'finalized' in finalize_data:
            return Div(
                Article(
                    H3(f'{self.ui["EMOJIS"]["LOCKED"]} {step.show}: Captured & SIFTed'),
                    role='region'
                ),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )
        elif user_val and state.get('_revert_target') != step_id:
            return Div(
                wand.display_revert_header(
                    step_id=step_id,
                    app_name=app_name,
                    message=f'{self.ui["EMOJIS"]["SUCCESS"]} {step.show}: Artifacts Extracted',
                    steps=steps
                ),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )
        else:
            return Div(
                Article(
                    H3(f'{self.ui["EMOJIS"]["WORKFLOW"]} {self.wand.fmt(step.id)}: {step.show}'),
                    P(f"Target: {target_url}", cls='text-muted'),
                    P("Engage undetected browser to drain CDP performance log, capture wire response vs. hydrated DOM, and run the SIFT comparator.", cls='text-muted'),
                    Form(
                        Label(
                            Input(
                                type='checkbox',
                                name='show_browser',
                                role='switch',
                                checked=bool(state.get('show_browser', False)),
                                id='optics-step02-show-browser'
                            ),
                            ' Pop visible browser window (headful mode; default is headless)',
                            _for='optics-step02-show-browser',
                            style='margin-bottom: 0.75rem; font-size: 0.88rem; display: block;'
                        ),
                        Button("Engage Optics SIFT 👁️", type='submit', cls=self.ui['BUTTON_STYLES']['PRIMARY'], id='optics-step02-btn'),
                        hx_post=f'/{app_name}/{step_id}_submit',
                        hx_target=f'#{step_id}',
                        onsubmit="const b=this.querySelector('button');if(b){b.setAttribute('aria-busy','true');b.textContent='Capturing Wire & DOM (SIFTing)...';}",
                        id='optics-step02-form'
                    ),
                    role='region'
                ),
                Div(id=next_step_id),
                id=step_id
            )

    async def step_02_submit(self, request):
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        step_id = 'step_02'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        pipeline_id = wand.db.get("pipeline_id", "unknown")

        target_url = wand.get_step_data(pipeline_id, 'step_01', {}).get('url', '')
        parsed = urlparse(target_url)
        domain = parsed.netloc or "unknown"
        slug = quote(parsed.path or "/", safe="").replace("/", "_")[:100] or "%2F"
        output_dir = Path("browser_cache") / domain / slug
        output_dir.mkdir(parents=True, exist_ok=True)

        form = await request.form()
        show_browser = bool(form.get('show_browser'))
        state = wand.read_state(pipeline_id)
        state['show_browser'] = show_browser
        wand.write_state(pipeline_id, state)
        params = {
            "url": target_url,
            "domain": domain,
            "url_path_slug": slug,
            "take_screenshot": False,
            "headless": not show_browser,
            "is_notebook_context": True,
            "verbose": False,
            "persistent": False,
            "override_cache": True,
        }

        try:
            res = await selenium_automation(params)
        except Exception as e:
            logger.warning(f"Selenium capture failed: {e}; attempting HTTP fallback")
            res = {"success": False}

        if res.get("success"):
            looking_at = res.get("looking_at_files") or {}
            sample_path = next((Path(v) for v in looking_at.values() if v), None)
            if sample_path and sample_path.parent.exists():
                output_dir = sample_path.parent
            if not (output_dir / "hydrated_dom_layout_boxes.txt").exists():
                await generate_optics_subprocess(str(output_dir))
        else:
            import urllib.request
            try:
                req = urllib.request.Request(
                    target_url,
                    headers={"User-Agent": "Mozilla/5.0 (Pipulate-Optics/1.0)", "Accept": "text/html,text/markdown;q=0.9"}
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    raw_html = resp.read().decode('utf-8', errors='replace')
                    headers_dict = {k.lower(): v for k, v in resp.headers.items()}
                (output_dir / "source.html").write_text(raw_html, encoding='utf-8')
                (output_dir / "hydrated_dom.html").write_text(raw_html, encoding='utf-8')
                (output_dir / "simple_source_html.html").write_text(raw_html, encoding='utf-8')
                (output_dir / "simple_hydrated_dom.html").write_text(raw_html, encoding='utf-8')
                (output_dir / "headers.json").write_text(json.dumps({
                    "url": target_url,
                    "final_url": target_url,
                    "source_provenance": "http_fallback",
                    "headers": headers_dict
                }, indent=2), encoding='utf-8')
                await generate_optics_subprocess(str(output_dir))
            except Exception as fb_err:
                error_msg = f'{self.ui["EMOJIS"]["ERROR"]} Capture failed: {fb_err}'
                await self.message_queue.add(wand, error_msg, verbatim=True)
                return P(error_msg, cls='text-invalid')

        # Active RFC 9110 Content Negotiation Probe (Accept: text/markdown)
        import urllib.request
        rfc9110_meta = {
            "url": target_url,
            "negotiated": False,
            "status": 0,
            "content_type": "",
            "vary": "",
            "bytes": 0,
        }
        try:
            md_req = urllib.request.Request(
                target_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; Pipulate-911-Optics/1.0; +https://pipulate.com)",
                    "Accept": "text/markdown",
                },
            )
            with urllib.request.urlopen(md_req, timeout=12) as md_resp:
                md_bytes_raw = md_resp.read()
                md_ctype = md_resp.headers.get("Content-Type", "")
                md_vary = md_resp.headers.get("Vary", "")
                is_md = "text/markdown" in md_ctype.lower()
                rfc9110_meta = {
                    "url": target_url,
                    "negotiated": is_md,
                    "status": getattr(md_resp, "status", 200),
                    "content_type": md_ctype,
                    "vary": md_vary,
                    "bytes": len(md_bytes_raw),
                }
                if is_md:
                    (output_dir / "origin_markdown.md").write_bytes(md_bytes_raw)
        except Exception as md_err:
            logger.debug(f"RFC 9110 markdown probe note for {target_url}: {md_err}")
        (output_dir / "rfc9110_probe.json").write_text(
            json.dumps(rfc9110_meta, indent=2), encoding="utf-8"
        )
        self._ensure_dom_link_graph(output_dir, target_url)
        stored_val = str(output_dir)
        await wand.set_step_data(pipeline_id, step_id, stored_val, steps)
        await self.message_queue.add(wand, f'{self.ui["EMOJIS"]["SUCCESS"]} Optics capture complete for {domain}', verbatim=True)
        self._speak_step_cue(pipeline_id, "Optics capture complete. Diff ready for inspection.")
        return wand.chain_reverter(step_id, step_index, steps, app_name, stored_val)

    # --- STEP 03: OPTICAL ANALYSIS ---
    async def step_03(self, request):
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        step_id = 'step_03'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else 'finalize'
        pipeline_id = wand.db.get('pipeline_id', 'unknown')
        state = wand.read_state(pipeline_id)
        step_data = wand.get_step_data(pipeline_id, step_id, {})
        user_val = step_data.get(step.done, '')
        finalize_data = wand.get_step_data(pipeline_id, 'finalize', {})

        out_dir_str = wand.get_step_data(pipeline_id, 'step_02', {}).get('captured', '')
        out_dir = Path(out_dir_str) if out_dir_str else None

        if 'finalized' in finalize_data:
            return Div(
                Article(
                    H3(f'{self.ui["EMOJIS"]["LOCKED"]} {step.show}: Inspection Verified'),
                    role='region'
                ),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )
        elif user_val and state.get('_revert_target') != step_id:
            return Div(
                wand.display_revert_header(
                    step_id=step_id,
                    app_name=app_name,
                    message=f'{self.ui["EMOJIS"]["SUCCESS"]} {step.show}: Verified',
                    steps=steps
                ),
                Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                id=step_id
            )
        else:
            # Read artifacts
            diff_text = "No diff artifact found."
            hier_diff_text = "No hierarchy diff found."
            hier_tree_text = "No DOM hierarchy tree found."
            hier_tree_html = ""
            boxes_text = "No layout boxes found."
            boxes_html = ""
            boxes_diff_text = "No layout boxes diff found."
            seo_md_text = "No agent markdown extracted."
            origin_md_text = "Origin did not serve text/markdown on RFC 9110 probe."
            links_text = "No link lens found."
            provenance = "unknown"
            rfc_headers_text = "No RFC 9110/9111 headers captured."
            src_bytes = 0
            hyd_bytes = 0
            hydration_only_links = "0 anchor(s)"
            has_vary_accept = False
            md_negotiated = False
            md_bytes = 0
            md_ctype = ""

            if out_dir and out_dir.exists():
                src_file = out_dir / "source.html"
                hyd_file = out_dir / "hydrated_dom.html"
                rfc_probe_file = out_dir / "rfc9110_probe.json"
                if rfc_probe_file.exists():
                    try:
                        p_data = json.loads(rfc_probe_file.read_text(encoding="utf-8"))
                        md_negotiated = bool(p_data.get("negotiated", False))
                        md_bytes = int(p_data.get("bytes", 0))
                        md_ctype = str(p_data.get("content_type", ""))
                        if "accept" in str(p_data.get("vary", "")).lower():
                            has_vary_accept = True
                    except Exception:
                        pass
                if src_file.exists():
                    src_bytes = src_file.stat().st_size
                if hyd_file.exists():
                    hyd_bytes = hyd_file.stat().st_size
                diff_path = out_dir / "diff_simple_dom.txt"
                if not diff_path.exists():
                    diff_path = out_dir / "diff_hierarchy.txt"
                if diff_path.exists():
                    diff_text = diff_path.read_text(encoding='utf-8')[:4000]

                hier_path = out_dir / "diff_hierarchy.txt"
                if hier_path.exists():
                    hier_diff_text = hier_path.read_text(encoding='utf-8')[:4000]
                tree_path = out_dir / "hydrated_dom_hierarchy.txt"
                if tree_path.exists():
                    hier_tree_text = tree_path.read_text(encoding='utf-8')[:6000]
                tree_html_path = out_dir / "hydrated_dom_hierarchy.html"
                if tree_html_path.exists():
                    hier_tree_html = tree_html_path.read_text(encoding='utf-8')

                boxes_path = out_dir / "hydrated_dom_layout_boxes.txt"
                if boxes_path.exists():
                    boxes_text = boxes_path.read_text(encoding='utf-8')[:6000]
                boxes_html_path = out_dir / "hydrated_dom_layout_boxes.html"
                if boxes_html_path.exists():
                    boxes_html = boxes_html_path.read_text(encoding='utf-8')
                boxes_diff_path = out_dir / "diff_boxes.txt"
                if boxes_diff_path.exists():
                    boxes_diff_text = boxes_diff_path.read_text(encoding='utf-8')[:4000]

                seo_path = out_dir / "seo.md"
                if seo_path.exists():
                    seo_md_text = seo_path.read_text(encoding='utf-8')[:3000]
                origin_md_path = out_dir / "origin_markdown.md"
                if origin_md_path.exists():
                    origin_md_text = origin_md_path.read_text(encoding='utf-8', errors='replace')[:4000]

                links_path = out_dir / "links.md"
                if links_path.exists():
                    full_links = links_path.read_text(encoding='utf-8')
                    links_text = full_links[:2500]
                    for ln in full_links.splitlines():
                        if "present only after hydration:" in ln:
                            hydration_only_links = ln.split("present only after hydration:", 1)[1].strip()
                            break

                headers_path = out_dir / "headers.json"
                if headers_path.exists():
                    try:
                        h_data = json.loads(headers_path.read_text(encoding='utf-8'))
                        provenance = h_data.get("source_provenance") or h_data.get("header_selection") or "wire"
                        hdr_source = h_data.get("headers") or h_data.get("response_headers") or {}
                        raw_hdrs = {str(k).lower(): v for k, v in hdr_source.items()}
                        has_vary_accept = "accept" in str(raw_hdrs.get("vary", "")).lower()
                        meta_lines = []
                        if "status" in h_data:
                            meta_lines.append(f"status: {h_data['status']}")
                        if "header_selection" in h_data:
                            meta_lines.append(f"header-selection: {h_data['header_selection']}")
                        rfc_keys = [
                            "content-type", "vary", "cache-control", "etag",
                            "age", "cache-status", "cf-cache-status", "link",
                            "content-signal", "server"
                        ]
                        found_hdrs = [f"{k}: {raw_hdrs[k]}" for k in rfc_keys if k in raw_hdrs]
                        if not found_hdrs and raw_hdrs:
                            found_hdrs = [f"{k}: {v}" for k, v in list(raw_hdrs.items())[:12]]
                        combined_hdrs = meta_lines + found_hdrs
                        if combined_hdrs:
                            rfc_headers_text = "\n".join(combined_hdrs)
                    except Exception:
                        pass

            vary_badge = "✅ RFC 9111 Vary: Accept" if has_vary_accept else "⚠️ No Vary: Accept"
            md_badge = f"✅ RFC 9110 Markdown: {md_bytes:,} B" if md_negotiated else "❌ RFC 9110 Markdown: Not Served"
            if out_dir and out_dir.exists():
                target_url_str = wand.get_step_data(pipeline_id, 'step_01', {}).get('url', 'unknown')
                report_lines = [
                    "# 911 LLM Optics: Single-Page AI-Readiness Audit Deed",
                    "",
                    f"- **Target URL**: `{target_url_str}`",
                    f"- **Wire Provenance**: `{provenance.upper()}`",
                    f"- **RFC 9110 (`Accept: text/markdown`)**: {md_badge} (`{md_ctype or 'n/a'}`)",
                    f"- **RFC 9111 (`Vary: Accept` Edge Partitioning)**: {vary_badge}",
                    f"- **Wire Source HTML**: `{src_bytes:,}` bytes",
                    f"- **Hydrated DOM HTML**: `{hyd_bytes:,}` bytes",
                    f"- **Links Visible Only After JS Hydration**: `{hydration_only_links}`",
                    "",
                    "## Selected Wire Headers",
                    "```yaml",
                    rfc_headers_text,
                    "```",
                ]
                dom_graph_data = self._ensure_dom_link_graph(out_dir, target_url_str)
                g_stats = dom_graph_data.get("stats") or {}
                if dom_graph_data.get("clusters"):
                    report_lines.extend([
                        "",
                        "## Radial DOM Link-Graph Summary (`dom_link_graph.html`)",
                        f"- **DOM Landmark / `<div>` Clusters**: `{g_stats.get('cluster_count', 0)}`",
                        f"- **Unique Page Links**: `{g_stats.get('unique_links', 0)}` (`{g_stats.get('wire_links', 0)}` in raw wire HTML, `{g_stats.get('js_only_links', 0)}` JS-only)",
                        "",
                        "| DOM Container | Total Links | Wire HTML | JS-Only |",
                        "| :--- | ---: | ---: | ---: |",
                    ])
                    for c_row in dom_graph_data["clusters"]:
                        report_lines.append(
                            f"| `{c_row['name']}` | {c_row['total']} | {c_row['wire']} | {c_row['js_only']} |"
                        )
                (out_dir / "audit_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
            else:
                dom_graph_data = {}
            accordion_css = Style("""
                #step_03 details > summary {
                    list-style: none;
                    padding: 0.35rem 0.6rem;
                    background: #161b22;
                    border: 1px solid #30363d;
                    border-radius: 5px;
                    user-select: none;
                    transition: background 0.15s ease;
                }
                #step_03 details > summary:hover {
                    background: #1f2937;
                }
                #step_03 details > summary::-webkit-details-marker {
                    display: none;
                }
                #step_03 details > summary::before {
                    content: "▸ ";
                    display: inline-block;
                    width: 1.15rem;
                    font-weight: bold;
                }
                #step_03 details[open] > summary::before {
                    content: "▾ ";
                }
            """)
            return Div(
                accordion_css,
                Article(
                    H3(f'{self.ui["EMOJIS"]["GREETING"]} {self.wand.fmt(step.id)}: {step.show}'),
                    P(f"Wire Truth Provenance: {provenance.upper()}", cls='text-muted'),
                    Div(
                        Strong("📊 Executive AI-Readiness Verdict: "),
                        Span(f"Wire HTML: {src_bytes:,} B vs. Hydrated DOM: {hyd_bytes:,} B | "),
                        Span(f"{md_badge} | "),
                        Span(f"JS-Only Links: {hydration_only_links} | "),
                        Span(vary_badge),
                        id='optics-executive-verdict',
                        style='background: #161b22; color: #f0f6fc; border: 1px solid #30363d; border-left: 4px solid #50fa7b; padding: 0.75rem 1rem; border-radius: 6px; margin-bottom: 1rem; font-size: 0.85rem;'
                    ),
                    H4("1. RFC 9110 / 9111 Wire Headers (Semantics & Caching)"),
                    Pre(
                        Code(rfc_headers_text, cls='language-yaml'),
                        cls='language-yaml',
                        style='max-height: 180px; overflow-y: auto; border-radius: 4px; font-size: 0.78rem;'
                    ),
                    H4("2. DOM Structural Diff (Source vs. Hydrated)"),
                    self._render_colored_diff(diff_text),
                    H4("3. Radial DOM Link-Graph & Anchor Accounting"),
                    self._render_radial_dom_graph(dom_graph_data, f"optics_rg_{pipeline_id.replace('-', '_')}"),
                    self._render_markdown_lens(links_text, f"optics-links-{pipeline_id.replace('-', '_')}"),
                    H4("4. Colorized DOM Hierarchy Tree & ASCII Layout Boxes"),
                    Details(
                        Summary("View Hydrated DOM Hierarchy Tree (🌐 Document Root — Monokai Color)", id='optics-tree-summary', style='font-size: 0.84rem; cursor: pointer; color: #f1fa8c; margin-bottom: 0.4rem;'),
                        self._render_rich_html_lens(hier_tree_html, hier_tree_text, "optics_tree"),
                        id='optics-tree-details'
                    ),
                    Details(
                        Summary("View Hydrated ASCII Layout Boxes (Monokai Color)", id='optics-boxes-summary', style='font-size: 0.84rem; cursor: pointer; color: #50fa7b; margin-top: 0.4rem; margin-bottom: 0.4rem;'),
                        self._render_rich_html_lens(boxes_html, boxes_text, "optics_boxes"),
                        id='optics-boxes-details'
                    ),
                    Details(
                        Summary("View Hierarchy Diff (Source vs. Hydrated Tree)", id='optics-hier-summary', style='font-size: 0.84rem; cursor: pointer; color: #8be9fd; margin-top: 0.4rem; margin-bottom: 0.4rem;'),
                        self._render_colored_diff(hier_diff_text),
                        id='optics-hier-details'
                    ),
                    Details(
                        Summary("View ASCII Layout Boxes Diff (Source vs. Hydrated Boxes)", id='optics-boxes-diff-summary', style='font-size: 0.84rem; cursor: pointer; color: #ffb86c; margin-top: 0.4rem; margin-bottom: 0.4rem;'),
                        self._render_colored_diff(boxes_diff_text),
                        id='optics-boxes-diff-details'
                    ),
                    H4("5. RFC 9110 Origin Markdown vs. Distilled DOM Markdown"),
                    Details(
                        Summary("View RFC 9110 Negotiated Origin Markdown (origin_markdown.md)", id='optics-origin-md-summary', style='font-size: 0.84rem; cursor: pointer; color: #50fa7b; margin-bottom: 0.4rem;'),
                        self._render_markdown_lens(origin_md_text, f"optics-origin-md-{pipeline_id.replace('-', '_')}"),
                        id='optics-origin-md-details'
                    ),
                    Details(
                        Summary("View Distilled DOM Markdown Payload (seo.md)", id='optics-seo-summary', style='font-size: 0.84rem; cursor: pointer; color: #bd93f9; margin-top: 0.4rem; margin-bottom: 0.4rem;'),
                        self._render_markdown_lens(seo_md_text, f"optics-seo-{pipeline_id.replace('-', '_')}"),
                        id='optics-seo-details'
                    ),
                    Form(
                        Button("Accept Optical Findings & Seal ▸", type='submit', cls=self.ui['BUTTON_STYLES']['PRIMARY'], id='optics-step03-accept-btn'),
                        hx_post=f'/{app_name}/{step_id}_submit',
                        hx_target=f'#{step_id}',
                        style='margin-top: 1rem;',
                        id='optics-step03-form'
                    ),
                    role='region'
                ),
                Div(id=next_step_id),
                id=step_id
            )

    async def step_03_submit(self, request):
        wand, steps, app_name = (self.wand, self.steps, self.app_name)
        step_id = 'step_03'
        step_index = self.steps_indices[step_id]
        step = steps[step_index]
        pipeline_id = wand.db.get("pipeline_id", "unknown")

        stored_val = "verified"
        await wand.set_step_data(pipeline_id, step_id, stored_val, steps)
        await self.message_queue.add(wand, f'{self.ui["EMOJIS"]["SUCCESS"]} Optical analysis verified.', verbatim=True)
        self._speak_step_cue(pipeline_id, "Optical analysis accepted. Ready to seal deed.")
        return wand.chain_reverter(step_id, step_index, steps, app_name, stored_val)
