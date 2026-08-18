"""Drawings for the notebook.

Presentation scaffolding, not part of the system. Pure SVG built as strings, so
there is no plotting dependency and the pictures survive in the saved notebook
for anyone reading it without running it.

Three things are worth seeing rather than reading about:

    bitemporal_svg   two clocks per fact -- when it was true in her life, and
                     when the archive believed it. The second one is invisible
                     in any ordinary timeline, and it is the whole reason a
                     later telling can retire an earlier one without deleting it.
    graph_svg        the semantic subgraph, coloured by community. Communities
                     are hard to argue about in prose and obvious in a picture.
    search_svg       which facts a query reached, and whether it got there by
                     matching words or by walking edges.
"""

from __future__ import annotations

import math
from html import escape

# Reuses the app's palette so the notebook and the product look related.
INK = "#241E1A"
SOFT = "#4A403B"
FAINT = "#8A7F76"
RED = "#9C3B24"
GREEN = "#2F5D50"
PAPER = "#EDE4D6"
CARD = "#FFFCF5"
LINE = "#EADFCC"

COMMUNITY_COLOURS = ["#9C3B24", "#2F5D50", "#7A5C2E", "#4A5C7A", "#6B3A5C"]


def _text(
    x: float,
    y: float,
    s: str,
    size: float = 12,
    fill: str = INK,
    anchor: str = "start",
    weight: str = "normal",
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="Georgia, serif" '
        f'font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
        f'font-weight="{weight}">{escape(s)}</text>'
    )


def bitemporal_svg(facts, width: int = 820) -> str:
    """Valid time as bars; transaction time as whether the bar is still asserted.

    A fact she has since retold is drawn hollow and struck through: still in the
    archive, no longer what it shows. That distinction is the point of holding
    two clocks and cannot be seen on a single timeline.
    """
    dated = [f for f in facts if f.year_span[0] or f.year_span[1]]
    if not dated:
        return "<p>No fact has a year yet.</p>"

    years = [y for f in dated for y in f.year_span if y]
    lo, hi = min(years), max(years)
    span = max(hi - lo, 1)

    left, right = 250, width - 40
    row_h, top = 26, 54
    height = top + row_h * len(dated) + 46

    def x_of(year: int) -> float:
        return left + (year - lo) / span * (right - left)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="{PAPER}"/>',
        _text(
            20,
            26,
            "Valid time — when each fact was true in her life",
            14,
            INK,
            weight="bold",
        ),
    ]

    # Decade gridlines, so the bars sit on something.
    decade = (lo // 10) * 10
    while decade <= hi:
        if decade >= lo:
            x = x_of(decade)
            out.append(
                f'<line x1="{x:.1f}" y1="{top - 10}" x2="{x:.1f}" '
                f'y2="{height - 34}" stroke="{LINE}" stroke-width="1"/>'
            )
            out.append(_text(x, height - 18, str(decade), 11, FAINT, "middle"))
        decade += 10

    for i, fact in enumerate(dated):
        y = top + i * row_h
        start, end = fact.year_span
        x1 = x_of(start or end)
        x2 = x_of(end or start)
        if x2 - x1 < 6:
            x2 = x1 + 6

        label = fact.statement
        out.append(_text(240, y + 12, label[:44], 11.5, SOFT, "end"))

        if fact.is_current:
            out.append(
                f'<rect x="{x1:.1f}" y="{y + 2}" width="{x2 - x1:.1f}" '
                f'height="14" rx="4" fill="{RED}" opacity="0.85"/>'
            )
        else:
            # Superseded: kept, drawn hollow, struck through.
            out.append(
                f'<rect x="{x1:.1f}" y="{y + 2}" width="{x2 - x1:.1f}" '
                f'height="14" rx="4" fill="none" stroke="{FAINT}" '
                f'stroke-width="1.5" stroke-dasharray="3 2"/>'
            )
            out.append(
                f'<line x1="{x1:.1f}" y1="{y + 9}" x2="{x2:.1f}" y2="{y + 9}" '
                f'stroke="{FAINT}" stroke-width="1"/>'
            )

    out.append(
        _text(
            20,
            height - 6,
            "solid = currently asserted   ·   hollow = she has since "
            "told it differently, kept but no longer shown",
            11,
            FAINT,
        )
    )
    out.append("</svg>")
    return "".join(out)


def graph_svg(
    entities, facts, groups=None, hub=None, width: int = 820, height: int = 470
) -> str:
    """The semantic subgraph: entity nodes, fact edges, coloured by community.

    Communities are laid out as clusters rather than found by a force
    simulation, because the point is to show the grouping the algorithm
    produced, not to re-derive it visually.
    """
    name = {e.entity_id: e.canonical_name for e in entities}
    groups = groups or []
    hub = hub or set()

    placed: dict[str, tuple[float, float]] = {}
    colour: dict[str, str] = {}

    clusters = [list(g) for g in groups] or [[e.entity_id for e in entities]]
    loose = [
        e.entity_id
        for e in entities
        if not any(e.entity_id in g for g in clusters) and e.entity_id not in hub
    ]

    cx, cy = width / 2, height / 2 + 8
    ring = min(width, height) * 0.31

    for gi, members in enumerate(clusters):
        angle = 2 * math.pi * gi / max(len(clusters), 1) - math.pi / 2
        gx = cx + ring * math.cos(angle)
        gy = cy + ring * math.sin(angle) * 0.78
        tone = COMMUNITY_COLOURS[gi % len(COMMUNITY_COLOURS)]
        spread = 26 + 7 * len(members)
        for mi, node in enumerate(members):
            a = 2 * math.pi * mi / max(len(members), 1)
            placed[node] = (gx + spread * math.cos(a), gy + spread * math.sin(a) * 0.72)
            colour[node] = tone

    for i, node in enumerate(loose):
        placed[node] = (60 + 66 * (i % 10), height - 34)
        colour[node] = FAINT

    for node in hub:
        placed[node] = (cx, cy)
        colour[node] = INK

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="{PAPER}"/>',
    ]

    for fact in facts:
        a, b = placed.get(fact.subject_id), placed.get(fact.object_id or "")
        if not a or not b:
            continue
        out.append(
            f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" '
            f'y2="{b[1]:.1f}" stroke="{LINE}" stroke-width="1.4"/>'
        )

    for node, (x, y) in placed.items():
        is_hub = node in hub
        r = 9 if is_hub else 6
        out.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" '
            f'fill="{colour.get(node, FAINT)}" stroke="{CARD}" stroke-width="2"/>'
        )
        out.append(
            _text(
                x,
                y - r - 5,
                name.get(node, node)[:22],
                10.5,
                INK if is_hub else SOFT,
                "middle",
                "bold" if is_hub else "normal",
            )
        )

    out.append("</svg>")
    return "".join(out)


