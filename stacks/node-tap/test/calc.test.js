import assert from 'node:assert/strict';
import test from 'node:test';
import { add, divide } from '../src/calc.js';

test('adds', () => {
  assert.equal(add(2, 3), 5);
});

test('divides', () => {
  assert.equal(divide(9, 3), 3);
});

test('refuses to divide by zero', () => {
  assert.throws(() => divide(1, 0), /division by zero/);
});
