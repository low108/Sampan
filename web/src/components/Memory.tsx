import { useEffect, useRef, useState } from 'react';

/* The image at the head of a story card.
 *
 * Generated with Veo from what she actually said — the line house and the rice
 * and soy sauce, the room above the shop — and never from a photograph of
 * anyone. Rooms, not faces. Inventing a face for her father would put a
 * generated person exactly where the product promises a real memory, and the
 * quote box two inches below it is the thing the whole design protects.
 *
 * Video, not a still, because a memory that breathes is worth the bytes. But
 * the still is the contract: it is the poster, it is what shows before the
 * first frame decodes, it is what shows if the video never loads, and it is
 * what shows to anyone who has asked their machine to stop moving things.
 */

export interface MemoryMedia {
  /** Looping clip. Optional: a still alone is a complete card. */
  video?: string;
  /**
   * Poster, and the fallback for every case where the video does not play.
   *
   * Empty for a freshly generated memory: Veo returns an mp4 and nothing else,
   * so there is no frame to hold until the video decodes. The pre-rendered
   * library clips ship with one and use it. Where there is none the video
   * carries the card alone, which is why nothing below may assume a still.
   */
  still: string;
  /** What it depicts, for anyone who cannot see it. */
  alt: string;
}

/* Which memory belongs to which story.
 *
 * Matched on words she used rather than on story ids, because ids change every
 * time the demo archive is reset and these images outlive that. A story with no
 * match gets no image, which is the honest default: most of her stories have no
 * picture and inventing one for each would be inventing her life.
 */
const LIBRARY: { match: RegExp; media: MemoryMedia }[] = [
  {
    match: /line house|soy sauce|salted fish|estate/i,
    media: {
      video: '/memories/line-house.mp4',
      still: '/memories/line-house.jpg',
      alt: 'A plate of rice and a bottle of soy sauce on a wooden table in a line house, lit through timber slats.',
    },
  },
  {
    match: /above the coffee shop|room upstairs|upstairs|milo/i,
    media: {
      video: '/memories/room-above-the-shop.mp4',
      still: '/memories/room-above-the-shop.jpg',
      alt: 'A bare room above a coffee shop at dawn, shutters half open onto the street, charcoal smoke drifting.',
    },
  },
];

export function memoryFor(title: string): MemoryMedia | null {
  return LIBRARY.find((entry) => entry.match.test(title))?.media ?? null;
}

/* What the archive generated for this story, if anything, and the shipped
 * library otherwise.
 *
 * The served asset wins: it was filmed from the sense detail she gave on the
 * call, and the library is a keyword guess made before that call existed. The
 * order matters most for the two stories that match a library regex *and* have
 * been through Veo — the generated one is about the story, the matched one is
 * merely about a word in its title.
 *
 * Both may be absent, which stays the honest default. */
export function memoryOf(
  card: { title?: string; memory_video?: string; memory_still?: string } | null,
  title: string,
): MemoryMedia | null {
  if (card?.memory_video || card?.memory_still) {
    return {
      video: card.memory_video || undefined,
      still: card.memory_still || '',
      /* Said plainly, and "generated" is the first word for a reason: the one
       * thing a listener must not conclude is that this is a photograph of her
       * life. The library entries above can afford a literal description
       * because a human wrote them knowing what was rendered; here nothing has
       * looked at the frames, so describing them would be inventing them. */
      alt: `A generated scene for "${card.title || title}". No people in it.`,
    };
  }
  return memoryFor(title);
}

interface Props {
  media: MemoryMedia;
  /** Overlaid on the image, bottom-left: the certainty pill, usually. */
  children?: React.ReactNode;
}

export function Memory({ media, children }: Props) {
  const video = useRef<HTMLVideoElement>(null);
  const [still, setStill] = useState(true);

  /* Honour the system setting rather than asking. Someone who has turned off
   * motion has already answered this question once and should not be asked
   * again by every product they open. */
  const [motionOk] = useState(
    () =>
      typeof window.matchMedia === 'function' &&
      !window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  );

  /* Play only while on screen. A card sheet can hold several of these, and a
   * phone decoding four loops at once for the sake of one the reader is
   * actually looking at is how a quiet product starts draining a battery. */
  useEffect(() => {
    const node = video.current;
    if (!node || !motionOk) return;
    if (typeof IntersectionObserver !== 'function') {
      void node.play().catch(() => undefined);
      return;
    }
    const watcher = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) void node.play().catch(() => undefined);
        else node.pause();
      },
      { threshold: 0.2 },
    );
    watcher.observe(node);
    return () => watcher.disconnect();
  }, [motionOk]);

  /* A generated memory arrives as an mp4 with no poster, so the video element
   * has to be mounted even when motion is off -- paused, it shows its own first
   * frame, which honours the setting and still gives the card a picture. Only
   * where a still exists can the video be left out entirely. */
  const showVideo = Boolean(media.video) && (motionOk || !media.still);

  return (
    <div className="memory" data-still={media.still ? 'true' : 'false'}>
      {media.still && (
        <img src={media.still} alt={media.alt} data-hidden={!still} />
      )}
      {showVideo && (
        <video
          ref={video}
          src={media.video}
          poster={media.still || undefined}
          muted
          loop
          playsInline
          preload={media.still ? 'metadata' : 'auto'}
          aria-hidden={media.still ? 'true' : undefined}
          aria-label={media.still ? undefined : media.alt}
          onPlaying={() => setStill(false)}
          onError={() => setStill(true)}
        />
      )}
      {children}
    </div>
  );
}
