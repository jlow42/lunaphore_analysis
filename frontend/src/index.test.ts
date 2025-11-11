import { describe, expect, it } from 'vitest';
import { App } from './index';

describe('App export', () => {
  it('exposes the root application component', () => {
    expect(App).toBeDefined();
  });
});
