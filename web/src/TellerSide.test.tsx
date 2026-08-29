import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { TellerSide } from './App';

/* Her three screens, and the rules that make them hers.
 *
 * These exist because two of the three cannot be reached by hand at will: the
 * question screen only appears when a family question is waiting AND the
 * server is not in quiet hours, and the recording screen needs a microphone.
 * Testing them from the outside is the only way the rules below stay checked.
 *
 * The rules, from the brief: nothing the teller has to read is below 22px, no
 * touch target is under 64px, and any question shown to them carries the name of the
 * person who asked. "No senior mode" is what makes these load-bearing — the
 * scale is the accommodation, so if it drifts there is nothing else.
 */

describe('teller side · waiting', () => {
  it('offers one thing to press and nothing else', () => {
    render(
      <TellerSide question={null} note="" live={false} said="" kept={null} onToggle={vi.fn()} onLater={vi.fn()} />,
    );

    expect(screen.getAllByRole('button')).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Talk' })).toBeInTheDocument();
  });

  it('explains the silence when the server is holding a question back', () => {
    const note = 'It is late now. Xiao Chuan will bring you this question in the morning.';
    render(
      <TellerSide question={null} note={note} live={false} said="" kept={null} onToggle={vi.fn()} onLater={vi.fn()} />,
    );

    /* Arriving at an apparently empty screen after the bell said someone had
       asked something reads as broken. The reason is deliberate, so it is said. */
    expect(screen.getByText(note)).toBeInTheDocument();
  });
});