def search_svg(query, cold, seeded, width: int = 820) -> str:
    """Which facts a query reached, and how it got to each one."""
    cold_ids = {f.fact_id for f in cold}
    rows = list(seeded)
    height = 78 + 24 * max(len(rows), 1)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="{PAPER}"/>',
        _text(
            20,
            26,
            f'Searching for "{query}", while she is talking about the shop',
            14,
            INK,
            weight="bold",
        ),
    ]
    for i, fact in enumerate(rows):
        y = 56 + i * 24
        by_words = fact.fact_id in cold_ids
        tone = RED if by_words else GREEN
        how = "matched the words" if by_words else "reached through the graph"
        out.append(f'<circle cx="30" cy="{y - 4}" r="5" fill="{tone}"/>')
        out.append(_text(46, y, fact.statement[:62], 11.5, SOFT))
        out.append(_text(width - 24, y, how, 10.5, tone, "end"))
    out.append("</svg>")
    return "".join(out)


D3_TEMPLATE = """
<!doctype html>
<meta charset="utf-8">
<title>__TITLE__</title>
<body style="margin:0;background:#EDE4D6;font-family:Georgia,serif">
<div id="__ID__" style="background:#EDE4D6;border-radius:10px;padding:6px 10px 10px">
  <div style="font:13px Georgia,serif;color:#241E1A;padding:6px 2px 4px">
    <b>__TITLE__</b>
    <span style="color:#8A7F76">
      &nbsp;drag to move &middot; hover an edge for what she said &middot; click a
      node to isolate it
    </span>
  </div>
  <div id="__ID__-legend" style="font:11px Georgia,serif;padding:2px 2px 6px"></div>
  <svg id="__ID__-svg" width="820" height="__H__" style="max-width:100%"></svg>
  <div id="__ID__-tip" style="font:12px Georgia,serif;color:#4A403B;
       min-height:2.6em;padding:4px 2px"></div>
</div>
<script>
(function () {
  // A <script src> injected through innerHTML does not block, so the drawing
  // code below cannot assume d3 exists yet -- it runs first and dies silently,
  // leaving an empty panel. Load it explicitly and draw on the callback.
  function start() {
    if (window.d3 && window.d3.forceSimulation) { draw(); return; }
    const existing = document.getElementById("d3-v7-loader");
    if (existing) { existing.addEventListener("load", draw); return; }
    const tag = document.createElement("script");
    tag.id = "d3-v7-loader";
    tag.src = "https://d3js.org/d3.v7.min.js";
    tag.onload = draw;
    tag.onerror = function () {
      document.getElementById("__ID__-tip").innerHTML =
        "Could not load D3 from its CDN — the graph needs a network connection.";
    };
    document.head.appendChild(tag);
  }

  function draw() {
  const data = __DATA__;
  const root = document.getElementById("__ID__-svg");
  const tip = document.getElementById("__ID__-tip");
  const width = root.clientWidth || 820, height = __H__;
  const svg = d3.select(root).attr("viewBox", [0, 0, width, height]);
  svg.selectAll("*").remove();

  const legend = d3.select("#__ID__-legend");
  data.legend.forEach(function (entry) {
    legend.append("span")
      .style("margin-right", "14px")
      .html('<span style="display:inline-block;width:9px;height:9px;border-radius:9px;'
            + 'background:' + entry.colour + ';margin-right:5px">'
            + '</span>' + entry.label);
  });

  const link = svg.append("g").selectAll("line").data(data.links).join("line")
    .attr("stroke", "#C9BCA6").attr("stroke-width", 1.6)
    .on("mouseover", function (event, d) {
      d3.select(this).attr("stroke", "#9C3B24").attr("stroke-width", 3);
      tip.innerHTML = "<b>" + d.statement + "</b><br><i>she said: &ldquo;"
                    + d.quote + "&rdquo;</i>";
    })
    .on("mouseout", function () {
      d3.select(this).attr("stroke", "#C9BCA6").attr("stroke-width", 1.6);
    });

  const node = svg.append("g").selectAll("circle").data(data.nodes).join("circle")
    .attr("r", function (d) { return 5 + Math.min(d.degree, 8) * 1.6; })
    .attr("fill", function (d) { return d.colour; })
    .attr("stroke", "#FFFCF5").attr("stroke-width", 2)
    .style("cursor", "pointer")
    .on("mouseover", function (event, d) {
      tip.innerHTML = "<b>" + d.name + "</b> &mdash; " + d.degree
                    + " connection(s)" + (d.detail ? "<br>" + d.detail : "");
    })
    .on("click", function (event, d) {
      const near = new Set([d.id]);
      data.links.forEach(function (l) {
        const a = l.source.id || l.source, b = l.target.id || l.target;
        if (a === d.id) near.add(b);
        if (b === d.id) near.add(a);
      });
      node.attr("opacity", function (n) { return near.has(n.id) ? 1 : 0.15; });
      label.attr("opacity", function (n) { return near.has(n.id) ? 1 : 0.15; });
      link.attr("opacity", function (l) {
        const a = l.source.id || l.source, b = l.target.id || l.target;
        return (a === d.id || b === d.id) ? 1 : 0.08;
      });
    })
    .call(d3.drag()
      .on("start", function (event, d) {
        if (!event.active) sim.alphaTarget(0.3).restart();
        d.fx = d.x; d.fy = d.y;
      })
      .on("drag", function (event, d) { d.fx = event.x; d.fy = event.y; })
      .on("end", function (event, d) {
        if (!event.active) sim.alphaTarget(0);
        d.fx = null; d.fy = null;
      }));

  const label = svg.append("g").selectAll("text").data(data.nodes).join("text")
    .text(function (d) { return d.name; })
    .attr("font-family", "Georgia, serif").attr("font-size", 10.5)
    .attr("fill", "#241E1A").attr("text-anchor", "middle").attr("dy", -11)
    .style("pointer-events", "none");

  svg.on("dblclick", function () {
    node.attr("opacity", 1); label.attr("opacity", 1); link.attr("opacity", 1);
    tip.innerHTML = "";
  });

  const sim = d3.forceSimulation(data.nodes)
    .force("link", d3.forceLink(data.links).id(function (d) { return d.id; })
                     .distance(95).strength(0.45))
    .force("charge", d3.forceManyBody().strength(-430))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collide", d3.forceCollide().radius(34))
    .on("tick", function () {
      link.attr("x1", function (d) { return d.source.x; })
          .attr("y1", function (d) { return d.source.y; })
          .attr("x2", function (d) { return d.target.x; })
          .attr("y2", function (d) { return d.target.y; });
      node.attr("cx", function (d) { return d.x; })
          .attr("cy", function (d) { return d.y; });
      label.attr("x", function (d) { return d.x; })
           .attr("y", function (d) { return d.y; });
    });
  }

  start();
})();
</script>
"""


