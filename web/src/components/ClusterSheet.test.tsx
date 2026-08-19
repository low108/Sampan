import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ClusterSheet } from './ClusterSheet';
import type { Pin } from '../types';

/* Three of her pins sit within a few hundred metres of each other, so at any
 * usable zoom the map draws them as one marker. The old page listened for
 * `sampan-pin` and not `sampan-cluster`, so tapping that marker did nothing at
 * all and the map felt dead. These cover the sheet that now catches it. */

const pin = (id: string, title: string, year: number | null): Pin => ({
  id,
  title,
  lat: 4.6,
  lng: 101.1,
  precision: 'street',
  linked: false,
  year,
  narrator_id: 'ah_khim',
  narrator_name: 'Lim Siew Khim',
});

const PINS = [
  pin('a', 'The coffee shop on Jalan Bandar', 1958),
  pin('b', 'The last cup of Milo', 1969),
  pin('c', 'The wedding photograph', 1968),
];

describe('ClusterSheet', () => {
  it('lists every story sharing the dot', () => {
    render(<ClusterSheet pins={PINS} onPick={vi.fn()} onClose={vi.fn()} />);

    expect(screen.getByText('3 stories here')).toBeInTheDocument();
    for (const p of PINS) expect(screen.getByText(p.title)).toBeInTheDocument();
  });

  it('shows the years it spans, earliest first', () => {
    render(<ClusterSheet pins={PINS} onPick={vi.fn()} onClose={vi.fn()} />);

    expect(screen.getByText('1958–1969')).toBeInTheDocument();
  });

  it('opens the story that was tapped', async () => {
    const onPick = vi.fn();
    render(<ClusterSheet pins={PINS} onPick={onPick} onClose={vi.fn()} />);

    await userEvent.click(screen.getByText('The last cup of Milo'));

    expect(onPick).toHaveBeenCalledWith('b');
  });

  it('says so rather than guessing when a story has no year', () => {
    render(
      <ClusterSheet pins={[pin('d', "Grandfather's crossing", null)]} onPick={vi.fn()} onClose={vi.fn()} />,
    );

    expect(screen.getByText('year not yet told')).toBeInTheDocument();
  });
});
