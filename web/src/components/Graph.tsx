import type { SearchResult } from '../types';

/* The subgraph the question walked.
 *
 * Concentric rings by hop distance, not a force simulation. A force layout is
 * the conventional choice and looks livelier; it also settles somewhere
 * slightly different every run, which would quietly contradict the one claim
 * this whole panel makes — that the same question gives the same answer. The
 * rings are the exploration stage drawn literally: seeds at the centre, then
 * what they reached, ring by ring.
 */

const RING = [0, 96, 176, 240];
/* How far apart several seeds sit when they share the centre. */
const CORE = 40;

/* A label that fits beside a dot.
 *
 * The API returns real names at full length, because the create panel finds
 * its subject by looking for one inside the typed sentence. Only the drawing
 * needs them short: a food entity is named the way she said it — "toast the
 * bread, charcoal fire one, spread butter" — which is a fine name and an
 * impossible label, and an invented node falls back to the whole sentence
 * that created it. The full text stays on the edge's tooltip. */
const LABEL = 26;

function short(text: string): string {
  if (text.length <= LABEL) return text;
  const cut = text.slice(0, LABEL).replace(/\s+\S*$/, '') || text.slice(0, LABEL);
  return `${cut}…`;
}

interface Placed {
  id: string;
  name: string;
  x: number;
  y: number;
  hops: number | null;
  seed: boolean;
  invented: boolean;
}

export function place(nodes: SearchResult['nodes'], size: number): Placed[] {
  const mid = size / 2;
  const byRing = new Map<number, SearchResult['nodes']>();
  for (const node of nodes) {
    /* Unreached nodes go to the outer ring. They are in the picture because an
       edge touches them, not because the question found them. */
    const ring =
      node.hops === null ? RING.length - 1 : Math.min(node.hops, RING.length - 1);
    byRing.set(ring, [...(byRing.get(ring) ?? []), node]);
  }

  const out: Placed[] = [];
  for (const [ring, members] of byRing) {
    const radius = RING[ring] ?? 240;
    members.forEach((node, i) => {
      /* Rotate each ring so nodes do not line up radially and collide. */
      const angle = (2 * Math.PI * i) / members.length - Math.PI / 2 + ring * 0.4;
      /* Ring zero has radius zero, which is right for one seed and wrong for
         several — "what did her father do at the coffee shop" names two, and
         they landed on the same point with their labels on top of each other.
         Several seeds get a small huddle at the centre instead. */
      const r = radius === 0 && members.length > 1 ? CORE : radius;
      out.push({
        id: node.id,
        name: node.name,
        hops: node.hops,
        seed: node.seed,
        invented: node.invented ?? false,
        x: mid + r * Math.cos(angle),
        y: mid + r * Math.sin(angle),
      });
    });
  }
  return out;
}

export function Graph({ result }: { result: SearchResult }) {
  const size = 560;
  const placed = place(result.nodes, size);
  const at = new Map(placed.map((p) => [p.id, p]));
  const fresh = new Set(
    result.edges.filter((e) => e.fact_id.startsWith('demo_')).map((e) => e.fact_id),
  );

  return (
    <div className="graph">
      <div className="lbl dim">
        {placed.length} nodes · {result.edges.length} edges · rings are hops from the question
      </div>
      <svg viewBox={`0 0 ${size} ${size}`} role="img" aria-label="The subgraph this question walked">
        {RING.filter((r) => r > 0).map((r) => (
          <circle key={r} cx={size / 2} cy={size / 2} r={r} className="ring" />
        ))}
        {result.edges.map((e) => {
          const a = at.get(e.source);
          const b = at.get(e.target);
          if (!a || !b) return null;
          return (
            <line
              key={e.fact_id}
              x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              className="edge"
              data-returned={e.rank !== null}
              data-retired={e.retired}
              data-fresh={fresh.has(e.fact_id)}
            >
              <title>{e.statement}</title>
            </line>
          );
        })}
        {placed.map((p) => {
          /* Labels on the right half grow inward. Anchoring everything at the
             start is tidier to read but sends the outer-ring names off the
             edge of the viewBox, where they are simply gone. */
          const right = p.x > size / 2;
          return (
            <g key={p.id} className="node" data-seed={p.seed} data-invented={p.invented}>
              <circle cx={p.x} cy={p.y} r={p.seed ? 9 : 6}>
                <title>{p.name}</title>
              </circle>
              <text
                x={right ? p.x - 12 : p.x + 12}
                y={p.y + 4}
                textAnchor={right ? 'end' : 'start'}
              >
                {short(p.name)}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="key">
        <span><s className="seed" /> named by the question</span>
        <span><s className="ret" /> returned</span>
        <span><s className="exp" /> no longer asserted</span>
      </div>
    </div>
  );
}
