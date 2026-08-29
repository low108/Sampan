/* The shapes the server actually returns.
 *
 * Written against the live responses from /api/household, /api/bell,
 * /api/family and /api/talk rather than from the Python models, because the
 * serialised form is what the browser has to survive — optional fields that
 * Pydantic fills with defaults still arrive as null often enough to matter.
 */

export type Precision = 'exact' | 'street' | 'town' | 'region' | 'unknown';

/** A story that reached the map: it has a place and a position. */
export interface Pin {
  id: string;
  title: string;
  lat: number;
  lng: number;
  precision: Precision;
  /** True when the place was reached by joining a relational name to somewhere
   *  she named in another session. Such pins can show the sentence behind them. */
  linked: boolean;
  year: number | null;
  narrator_id: string;
  narrator_name: string;
}

/** A story with no place at all — held deliberately, never hidden. */
export interface Unplaced {
  story_id: string;
  title: string;
  narrator_id: string;
  narrator_name: string;
  where_said: string;
  sense_detail: string;
}

export interface Member {
  narrator_id: string;
  display_name: string;
  relation: string;
  born: number | null;
  records: boolean;
  story_count: number;
  session_count: number;
}

export interface Household {
  members: Member[];
  pins: Pin[];
  unplaced: Unplaced[];
}

export type NotificationOpens = 'record' | 'member' | 'story';

export interface Notification {
  id: string;
  kind: 'asked_you' | 'new_story' | 'concern';
  title: string;
  subtitle: string;
  from_name: string;
  at: string;
  seen: boolean;
  opens: NotificationOpens;
  target: string;
}

export interface Bell {
  unseen: number;
  notifications: Notification[];
}

export interface StoryCard {
  story_id: string;
  title: string;
  narrative: string;
  sense_detail: string;
  where_said: string;
  year_from: number | null;
  year_to: number | null;
  /** The clip Veo made from this story, once there is one. Usually empty:
   *  generation is queued at the end of a call and takes tens of seconds. */
  memory_video?: string;
  /** A poster for it. Veo returns no frame, so in practice this is empty and
   *  only the pre-rendered library clips carry one. */
  memory_still?: string;
}

export interface FeedView {
  narrator_id: string;
  stories: StoryCard[];
}

export interface ChapterFact {
  /** Rendered with its interval, e.g. "1958–1969 · her father ran a coffee shop". */
  fact: string;
  /** The sentence she said that put it there. */
  she_said: string;
}

export interface Chapter {
  id: string;
  name: string;
  summary: string;
  members: string[];
  facts: ChapterFact[];
  /** Tellings she later replaced. Kept, shown, and marked as retired — the
   *  family may correct the system, never her. */
  retired?: ChapterFact[];
}

export interface ChaptersView {
  chapters: Chapter[];
}

export interface TimelineView {
  stories: StoryCard[];
}

export interface MapPlace {
  raw_name: string;
  display_name: string;
  precision: Precision;
  linked_from: string;
  linked_evidence: string;
}

export interface MapView {
  map: {
    pins: { place: MapPlace; stories: { story_id: string; title: string }[] }[];
    tray: MapPlace[];
  };
}

export interface PendingAsk {
  waiting: boolean;
  from_name?: string;
  question?: string;
  /** Set when a question is waiting but it is too late at night to bring it
   *  to her. The server decides this, not the browser. */
  quiet_hours?: boolean;
  /** What her last telling left on the family's map, if it was recent. Her
   *  proof that talking did something — the family side is the side she does
   *  not open. Null once it stops being news; the server decides when. */
  kept?: Kept | null;
}

export interface Kept {
  story_id: string;
  title: string;
  /** The place she named, under the name written on the pin. */
  where: string;
  at: string;
}

export interface AboutAnswer {
  answer: string;
  follow_up: string;
}

/** One line in the "ask about her" conversation. */
export interface ChatLine {
  text: string;
  mine?: boolean;
  /** A question worth putting to her on the next call, offered as an action. */
  follow?: string;
}

/** One fact, with every number that decided where it ranked. */
export interface Scored {
  fact_id: string;
  statement: string;
  bm25: number;
  hops: number | null;
  rrf: number;
  mentions: number;
  confidence: number;
  /** Position in the returned list, or null for a candidate that was scored
   *  and rejected — the more interesting half. */
  rank: number | null;
}

/** A fact the query matched that the archive no longer asserts. */
export interface Passed {
  fact_id: string;
  statement: string;
  superseded_by: string;
  expired_at: string;
}

/** Why a query returned what it did. No model anywhere in this path, so the
 *  same question traced twice gives identical numbers. */
export interface SearchTrace {
  query: string;
  terms: string[];
  dropped: string[];
  seeds: string[];
  reached: Record<string, number>;
  considered: number;
  lexical_hits: number;
  structural_hits: number;
  candidates: Scored[];
  returned: string[];
  retired: Passed[];
}

/** A fact the demo invented. Travels with the request; never stored. */
export interface DraftFact {
  subject_id: string;
  predicate: string;
  object_literal: string;
  statement: string;
}

/** A later telling replacing an earlier one. The replacement inherits the old
 *  fact's subject and predicate, so it lands on the same node and the two can
 *  be seen side by side — one current, one no longer asserted. */
export interface Supersession {
  fact_id: string;
  statement: string;
  object_literal: string;
}

export interface SearchResult {
  trace: SearchTrace;
  nodes: {
    id: string;
    name: string;
    hops: number | null;
    seed: boolean;
    /** Added by the demo sandbox, not by her. Drawn differently. */
    invented?: boolean;
  }[];
  edges: {
    fact_id: string;
    source: string;
    target: string;
    literal: string;
    predicate: string;
    statement: string;
    quote: string;
    rank: number | null;
    retired: boolean;
    superseded_by: string;
    /** Valid time — her life, in her own words, and often empty because she
     *  rarely speaks in dates. A state change fills in `valid_to`. */
    valid_from: string;
    valid_to: string;
    /** Transaction time — when the archive began asserting this, and if ever,
     *  when it stopped. Conflicting testimony fills in `t_expired`. */
    t_created: string;
    t_expired: string;
  }[];
  /** What the contradiction judge made of each correction. The only part of
   *  a search response that came from a model. */
  verdicts: Verdict[];
}

/** One correction, as the judge saw it. */
export interface Verdict {
  fact_id: string;
  /** state_change | conflicting_testimony | none */
  kind: string;
  reason: string;
  confidence: number;
  /** "valid time" or "transaction time" — which clock moved. */
  clock: string;
  /** False when the model did not run and the conservative default was used. */
  judged: boolean;
  replacement: string;
}

export type Tab = 'map' | 'record' | 'family';
export type MemberTab = 'chat' | 'map' | 'chapters' | 'graph' | 'ask';
export type Sheet = 'notifs' | 'unplaced' | 'cluster' | 'viewer';
export type RecordState = 'idle' | 'live';
