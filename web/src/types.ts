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

export type Tab = 'map' | 'record' | 'family';
export type MemberTab = 'chat' | 'map' | 'chapters' | 'ask';
export type Sheet = 'notifs' | 'unplaced' | 'cluster';
export type RecordState = 'idle' | 'live';
