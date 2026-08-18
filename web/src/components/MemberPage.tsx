import { useState } from 'react';
import { api, givenName, ME } from '../api';
import { SampanMap } from '../SampanMap';
import { Chapters } from './Chapters';
import type { ChatLine, Member, MemberTab, Pin } from '../types';

interface Props {
  person: Member;
  tab: MemberTab;
  onTab: (t: MemberTab) => void;
  pins: Pin[];
  selected: string | null;
  onPin: (id: string) => void;
  onCluster: (ids: string[]) => void;
  onBlank: () => void;
}

const TABS: [MemberTab, string][] = [
  ['chat', 'Ask about her'],
  ['map', 'Her map'],
  ['chapters', 'Her chapters'],
  ['ask', 'Leave a question'],
];

export function MemberPage(props: Props) {
  const { person, tab, onTab } = props;

  const subtabs = (
    <div className="subtabs">
      {TABS.map(([id, label]) => (
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
          style={{ top: '4rem' }}
        />
      </>
    );
  }

  if (tab === 'chapters') {
    return (
      <div className="pad">
        {subtabs}
        <Chapters narratorId={person.narrator_id} />
      </div>
    );
  }

  if (tab === 'ask') return <AskForm person={person} subtabs={subtabs} />;
  return <AskAbout person={person} subtabs={subtabs} />;
}

/* ── leave a question ─────────────────────────────────────────── */

function AskForm({ person, subtabs }: { person: Member; subtabs: React.ReactNode }) {
  const [from, setFrom] = useState('');
  const [question, setQuestion] = useState('');
  const [sent, setSent] = useState('');

  const send = async () => {
    if (!from.trim() || !question.trim()) {
      setSent('Both your name and a question are needed');
      return;
    }
    try {
      await api.ask(person.narrator_id, from.trim(), question.trim());
      setSent('Sent. She will hear it when she next picks up.');
      setQuestion('');
    } catch {
      setSent("Couldn't send. Try again in a moment.");
    }
  };

  return (
    <div className="pad">
      {subtabs}
      <p>
        Leave a question for {givenName(person.display_name)}. Xiao Chuan will ask it on
        the next call — and say that it came from you.
      </p>
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
      <div className="row">
        <button className="btn" onClick={() => void send()}>
          Send
        </button>
      </div>
      <p className="en">{sent}</p>
    </div>
  );
}

/* ── ask about her ────────────────────────────────────────────── */

function AskAbout({ person, subtabs }: { person: Member; subtabs: React.ReactNode }) {
  const [chat, setChat] = useState<ChatLine[]>([]);
  const [q, setQ] = useState('');

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
      { text: 'Make her timeline', mine: true },
      { text: 'Xiao Chuan is putting it in order…' },
    ]);
    try {
      const d = await api.timeline(person.narrator_id);
      const lines = d.stories.map(
        (s) => `${s.year_from ?? s.year_to ?? 'year not yet told'} · ${s.title}`,
      );
      const text = `${givenName(person.display_name)}'s life\n\n${lines.join('\n')}`;
      setChat((c) => [...c.slice(0, -1), { text }]);
    } catch {
      setChat((c) => [...c.slice(0, -1), { text: "Couldn't put it in order. Try again in a moment." }]);
    }
  };

  const queue = async (question: string) => {
    await api.ask(person.narrator_id, givenName(ME), question).catch(() => undefined);
    setChat((c) => [...c, { text: 'Alright — Xiao Chuan will ask her next call.' }]);
  };

  return (
    <div className="pad">
      {subtabs}
      {chat.length === 0 && (
        <p className="empty">Ask anything about {givenName(person.display_name)}.</p>
      )}
      {chat.map((m, i) => (
        <div key={i} className={m.mine ? 'bubble mine' : 'bubble'}>
          {m.text}
          {m.follow && (
            <>
              <p className="gap">
                <b>Worth asking her</b> · {m.follow}
              </p>
              <button className="btn ghost small" onClick={() => void queue(m.follow!)}>
                Ask her this next call ›
              </button>
            </>
          )}
        </div>
      ))}
      <label htmlFor="q">Ask about her</label>
      <input
        id="q"
        value={q}
        placeholder="What did her father do for a living?"
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
          Make her timeline
        </button>
      </div>
    </div>
  );
}
