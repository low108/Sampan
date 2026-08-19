import { initial } from '../api';
import type { Bell, Notification } from '../types';
import { Sheet } from './Sheet';

/* The bell is the bridge made visible: "Wei Lun asked you something" opens a
 * recording with his question already loaded, so the distance between someone
 * was thinking of you and she starts talking is a single tap.
 *
 * Lime marks only the two things that are hers: a story that just arrived, and
 * a question waiting for her. Everything else in this list is quiet. */
interface Props {
  bell: Bell | null;
  onOpen: (n: Notification) => void;
  onClose: () => void;
}

/* A concern gets a way in but never the lime: lime means something of theirs
   is new, and a wellbeing flag is not news to celebrate. It outranks
   everything in the sort order instead. */
const CTA: Partial<Record<Notification['kind'], string>> = {
  asked_you: 'Tap to answer',
  new_story: 'Read it',
  concern: 'Look in on them',
};

export function BellSheet({ bell, onOpen, onClose }: Props) {
  const items = bell?.notifications ?? [];
  return (
    <Sheet onClose={onClose}>
      <div className="lbl dim">
        {items.length === 0
          ? 'Nothing waiting'
          : `${items.length} ${items.length === 1 ? 'thing' : 'things'} · ${bell?.unseen ?? 0} new`}
      </div>
      <h2 className="ttl l" style={{ marginTop: 10 }}>
        Messages
      </h2>

      <div style={{ marginTop: 22 }}>
        {items.length === 0 && <p className="empty">Nothing new.</p>}
        {items.map((n) => {
          const hers = n.kind === 'asked_you' || n.kind === 'new_story';
          return (
            <article
              key={n.id}
              className="card tap"
              role="button"
              tabIndex={0}
              onClick={() => onOpen(n)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') onOpen(n);
              }}
            >
              <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
                <div className="face">{initial(n.from_name)}</div>
                <div style={{ minWidth: 0 }}>
                  <h3 className="ttl s">{n.title}</h3>
                  <p className="prose" style={{ marginTop: 8 }}>
                    {n.subtitle}
                  </p>
                </div>
              </div>
              {CTA[n.kind] && (
                <div className="pills" style={{ marginTop: 14 }}>
                  <span className={hers && !n.seen ? 'pill lime' : 'pill'}>
                    {CTA[n.kind]}
                  </span>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </Sheet>
  );
}
