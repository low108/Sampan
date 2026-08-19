import { useEffect, useRef } from 'react';
import type { Pin } from './types';

/* The <sampan-map> web component (Leaflet + OpenStreetMap) is kept verbatim
 * from the approved design and is not reimplemented here. What React adds is a
 * typed boundary around it.
 *
 * That boundary is the point. The element emits four events, and the old
 * vanilla page listened for two — so clicking any grouped marker fired
 * `sampan-cluster` into nothing and the map simply felt dead. With the event
 * map written down, a missing handler is a type error rather than a silence.
 */

export interface SampanMapEvents {
  'sampan-pin': { id: string };
  'sampan-cluster': { ids: string[] };
  'sampan-blank': Record<string, never>;
  'sampan-offscreen': unknown;
}

interface SampanMapElement extends HTMLElement {
  setPins(pins: Pin[]): void;
  select(id: string | null): void;
}

interface Props {
  pins: Pin[];
  selected: string | null;
  onPin: (id: string) => void;
  /** Several stories share one dot. Every one of them must stay reachable. */
  onCluster: (ids: string[]) => void;
  onBlank: () => void;
  style?: React.CSSProperties;
}

export function SampanMap({ pins, selected, onPin, onCluster, onBlank, style }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const el = useRef<SampanMapElement | null>(null);

  /* Handlers live in a ref so the element is created once and never torn down:
   * remounting Leaflet on every render loses pan, zoom and tile cache. */
  const handlers = useRef({ onPin, onCluster, onBlank });
  handlers.current = { onPin, onCluster, onBlank };

  useEffect(() => {
    if (!host.current) return;
    if (!el.current) {
      const node = document.createElement('sampan-map') as SampanMapElement;
      node.addEventListener('sampan-pin', (e) => {
        handlers.current.onPin((e as CustomEvent<SampanMapEvents['sampan-pin']>).detail.id);
      });
      node.addEventListener('sampan-cluster', (e) => {
        handlers.current.onCluster(
          (e as CustomEvent<SampanMapEvents['sampan-cluster']>).detail.ids,
        );
      });
      node.addEventListener('sampan-blank', () => handlers.current.onBlank());
      el.current = node;
    }
    const node = el.current;
    if (node.parentElement !== host.current) host.current.appendChild(node);
  }, []);

  useEffect(() => {
    const node = el.current;
    if (!node) return;
    /* The element upgrades asynchronously; before that its methods do not
     * exist yet, so retry on the next frame rather than dropping the pins. */
    const apply = () => {
      if (typeof node.setPins !== 'function') {
        requestAnimationFrame(apply);
        return;
      }
      try {
        node.setPins(pins);
        node.select(selected);
      } catch (err) {
        /* Leaflet throws from deep inside its own callbacks. Losing the map is
         * survivable; losing the archive because of it is not. */
        console.error('map could not draw these pins', err);
      }
    };
    apply();
  }, [pins, selected]);

  return <div className="maprap" ref={host} style={style} />;
}
