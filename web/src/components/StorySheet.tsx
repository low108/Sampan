import { useEffect, useState } from 'react';
import { api, givenName, initial } from '../api';
import type { Pin, StoryCard } from '../types';
import { Memory, memoryFor } from './Memory';
import { Sheet } from './Sheet';

/** Anything coarser than a street is a guess, and is said to be one: a
 *  plausible wrong pin is worse than a visibly uncertain one, because nobody
 *  corrects what looks right. */
const isGuess = (p: Pin) => p.precision === 'town' || p.precision === 'region';

/** Words, never a guessed date. No circa, no bracketed estimate — a year
 *  nobody said is not written down, and the eyebrow says so plainly. */
function era(card: StoryCard | null, pin: Pin): string {
  const from = card?.year_from ?? pin.year;
  const to = card?.year_to ?? null;
  if (from && to && from !== to) return `${from}–${to}`;
  if (from) return String(from);
  return 'year not yet told';
}

interface Props {
  pin: Pin;
  onClose: () => void;
  onCorrect: (pin: Pin) => void;
  /** Turn this story into a question on the teller's next call. The agent will
   *  say who asked — that is the whole product, so it is a primary action. */
  onAsk: (pin: Pin) => void;
}

export function StorySheet({ pin, onClose, onCorrect, onAsk }: Props) {
  const [card, setCard] = useState<StoryCard | null>(null);
  const [why, setWhy] = useState<string | null>(null);
  const [asked, setAsked] = useState(false);
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

  /* Only linked pins can explain themselves, and the explanation is the
   * teller's own sentence — the one the linker had to find before it was
   * allowed to move the story onto the map. */
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
  /* Whose story this is. The archive holds three people's, so nothing on this
   * card may assume the teller is her — the given name says who it was. */
  const teller = givenName(pin.narrator_name);
  /* Not every story has one, and that is the honest default — most of her life
   * has no picture, and generating one per story would be inventing it. */
  const media = memoryFor(pin.title);

  return (
    <Sheet onClose={onClose}>
      {media && (
        <Memory media={media}>
          <span className={guess ? 'pill dash' : 'pill'}>
            {guess ? 'Place guessed by the system' : `Place ${teller} named`}
          </span>
        </Memory>
      )}
      <div className="lbl dim">
        {card?.where_said || pin.title} · {era(card, pin)}
      </div>
      <h2 className="ttl xl" style={{ marginTop: 12 }}>
        {pin.title}
      </h2>

      <div className="pills" style={{ marginTop: 18 }}>
        {!media && (
          <span className={guess ? 'pill dash' : 'pill'}>
            {guess ? 'Place guessed' : `Place ${teller} named`}
          </span>
        )}
        <span className="pill">{pin.narrator_name}</span>
      </div>

      {/* The quote box. The one thing on this screen that is theirs, verbatim. */}
      {card?.sense_detail && (
        <div className="quote">
          <div className="face">{initial(pin.narrator_name)}</div>
          <div>
            <q>{card.sense_detail}</q>
            <div className="lbl dim by">Told by {pin.narrator_name}</div>
          </div>
        </div>
      )}

      <div className="row">
        <button className="btn accent" disabled={asked} onClick={() => { onAsk(pin); setAsked(true); }}>
          {asked ? `${teller} will be asked` : `Ask ${teller} about this`}
        </button>
      </div>

      {/* Correction lives inside the thing it corrects: there is no settings
          screen, and the label says exactly what is being changed. */}
      {guess && (
        <div style={{ marginTop: 26, borderTop: '1px solid var(--line)', paddingTop: 20 }}>
          <div className="lbl dim">You are correcting the system, not {teller}</div>
          <p className="prose" style={{ marginTop: 10 }}>
            {teller} named the town but not the street, so this pin is placed
            by inference. Is it in the right place?
          </p>
          <div className="row">
            <button className="btn ghost" disabled={thanked} onClick={() => setThanked(true)}>
              {thanked ? 'Thank you' : "Yes, that's right"}
            </button>
            <button className="btn ghost" onClick={() => onCorrect(pin)}>
              No — let me fix it
            </button>
          </div>
        </div>
      )}

      {pin.linked && (
        <div style={{ marginTop: 26 }}>
          <div className="lbl dim">Why this pin is here</div>
          <p className="prose" style={{ marginTop: 10 }}>
            {why
              ? `${teller} said: “${why}”`
              : `${teller} named this place in another conversation.`}
          </p>
        </div>
      )}

      <div style={{ marginTop: 26 }}>
        <div className="lbl dim">In their own words</div>
        <p className="prose big" style={{ marginTop: 10 }}>
          {card ? card.narrative : '…'}
        </p>
      </div>
    </Sheet>
  );
}
