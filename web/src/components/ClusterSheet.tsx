import type { Pin } from '../types';
import { Sheet } from './Sheet';

/* Several stories at one dot.
 *
 * The shop, the room above it and the station are a few hundred metres apart,
 * so at any usable zoom they are one marker — and to her they are one place
 * anyway. The map was already grouping them correctly; nothing was listening,
 * so tapping the group did nothing at all and the map felt dead.
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
      {/* A dot on the household map can hold stories from more than one
          person, so name all of them rather than assuming the first. */}
      <div className="lbl dim">{[...new Set(pins.map((p) => p.narrator_name))].join(' · ')}</div>
      <h2 className="ttl l" style={{ marginTop: 10 }}>
        {pins.length} stories here
      </h2>
      {span && (
        <div className="lbl dim" style={{ marginTop: 10 }}>
          {span}
        </div>
      )}

      <div style={{ marginTop: 22 }}>
        {pins.map((p) => (
          <article
            key={p.id}
            className="card tap"
            role="button"
            tabIndex={0}
            onClick={() => onPick(p.id)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') onPick(p.id);
            }}
          >
            <h3 className="ttl s">{p.title}</h3>
            <div className="meta" style={{ marginTop: 10 }}>
              <span>{p.year ?? 'year not yet told'}</span>
              <span
                className={
                  p.precision === 'town' || p.precision === 'region'
                    ? 'certainty guess'
                    : 'certainty'
                }
              >
                <s />
                {p.precision === 'town' || p.precision === 'region'
                  ? 'guessed'
                  : 'named in the telling'}
              </span>
            </div>
          </article>
        ))}
      </div>
    </Sheet>
  );
}
