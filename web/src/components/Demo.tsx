import { useEffect, useState } from 'react';
import { api } from '../api';
import type { DraftFact, SearchResult } from '../types';
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
  ['update', 'Update', 'retire a telling and watch it step aside'],
];

const SUGGESTED = [
  'who is Ah Chwee',
  'where did her father work',
  'what did her mother cook',
];

export function Demo({ narratorId, name, onClose }: {
  narratorId: string;
  name: string;
  onClose: () => void;
}) {
  const [mode, setMode] = useState<Mode>('retrieve');
  const [query, setQuery] = useState('who is Ah Chwee');
  const [result, setResult] = useState<SearchResult | null>(null);
  const [asking, setAsking] = useState(false);
  const [failed, setFailed] = useState('');

  /* The sandbox. It survives a mode change on purpose — creating an edge and
     then retiring the one it disagrees with is the whole story, and clearing
     between the two would break it in half. The Reset button is the way back,
     and it says how many changes are being carried. */
  const [added, setAdded] = useState<DraftFact[]>([]);
  const [retired, setRetired] = useState<string[]>([]);
  const [draft, setDraft] = useState('');

  const run = async (over?: {
    added?: DraftFact[];
    retired?: string[];
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
    void run({ added: [], retired: [] });
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

  const retire = (factId: string) => {
    const next = [...retired, factId];
    setRetired(next);
    void run({ retired: next });
  };

  const trace = result?.trace;
  const touched = added.length + retired.length;

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
                placeholder="Her father worked at the tin mine before the shop."
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
              <div className="lbl dim">Retire a telling</div>
              <p className="prose">
                Retiring moves a fact in <em>transaction time</em> — the archive
                stops asserting it and keeps it, with her own dates untouched.
                It is not a delete, and it never records that she was wrong.
              </p>
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
                  {mode === 'update' && ' · click a row to retire it'}
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
                        onClick={() => mode === 'update' && retire(c.fact_id)}
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
                  {trace.retired.map((r) => (
                    <div key={r.fact_id} className="quote retired">
                      <div>
                        <q>{r.statement}</q>
                        <div className="lbl dim by">
                          transaction time · her dates untouched
                        </div>
                      </div>
                    </div>
                  ))}
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
