import { useCallback, useEffect, useMemo, useState } from 'react';
import { ApiError, api, givenName, initial, ME } from './api';
import { SampanMap } from './SampanMap';
import { BellSheet } from './components/BellSheet';
import { ClusterSheet } from './components/ClusterSheet';
import { MemberPage } from './components/MemberPage';
import { StorySheet } from './components/StorySheet';
import { UnplacedSheet } from './components/UnplacedSheet';
import { useRecorder } from './useRecorder';
import type { Bell, Household, MemberTab, Notification, Pin, Sheet, Tab } from './types';

const TABS: [Tab, string, string][] = [
  ['map', '🗺', 'Map'],
  ['record', '🎙', 'Tell a story'],
  ['family', '👵', 'Family'],
];

export function App() {
  const [house, setHouse] = useState<Household | null>(null);
  const [bell, setBell] = useState<Bell | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const [tab, setTab] = useState<Tab>('map');
  const [member, setMember] = useState<string | null>(null);
  const [memberTab, setMemberTab] = useState<MemberTab>('chat');
  const [story, setStory] = useState<string | null>(null);
  const [cluster, setCluster] = useState<string[]>([]);
  const [sheet, setSheet] = useState<Sheet | null>(null);
  const [recQuestion, setRecQuestion] = useState<{ from_name: string; question: string } | null>(
    null,
  );
  /* Why there is no question here, when the bell said there was one. */
  const [recNote, setRecNote] = useState('');

  const load = useCallback(async () => {
    try {
      const [h, b] = await Promise.all([
        api.household(),
        api.bell(ME).catch(() => ({ unseen: 0, notifications: [] }) as Bell),
      ]);
      setHouse(h);
      setBell(b);
      setFailure(null);
    } catch (err) {
      /* A blank page cannot tell you whether the key is missing, the service is
       * cold, or the archive is empty. Say which. */
      setFailure(
        err instanceof ApiError && err.status === 401
          ? 'MISSING_KEY'
          : `Could not reach the archive (${(err as Error).message}). It may still be starting up — try again in a moment.`,
      );
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const recorder = useRecorder(load);

  const members = house?.members ?? [];
  const person = useMemo(
    () => members.find((m) => m.narrator_id === member) ?? null,
    [members, member],
  );

  /* On a member's own map, only her pins. */
  const pins = useMemo(() => {
    const all = house?.pins ?? [];
    const scope = member && memberTab === 'map' ? member : null;
    return scope ? all.filter((p) => p.narrator_id === scope) : all;
  }, [house, member, memberTab]);

  const pinById = useCallback(
    (id: string): Pin | undefined => house?.pins.find((p) => p.id === id),
    [house],
  );

  const clusterPins = useMemo(
    () => cluster.map(pinById).filter((p): p is Pin => p !== undefined),
    [cluster, pinById],
  );

  const openNotification = async (n: Notification) => {
    await api.markSeen(ME, [n.id]).catch(() => undefined);
    setSheet(null);
    if (n.opens === 'record') {
      const p = await api.pending(ME).catch(() => null);
      setRecQuestion(
        p?.waiting && p.from_name && p.question
          ? { from_name: p.from_name, question: p.question }
          : null,
      );
      /* Tapping "Wei Lun asked you something" and arriving at a blank page
       * reads as broken. The reason is deliberate, so it should be said. */
      setRecNote(
        p && !p.waiting && p.quiet_hours
          ? 'It is late now. Xiao Chuan will bring you this question in the morning.'
          : '',
      );
      setTab('record');
      setMember(null);
    } else if (n.opens === 'member') {
      setTab('family');
      setMember(n.target);
      setMemberTab('chat');
    } else {
      setTab('map');
      setMember(null);
      setStory(n.target);
    }
    void api.bell(ME).then(setBell).catch(() => undefined);
  };

  /* Correction lives inside the thing it corrects: there is no admin screen. */
  const placeByName = async (rawName: string, narratorId: string) => {
    const value = window.prompt(`Where is "${rawName}"?`, '');
    if (!value) return;
    await api.correctPlace(narratorId, rawName, value, ME).catch(() => undefined);
    await load();
  };

  const correctPin = async (pin: Pin) => {
    const d = await api.mapView(pin.narrator_id).catch(() => null);
    const name = d?.map.pins.find((p) => p.stories.some((s) => s.story_id === pin.id))?.place
      .raw_name;
    if (name) await placeByName(name, pin.narrator_id);
  };

  if (failure) {
    return (
      <div className="failed">
        <h1>Sampan</h1>
        {failure === 'MISSING_KEY' ? (
          <p>
            This link is missing its access key. Open the URL that ends in <code>?key=…</code>.
          </p>
        ) : (
          <p>{failure}</p>
        )}
      </div>
    );
  }

  const onMap = tab === 'map' || (member !== null && memberTab === 'map');
  const unplaced = house?.unplaced ?? [];
  const openStory = story ? pinById(story) : undefined;

  return (
    <>
      <header className="top">
        {person ? (
          <>
            <button
              className="bell"
              aria-label="Back"
              onClick={() => {
                setMember(null);
                setStory(null);
              }}
            >
              ‹
            </button>
            <h1>
              {givenName(person.display_name)}
              <small>{person.relation}</small>
            </h1>
          </>
        ) : (
          <h1>
            Sampan<small>Xiao Chuan</small>
          </h1>
        )}
        <button className="bell" aria-label="Messages" onClick={() => setSheet('notifs')}>
          🔔{bell?.unseen ? <b>{bell.unseen}</b> : null}
        </button>
      </header>

      <main className={onMap ? 'nopad' : ''}>
        {person ? (
          <MemberPage
            person={person}
            tab={memberTab}
            onTab={(t) => {
              setMemberTab(t);
              setStory(null);
            }}
            pins={pins}
            selected={story}
            onPin={setStory}
            onCluster={(ids) => {
              setCluster(ids);
              setSheet('cluster');
            }}
            onBlank={() => setStory(null)}
          />
        ) : tab === 'map' ? (
          <>
            <SampanMap
              pins={pins}
              selected={story}
              onPin={setStory}
              onCluster={(ids) => {
                setCluster(ids);
                setSheet('cluster');
              }}
              onBlank={() => setStory(null)}
            />
            {unplaced.length > 0 && (
              <button className="unplaced-bar" onClick={() => setSheet('unplaced')}>
                {unplaced.length} {unplaced.length === 1 ? 'story has' : 'stories have'} no
                place
                <span className="en">— they only say "home"</span>
              </button>
            )}
          </>
        ) : tab === 'record' ? (
          <div className="rec">
            {recQuestion ? (
              <div className="asked">
                <div className="who">{recQuestion.from_name} asked you</div>
                <p>{recQuestion.question}</p>
              </div>
            ) : recNote ? (
              <div className="asked">
                <p>{recNote}</p>
              </div>
            ) : (
              <p>Say whatever comes to mind, any time.</p>
            )}
            <button
              className="bigbtn"
              data-on={recorder.state === 'live'}
              onClick={() => void recorder.toggle()}
            >
              {recorder.state === 'live' ? "That's enough" : 'Tell a story'}
            </button>
            <p className="en">{recorder.said}</p>
          </div>
        ) : (
          <div className="pad">
            {members.map((m) => (
              <div
                key={m.narrator_id}
                className="person"
                role="button"
                tabIndex={0}
                onClick={() => {
                  setMember(m.narrator_id);
                  setMemberTab('chat');
                  setStory(null);
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    setMember(m.narrator_id);
                    setMemberTab('chat');
                  }
                }}
              >
                <div className="face">{initial(m.display_name)}</div>
                <div>
                  <div className="who">{m.display_name}</div>
                  <div className="meta">
                    <span>{m.relation}</span>
                    <span>
                      {m.story_count
                        ? `${m.story_count} ${m.story_count === 1 ? 'story' : 'stories'}`
                        : 'nothing told yet'}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {!person && (
        <nav className="tabs">
          {TABS.map(([id, icon, label]) => (
            <button
              key={id}
              onClick={() => {
                setTab(id);
                setMember(null);
                setStory(null);
              }}
              aria-current={tab === id}
            >
              <i>{icon}</i>
              {label}
            </button>
          ))}
        </nav>
      )}

      {openStory && (
        <StorySheet pin={openStory} onClose={() => setStory(null)} onCorrect={correctPin} />
      )}
      {sheet === 'cluster' && clusterPins.length > 0 && (
        <ClusterSheet
          pins={clusterPins}
          onPick={(id) => {
            setSheet(null);
            setStory(id);
          }}
          onClose={() => setSheet(null)}
        />
      )}
      {sheet === 'unplaced' && (
        <UnplacedSheet
          list={unplaced}
          onPlace={(where, narrator) => void placeByName(where, narrator)}
          onClose={() => setSheet(null)}
        />
      )}
      {sheet === 'notifs' && (
        <BellSheet
          bell={bell}
          onOpen={(n) => void openNotification(n)}
          onClose={() => setSheet(null)}
        />
      )}
    </>
  );
}
