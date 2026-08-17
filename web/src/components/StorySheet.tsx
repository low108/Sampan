import { useEffect, useState } from 'react';
import { api } from '../api';
import type { Pin, StoryCard } from '../types';
import { Sheet } from './Sheet';

/** Anything coarser than a street is a guess, and is said to be one: a
 *  plausible wrong pin is worse than a visibly uncertain one, because nobody
 *  corrects what looks right. */
const isGuess = (p: Pin) => p.precision === 'town' || p.precision === 'region';

interface Props {
  pin: Pin;
  onClose: () => void;
  onCorrect: (pin: Pin) => void;
}

export function StorySheet({ pin, onClose, onCorrect }: Props) {
  const [card, setCard] = useState<StoryCard | null>(null);
  const [why, setWhy] = useState<string | null>(null);
  const [thanked, setThanked] = useState(false);

  /* Fetched after the sheet is on screen so it opens instantly. */
  useEffect(() => {
    let live = true;
    setCard(null);
    void api
      .feed(pin.narrator_id)
      .then((d) => {
        if (live) setCard(d.stories.find((s) => s.story_id === pin.id) ?? null);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [pin.id, pin.narrator_id]);

  /* Only linked pins can explain themselves, and the explanation is her own
   * sentence — the one the linker had to find before it was allowed to move
   * the story onto the map. */
  useEffect(() => {
    if (!pin.linked) return;
    let live = true;
    void api
      .mapView(pin.narrator_id)
      .then((d) => {
        if (!live) return;
        const place = d.map.pins.find((p) =>
          p.stories.some((s) => s.story_id === pin.id),
        )?.place;
        setWhy(place?.linked_evidence || null);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [pin.id, pin.linked, pin.narrator_id]);

  const guess = isGuess(pin);

  return (
    <Sheet onClose={onClose}>
      <h2>{pin.title}</h2>
      <div className="meta">
        <span>{pin.year ?? 'year not yet told'}</span>
        <span>{pin.narrator_name}</span>
        <span className={guess ? 'certainty guess' : 'certainty'}>
          <s />
          {guess ? 'Xiao Chuan guessed this place' : 'the place she named'}
        </span>
      </div>

      {pin.linked && (
        <details className="more">
          <summary>Why this pin is here</summary>
          <p className="narr">
            {why ? `She said: "${why}"` : 'She named this place in another conversation.'}
          </p>
        </details>
      )}

      {guess && (
        <div className="row">
          <button
            className="btn ghost small"
            disabled={thanked}
            onClick={() => setThanked(true)}
          >
            {thanked ? 'Thank you' : "That's right"}
          </button>
          <button className="btn ghost small" onClick={() => onCorrect(pin)}>
            No — let me fix it
          </button>
        </div>
      )}

      <details className="more" open>
        <summary>Her words</summary>
        {card ? (
          <div className="narr">
            {/* Her sensory detail is set apart, not run into the narrative:
                it is the line the whole story hangs on. */}
            {card.sense_detail && <p className="said">{card.sense_detail}</p>}
            <p>{card.narrative}</p>
          </div>
        ) : (
          <p className="narr">…</p>
        )}
      </details>
    </Sheet>
  );
}
