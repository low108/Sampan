import type { ReactNode } from 'react';

/* Every sheet in the app: scrim behind, rounded panel rising from the bottom.
 * Tapping the scrim closes it, because reaching a small × in the corner is the
 * hardest thing on the screen for the person this is built for. */
export function Sheet({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  return (
    <>
      <div className="scrim" onClick={onClose} />
      <div className="sheet" role="dialog" aria-modal="true">
        <div className="grab" />
        {children}
      </div>
    </>
  );
}
