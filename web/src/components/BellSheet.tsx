import type { Bell, Notification } from '../types';
import { Sheet } from './Sheet';

/* The bell is the bridge made visible: "Wei Lun asked you something" opens a
 * recording with his question already loaded, so the distance between someone
 * was thinking of you and she starts talking is a single tap. */
interface Props {
  bell: Bell | null;
  onOpen: (n: Notification) => void;
  onClose: () => void;
}

export function BellSheet({ bell, onOpen, onClose }: Props) {
  const items = bell?.notifications ?? [];
  return (
    <Sheet onClose={onClose}>
      <h2>Messages</h2>
      {items.length === 0 && <p className="empty">Nothing new.</p>}
      {items.map((n) => (
        <article
          key={n.id}
          className="card"
          role="button"
          tabIndex={0}
          onClick={() => onOpen(n)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') onOpen(n);
          }}
        >
          <h3>{n.title}</h3>
          <div className="meta">
            <span className="en">{n.subtitle}</span>
          </div>
          {n.opens === 'record' && (
            <p className="gap">
              <b>Tap to answer</b>
            </p>
          )}
        </article>
      ))}
    </Sheet>
  );
}
