import { useState } from 'react';
import { api } from '../api';
import type { SearchResult } from '../types';
import { Graph } from './Graph';

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

  const trace = result?.trace;
  const reached = result
    ? result.nodes.filter((n) => n.hops !== null).sort((a, b) => (a.hops ?? 0) - (b.hops ?? 0))
    : [];

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
                  {reached.map((n) => (
                    <span key={n.id} className={n.seed ? 'pill accent' : 'pill'}>
                      {n.name} · {n.hops} hop
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

            <Graph result={result} />
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
