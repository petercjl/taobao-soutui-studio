import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const read = relative => JSON.parse(fs.readFileSync(path.join(root, relative), 'utf8'));
const pkg = read('package.json');
const skill = 'skills/taobao-soutui-studio';
const sync = process.argv.includes('--sync');
const manifestPath = skill + '/package.json';
if (sync) {
  for (const [file, data] of [
    ['capabilities.json', { ...read('capabilities.json'), version: pkg.version }],
    [manifestPath, { name: 'taobao-soutui-studio-skill', version: pkg.version, ownerPackage: pkg.name }],
  ]) fs.writeFileSync(path.join(root, file), JSON.stringify(data, null, 2) + '\n');
}

const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const inventory = {};
function walk(relative) {
  for (const entry of fs.readdirSync(path.join(root, relative), { withFileTypes: true }).sort((a,b) => a.name.localeCompare(b.name))) {
    if (entry.name === '__pycache__' || entry.name === '.DS_Store') continue;
    const file = relative + '/' + entry.name;
    if (entry.isDirectory()) walk(file);
    else if (entry.isFile()) inventory[file] = hash(path.join(root,file));
    else throw new Error('UNSUPPORTED_SKILL_FILE: ' + file);
  }
}
walk(skill);
for (const file of ['capabilities.json', 'INSTALL.md', 'UPDATE.md', pkg.bin['taobao-soutui-studio']]) {
  inventory[file] = hash(path.join(root,file));
}
const expected = { package: pkg.name, version: pkg.version, files: inventory };
if (sync) fs.writeFileSync(path.join(root,'skill-integrity.json'), JSON.stringify(expected,null,2) + '\n');
if (read(manifestPath).version !== pkg.version || read('capabilities.json').version !== pkg.version) {
  throw new Error('PACKAGE_SKILL_VERSION_DRIFT');
}
if (JSON.stringify(read('skill-integrity.json')) !== JSON.stringify(expected)) {
  throw new Error('PACKAGE_INTEGRITY_MISMATCH');
}
