#!/usr/bin/env python3
"""Create or finalize one local creative run."""
import argparse
import json
import os
import re
import shutil
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from image_loop import load, require, run
from image_review_html import render

STAGES = ('01_小红书研究', '02_图文策划', '03_方向资产', '04_生图与验收',
          '05_文案过程', '06_交付', '07_复盘')
MANIFEST = '运行清单.json'


def initialize(project, item, local_date, direction):
    require(re.fullmatch(r'\d{1,30}', item), '商品ID无效')
    require(date.fromisoformat(local_date).isoformat() == local_date, '日期格式须为 YYYY-MM-DD')
    require(not direction or re.fullmatch(r'[\w-]{1,48}', direction), '方向编号无效')
    runs = project / '创作记录'
    runs.mkdir(parents=True, exist_ok=True)
    for index in range(1, 10000):
        run_id = f'{local_date}_{index:03d}'
        if any(runs.glob(run_id + '_*')) or (runs / run_id).exists():
            continue
        # Reserve the sequence independently of the optional direction suffix.
        reservation = runs / f'.{run_id}.lock'
        try:
            reservation.mkdir()
        except FileExistsError:
            continue
        try:
            if any(runs.glob(run_id + '_*')) or (runs / run_id).exists():
                continue
            root = runs / (f'{run_id}_{direction}' if direction else run_id)
            root.mkdir()
            for stage in STAGES:
                (root / stage).mkdir()
            for relative in ('01_小红书研究/笔记', '03_方向资产/环境', '03_方向资产/人物',
                             '03_方向资产/风格', '04_生图与验收/镜头', '05_文案过程/草稿'):
                (root / relative).mkdir()
            for relative in ('商品资料/主图', '商品资料/产品资产'):
                (project / relative).mkdir(parents=True, exist_ok=True)
            manifest = dict(schemaVersion=1, runId=run_id, itemId=item, directionId=direction,
                            status='in-progress', stage='N2', inputVersions={})
            with (root / MANIFEST).open('x', encoding='utf-8') as file:
                json.dump(manifest, file, ensure_ascii=False, indent=2)
            return root
        finally:
            reservation.rmdir()
    raise ValueError('当日运行编号已用完')


def finalize(root, copy):
    manifest_path = root / MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    require(manifest['status'] == 'in-progress', '运行已归档')
    require(manifest['directionId'], '请先登记方向编号')
    project = root.parent.parent
    os.chdir(project)
    loop = root / STAGES[3] / '迭代台账'
    state = load(loop)
    report = root / STAGES[6] / '生图复盘.html'
    html = render(state, report.parent)
    complete = all(s['status'] == 'passed' for s in state['shots'])
    require(not report.exists() or report.read_text(encoding='utf-8') == html, '已有不同版本的复盘')
    delivery = root / STAGES[5]
    if complete:
        require(copy and copy.is_file(), '完整交付需要发布文案 TXT')
        copy_text = copy.read_text(encoding='utf-8').strip()
        title, _, body = copy_text.partition('\n')
        length = lambda text: len(text.encode('utf-16-le')) // 2
        require(5 <= length(title) <= 20 and 10 <= length(body.strip()) <= 1000,
                '发布文案标题或正文长度不符合合同')
        results = sorted(run(loop, 'export')['files'], key=lambda result: result['shotId'])
        require([r['shotId'] for r in results] == [f'{i:02d}' for i in range(1, 9)], '需要八个按序镜头')
        expected = {}
        for result in results:
            source = Path(result['artifact']['path'])
            require(source.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'), '不支持的交付图片格式')
            expected[f'{result["shotId"]}{source.suffix.lower()}'] = source.read_bytes()
        expected['发布文案.txt'] = copy.read_bytes()
        if any(delivery.iterdir()):
            require({p.name for p in delivery.iterdir()} == set(expected) and
                    all((delivery / name).read_bytes() == data for name, data in expected.items()),
                    '已有不同版本的交付')
        else:
            with TemporaryDirectory(dir=root) as scratch:
                staged = Path(scratch) / 'delivery'
                staged.mkdir()
                for name, data in expected.items():
                    (staged / name).write_bytes(data)
                os.replace(staged, delivery)
    if not report.exists():
        with report.open('x', encoding='utf-8') as file:
            file.write(html)
    manifest.update(status='complete' if complete else 'partial', stage='finished',
                    review=str(report.relative_to(root)),
                    delivery=str(delivery.relative_to(root)) if complete else None,
                    missingShots=[s['id'] for s in state['shots'] if s['status'] != 'passed'])
    with TemporaryDirectory(dir=root) as scratch:
        staged = Path(scratch) / MANIFEST
        staged.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(staged, manifest_path)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init')
    init.add_argument('--project', type=Path, required=True)
    init.add_argument('--item-id', required=True)
    init.add_argument('--date', required=True)
    init.add_argument('--direction')
    finish = commands.add_parser('finalize')
    finish.add_argument('--run', type=Path, required=True)
    finish.add_argument('--copy', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'init':
            root = initialize(args.project.resolve(), args.item_id, args.date, args.direction)
            print(json.dumps({'run': str(root)}, ensure_ascii=False))
        else:
            print(json.dumps(finalize(args.run.resolve(), args.copy.resolve() if args.copy else None),
                             ensure_ascii=False))
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
