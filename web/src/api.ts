import type {
  AboutAnswer,
  ChaptersView,
  Bell,
  FeedView,
  Household,
  MapView,
  PendingAsk,
  SearchResult,
  TimelineView,
} from './types';

const params = new URLSearchParams(location.search);

/** Demo affordance: the key rides in the query string so a link is enough to
 *  open the archive. Stated as a limitation in the PRD; not an auth model. */
export const KEY = params.get('key') ?? '';
export const ME = params.get('user') ?? 'ah_khim';

export class ApiError extends Error {
  constructor(readonly status: number) {
    super(String(status));
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      'X-Sampan-Key': KEY,
      'Content-Type': 'application/json',
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) throw new ApiError(res.status);
  return (await res.json()) as T;
}

export const api = {
  household: () => request<Household>('/api/household'),

  bell: (viewer: string) => request<Bell>(`/api/bell/${encodeURIComponent(viewer)}`),

  markSeen: (viewer: string, ids: string[]) =>
    request<unknown>(`/api/bell/${encodeURIComponent(viewer)}/seen`, {
      method: 'POST',
      body: JSON.stringify({ ids }),
    }),

  feed: (narrator: string) =>
    request<FeedView>(`/api/family/${encodeURIComponent(narrator)}?view=feed`),

  mapView: (narrator: string) =>
    request<MapView>(`/api/family/${encodeURIComponent(narrator)}?view=map`),

  chapters: (narrator: string) =>
    request<ChaptersView>(`/api/family/${encodeURIComponent(narrator)}?view=chapters`),

  timeline: (narrator: string) =>
    request<TimelineView>(`/api/family/${encodeURIComponent(narrator)}?view=timeline`),

  pending: (narrator: string) =>
    request<PendingAsk>(`/api/talk/${encodeURIComponent(narrator)}/pending`),

  /** Answer this one next. The call carries one question, so opening a
   *  specific one from the bell has to decide which — otherwise the agent
   *  asks whatever is oldest and names the wrong person out loud. */
  chooseAsk: (narrator: string, ask_id: string) =>
    request<unknown>(`/api/talk/${encodeURIComponent(narrator)}/pending/choose`, {
      method: 'POST',
      body: JSON.stringify({ ask_id }),
    }),

  /** The agent's own retrieval, driven from a text box, with its working. */
  search: (narrator: string, question: string) =>
    request<SearchResult>(`/api/family/${encodeURIComponent(narrator)}/search`, {
      method: 'POST',
      body: JSON.stringify({ question }),
    }),

  about: (narrator: string, question: string) =>
    request<AboutAnswer>(`/api/family/${encodeURIComponent(narrator)}/about`, {
      method: 'POST',
      body: JSON.stringify({ question }),
    }),

  ask: (narrator: string, from_name: string, question: string) =>
    request<unknown>(`/api/family/${encodeURIComponent(narrator)}/ask`, {
      method: 'POST',
      body: JSON.stringify({ from_name, question }),
    }),

  correctPlace: (narrator: string, target: string, value: string, by: string) =>
    request<unknown>(`/api/family/${encodeURIComponent(narrator)}/corrections`, {
      method: 'POST',
      body: JSON.stringify({ kind: 'place', target, value, by }),
    }),
};

/** Chinese names are surname-first, so the first token of "Lim Siew Khim" is
 *  the family name half this household shares. The given name is what follows. */
export function givenName(displayName: string): string {
  const parts = displayName.trim().split(/\s+/).filter(Boolean);
  return parts.length < 2 ? displayName.trim() : parts.slice(1).join(' ');
}

export function initial(name: string): string {
  return name.trim()[0] ?? '?';
}
