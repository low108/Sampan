import type { Pin } from '../types';
import { Sheet } from './Sheet';

/* Several stories at one dot.
 *
 * The shop, the room above it and the station are a few hundred metres apart,
 * so at any usable zoom they are one marker — and to her they are one place
 * anyway. The map was already grouping them correctly; nothing was listening,
 * so tapping the group did nothing at all and the map felt broken.
 */
interface Props {
  pins: Pin[];
  onPick: (id: string) => void;
  onClose: () => void;
}

export function ClusterSheet({ pins, onPick, onClose }: Props) {
  const years = pins
    .map((p) => p.year)
    .filter((y): y is number => y !== null)
    .sort((a, b) => a - b);
  const span =
    years.length > 1 && years[0] !== years[years.length - 1]
      ? `${years[0]}–${years[years.length - 1]}`
      : (years[0]?.toString() ?? '');

  return (
    <Sheet onClose={onClose}>
      <h2>{pins.length} stories here</h2>
      {span && <p className="en">{span}</p>}
      {pins.map((p) => (
        <article
          key={p.id}
          className="card"
          role="button"
          tabIndex={0}
          onClick={() => onPick(p.id)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') onPick(p.id);
          }}
        >
          <h3>{p.title}</h3>
          <div className="meta">
            <span>{p.year ?? 'year not yet told'}</span>
            <span>{p.narrator_name}</span>
          </div>
        </article>
      ))}
    </Sheet>
  );
}
