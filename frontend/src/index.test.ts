import { describe, expect, it } from 'vitest';
import { placeholder } from './index';

describe('placeholder', () => {
  it('returns the project name', () => {
    expect(placeholder()).toBe('sparc');
  });
});
