import { useState } from 'react';
import { api, givenName, initial } from '../api';
import { SampanMap } from '../SampanMap';
import { Chapters } from './Chapters';
import { Retrieval } from './Retrieval';
import type { ChatLine, Member, MemberTab, Pin } from '../types';

interface Props {
  person: Member;
  /** The viewer's given name. Anything queued from this page is attributed to
   *  them by name — the agent never takes credit, so it needs a real one. */
  me: string;
  /** Sending a question changes what the bell holds, so the shell reloads. */
  onSent: () => void;
  tab: MemberTab;
  onTab: (t: MemberTab) => void;
  pins: Pin[];
  selected: string | null;
  onPin: (id: string) => void;
  onCluster: (ids: string[]) => void;
  onBlank: () => void;
}

/* Tab labels carry the member's own name rather than a pronoun.
 *
 * "Her map" was wrong on two of the three people in this household, and
 * wrong in a way nobody would report as a bug — it just quietly told you the
 * archive was about one person. Names are also shorter than the alternatives
 * and read as more personal, which is the right trade at 10.5px. */
const tabsFor = (name: string): [MemberTab, string][] => [
  ['chat', `Ask about ${name}`],
  ['map', `${name}'s map`],
  ['chapters', `${name}'s chapters`],
  ['graph', 'Inside the memory'],
  ['ask', 'Leave a question'],
];

export function MemberPage(props: Props) {
  const { person, tab, onTab, me, onSent } = props;
  const who = givenName(person.display_name);

  const subtabs = (
    <div className="subtabs">
      {tabsFor(who).map(([id, label]) => (
        <button key={id} onClick={() => onTab(id)} aria-current={tab === id}>
          {label}
        </button>
      ))}
    </div>
  );

  if (tab === 'map') {
    return (
      <>
        {subtabs}
        <SampanMap
          pins={props.pins}
          selected={props.selected}
          onPin={props.onPin}
          onCluster={props.onCluster}
          onBlank={props.onBlank}
          style={{ top: '3rem' }}
        />
      </>
    );
  }

  if (tab === 'chapters') {
    return (
      <>
        {subtabs}
        <div className="page">
          <Chapters narratorId={person.narrator_id} name={who} />
        </div>
      </>
    );
  }

  if (tab === 'graph') {
    return (
      <>
        {subtabs}
        <Retrieval narratorId={person.narrator_id} name={who} />
      </>
    );
  }

  if (tab === 'ask') return <AskForm person={person} subtabs={subtabs} me={me} onSent={onSent} />;
  return <AskAbout person={person} subtabs={subtabs} me={me} onSent={onSent} />;
}

/* ── G · leave a question ─────────────────────────────────────
   The agent never takes credit. Every question it puts to someone carries the
   name of the person who asked, and this form says so before you type. */

function AskForm({
  person,
  subtabs,
  me,
  onSent,
}: {
  person: Member;
  subtabs: React.ReactNode;
  me: string;
  onSent: () => void;
}) {
  /* Prefilled from who you are signed in as, and still editable: the name on
     the question is the whole point, so it is never left blank by default. */
  const [from, setFrom] = useState(me);
  const [question, setQuestion] = useState('');
  const [sent, setSent] = useState('');

  const who = givenName(person.display_name);

  const send = async () => {
    if (!from.trim() || !question.trim()) {
      setSent('Both your name and a question are needed');
      return;
    }
    try {
      await api.ask(person.narrator_id, from.trim(), question.trim());
      setSent(`Sent. ${who} will hear it on the next call.`);
      setQuestion('');
      onSent();
    } catch {
      setSent("Couldn't send. Try again in a moment.");
    }
  };

  return (
    <>
      {subtabs}
      <div className="hero">
        <div className="lbl">Leave a question · {who}</div>
        <h2 className="ttl xl">{who} will be told who asked</h2>
        <p className="prose big">
          Xiao Chuan will bring this up on the next call and say your name
          first. It is a message from you, carried — not a question from a
          machine.
        </p>
      </div>

      <div className="page">
        <div className="col">
          <label htmlFor="askfrom">Who are you</label>
          <input
            id="askfrom"
            value={from}
            placeholder="Wei Lun"
            onChange={(e) => setFrom(e.target.value)}
          />
          <label htmlFor="askq">What would you like to ask</label>
          <textarea
            id="askq"
            value={question}
            placeholder="Did Ah Gong leave anything behind?"
            onChange={(e) => setQuestion(e.target.value)}
          />

          {from.trim() && question.trim() && (
            <div className="quote" style={{ marginTop: 22 }}>
              <div className="face">{initial(from)}</div>
              <div>
                <div className="lbl dim">{who} will hear</div>
                <q style={{ marginTop: 8 }}>
                  {from.trim()} wants to ask you: {question.trim()}
                </q>
              </div>
            </div>
          )}

          <div className="row">
            <button className="btn wide" onClick={() => void send()}>
              Send it to {who}
            </button>
          </div>
          {sent && (
            <p className="prose" style={{ marginTop: 16 }}>
              {sent}
            </p>
          )}
        </div>
      </div>
    </>
  );
}

