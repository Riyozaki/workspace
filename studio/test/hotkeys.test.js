import { test } from 'node:test';
import assert from 'node:assert/strict';
import { normalizeBinding, bindingFromEvent, HotkeyRegistry, createDefaultHotkeys, HotkeyError } from '../src/hotkeys.js';

test('normalizeBinding makes modifier order and case irrelevant', () => {
  assert.equal(normalizeBinding('shift+ctrl+z'), 'Ctrl+Shift+Z');
  assert.equal(normalizeBinding('Control + Shift + z'), 'Ctrl+Shift+Z');
  assert.equal(normalizeBinding('delete'), 'Delete');
  assert.equal(normalizeBinding('cmd+s'), 'Meta+S');
});

test('invalid bindings are rejected with a message', () => {
  assert.throws(() => normalizeBinding(''), HotkeyError);
  assert.throws(() => normalizeBinding('Ctrl+'), HotkeyError);
  assert.throws(() => normalizeBinding('a+b'), /больше одной/);
});

test('bindingFromEvent produces canonical names from key events', () => {
  assert.equal(bindingFromEvent({ key: 'z', ctrlKey: true, shiftKey: true }), 'Ctrl+Shift+Z');
  assert.equal(bindingFromEvent({ key: '1' }), '1');
  assert.equal(bindingFromEvent({ key: 'Shift', shiftKey: true }), null);
  assert.equal(bindingFromEvent({ key: 'Delete' }), 'Delete');
});

test('registry refuses a binding already owned by another action', () => {
  const reg = new HotkeyRegistry();
  reg.bind('a', 'Ctrl+K');
  assert.throws(() => reg.bind('b', 'ctrl+k'), /уже назначено действию «a»/);
  assert.equal(reg.resolve('Ctrl+K'), 'a');
});

test('rebinding an action frees its old key', () => {
  const reg = new HotkeyRegistry();
  reg.bind('a', 'Ctrl+K');
  reg.bind('a', 'Ctrl+J');
  assert.equal(reg.resolve('Ctrl+K'), null);
  reg.bind('b', 'Ctrl+K');
  assert.equal(reg.resolve('Ctrl+K'), 'b');
});

test('default bindings have no conflicts', () => {
  const reg = createDefaultHotkeys();
  assert.equal(reg.list().length, 19);
  assert.equal(reg.resolve('Ctrl+Shift+Z'), 'edit.redo');
});
