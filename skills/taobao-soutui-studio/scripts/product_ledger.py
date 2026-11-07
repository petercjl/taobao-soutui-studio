#!/usr/bin/env python3
"""Append-only product projects. Local state only; no network or media submission."""
import argparse
import copy
import hashlib
import html
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


class LedgerError(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise LedgerError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_new(path, value):
    path = Path(path)
    need(not path.exists() and not path.is_symlink(), 'OUTPUT_EXISTS: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def load(project, revision=None):
    project = Path(project).resolve()
    files = sorted((project / 'ledger').glob('[0-9]' * 8 + '.json'))
    need(bool(files), 'PROJECT_NOT_FOUND')
    path = project / 'ledger' / f'{revision:08d}.json' if revision is not None else files[-1]
    state = read(path)
    need(project.name == state['itemId'], 'PROJECT_ID_MISMATCH')
    return state


def asset_path(project, path):
    p = Path(path)
    return p.resolve() if p.is_absolute() else (Path(project) / p).resolve()


def verify_asset(project, asset):
    raw = Path(asset['path'])
    raw = raw if raw.is_absolute() else Path(project) / raw
    need(not raw.is_symlink(), 'ASSET_SYMLINK')
    p = raw.resolve()
    need(p.is_file(), 'ASSET_MISSING')
    need(hashlib.sha256(p.read_bytes()).hexdigest() == asset['sha256'], 'ASSET_HASH_MISMATCH')
    return p


def find_batch(state, direction_id, batch_id):
    directions = state['directions'] + [d for plan in state.get('directionPlanHistory', []) for d in plan['directions']]
    direction = next((d for d in directions if d['id'] == direction_id), None)
    need(direction is not None, 'DIRECTION_NOT_FOUND')
    batch = next((b for b in direction.get('batches', []) if b['id'] == batch_id), None)
    need(batch is not None, 'BATCH_NOT_FOUND')
    return direction, batch


def validate(state):
    need(state.get('schemaVersion') == 1 and re.fullmatch(r'\d{1,30}', state['itemId']), 'INVALID_PRODUCT')
    directions = state.get('directions', [])
    need(len(directions) == 9 and len({d['id'] for d in directions}) == 9, 'NINE_UNIQUE_DIRECTIONS_REQUIRED')
    history = state.get('directionPlanHistory', [])
    need(all(len(p['directions']) == 9 for p in history), 'INVALID_PLAN_HISTORY')
    directions = directions + [d for p in history for d in p['directions']]
    need(len({d['id'] for d in directions}) == len(directions), 'DIRECTION_IDS_MUST_BE_GLOBALLY_UNIQUE')
    for direction in directions:
        need(all(direction.get(k) for k in ('id', 'title', 'need', 'scene', 'style', 'narrative', 'copyAngle')), 'INCOMPLETE_DIRECTION')
        batches = direction.get('batches', [])
        need(len({b['id'] for b in batches}) == len(batches), 'DUPLICATE_BATCH')
        for batch in batches:
            candidates = batch['candidates']
            need(len(candidates) <= (batch.get('targetCount', 8)), 'TOO_MANY_CANDIDATES')
            need(batch.get('imported') is True or batch.get('targetCount', 8) == 8 or (batch.get('kind') == 'pilot' and batch.get('targetCount') == 1), 'EIGHT_CANDIDATES_OR_SINGLE_PILOT_REQUIRED')
            ids = [c['id'] for c in candidates]
            need(len(ids) == len(set(ids)), 'DUPLICATE_CANDIDATE_ID')
            need(all(c.get('path') and re.fullmatch(r'[0-9a-f]{64}', c.get('sha256', '')) and c.get('decisionQuestion') for c in candidates), 'INVALID_CANDIDATE')
            selection = batch.get('selection')
            if selection:
                chosen = selection['ids']
                need(3 <= len(chosen) <= 8 and len(set(chosen)) == len(chosen) and set(chosen) <= set(ids), 'SELECT_3_TO_8_UNIQUE_IMAGES')
                need(selection.get('confirmedBy') == 'user' and selection.get('evidence'), 'USER_SELECTION_REQUIRED')


def apply_event(state, event, project):
    state = copy.deepcopy(state)
    op = event['operation']
    if op == 'product':
        need(set(event['values']) <= {'title', 'shopName', 'productName', 'productUrl', 'references', 'facts', 'unknownFacts', 'timezone'}, 'INVALID_PRODUCT_FIELDS')
        state['product'].update(event['values'])
    elif op == 'replan':
        need(event.get('planId') and event.get('reason'), 'PLAN_ID_AND_REASON_REQUIRED')
        plans = state.get('directionPlanHistory', [])
        need(event['planId'] not in [p['id'] for p in plans] + [state.get('directionPlanId', 'v1')], 'PLAN_ID_EXISTS')
        proposed = event['directions']
        need(len(proposed) == 9 and all(not d.get('batches') for d in proposed), 'NEW_PLAN_REQUIRES_NINE_UNGENERATED_DIRECTIONS')
        need(all(all(d.get('visual', {}).get(k) for k in ('environment', 'surface', 'props', 'palette', 'lighting', 'camera', 'composition')) for d in proposed), 'VISUAL_CONTRACT_REQUIRED')
        state.setdefault('directionPlanHistory', []).append({'id': state.get('directionPlanId', 'v1'), 'directions': state['directions'], 'archiveReason': event['reason']})
        state['directionPlanId'] = event['planId']
        state['directions'] = proposed
    elif op == 'plan-direction':
        d = next((d for d in state['directions'] if d['id'] == event['directionId']), None)
        need(d is not None and not d.get('batches'), 'DIRECTION_IN_USE')
        need(set(event['values']) <= {'title', 'need', 'scene', 'style', 'narrative', 'copyAngle', 'difference', 'visual', 'selected'}, 'INVALID_DIRECTION_FIELDS')
        d.update(event['values'])
    elif op == 'add-batch':
        d = next((d for d in state['directions'] if d['id'] == event['directionId']), None)
        need(d is not None, 'DIRECTION_NOT_FOUND')
        b = copy.deepcopy(event['batch'])
        need(not any(x['id'] == b['id'] for x in d.get('batches', [])), 'BATCH_EXISTS')
        need(not b.get('selection') and not b.get('receipts'), 'IMPORT_SELECTION_AND_RECEIPTS_SEPARATELY')
        d.setdefault('batches', []).append(b)
    elif op == 'add-candidate':
        _, b = find_batch(state, event['directionId'], event['batchId'])
        need(not b.get('selection'), 'BATCH_ALREADY_SELECTED')
        c = event['candidate']; verify_asset(project, c)
        b['candidates'].append(c)
    elif op == 'task':
        _, b = find_batch(state, event['directionId'], event['batchId'])
        need(not b.get('selection'), 'BATCH_ALREADY_SELECTED')
        task = event['task']
        need(task.get('taskId') and task.get('candidateId') and task.get('status'), 'INVALID_TASK')
        b.setdefault('tasks', {})[task['candidateId']] = task
    elif op == 'intent':
        _, b = find_batch(state, event['directionId'], event['batchId'])
        need(event['kind'] in ('upload', 'prepare', 'publish'), 'INVALID_INTENT')
        need(event.get('authorization') and event.get('requestId'), 'INTENT_AUTHORIZATION_REQUIRED')
        b.setdefault('intents', []).append({k: event[k] for k in ('kind', 'authorization', 'requestId')})
    elif op == 'select':
        _, b = find_batch(state, event['directionId'], event['batchId'])
        need(not b.get('receipts'), 'RECEIPTED_BATCH_IMMUTABLE: create a new batch for new intent')
        for c in b['candidates']:
            if c['id'] in event['ids']:
                verify_asset(project, c)
        version = b.get('selection', {}).get('version', 0) + 1
        b['selection'] = {'ids': event['ids'], 'version': version, 'confirmedBy': event['confirmedBy'], 'evidence': event['evidence']}
        b.pop('copy', None)
    elif op == 'copy':
        _, b = find_batch(state, event['directionId'], event['batchId'])
        need(b.get('selection') and not b.get('receipts'), 'SELECTION_REQUIRED_OR_BATCH_RECEIPTED')
        b['copy'] = {**event['copy'], 'selectionVersion': b['selection']['version']}
    elif op == 'receipt':
        _, b = find_batch(state, event['directionId'], event['batchId'])
        need(b.get('selection') and b.get('copy'), 'SELECT_AND_COPY_FIRST')
        kind = event['kind']; need(kind in ('upload', 'prepare', 'publish'), 'INVALID_RECEIPT_KIND')
        need(event['selectionVersion'] == b['selection']['version'], 'STALE_SELECTION')
        receipt_path = asset_path(project, event['path']); receipt = read(receipt_path)
        need(receipt.get('shopName') == state['product']['shopName'], 'RECEIPT_SHOP_MISMATCH')
        if kind == 'upload':
            need(receipt.get('status') == 'uploaded' and receipt.get('folderVerified') is True, 'UPLOAD_NOT_VERIFIED')
            chosen = {c['id']: c for c in b['candidates']}
            hashes = [chosen[i]['sha256'] for i in b['selection']['ids']]
            need([f.get('sha256') for f in receipt['files']] == hashes, 'UPLOAD_SELECTION_MISMATCH')
        else:
            need(any(r['kind'] == 'upload' for r in b.get('receipts', [])), 'UPLOAD_RECEIPT_REQUIRED')
            need(str(receipt.get('itemId')) == state['itemId'], 'RECEIPT_ITEM_MISMATCH')
            need(receipt.get('status') in ('prepared', 'published', 'unknown'), 'INVALID_PUBLICATION_STATUS')
            need(kind == 'publish' or receipt.get('status') == 'prepared', 'INVALID_PREPARE_STATUS')
            need(receipt.get('status') != 'published' or receipt.get('contentId'), 'CONTENT_ID_REQUIRED')
        b.setdefault('receipts', []).append({'kind': kind, 'path': str(receipt_path.relative_to(project)) if receipt_path.is_relative_to(project) else str(receipt_path), 'sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest(), 'status': receipt['status'], 'contentId': receipt.get('contentId'), 'listVerified': receipt.get('listVerified'), 'selectionVersion': event['selectionVersion']})
    else:
        raise LedgerError('UNKNOWN_OPERATION')
    validate(state)
    return state


def status(batch, project=None):
    if batch.get('runPath') and project is not None:
        manifest = asset_path(project, batch['runPath']) / '运行清单.json'
        if manifest.is_file():
            return {'complete': '创作已交付', 'partial': '创作部分完成'}.get(
                read(manifest)['status'], '创作中')
        return '运行清单待核实'
    if batch.get('kind') == 'pilot':
        return '待确认单张样图' if len(batch['candidates']) == 1 else '单张调试中'
    receipts = batch.get('receipts', [])
    if any(r['status'] == 'unknown' for r in receipts) and not any(r['status'] == 'published' for r in receipts):
        return '结果待核实'
    if any(r['status'] == 'published' for r in receipts):
        return '已发布'
    if any(r['status'] == 'prepared' for r in receipts):
        return '已填表'
    if any(r['kind'] == 'upload' for r in receipts):
        return '已上传'
    if batch.get('selection'):
        return '已选图' if not batch.get('copy') else '待上传'
    return '待选图' if len(batch['candidates']) == batch.get('targetCount', 8) else '生成中'


def dashboard(state, project):
    esc = lambda x: html.escape(str(x))
    rows = []
    history_directions = [dict(d, title='历史方案 · ' + d['title']) for plan in state.get('directionPlanHistory', []) for d in plan['directions'] if d.get('batches')]
    for d in state['directions'] + history_directions:
        batches = d.get('batches', [])
        label = ' / '.join(status(b, project) for b in batches) or ('待生成' if d.get('selected') else '待选择')
        details = ''
        for b in batches:
            chosen = b.get('selection', {}).get('ids', [])
            receipts = b.get('receipts', [])
            progress = ('✓ 已生成' if len(b['candidates']) == b.get('targetCount', 8) else '□ 生成中') + ' · ' + ('✓ 已选图' if chosen else '□ 待选图') + ' · ' + ('✓ 已上传' if any(r['kind'] == 'upload' for r in receipts) else '□ 未上传') + ' · ' + ('✓ 已发布' if any(r['status'] == 'published' for r in receipts) else '□ 未发布')
            cards = ''
            for c in b['candidates']:
                p = verify_asset(project, c)
                cards += f'<figure><a href="{esc(p.as_uri())}"><img src="{esc(p.as_uri())}"></a><figcaption>{esc(c["id"])} {"✓ 已选" if c["id"] in chosen else "候选"}</figcaption></figure>'
            if b.get('runPath'):
                manifest_path = asset_path(project, b['runPath']) / '运行清单.json'
                link = f'<a href="{esc(manifest_path.as_uri())}">运行清单</a>' if manifest_path.is_file() else ''
                details += f'<details><summary>{esc(b["id"])} · {esc(status(b, project))}</summary>{link}<div class="images">{cards}</div></details>'
                continue
            cp = b.get('copy', {})
            details += f'<p>{esc(progress)}</p><details><summary>{esc(b["id"])} · {esc(status(b, project))} · 选图顺序 {esc(chosen)}</summary><div class="images">{cards}</div><p>{esc(cp.get("title", ""))}</p><pre>{esc(cp.get("body", ""))}</pre></details>'
        visual = d.get('visual', {})
        visual_text = '<p>' + esc(' · '.join(str(visual[k]) for k in ('environment', 'surface', 'props', 'lighting', 'camera') if k in visual)) + '</p>' if visual else ''
        rows.append(f'<article><h2>{esc(d["id"])} · {esc(d["title"])} · {esc(label)}</h2><p>{esc(d["scene"])} / {esc(d["style"])} / {esc(d["copyAngle"])}</p>{visual_text}{details}</article>')
    references = '<details><summary>商品主图及来源</summary><ul>'
    for ref in state['product'].get('references', []):
        local = asset_path(project, ref['path']).as_uri() if ref.get('path') else None
        references += '<li>' + esc(ref.get('order', '')) + ' ' + (f'<a href="{esc(local)}">本地主图</a> ' if local else '') + (f'<a href="{esc(ref["url"])}">原始URL</a>' if ref.get('url') else '') + '</li>'
    references += '</ul></details>'
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>商品搜推台账</title><style>body{font:16px/1.7 system-ui;background:#f6f4ef;padding:24px}article{background:white;padding:20px;margin:16px 0;border-radius:12px}h2{font-size:20px}.images{display:flex;flex-wrap:wrap}figure{width:180px;margin:10px}img{width:100%}pre{white-space:pre-wrap}</style><h1>'+esc(state['product'].get('title', state['itemId']))+'</h1><p>商品 '+esc(state['itemId'])+' · 台账版本 '+str(state['revision'])+'</p>'+references+''.join(rows)


def commit(project, expected, event):
    project = Path(project).resolve()
    lock = project / '.ledger.lock'
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise LedgerError('PROJECT_LOCKED: inspect existing operation; do not remove an active lock')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(json.dumps({'pid': os.getpid(), 'startedAt': datetime.now(timezone.utc).isoformat()}))
        state = load(project)
        need(state['revision'] == expected, 'REVISION_CONFLICT: reload latest state')
        new = apply_event(state, event, project)
        new['revision'] += 1
        new['updatedAt'] = datetime.now(timezone.utc).isoformat()
        new['lastEvent'] = event
        # Exclusive creation preserves all prior revisions, including on interruption.
        write_new(project / 'ledger' / f'{new["revision"]:08d}.json', new)
        return new
    finally:
        lock.unlink()


def export_manifest(project, state, direction_id, batch_id, inspection, local_date, mode):
    _, b = find_batch(state, direction_id, batch_id)
    need(b.get('selection') and b.get('copy'), 'SELECT_AND_COPY_FIRST')
    need(not any(r['kind'] in ('upload', 'publish') for r in b.get('receipts', [])), 'RESUME_EXISTING_RECEIPT: do not rebuild a new upload')
    selection = b['selection']; cp = b['copy']
    need(cp['selectionVersion'] == selection['version'], 'STALE_COPY')
    candidates = {c['id']: c for c in b['candidates']}
    images = []
    for i in selection['ids']:
        c = candidates[i]
        images.append({'path': str(verify_asset(project, c)), 'candidateId': i, 'decisionQuestion': c['decisionQuestion'], 'reviewed': True})
    return {'schemaVersion': 2, 'itemId': state['itemId'], 'shopName': state['product']['shopName'], 'productName': state['product']['productName'], 'localDate': local_date, 'mode': mode, 'merchantInspection': str(Path(inspection).resolve()), 'title': cp['title'], 'body': cp['body'], 'review': cp.get('review', {}), 'images': images, 'selectionProof': {'project': str(Path(project).resolve()), 'revision': state['revision'], 'directionId': direction_id, 'batchId': batch_id, 'version': selection['version']}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('init'); p.add_argument('--root', required=True); p.add_argument('--input', required=True)
    p = sub.add_parser('show'); p.add_argument('--project', required=True)
    p = sub.add_parser('commit'); p.add_argument('--project', required=True); p.add_argument('--expect-revision', type=int, required=True); p.add_argument('--input', required=True)
    p = sub.add_parser('render'); p.add_argument('--project', required=True); p.add_argument('--out', required=True)
    p = sub.add_parser('export-manifest'); p.add_argument('--project', required=True); p.add_argument('--direction', required=True); p.add_argument('--batch', required=True); p.add_argument('--inspection', required=True); p.add_argument('--date', required=True); p.add_argument('--mode', choices=('publish', 'prepare'), default='publish'); p.add_argument('--out', required=True)
    args = parser.parse_args()
    if args.command == 'init':
        state = read(args.input); validate(state)
        project = Path(args.root).resolve() / state['itemId']
        if project.exists():
            need(project.is_dir() and {p.name for p in project.iterdir()} <= {'商品资料', '创作记录'},
                 'PROJECT_EXISTS: use show/resume')
        else:
            project.mkdir(parents=True)
        state = {**state, 'revision': 1, 'updatedAt': datetime.now(timezone.utc).isoformat()}
        write_new(project / 'ledger' / '00000001.json', state)
    else:
        project = Path(args.project).resolve(); state = load(project)
        if args.command == 'commit':
            state = commit(project, args.expect_revision, read(args.input))
        elif args.command == 'render':
            write_new(args.out, dashboard(state, project))
        elif args.command == 'export-manifest':
            write_new(args.out, export_manifest(project, state, args.direction, args.batch, args.inspection, args.date, args.mode))
    print(json.dumps({'ok': True, 'project': str(project), 'revision': state['revision'], 'state': state if args.command == 'show' else None}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (LedgerError, OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False))
        sys.exit(1)
