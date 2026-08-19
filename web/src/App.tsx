import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, api, givenName, initial, ME } from './api';
import { SampanMap } from './SampanMap';
import { BellSheet } from './components/BellSheet';
import { ClusterSheet } from './components/ClusterSheet';
import { MemberPage } from './components/MemberPage';
import { StorySheet } from './components/StorySheet';
import { UnplacedSheet } from './components/UnplacedSheet';
import { ViewerSheet } from './components/ViewerSheet';
import { useRecorder } from './useRecorder';
import type { Bell, Household, MemberTab, Notification, Pin, Sheet, Tab } from './types';

/* "Her side" named the wrong thing: this screen is whoever is holding the
 * phone, and three people in this household record. */
const TABS: [Tab, string][] = [
  ['map', 'Map'],
  ['record', 'Tell a story'],
  ['family', 'Household'],
];

/* The legend describes the pin, not the person. Two of the three people in
 * this archive are not her, and their pins land on this same map. */
const LEGEND: [string, string][] = [
  ['named', 'Named in the telling'],
  ['guessed', 'The system guessed'],
  ['cluster', 'Several stories'],
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
  /* Set when the teller has chosen "later". The question stays waiting on the
   * server; this only stops the app putting it in front of them again now. */
  const [deferred, setDeferred] = useState(false);
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

  /* The recording screen asks the server what is waiting the moment it opens,
   * however it was reached. Before, only the bell route did, so opening it
   * directly never showed a question that was sitting there. */
  useEffect(() => {
    if (tab !== 'record' || member !== null) return;
    let live = true;
    void api
      .pending(ME)
      .then((p) => {
        if (!live) return;
        setRecQuestion(
          p.waiting && p.from_name && p.question
            ? { from_name: p.from_name, question: p.question }
            : null,
        );
        setRecNote(
          !p.waiting && p.quiet_hours
            ? 'It is late now. Xiao Chuan will bring you this question in the morning.'
            : '',
        );
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [tab, member]);

  const members = house?.members ?? [];
  const person = useMemo(
    () => members.find((m) => m.narrator_id === member) ?? null,
    [members, member],
  );

  /* Who is holding the phone. The bell, the waiting question and the name on
   * anything you ask all key off this, so it needs a display name and not the
   * raw id — "ah_khim asked you something" was what the id looked like once it
   * reached the top of someone else's bell. */
  const viewer = members.find((m) => m.narrator_id === ME) ?? null;
  const viewerName = viewer ? givenName(viewer.display_name) : ME;

  /* A full navigation, not a state change: ME is read from the URL once at
   * module load, and half the app would go on believing the old answer. */
  const beViewer = (id: string) => {
    const url = new URL(window.location.href);
    url.searchParams.set('user', id);
    window.location.assign(url.toString());
  };

  /* On a member's own map, only their pins. */
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
      /* Before switching, tell the server this is the one she picked. The
       * recording screen and the voice agent both read the same queue, so
       * without this both would open on whatever question is oldest —
       * "Wei Lun asked you something" led to the agent asking her about
       * something else entirely, in someone else's name. */
      await api.chooseAsk(ME, n.target).catch(() => undefined);
      setDeferred(false);
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

  /* Turning a story into a question is the bridge working in the other
   * direction, so it carries the asker's name exactly as the form does — and
   * refreshes the bell, because a question you just sent that leaves the badge
   * unchanged looks like it went nowhere. */
  const askAboutStory = (pin: Pin) => {
    void api
      .ask(pin.narrator_id, viewerName, `Tell me more about ${pin.title}.`)
      .then(load)
      .catch(() => undefined);
  };

  const onMap = tab === 'map' || (member !== null && memberTab === 'map');
  const tellerSide = tab === 'record' && member === null;

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

  const unplaced = house?.unplaced ?? [];
  const openStory = story ? pinById(story) : undefined;
  const somethingNew = (bell?.unseen ?? 0) > 0;

  return (
    <>
      {/* The recording screen carries no chrome at all: no nav, no bell, no brand. */}
      {!tellerSide && (
        <header className="top">
          <div className="brand">
            {person ? (
              <>
                <button
                  className="back"
                  aria-label="Back"
                  onClick={() => {
                    setMember(null);
                    setStory(null);
                  }}
                >
                  ‹
                </button>
                <span className="who">{givenName(person.display_name)}</span>
                <span className="lbl dim">{person.relation}</span>
              </>
            ) : (
              <>
                <h1>Sampan</h1>
                <span className="lbl dim">Xiao Chuan</span>
              </>
            )}
          </div>
          <div className="headbar">
            {/* Who you are, and a way to be someone else.
             *
             * There is no login: the viewer is the `user` query parameter, and
             * everything personal keys off it — whose questions are waiting,
             * whose bell this is, who a recording is attributed to. Without a
             * control the parameter was invisible, so the app could only ever
             * be demonstrated as one person and the family half of the product
             * was unreachable. This is a demo affordance and says so. */}
            <button className="asme" onClick={() => setSheet('viewer')}>
              As {viewerName}
            </button>
            <button
              className="bell"
              data-new={somethingNew}
              aria-label="Messages"
              onClick={() => setSheet('notifs')}
            >
              Bell{bell?.unseen ? <b>{bell.unseen}</b> : null}
            </button>
          </div>
        </header>
      )}

      <main className={onMap || tellerSide ? 'nopad' : ''}>
        {person ? (
          <MemberPage
            person={person}
            me={viewerName}
            onSent={() => void load()}
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
            {/* Uncertainty is drawn, not written — so the map states it once,
                in the corner, and never explains a pin in a sentence. */}
            <div className="map-legend">
              <div className="lbl on-dark">Drag to move · pinch to zoom · tap a number</div>
              {LEGEND.map(([kind, label]) => (
                <div key={kind} className="key">
                  <s className={kind} />
                  <span className="lbl on-dark">{label}</span>
                </div>
              ))}
            </div>
            {/* Absence is a place on the page: docked, and never dismissable. */}
            {unplaced.length > 0 && (
              <button className="tray" onClick={() => setSheet('unplaced')}>
                <div className="lbl">No place at all · {unplaced.length}</div>
                <p className="prose">
                  Told in full, never located — the only place named was{' '}
                  <em>{unplaced[0]?.where_said}</em>.
                </p>
                <div className="pills">
                  <span className="pill dash">Open the tray</span>
                </div>
              </button>
            )}
          </>
        ) : tab === 'record' ? (
          <TellerSide
            question={deferred ? null : recQuestion}
            note={recNote}
            live={recorder.state === 'live'}
            said={recorder.said}
            onToggle={() => void recorder.toggle()}
            onLater={() => setDeferred(true)}
          />
        ) : (
          <>
            <div className="hero">
              <div className="lbl">
                {members.length} {members.length === 1 ? 'person' : 'people'} · one archive
              </div>
              <h2 className="ttl xl">Household</h2>
              <p className="prose big">
                Everything here was said out loud by someone in this list. Open
                a name to walk through what they have told.
              </p>
            </div>
            <div className="people">
              {members.map((m) => (
                <button
                  key={m.narrator_id}
                  className="person"
                  onClick={() => {
                    setMember(m.narrator_id);
                    setMemberTab('chat');
                    setStory(null);
                  }}
                >
                  <div className="face l">{initial(m.display_name)}</div>
                  <div style={{ minWidth: 0 }}>
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
                  <span className="go">›</span>
                </button>
              ))}
            </div>
          </>
        )}
      </main>

      {!person && !tellerSide && (
        <nav className="tabs">
          {TABS.map(([id, label]) => (
            <button
              key={id}
              onClick={() => {
                setTab(id);
                setMember(null);
                setStory(null);
              }}
              aria-current={tab === id}
            >
              {label}
            </button>
          ))}
        </nav>
      )}

      {/* Her side has one way back, and it is not a tab bar — nor a 10.5px
          mono pill, which is exactly the thing her screens may not contain.
          It is set at her scale like everything else she has to read. */}
      {tellerSide && recorder.state !== 'live' && (
        <button className="teller-back" onClick={() => setTab('map')}>
          Back to the family view
        </button>
      )}

      {openStory && (
        <StorySheet
          pin={openStory}
          onClose={() => setStory(null)}
          onCorrect={correctPin}
          onAsk={askAboutStory}
        />
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
      {sheet === 'viewer' && (
        <ViewerSheet
          members={members}
          current={ME}
          onPick={beViewer}
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

/* ═══ THE TELLER'S SIDE · I, J, K ═════════════════════════════
   Three states, one at a time, and never more than one decision on screen.
   Nothing below 22px, nothing smaller than a thumb, and no mono label the
   person recording has to read. */

interface TellerProps {
  question: { from_name: string; question: string } | null;
  note: string;
  live: boolean;
  said: string;
  onToggle: () => void;
  onLater: () => void;
}

export function TellerSide({ question, note, live, said, onToggle, onLater }: TellerProps) {
  /* J · RECORDING — dark so the room stays quiet, lime only in the waveform,
     because the waveform is the proof it is hearing her. */
  if (live) return <Recording said={said} onStop={onToggle} />;

  /* K · A QUESTION ARRIVES — his face is the biggest thing on the screen,
     then his question, then one action. "Later" is always available and is
     never a dead end. */
  if (question) {
    return (
      <div className="teller">
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}>
          <div className="face xl">{initial(question.from_name)}</div>
          <p className="say" style={{ textAlign: 'center' }}>
            {question.from_name} wants to ask you something
          </p>
        </div>
        <div className="mid">
          <div className="asked">
            <q>{question.question}</q>
          </div>
        </div>
        <div className="actions">
          <button className="go" onClick={onToggle}>
            I'll tell {question.from_name}
          </button>
          <button onClick={onLater}>Another time</button>
        </div>
      </div>
    );
  }

  /* I · WAITING — one button, thumb-height, and nothing else to decide. */
  return (
    <div className="teller">
      <div>
        <p className="say">Talk any time you like.</p>
        <p className="sub">
          {note || 'Nobody is waiting on the line. Say whatever comes to mind.'}
        </p>
      </div>
      <div className="mid">
        <button className="bigbtn" onClick={onToggle}>
          Talk
        </button>
        <p className="hint">
          Press it when you want to.
          <br />
          You don't have to wait for a call.
        </p>
      </div>
    </div>
  );
}

function Recording({ said, onStop }: { said: string; onStop: () => void }) {
  const [secs, setSecs] = useState(0);
  const started = useRef(Date.now());

  useEffect(() => {
    const t = setInterval(() => setSecs(Math.floor((Date.now() - started.current) / 1000)), 500);
    return () => clearInterval(t);
  }, []);

  const clock = `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`;
  const bars = [46, 92, 64, 120, 78, 54, 100];

  return (
    <div className="teller dark">
      <div>
        <p className="say">I'm listening.</p>
        <p className="sub">{said || 'Take your time.'}</p>
      </div>
      <div className="mid">
        <div className="wave" aria-hidden="true">
          {bars.map((h, i) => (
            <span
              key={i}
              style={{ height: `${h}px`, animationDelay: `${i * 0.12}s` }}
            />
          ))}
        </div>
        <div className="elapsed">{clock}</div>
      </div>
      <div className="actions">
        <button className="stopbtn" onClick={onStop}>
          That's enough
        </button>
        <p className="hint">Go slowly. There is no time limit.</p>
      </div>
    </div>
  );
}
