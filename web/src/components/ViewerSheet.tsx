import { initial } from '../api';
import type { Member } from '../types';
import { Sheet } from './Sheet';

/* Who you are, for the length of this demo.
 *
 * Sampan has no accounts. The viewer is a query parameter, and every personal
 * thing in the app reads from it: which questions are waiting for you, whose
 * bell you are looking at, who a recording is attributed to, and — because
 * nobody is notified about their own stories — what the bell can show you at
 * all. Ah Khim's bell can never contain "Ah Khim mentioned hopelessness"; only
 * her family's can.
 *
 * That is the correct behaviour and it was invisible, which made the family
 * half of the product impossible to show. This says plainly what it is rather
 * than pretending to be a login.
 */
interface Props {
  members: Member[];
  current: string;
  onPick: (narratorId: string) => void;
  onClose: () => void;
}

export function ViewerSheet({ members, current, onPick, onClose }: Props) {
  return (
    <Sheet onClose={onClose}>
      <div className="lbl dim">No accounts · demo only</div>
      <h2 className="ttl l" style={{ marginTop: 10 }}>
        Who are you right now?
      </h2>
      <p className="prose" style={{ marginTop: 12 }}>
        Everything personal follows this choice — the bell, the question
        waiting on the recording screen, and the name attached to anything you
        ask. Nobody is ever notified about their own stories, so switching is
        the only way to see the other side of the bridge.
      </p>

      <div style={{ marginTop: 22 }}>
        {members.map((m) => (
          <button
            key={m.narrator_id}
            className="person"
            aria-current={m.narrator_id === current}
            onClick={() => onPick(m.narrator_id)}
          >
            <div className="face l">{initial(m.display_name)}</div>
            <div style={{ minWidth: 0 }}>
              <div className="who">{m.display_name}</div>
              <div className="meta">
                <span>{m.relation}</span>
                <span>{m.records ? 'records' : 'reads only'}</span>
              </div>
            </div>
            {m.narrator_id === current && <span className="pill accent">You</span>}
          </button>
        ))}
      </div>
    </Sheet>
  );
}
