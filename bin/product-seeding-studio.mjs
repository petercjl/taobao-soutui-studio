#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { runMaintenance, maintenanceManifest } from '../src/package-runtime.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
const tool = 'product-seeding-studio';
const config = {
  root, name: pkg.name, version: pkg.version, tool, skills: [tool],
  skillRoot: 'skills', entry: pkg.bin[tool], runtimeItems: [...pkg.files, 'package.json'],
  targetEnvironment: 'PRODUCT_SEEDING_STUDIO_SKILL_TARGET',
};
const [command = 'help', ...args] = process.argv.slice(2);
const print = value => console.log(JSON.stringify(value));

try {
  if (command === 'version' || command === '--version') {
    if (args.includes('--json')) print({ ok: true, package: pkg.name, version: pkg.version });
    else console.log(pkg.version);
  } else if (['skill', 'update', 'operation'].includes(command)) {
    await runMaintenance(config, command, args);
  } else if (command === 'capabilities') {
    print(maintenanceManifest(config));
  } else if (command === 'doctor' && !args.includes('--help')) {
    const runtime = spawnSync(process.execPath, [path.join(root, 'src/identity.mjs')], { encoding: 'utf8' });
    const python = spawnSync(process.platform === 'win32' ? 'python' : 'python3', ['-c',
      'import sys; assert sys.version_info >= (3, 10); import PIL'], { encoding: 'utf8' });
    print({ ok: runtime.status === 0, package: pkg.name, version: pkg.version,
      integrity: runtime.status === 0, businessReady: python.status === 0,
      dependencies: { pythonAndPillow: python.status === 0, serviceSkills: 'verify-at-use' } });
    if (runtime.status !== 0) process.exitCode = 1;
  } else if (command === 'help' || command === '--help' || command === 'doctor') {
    print(maintenanceManifest(config));
  } else {
    throw Object.assign(new Error('Unknown command'), { code: 'UNKNOWN_COMMAND' });
  }
} catch (error) {
  console.error(JSON.stringify({ ok: false, code: error.code ?? 'RUNTIME_ERROR', message: error.message }));
  process.exitCode = 1;
}
