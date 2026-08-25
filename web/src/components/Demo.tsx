import { useEffect, useState } from 'react';
import { api } from '../api';
import type { DraftFact, Scored, SearchResult, Supersession } from '../types';
import { Graph } from './Graph';

/* Inside the memory: retrieve, create, update.
 *
 * Three things you can do to a knowledge graph, and this runs all of them
 * through the code the Companion actually uses — the same `search_facts`, the
 * same BM25 and hop distance and RRF, with the working shown at every stage.
 *
 * Nothing is written. The sandbox travels with the request, so a created fact
 * or a retired one exists for exactly one query and leaves no mark. That is
 * not squeamishness about demo data: the product's rule is that the family may
 * correct the system and never her, and a demo that let anyone invent
 * sentences into her archive would be the clearest possible violation of it.
 */

type Mode = 'retrieve' | 'create' | 'update';

const MODES: [Mode, string, string][] = [
  ['retrieve', 'Retrieve', 'ask the graph and watch it rank'],
  ['create', 'Create', 'add an edge and watch it compete'],
  ['update', 'Update', 'replace a telling and watch the belief move'],
];

/* The three questions the demo is built on, so it can be driven by clicking.
 *
 *   the first names two entities in one sentence -- a place directly, and a
 *   person only by his role -- and its third row outscores its second on
 *   keywords while ranking below it on graph distance, which is the clearest
 *   evidence in the whole panel that the graph is doing work
 *
 *   the second puts the fact worth retiring at rank one
 *
 *   the third finds nothing, which is the case most worth explaining
 */
const OPENING = 'what did her father do at the coffee shop';
const SUGGESTED = [OPENING, 'who lived in Sungai Siput', 'who is Ah Seng'];

