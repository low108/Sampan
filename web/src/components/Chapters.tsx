import { useEffect, useState } from 'react';
import { api } from '../api';
import type { Chapter, ChapterFact } from '../types';

/* A life in named sections.
 *
 * Nobody wrote these. They fall out of the memory graph: entities that keep
 * appearing together get clustered, and the cluster is named from the facts
 * connecting them. "Ah Gong's Jalan Bandar coffee shop" is not a category
 * someone chose — it is what the archive found. The header says so, because a
 * grid this editorial otherwise reads as something a person curated.
 *
 * Every chapter opens down to the teller's own sentences, because a summary
 * of a person's life assembled by a machine is worth nothing if you cannot
 * check it against what they actually said.
 */

/* The facts arrive pre-rendered as "1958–1969 · her father ran a coffee shop"
 * -- the sentence is whatever was said, so the code reads the shape, not it --
 * so the interval is the label and the rest is the fact. When there is no
 * interval the label says that in words — never a guessed date. */
function split(f: ChapterFact): { label: string; value: string } {
  const at = f.fact.indexOf(' · ');
  if (at === -1) return { label: 'year not yet told', value: f.fact };
  return { label: f.fact.slice(0, at), value: f.fact.slice(at + 3) };
}

/* No photography in the archive, so the tiles carry a ground of their own.
 * The mechanic is the reference's: grey until something in it is live, then
 * it blooms. */
const TINTS = ['#1E2A24', '#2A2119', '#191F2A', '#251A22', '#1A2621', '#26221A'];

export function Chapters({ narratorId, name }: { narratorId: string; name: string }) {
  const [chapters, setChapters] = useState<Chapter[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setChapters(null);
    setFailed(false);
    setOpen(null);
    void api
      .chapters(narratorId)
      .then((d) => live && setChapters(d.chapters))
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [narratorId]);

  if (failed) return <p className="empty">Could not load these chapters just now.</p>;
  if (chapters === null) return <p className="empty">Reading the archive…</p>;
  if (chapters.length === 0) {
    return (
      <p className="empty">
        Not enough yet. Chapters appear once {name} has told enough for the
        same people and places to keep turning up together.
      </p>
    );
  }

  const current = chapters.find((c) => c.id === open) ?? null;

  return (
    <>
      <div className="lbl dim" style={{ padding: '0 0 14px' }}>
        {chapters.length} {chapters.length === 1 ? 'chapter' : 'chapters'} found ·
        not written by anyone
      </div>

      <div className="chapter-grid">
        {chapters.map((c, i) => (
          <button
            key={c.id}
            className="tile"
            data-new={c.id === open}
            aria-current={c.id === open}
            style={{ background: TINTS[i % TINTS.length] }}
            onClick={() => setOpen(c.id === open ? null : c.id)}
          >
            <span className="lbl">
              {c.facts.length} {c.facts.length === 1 ? 'fact' : 'facts'} ·{' '}
              {c.members.length} {c.members.length === 1 ? 'thread' : 'threads'}
            </span>
            <span className="ttl l">{c.name || 'Unnamed chapter'}</span>
            <span className="pills">
              <span className="pill on-dark">
                {c.id === open ? 'Open' : 'Look inside'}
              </span>
            </span>
          </button>
        ))}
      </div>

      {current && (
        <div className="chapter-open">
          <div className="facts">
            <div className="lbl dim">Inside a chapter · {current.name}</div>
            <h3 className="ttl xl" style={{ marginTop: 12 }}>
              {current.facts.length}{' '}
              {current.facts.length === 1 ? 'fact' : 'facts'}, then{' '}
              {name}'s sentences
            </h3>
            {current.summary && (
              <p className="prose" style={{ marginTop: 14 }}>
                {current.summary}
              </p>
            )}
            <div className="fact-strip">
              {current.facts.map((f, i) => {
                const { label, value } = split(f);
                return (
                  <div key={i} className="f">
                    <div className="lbl dim">{label}</div>
                    <div className="ttl s">{value}</div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* The only place on this screen where words appear in their voice. */}
          <div className="sentences">
            <div className="lbl dim">{name}'s sentences · verbatim, ordered by call</div>
            {current.facts
              .filter((f) => f.she_said)
              .map((f, i) => (
                <div key={i} className="quote">
                  <div>
                    <q>{f.she_said}</q>
                    <div className="lbl dim by">{split(f).label}</div>
                  </div>
                </div>
              ))}

            {/* Told differently later. Both are kept; the earlier one greys
                back behind a rule and says so. Nothing is deleted, and
                nothing here implies the teller was wrong. */}
            {(current.retired ?? [])
              .filter((f) => f.she_said)
              .map((f, i) => (
                <div key={`retired-${i}`} className="quote retired">
                  <div>
                    <q>{f.she_said}</q>
                    <div className="lbl dim by">Retired, kept · {split(f).label}</div>
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}
    </>
  );
}