describe('teller side · a question arrives', () => {
  const question = { from_name: 'Wei Lun', question: 'Why did Ah Gong close the shop in the end?' };

  it('says who asked, in his own name', () => {
    render(
      <TellerSide question={question} note="" live={false} said="" kept={null} onToggle={vi.fn()} onLater={vi.fn()} />,
    );

    /* The agent never takes credit. It is his question, carried. */
    expect(screen.getByText('Wei Lun wants to ask you something')).toBeInTheDocument();
    expect(screen.getByText(question.question)).toBeInTheDocument();
  });

  it('always offers a way out that is not a dead end', async () => {
    const onLater = vi.fn();
    const onToggle = vi.fn();
    render(
      <TellerSide question={question} note="" live={false} said="" kept={null} onToggle={onToggle} onLater={onLater} />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Another time' }));

    expect(onLater).toHaveBeenCalled();
    expect(onToggle).not.toHaveBeenCalled();
  });

  it('starts them talking when they agree to answer', async () => {
    const onToggle = vi.fn();
    render(
      <TellerSide question={question} note="" live={false} said="" kept={null} onToggle={onToggle} onLater={vi.fn()} />,
    );

    await userEvent.click(screen.getByRole('button', { name: "I'll tell Wei Lun" }));

    expect(onToggle).toHaveBeenCalled();
  });
});

describe('teller side · recording', () => {
  it('gives them one control, and it is the one that stops', () => {
    render(
      <TellerSide question={null} note="" live={true} said="" kept={null} onToggle={vi.fn()} onLater={vi.fn()} />,
    );

    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(1);
    expect(buttons[0]).toHaveTextContent("That's enough");
  });

  it('shows it is listening rather than saying so twice', () => {
    render(
      <TellerSide question={null} note="" live={true} said="" kept={null} onToggle={vi.fn()} onLater={vi.fn()} />,
    );

    expect(screen.getByText("I'm listening.")).toBeInTheDocument();
    expect(screen.getByText('0:00')).toBeInTheDocument();
  });
});

/* jsdom does no layout and loads no stylesheet, so a computed font-size here
   is always NaN. Read the declarations instead — the same approach the map
   stacking test takes, and for the same reason: this cannot prove the pixels,
   but it can prove nobody removed the floor. */
const css = readFileSync(join(__dirname, 'app.css'), 'utf8');

const decl = (selector: string, prop: string): string => {
  const at = css.indexOf(selector);
  expect(at, `${selector} is missing from app.css`).toBeGreaterThan(-1);
  const body = css.slice(at, css.indexOf('}', at));
  const hit = new RegExp(`${prop}:\\s*([^;]+)`).exec(body)?.[1];
  expect(hit, `${selector} does not set ${prop}`).toBeDefined();
  return (hit ?? '').trim();
};

describe('teller scale', () => {
  it('keeps the floor at 22px and 64px', () => {
    /* Every size on a recording screen is written against these two, so raising a
       control above the floor is a local edit and lowering the floor is not. */
    expect(Number.parseFloat(decl('--teller-body:', '--teller-body'))).toBeGreaterThanOrEqual(22);
    expect(Number.parseFloat(decl('--teller-target:', '--teller-target'))).toBeGreaterThanOrEqual(64);
  });

  it.each([
    ['.teller .actions button {', 'min-height'],
    ['.teller .from {', 'min-height'],
    ['.teller-back {', 'min-height'],
  ])('sizes %s from the floor rather than a literal', (selector, prop) => {
    expect(decl(selector, prop)).toBe('var(--teller-target)');
  });

  it('sets every control on a recording screen above 22px', () => {
    for (const selector of ['.bigbtn {', '.stopbtn {', '.teller .actions button {', '.teller-back {']) {
      const size = decl(selector, 'font-size');
      const px = size.startsWith('var(') ? 22 : Number.parseFloat(size);
      expect(px, `${selector} font-size is ${size}`).toBeGreaterThanOrEqual(22);
    }
  });

  it('uses no letterspaced mono anywhere under .teller', () => {
    /* The 10.5px mono label is the family side's signature and is illegible
       to someone with presbyopia. It may decorate a recording screen; it may
       never carry something the teller has to read — so it is simply absent. */
    const scoped = css.slice(css.indexOf('.teller {'), css.indexOf('.failed {'));

    expect(scoped).not.toContain('--mono');
    expect(scoped).not.toContain('10.5px');
  });
});

describe('teller side · what her telling left behind', () => {
  const kept = {
    story_id: 's1',
    title: 'Buying curry puffs at Jalan Bandar with Mrs. Rajan',
    where: 'Jalan Bandar, Ipoh',
    at: '2026-08-27T03:08:47+00:00',
  };

  /* She talks, and then nothing on her screen ever changed to say it landed.
     The family side is the proof, and the family side is the side she does not
     open — so if it is not said here it is not said to her at all. */
  it('tells her what was kept, in the words she gave it', () => {
    render(
      <TellerSide question={null} note="" kept={kept} live={false} said="" onToggle={vi.fn()} onLater={vi.fn()} />,
    );

    expect(screen.getByText(/Buying curry puffs at Jalan Bandar/)).toBeInTheDocument();
    expect(screen.getByText(/Jalan Bandar, Ipoh/)).toBeInTheDocument();
  });

  it('still leaves one button to press', () => {
    /* The receipt is news, not an instruction. It must not become a second
       thing to decide about on a screen whose whole design is one choice. */
    render(
      <TellerSide question={null} note="" kept={kept} live={false} said="" onToggle={vi.fn()} onLater={vi.fn()} />,
    );

    expect(screen.getAllByRole('button')).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Talk' })).toBeInTheDocument();
  });

  it('says nothing at all when there is nothing recent', () => {
    render(
      <TellerSide question={null} note="" kept={null} live={false} said="" onToggle={vi.fn()} onLater={vi.fn()} />,
    );

    expect(screen.queryByText(/Kept for your family/)).not.toBeInTheDocument();
  });

  it('never shows it over a waiting question', () => {
    /* His question outranks her receipt: it is the thing with someone on the
       other end of it. */
    render(
      <TellerSide
        question={{ from_name: 'Wei Lun', question: 'Ah Ma, are you eating properly?' }}
        note=""
        kept={kept}
        live={false}
        said=""
        onToggle={vi.fn()}
        onLater={vi.fn()}
      />,
    );

    expect(screen.queryByText(/Kept for your family/)).not.toBeInTheDocument();
    expect(screen.getByText(/eating properly/)).toBeInTheDocument();
  });
});
