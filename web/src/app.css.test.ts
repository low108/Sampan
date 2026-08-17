import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

/* A stacking-context bug has no runtime error and no failing assertion: the
 * sheet is in the DOM, has the right content, reports the right z-index, and
 * is simply painted underneath the map. It cost a round of "the card is
 * blocked by the map" to find, so the rule that fixes it is pinned here.
 *
 * jsdom does no layout, so this reads the stylesheet rather than measuring.
 * It cannot prove the stacking is right; it can prove nobody deleted the line
 * that makes it right.
 */
const css = readFileSync(join(__dirname, 'app.css'), 'utf8');

const rule = (selector: string): string => {
  const at = css.indexOf(selector);
  expect(at, `${selector} is missing from app.css`).toBeGreaterThan(-1);
  return css.slice(at, css.indexOf('}', at));
};

describe('map stacking', () => {
  it('the map wrapper contains its own stacking context', () => {
    /* Leaflet numbers panes from 400 and controls up to 1000. Without a
       context here those compete with the whole app, and the zoom buttons and
       attribution strip paint straight through an open story card. */
    const maprap = rule('.maprap {');

    expect(maprap).toContain('isolation: isolate');
    expect(maprap).toContain('z-index: 0');
  });

  it('the sheet and its scrim sit above anything the map can contain', () => {
    const sheetZ = Number(/z-index:\s*(\d+)/.exec(rule('.sheet {'))?.[1]);
    const scrimZ = Number(/z-index:\s*(\d+)/.exec(rule('.scrim {'))?.[1]);

    expect(scrimZ).toBeGreaterThan(0);
    expect(sheetZ).toBeGreaterThan(scrimZ);
  });
});
