import { initial } from '../api';
import type { Unplaced } from '../types';
import { Sheet } from './Sheet';

/* Absence is a place on the page.
 *
 * A story she told fully but never located does not get quietly dropped: it
 * gets a permanent, tappable line, and the reason is stated plainly. The
 * archive says what it does not know. */
interface Props {
  list: Unplaced[];
  onPlace: (whereSaid: string, narratorId: string) => void;
  onClose: () => void;
}

export function UnplacedSheet({ list, onPlace, onClose }: Props) {
  return (
    <Sheet onClose={onClose}>
      <div className="lbl dim">No place at all · {list.length}</div>
      <h2 className="ttl l" style={{ marginTop: 10 }}>
        Told, never placed
      </h2>
      <p className="prose" style={{ marginTop: 12 }}>
        Some of the best stories in this archive are here. They are not lost
        and not hidden — nobody said where, so the archive does not guess.
      </p>

      <div style={{ marginTop: 22 }}>
        {list.map((c) => (
          <article key={c.story_id} className="card">
            <div className="lbl dim">
              {c.narrator_name} · only says “{c.where_said}”
            </div>
            <h3 className="ttl s" style={{ marginTop: 10 }}>
              {c.title}
            </h3>

            {c.sense_detail && (
              <div className="quote">
                <div className="face">{initial(c.narrator_name)}</div>
                <div>
                  <q>{c.sense_detail}</q>
                  <div className="lbl dim by">Told by {c.narrator_name}</div>
                </div>
              </div>
            )}

            {/* Correcting the system, not her: she said "home" and meant it. */}
            <div className="row">
              <button
                className="btn ghost"
                onClick={() => onPlace(c.where_said, c.narrator_id)}
              >
                I know which one
              </button>
            </div>
          </article>
        ))}
      </div>
    </Sheet>
  );
}
