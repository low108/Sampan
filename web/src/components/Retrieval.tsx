import { useState } from 'react';
import { api } from '../api';
import type { SearchResult } from '../types';

/* What the agent's memory does when it is asked something.
 *
 * The same `search_facts` the Companion calls mid-sentence, driven from a text
 * box so it can be watched. Four stages, and none of them is a model: the
 * terms that survived, the entities the question named, what those reached,
 * and what the ranking chose. The same question typed twice returns the same
 * numbers — which a retrieval pipeline that asks an LLM to pick edges cannot
 * promise, and is the only reason showing the numbers is worth anything.
 *
 * The graph is laid out by hop distance rather than by force. With a few dozen
 * nodes a physics simulation is a pretty way to hide the structure; concentric
 * rings put the seeds in the middle and everything the question reached around
 * them, which is what the exploration stage actually did.
 */

const RING = [0, 96, 176, 240];

interface Placed {
  id: string;
  name: string;
  x: number;
  y: number;
  hops: number | null;
  seed: boolean;
}

/** Concentric rings by hop distance. Deterministic: same query, same picture. */
function place(nodes: SearchResult['nodes'], size: number): Placed[] {
  const mid = size / 2;
  const byRing = new Map<number, SearchResult['nodes']>();
  for (const node of nodes) {
    /* Unreached nodes sit on the outermost ring. They are in the drawing
       because an edge touches them, not because the seeds found them. */
    const ring = node.hops === null ? RING.length - 1 : Math.min(node.hops, RING.length - 1);
    byRing.set(ring, [...(byRing.get(ring) ?? []), node]);
  }

  const out: Placed[] = [];
  for (const [ring, members] of byRing) {
    const radius = RING[ring] ?? RING[RING.length - 1] ?? 240;
    members.forEach((node, i) => {
      /* Offset each ring so nodes do not line up radially and overlap. */
      const angle = (2 * Math.PI * i) / members.length - Math.PI / 2 + ring * 0.4;
      out.push({
        id: node.id,
        name: node.name,
        hops: node.hops,
        seed: node.seed,
        x: mid + (radius === 0 && members.length === 1 ? 0 : radius) * Math.cos(angle),
        y: mid + (radius === 0 && members.length === 1 ? 0 : radius) * Math.sin(angle),
      });
    });
  }
  return out;
}