/* ── F · ask about them ───────────────────────────────────────
   Every answer is assembled only from things they said, and any answer can be
   turned into a question for their next call. */

function AskAbout({
  person,
  subtabs,
  me,
  onSent,
}: {
  person: Member;
  subtabs: React.ReactNode;
  me: string;
  onSent: () => void;
}) {
  const [chat, setChat] = useState<ChatLine[]>([]);
  const [q, setQ] = useState('');

  const who = givenName(person.display_name);

  const ask = async () => {
    const question = q.trim();
    if (!question) return;
    setQ('');
    setChat((c) => [...c, { text: question, mine: true }]);
    try {
      const d = await api.about(person.narrator_id, question);
      setChat((c) => [...c, { text: d.answer, follow: d.follow_up }]);
    } catch {
      setChat((c) => [...c, { text: "Couldn't reach that just now. Try again in a moment." }]);
    }
  };

  /* On demand, never automatic: a timeline is a request and should feel like one. */
  const timeline = async () => {
    setChat((c) => [
      ...c,
      { text: 'Make a timeline', mine: true },
      { text: 'Xiao Chuan is putting it in order…' },
    ]);
    try {
      const d = await api.timeline(person.narrator_id);
      const lines = d.stories.map(
        (s) => `${s.year_from ?? s.year_to ?? 'year not yet told'} · ${s.title}`,
      );
      const text = `${who}'s life\n\n${lines.join('\n')}`;
      setChat((c) => [...c.slice(0, -1), { text }]);
    } catch {
      setChat((c) => [...c.slice(0, -1), { text: "Couldn't put it in order. Try again in a moment." }]);
    }
  };

  const queue = async (question: string) => {
    await api.ask(person.narrator_id, me, question).catch(() => undefined);
    setChat((c) => [...c, { text: `Alright — Xiao Chuan will ask ${who} next call.` }]);
    onSent();
  };

  return (
    <>
      {subtabs}
      <div className="hero">
        <div className="lbl">Ask about {who} · answers use only their words</div>
        <h2 className="ttl xl">{person.display_name}</h2>
        <p className="prose big">
          {person.relation} ·{' '}
          {person.story_count
            ? `${person.story_count} ${person.story_count === 1 ? 'story' : 'stories'} told across ${person.session_count} ${person.session_count === 1 ? 'call' : 'calls'}`
            : 'nothing told yet'}
        </p>
      </div>

      <div className="page">
        <div className="col">
          {chat.length === 0 && (
            <p className="empty">
              Ask anything about {who}. Nothing here is invented — if it was
              never said out loud, the answer says so.
            </p>
          )}
          {chat.map((m, i) => (
            <div key={i} className={m.mine ? 'bubble mine' : 'bubble'}>
              {m.text}
              {m.follow && (
                <>
                  <div className="lbl dim" style={{ marginTop: 16 }}>
                    Worth asking {who}
                  </div>
                  <p className="prose" style={{ marginTop: 8 }}>
                    {m.follow}
                  </p>
                  <div className="row">
                    <button className="btn accent" onClick={() => void queue(m.follow!)}>
                      Ask this next call
                    </button>
                  </div>
                </>
              )}
            </div>
          ))}

          <label htmlFor="q">Ask about {who}</label>
          <input
            id="q"
            value={q}
            placeholder="What did their father do for a living?"
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void ask();
            }}
          />
          <div className="row">
            <button className="btn" onClick={() => void ask()}>
              Ask
            </button>
            <button className="btn ghost" onClick={() => void timeline()}>
              Make a timeline
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
