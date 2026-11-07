import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const entry = path.join(root, 'bin/product-seeding-studio.mjs');
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
const invoke = (...args) => spawnSync(process.execPath, [entry, ...args, '--json'], { encoding: 'utf8' });
const ok = result => {
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
};

test('version, discovery and explicit installation contract', () => {
  assert.equal(ok(invoke('version')).version, pkg.version);
  const source = ok(invoke('skill', 'source', '--all'));
  assert.equal(source.complete, true);
  assert.equal(source.sources[0].version, pkg.version);
  assert.equal(source.sources[0].source, path.join(root, 'skills/product-seeding-studio'));
  const missing = invoke('skill', 'install', '--agent', 'agent-test');
  assert.equal(JSON.parse(missing.stderr).code, 'TARGET_REQUIRED');
});

test('managed physical installation, repeat and edit protection', () => {
  const parent = fs.mkdtempSync(path.join(os.tmpdir(), 'soutui-test-'));
  try {
    const target = ['--target-dir', parent, '--agent', 'agent-test'];
    const installed = ok(invoke('skill', 'install', ...target));
    assert.equal(installed.current, true);
    assert.equal(installed.physicalCopy, true);
    assert.equal(ok(invoke('skill', 'update', ...target)).changed, false);
    assert.equal(fs.lstatSync(installed.destination).isSymbolicLink(), false);
    assert.equal(fs.lstatSync(installed.runtimeEntry).isSymbolicLink(), false);
    fs.appendFileSync(path.join(installed.destination, 'SKILL.md'), '\nlocal edit\n');
    assert.equal(JSON.parse(invoke('skill', 'update', ...target).stderr).code, 'TARGET_PROTECTED');
  } finally {
    fs.rmSync(parent, { recursive: true, force: true });
  }
});
