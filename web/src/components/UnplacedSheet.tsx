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
      <h2>Stories with no place</h2>
      <p className="en">Stories with nowhere to sit — not lost, just not placed.</p>
      {list.map((c) => (
        <article key={c.story_id} className="card">
          <h3>{c.title}</h3>
          <div className="meta">
            <span>{c.narrator_name}</span>
            <span>only says "{c.where_said}"</span>
          </div>
          {c.sense_detail && <p className="said">{c.sense_detail}</p>}
          <p className="gap">
            She never said which one. <span className="en">Xiao Chuan does not guess.</span>
          </p>
          <div className="row">
            <button
              className="btn ghost small"
              onClick={() => onPlace(c.where_said, c.narrator_id)}
            >
              I know which one
            </button>
          </div>
        </article>
      ))}
    </Sheet>
  );
}