def interactive_graph(
    entities, facts, groups=None, hub=None, title="Her memory graph", height=480
):
    """A force-directed D3 view of the semantic subgraph.

    The reason it is worth being interactive rather than a static picture: every
    edge here is a fact, and every fact carries the sentence she said. Hovering
    an edge shows that sentence, so the graph can be read all the way down to her
    own words rather than only as structure.

    Communities colour the nodes; the hub, when there is one, is drawn dark and
    large. Requires a network connection to load D3 from its CDN, as the GraphRAG
    notebook this follows also does.
    """
    import json
    import uuid

    groups = groups or []
    hub = set(hub or ())
    name = {e.entity_id: e.canonical_name for e in entities}
    detail = {e.entity_id: (e.detail or "")[:90] for e in entities}

    colour_of: dict[str, str] = {}
    legend = []
    for index, members in enumerate(groups):
        tone = COMMUNITY_COLOURS[index % len(COMMUNITY_COLOURS)]
        for member in members:
            colour_of[member] = tone
        shown = ", ".join(name.get(m, m) for m in members[:3])
        legend.append(
            {"colour": tone, "label": shown + ("…" if len(members) > 3 else "")}
        )
    for node in hub:
        colour_of[node] = INK
    if hub:
        legend.append(
            {
                "colour": INK,
                "label": "too connected to group: "
                + ", ".join(name.get(h, h) for h in hub),
            }
        )

    degree: dict[str, int] = {}
    links = []
    for fact in facts:
        if (
            not fact.object_id
            or fact.subject_id not in name
            or fact.object_id not in name
        ):
            continue
        degree[fact.subject_id] = degree.get(fact.subject_id, 0) + 1
        degree[fact.object_id] = degree.get(fact.object_id, 0) + 1
        links.append(
            {
                "source": fact.subject_id,
                "target": fact.object_id,
                "statement": fact.statement,
                "quote": fact.quote,
            }
        )

    nodes = [
        {
            "id": node,
            "name": name.get(node, node),
            "detail": detail.get(node, ""),
            "degree": degree[node],
            "colour": colour_of.get(node, FAINT),
        }
        for node in degree
    ]

    payload = json.dumps({"nodes": nodes, "links": links, "legend": legend})
    return (
        D3_TEMPLATE.replace("__ID__", "g" + uuid.uuid4().hex[:8])
        .replace("__DATA__", payload)
        .replace("__TITLE__", title)
        .replace("__H__", str(height))
    )


def save_graph(
    path, entities, facts, groups=None, hub=None, title="Her memory graph", height=520
):
    """Write the interactive graph to a standalone HTML file, and say where.

    Not displayed inline, and that is deliberate. A notebook viewer will happily
    show the container and silently refuse to run the script inside it, leaving
    a blank panel that looks like a broken cell. The GraphRAG notebook this
    follows does the same thing: it writes `ai_copyright_graph.html` and prints
    "open it in your browser to explore".

    A separate document also gets the whole window, which a force layout of
    thirty nodes needs more than a notebook cell can give it.
    """
    import pathlib as _pathlib

    html = interactive_graph(
        entities, facts, groups=groups, hub=hub, title=title, height=height
    )
    target = _pathlib.Path(path)
    target.write_text(html, encoding="utf-8")

    nodes = html.count('"id":')
    edges = html.count('"statement":')
    print(f"   graph written to {target.name} — {nodes} entities, {edges} facts")
    print(f"   open it to explore: {target.resolve()}")
    return target