export function Demo({ narratorId, name, onClose }: {
  narratorId: string;
  name: string;
  onClose: () => void;
}) {
  const [mode, setMode] = useState<Mode>('retrieve');
  const [query, setQuery] = useState(OPENING);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [asking, setAsking] = useState(false);
  const [failed, setFailed] = useState('');

  /* The sandbox. It survives a mode change on purpose — creating an edge and
     then retiring the one it disagrees with is the whole story, and clearing
     between the two would break it in half. The Reset button is the way back,
     and it says how many changes are being carried. */
  const [added, setAdded] = useState<DraftFact[]>([]);
  const [retired, setRetired] = useState<string[]>([]);
  const [replaced, setReplaced] = useState<Supersession[]>([]);
  const [draft, setDraft] = useState('');
  /* The telling being corrected, chosen by clicking a row. Held rather than
     inferred: the real path asks a model which fact a new one disagrees with,
     and a demo that guessed would be claiming a capability it is not running. */
  const [replacing, setReplacing] = useState<Scored | null>(null);
  const [later, setLater] = useState('');

  const run = async (over?: {
    added?: DraftFact[];
    retired?: string[];
    replaced?: Supersession[];
    ask?: string;
  }) => {
    const asked = (over?.ask ?? query).trim();
    if (!asked) return;
    setAsking(true);
    setFailed('');
    try {
      setResult(
        await api.search(narratorId, asked, {
          added: over?.added ?? added,
          retired: over?.retired ?? retired,
          replaced: over?.replaced ?? replaced,
        }),
      );
    } catch {
      setFailed('Could not reach the archive.');
    } finally {
      setAsking(false);
    }
  };

  useEffect(() => {
    void run();
    // Only on mount: afterwards the buttons drive it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const reset = () => {
    setAdded([]);
    setRetired([]);
    setReplaced([]);
    setReplacing(null);
    setLater('');
    void run({ added: [], retired: [], replaced: [] });
  };

  /* Create: one sentence in, and the subject is whichever entity the sentence
     names — the same lexical grounding the query uses, so an invented fact
     lands on a real node.
     
     When it names nobody the subject is left empty and the server invents one.
     The first version fell back to whichever node happened to be first, which
     silently drew a relationship the sentence never claimed. */
  const create = () => {
    const sentence = draft.trim();
    if (!sentence || !result) return;
    const named = result.nodes.find(
      (n) =>
        !n.invented &&
        n.name.length >= 4 &&
        sentence.toLowerCase().includes(n.name.toLowerCase()),
    );
    const next = [
      ...added,
      {
        subject_id: named?.id ?? '',
        predicate: 'worked_at',
        object_literal: '',
        statement: sentence,
      },
    ];
    setAdded(next);
    setDraft('');
    void run({ added: next });
  };

  /* Clicking an already-retired row is a no-op, not a second retirement. The
     server reports it once either way; it was only the change counter that
     double-counted, and a Reset button claiming two changes for one click is
     the kind of small lie that makes someone doubt the rest of the panel. */
  const retire = (factId: string) => {
    if (retired.includes(factId)) return;
    const next = [...retired, factId];
    setRetired(next);
    setReplacing(null);
    void run({ retired: next });
  };

  /* What the new edge should point at, for a label that reads like a place
     rather than a whole claim. "Ah Chwee lives in Kampung Baru now" → "Kampung
     Baru". A demo convenience and nothing more: the real archive gets its
     objects from the fact extractor, which is a model call on the transcript.
     When this finds nothing the server falls back to the sentence. */
  const objectOf = (sentence: string): string => {
    const m = /\b(?:in|at|to|on)\s+(.+)$/i.exec(sentence.trim());
    if (!m?.[1]) return '';
    return m[1]
      .replace(/\b(now|these days|nowadays|today)\b/gi, '')
      .replace(/[.!?,]+\s*$/, '')
      .trim();
  };

  /* Update: she says it differently now.

     The fact being replaced is the one that was clicked. Nothing infers it, and
     nothing compares the new sentence against the old — the server takes this
     id and looks it up. On a real call a model does that work, and saying so
     out loud is cheaper than being caught assuming otherwise.

     The replacement copies the old fact's subject and predicate on the server,
     so the new edge lands on the same node and both tellings are visible at
     once, one current and one not. */
  const supersede = () => {
    const sentence = later.trim();
    if (!sentence || !replacing) return;
    const next = [
      ...replaced,
      {
        fact_id: replacing.fact_id,
        statement: sentence,
        object_literal: objectOf(sentence),
      },
    ];
    setReplaced(next);
    setReplacing(null);
    setLater('');
    void run({ replaced: next });
  };

  const trace = result?.trace;
  const touched = added.length + retired.length + replaced.length;

  return (
    <div className="demo">
      <header className="demo-top">
        <div className="brand">
          <span className="lbl">Inside the memory</span>
          <span className="lbl dim">{name}'s graph · nothing here is written</span>
        </div>
        <div className="headbar">
          {touched > 0 && (
            <button className="asme" onClick={reset}>
              Reset · {touched} change{touched === 1 ? '' : 's'}
            </button>
          )}
          <button className="asme" onClick={onClose}>Close</button>
        </div>
      </header>

      <div className="demo-body">
        <div className="demo-left">
          <div className="modes">
            {MODES.map(([id, label, note]) => (
              <button key={id} onClick={() => setMode(id)} aria-current={mode === id}>
                <span className="lbl">{label}</span>
                <span className="lbl dim">{note}</span>
              </button>
            ))}
          </div>

          <label htmlFor="dq">Ask the graph</label>
          <input
            id="dq"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void run();
            }}
          />
          <div className="pills" style={{ marginTop: 10 }}>
            {SUGGESTED.map((q) => (
              <button
                key={q}
                className="pill"
                onClick={() => {
                  setQuery(q);
                  /* Passed through rather than read back from state: this
                     render still holds the old query. A suggestion that fills
                     the box and does nothing looks broken. */
                  void run({ ask: q });
                }}
              >
                {q}
              </button>
            ))}
          </div>
          <div className="row">
            <button className="btn accent" disabled={asking} onClick={() => void run()}>
              {asking ? 'Searching' : 'Query'}
            </button>
          </div>

          {mode === 'create' && (
            <div className="panel">
              <div className="lbl dim">Add an edge</div>
              <p className="prose">
                Write a sentence. It becomes an edge on whichever node it names,
                and then competes for rank like any other — no special treatment
                for being new.
              </p>
              <input
                value={draft}
                placeholder="Ah Fatt drank his kopi at the coffee shop every afternoon."
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') create();
                }}
              />
              <div className="row">
                <button className="btn ghost" onClick={create}>Add to the graph</button>
              </div>
            </div>
          )}

          {mode === 'update' && (
            <div className="panel">
              <div className="lbl dim">She says it differently now</div>
              {replacing === null ? (
                <p className="prose">
                  Pick the telling she is correcting — click any row below. Then
                  say what she says now. The archive keeps both and stops
                  standing behind the older one; it never records that she was
                  wrong.
                </p>
              ) : (
                <>
                  <p className="prose">
                    Replacing <q>{replacing.statement}</q>
                  </p>
                  <input
                    value={later}
                    placeholder="Ah Chwee lives in Kampung Baru now."
                    autoFocus
                    onChange={(e) => setLater(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') supersede();
                      if (e.key === 'Escape') setReplacing(null);
                    }}
                  />
                  <div className="row">
                    <button className="btn ghost" onClick={supersede}>
                      She said this instead
                    </button>
                    <button
                      className="btn ghost"
                      onClick={() => retire(replacing.fact_id)}
                    >
                      Just stop asserting it
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {failed && <p className="prose" style={{ marginTop: 16 }}>{failed}</p>}

          {trace && (
            <div className="stages">
              <section className="stage">
                <div className="lbl dim">1 · Grounding</div>
                <p className="lbl dim step">
                  {trace.terms.length} terms kept · {trace.dropped.length} ignored
                </p>
                <div className="pills">
                  {trace.terms.map((t) => <span key={t} className="pill">{t}</span>)}
                  {trace.dropped.map((t) => (
                    <span key={t} className="pill dropped">{t}</span>
                  ))}
                </div>
              </section>

              <section className="stage">
                <div className="lbl dim">2 · Exploration</div>
                <p className="lbl dim step">
                  {trace.seeds.length} named · {Object.keys(trace.reached).length} reached
                  within 2 hops · {trace.considered} edges held
                </p>
              </section>

              <section className="stage">
                <div className="lbl dim">3 · Focus</div>
                <p className="lbl dim step">
                  {trace.candidates.length} scored · {trace.returned.length} returned
                  {mode === 'update' && ' · click the telling she is correcting'}
                </p>
                <table className="scores">
                  <thead>
                    <tr><th>#</th><th>bm25</th><th>hops</th><th>rrf</th><th>fact</th></tr>
                  </thead>
                  <tbody>
                    {trace.candidates.slice(0, 7).map((c) => (
                      <tr
                        key={c.fact_id}
                        data-returned={c.rank !== null}
                        data-clickable={mode === 'update'}
                        data-picked={replacing?.fact_id === c.fact_id}
                        onClick={() => mode === 'update' && setReplacing(c)}
                      >
                        <td>{c.rank === null ? '—' : c.rank + 1}</td>
                        <td>{c.bm25.toFixed(2)}</td>
                        <td>{c.hops === null ? '—' : c.hops}</td>
                        <td>{c.rrf.toFixed(4)}</td>
                        <td>{c.statement}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>

              {trace.retired.length > 0 && (
                <section className="stage">
                  <div className="lbl dim">4 · No longer asserted</div>
                  <p className="lbl dim step">
                    matched the question · kept, and no longer standing behind it
                  </p>
                  {trace.retired.map((r) => {
                    /* `superseded_by` is a fact id. Resolve it against the
                       edges in this same response so the page can say what
                       replaced it, which is the only part of a supersession
                       anyone actually cares about. */
                    const by = result?.edges.find(
                      (e) => e.fact_id === r.superseded_by,
                    );
                    return (
                      <div key={r.fact_id} className="swap">
                        <div className="quote retired">
                          <div>
                            <q>{r.statement}</q>
                            <div className="lbl dim by">
                              transaction time moved · her dates untouched
                            </div>
                          </div>
                        </div>
                        {/* The replacement is the current belief, so it is not
                            dimmed with the telling it replaced. Showing them at
                            the same weight was the mistake: the archive stands
                            behind exactly one of these two. */}
                        {by && (
                          <div className="quote later">
                            <div>
                              <div className="lbl dim">she says this now</div>
                              <q>{by.statement}</q>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </section>
              )}
            </div>
          )}
        </div>

        <div className="demo-right">
          {result && <Graph result={result} />}
        </div>
      </div>
    </div>
  );
}
