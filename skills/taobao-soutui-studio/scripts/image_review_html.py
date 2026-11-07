#!/usr/bin/env python3
"""Render a local inspection report from a finished image loop."""
import argparse
import os
from html import escape
from pathlib import Path
from urllib.parse import quote

from image_loop import digest, load, require


SCORES = dict(product='商品一致性', use='场景与使用', plan='镜头任务',
              continuity='全组连续性', aesthetics='自然美观', salience='商品重点')
GATES = dict(identity='商品身份', count='商品数量', physics='物理接触',
             continuity='人物与空间', requiredContent='必需信息',
             overlay='画面覆盖层', technical='文件质量', relativeScale='相对尺度')
RESULTS = dict(pass_='通过', fail='不通过', unknown='待核实')


def image(item, directory, label):
    path = Path(item['path'])
    require(digest(path) == item['sha256'], f'文件摘要不符 {path}')
    url = quote(os.path.relpath(path, directory))
    return f'<a href="{url}"><img src="{url}" alt="{escape(label)}" loading="lazy"></a>'


def analysis(review):
    label = '通过' if review['passed'] else '不通过'
    scores = ''.join(f'<li>{SCORES[k]} {v["score"]}/5 · {escape(v["evidence"])}</li>'
                     for k, v in review['scores'].items())
    gates = ''.join(
        f'<li>{GATES[k]} · {RESULTS["pass_" if v["status"] == "pass" else v["status"]]}'
        f' · {escape(v["evidence"])}</li>' for k, v in review['gates'].items())
    return (f'<h4>分析与评分 · {review["total"]}/100 · {label}</h4>'
            f'<ul>{scores}</ul><details><summary>硬门检查</summary><ul>{gates}</ul></details>')


def render_attempt(attempt, repair, directory):
    refs = ''.join(
        f'<figure>{image(ref, directory, f"参考图{i}")}<figcaption>参考图{i}</figcaption></figure>'
        for i, ref in enumerate(attempt['spec']['references'], 1))
    output = image(attempt['artifact'], directory, '生成结果')
    prompt = escape(attempt['spec']['prompt'])
    adjustment = f'<p>{escape(repair["changeReason"])}</p>' if repair else ''
    return (f'<article><h3>第 {attempt["number"]} 轮</h3>{adjustment}'
            f'<div class="grid"><section><h4>参考图</h4><div class="refs">{refs}</div></section>'
            f'<section><h4>提示词</h4><pre>{prompt}</pre></section>'
            f'<section><h4>生成结果</h4>{output}</section></div>'
            f'{analysis(attempt["review"])}</article>')


def render(state, directory):
    shots = state['shots']
    require(all(s['status'] in ('passed', 'exhausted') for s in shots), '镜头迭代尚未结束')
    if all(s['status'] == 'passed' for s in shots):
        require(state['setReview'] and not state['setReview']['reopen'], '整组复核尚未通过')
    sections = []
    for shot in shots:
        attempts = shot['attempts']
        label = '通过' if shot['status'] == 'passed' else '未通过'
        title = escape(shot.get('title') or shot['purpose'])
        rounds = ''.join(render_attempt(a, shot['repairs'][i - 1] if i else None, directory)
                         for i, a in enumerate(attempts))
        sections.append(f'<details class="shot"><summary>{escape(shot["id"])} {title}'
                        f' · {len(attempts)} 轮 · {label}</summary>{rounds}</details>')
    return HEADER + '\n'.join(sections) + '</main></html>'


HEADER = '''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>生图复盘</title>
<style>
*{box-sizing:border-box}
body{max-width:1500px;margin:auto;padding:24px;font:16px/1.6 system-ui,sans-serif;color:#222}
summary{cursor:pointer}
.shot{padding:12px 0;border-top:1px solid #ddd}
.shot>summary{font-weight:600}
article{padding:8px 0 20px}
.grid{display:grid;grid-template-columns:1fr 1.25fr 1fr;gap:20px}
.grid section{min-width:0}
.refs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
figure{margin:0}
figcaption{font-size:13px}
img{display:block;width:100%;height:auto}
.refs img{height:145px;object-fit:contain;background:#f7f7f7}
pre{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;font-size:14px}
h4{margin:12px 0 8px}
@media(max-width:860px){.grid{grid-template-columns:1fr}.grid section:last-child img{max-width:480px}}
</style><main><h1>生图复盘</h1>
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    try:
        html = render(load(args.root), output.parent)
        with output.open('x', encoding='utf-8') as file:
            file.write(html)
    except (ValueError, OSError, KeyError, IndexError) as error:
        parser.exit(1, f'{error}\n')
    print(output)


if __name__ == '__main__':
    main()
