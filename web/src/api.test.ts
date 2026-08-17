import { describe, expect, it } from 'vitest';
import { givenName, initial } from './api';

describe('givenName', () => {
  /* The bell read "Lim told 9 new stories" for months. Lim is the surname half
     the household shares, so the notification named nobody. */
  it('drops the surname from a surname-first name', () => {
    expect(givenName('Lim Siew Khim')).toBe('Siew Khim');
    expect(givenName('Tan Wei Lun')).toBe('Wei Lun');
    expect(givenName('Tan Xin Yi')).toBe('Xin Yi');
  });

  it('leaves a single name alone', () => {
    expect(givenName('Khim')).toBe('Khim');
  });

  it('survives the whitespace a form will hand it', () => {
    expect(givenName('  Lim   Siew Khim  ')).toBe('Siew Khim');
    expect(givenName('')).toBe('');
  });
});

describe('initial', () => {
  it('takes the first letter for the avatar', () => {
    expect(initial('Lim Siew Khim')).toBe('L');
  });

  it('never returns undefined for an empty name', () => {
    expect(initial('')).toBe('?');
    expect(initial('   ')).toBe('?');
  });
});
