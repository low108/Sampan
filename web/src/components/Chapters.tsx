import { useEffect, useState } from 'react';
import { api } from '../api';
import type { Chapter } from '../types';

/* Her life in named sections.
 *
 * Nobody wrote these. They fall out of the memory graph: entities that keep
 * appearing together get clustered, and the cluster is named from the facts
 * connecting them. "Ah Gong's Jalan Bandar coffee shop" is not a category
 * someone chose — it is what the archive found.
 *
 * Every chapter opens down to her own sentences, because a summary of an
 * elderly person's life assembled by a machine is worth nothing if you cannot
 * check it against what she actually said.
 */
export function Chapters({ narratorId }: { narratorId: string }) {
  const [chapters, setChapters] = useState<Chapter[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    setChapters(null);
    setFailed(false);
    void api
      .chapters(narratorId)
      .then((d) => live && setChapters(d.chapters))
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [narratorId]);

  if (failed) return <p className="empty">Could not load her chapters just now.</p>;
  if (chapters === null) return <p className="empty">Reading the archive…</p>;
  if (chapters.length === 0) {
    return (
      <p className="empty">
        Not enough yet. Chapters appear once she has told enough for the same
        people and places to keep turning up together.
      </p>
    );
  }

  return (
    <>
      {chapters.map((chapter) => (
        <article key={chapter.id} className="card">
          <h3>{chapter.name || 'Unnamed chapter'}</h3>
          <div className="meta">
            <span>{chapter.members.join(' · ')}</span>
          </div>
          {chapter.summary && <p className="narr">{chapter.summary}</p>}
          {chapter.facts.length > 0 && (
            <details className="more">
              <summary>In her words</summary>
              {chapter.facts.map((f, i) => (
                <div key={i} className="gap">
                  {f.fact}
                  <p className="said">{f.she_said}</p>
                </div>
              ))}
            </details>
          )}
        </article>
      ))}
    </>
  );
}