export function Retrieval({ narratorId, name }: { narratorId: string; name: string }) {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<SearchResult | null>(null);
  const [asking, setAsking] = useState(false);
  const [failed, setFailed] = useState(false);

  const run = async () => {
    const asked = query.trim();
    if (!asked) return;
    setAsking(true);
    setFailed(false);
    try {
      setResult(await api.search(narratorId, asked));
    } catch {
      setFailed(true);
    } finally {
      setAsking(false);
    }
  };

  const size = 520;
  const placed = result ? place(result.nodes, size) : [];
  const at = new Map(placed.map((p) => [p.id, p]));
  const trace = result?.trace;

  return (
    <>
      <div className="hero">
        <div className="lbl">Inside the memory · no model in this path</div>
        <h2 className="ttl xl">Ask the graph directly</h2>
        <p className="prose big">
          This is the same lookup Xiao Chuan runs mid-sentence, with the working
          shown. Type the same question twice and the numbers will be identical —
          nothing here is a guess.
        </p>
      </div>

      <div className="page">
        <div className="col">
          <label htmlFor="gq">Ask about {name}</label>
          <input
            id="gq"
            value={query}
            placeholder="what did her father do at the coffee shop"
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void run();
            }}
          />
          <div className="row">
            <button className="btn accent" disabled={asking} onClick={() => void run()}>
              {asking ? 'Searching' : 'Search the graph'}
            </button>
          </div>
          {failed && <p className="prose" style={{ marginTop: 16 }}>Could not reach the archive.</p>}
        </div>

        {trace && (
          <div className="trace">
            <div className="stages">
              <Stage n={1} title="Grounding" note="which words survived, and which the index ignores">
                <div className="pills">
                  {trace.terms.map((t) => (
                    <span key={t} className="pill">{t}</span>
                  ))}
                  {trace.dropped.map((t) => (
                    <span key={t} className="pill dropped">{t}</span>
                  ))}
                </div>
                {trace.dropped.length > 0 && (
                  <p className="prose">
                    Words under three letters are discarded: in an archive this
                    small they match on the honorific alone, and{' '}
                    <em>Ah Seng</em> would come back as <em>Ah Chwee</em>.
                  </p>
                )}
              </Stage>

              <Stage
                n={2}
                title="Exploration"
                note={`${trace.seeds.length} entities named · ${Object.keys(trace.reached).length} reached within 2 hops`}
              >
                <div className="pills">
                  {placed
                    .filter((p) => p.hops !== null)
                    .sort((a, b) => (a.hops ?? 0) - (b.hops ?? 0))
                    .map((p) => (
                      <span key={p.id} className={p.seed ? 'pill accent' : 'pill'}>
                        {p.name} · {p.hops} hop
                      </span>
                    ))}
                </div>
              </Stage>

              <Stage
                n={3}
                title="Focus"
                note={`${trace.considered} edges held · ${trace.candidates.length} scored · ${trace.returned.length} returned`}
              >
                <table className="scores">
                  <thead>
                    <tr>
                      <th>#</th><th>bm25</th><th>hops</th><th>rrf</th><th>seen</th><th>fact</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trace.candidates.slice(0, 8).map((c) => (
                      <tr key={c.fact_id} data-returned={c.rank !== null}>
                        <td>{c.rank === null ? '—' : c.rank + 1}</td>
                        <td>{c.bm25.toFixed(2)}</td>
                        <td>{c.hops === null ? '—' : c.hops}</td>
                        <td>{c.rrf.toFixed(4)}</td>
                        <td>{c.mentions}</td>
                        <td>{c.statement}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="prose">
                  The rows marked — were scored and rejected. They are the more
                  useful half: they show what the ranking weighed, not just what
                  it picked.
                </p>
              </Stage>

              {trace.retired.length > 0 && (
                <Stage
                  n={4}
                  title="No longer asserted"
                  note="matched the question, and the archive has stopped standing behind it"
                >
                  {trace.retired.map((r) => (
                    <div key={r.fact_id} className="quote retired">
                      <div>
                        <q>{r.statement}</q>
                        <div className="lbl dim by">
                          Superseded by {r.superseded_by || 'a later telling'} · kept, not deleted
                        </div>
                      </div>
                    </div>
                  ))}
                  <p className="prose">
                    She told it differently later. Both are kept and neither says
                    she was wrong — a flat index cannot report what it stopped
                    believing.
                  </p>
                </Stage>
              )}
            </div>

            {/* The graph. Rings are hop distance from what the question named. */}
            <div className="graph">
              <div className="lbl dim">
                {placed.length} nodes · {result.edges.length} edges · rings are hops from the question
              </div>
              <svg viewBox={`0 0 ${size} ${size}`} role="img" aria-label="Retrieved subgraph">
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
                    />
                  );
                })}
                {placed.map((p) => (
                  <g key={p.id} className="node" data-seed={p.seed}>
                    <circle cx={p.x} cy={p.y} r={p.seed ? 9 : 6} />
                    <text x={p.x + 12} y={p.y + 4}>{p.name}</text>
                  </g>
                ))}
              </svg>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

function Stage({
  n,
  title,
  note,
  children,
}: {
  n: number;
  title: string;
  note: string;
  children: React.ReactNode;
}) {
  return (
    <section className="stage">
      <div className="lbl dim">
        {n} · {title}
      </div>
      <p className="lbl dim step">{note}</p>
      {children}
    </section>
  );
}
