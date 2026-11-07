#!/usr/bin/env python3
"""Application-owned bounded image QA loop. No provider calls or visual scoring."""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
from datetime import datetime, timezone

WEIGHTS = dict(product=30, use=20, plan=15, continuity=15, aesthetics=10, salience=10)
GATES = ('identity', 'count', 'physics', 'continuity', 'requiredContent', 'overlay', 'technical')

def require(ok, message):
    if not ok:
        raise ValueError(message)

def number(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def reference_prompt(references, scene):
    require(isinstance(scene, str) and scene.strip(), 'scene prompt required')
    require(all(isinstance(r.get('instruction'), str) and r['instruction'].strip()
                for r in references), 'explicit reference instructions required')
    return '\n'.join(f"参考图{i}：{r['instruction'].strip()}"
                     for i, r in enumerate(references, 1)) + '\n\n' + scene.strip()

def spec(value):
    require(isinstance(value.get('prompt'), str) and value['prompt'].strip(), 'prompt required')
    require(value.get('model') and value.get('ratio') and value.get('resolution'), 'model/ratio/resolution required')
    require(isinstance(value.get('references'), list) and value['references'], 'ordered references required')
    value = copy.deepcopy(value)
    for ref in value['references']:
        require(ref.get('role') and ref.get('version'), 'reference role/version required')
        actual = digest(ref['path'])
        require(not ref.get('sha256') or ref['sha256'] == actual, 'reference hash mismatch')
        ref['sha256'] = actual
    require(len({r['sha256'] for r in value['references']})==len(value['references']), 'duplicate reference image; merge roles or select correct asset')
    if value.get('scaleRequired'):
        require(sum(r['role']=='relative-scale-only' for r in value['references'])==1,
                'one relative-scale reference required')
    if value.get('scaleRequired') or 'scenePrompt' in value:
        require(value['prompt']==reference_prompt(value['references'], value.get('scenePrompt')),
                'reference instructions must match upload order')
    return value

def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def review_result(value, scale_required=False):
    require(set(value['scores']) == set(WEIGHTS), 'six scores required')
    require(set(value['gates']) == set(GATES) | ({'relativeScale'} if scale_required else set()), 'all gates required')
    for key, entry in value['scores'].items():
        require(number(entry['score']) and 0 <= entry['score'] <= 5 and entry.get('evidence'), 'score and visible evidence required: '+key)
    for key, entry in value['gates'].items():
        require(entry.get('status') in ('pass', 'fail', 'unknown') and entry.get('evidence'), 'gate and evidence required: '+key)
    total = round(sum(WEIGHTS[k]*v['score']/5 for k,v in value['scores'].items()), 2)
    passed = all(v['status']=='pass' for v in value['gates'].values()) and total >= 85 and all(value['scores'][k]['score'] >= 4 for k in ('product','use','plan'))
    return total, passed

def load(root):
    files = sorted(root.glob('[0-9]'*8+'.json'))
    require(files, 'loop not initialized')
    state = json.loads(files[-1].read_text())
    require(state['revision'] == len(files), 'revision gap')
    return state

def summary(state):
    return dict(revision=state['revision'], submitted=sum(len(s['attempts']) for s in state['shots']),
                committedCredits=sum(a['charged'] for s in state['shots'] for a in s['attempts']),
                shots=[dict(id=s['id'], status=s['status'], attempts=len(s['attempts']),
                            total=s['attempts'][-1].get('review',{}).get('total') if s['attempts'] else None,
                            taskId=s['attempts'][-1].get('taskId') if s['attempts'] else None) for s in state['shots']],
                setReview=state.get('setReview'))

def change(state, command, data):
    if command == 'set-review':
        require(all(s['status']=='passed' for s in state['shots']), 'set review requires all shots passed')
        require(data.get('evidence') and isinstance(data.get('reopen'),list), 'set evidence/reopen required')
        require(set(data['reopen']) <= {s['id'] for s in state['shots']}, 'unknown shot')
        state['setReview'] = data
        for shot in state['shots']:
            if shot['id'] in data['reopen']:
                shot['status'] = 'exhausted' if len(shot['attempts'])>=3 else 'needs-repair'
        return
    shot = next((s for s in state['shots'] if s['id']==data['shotId']),None)
    require(shot is not None,'unknown shot')
    if command == 'revise':
        require(shot['status']=='needs-repair', 'repair not pending')
        require(data.get('diagnosis') and data.get('changeReason'), 'diagnosis/changeReason required')
        updated = spec(data['spec'])
        require(not shot['spec'].get('scaleRequired') or updated.get('scaleRequired'),
                'cannot remove relative scale requirement')
        require(fingerprint(updated) != fingerprint(shot['spec']), 'retry inputs unchanged')
        shot['repairs'].append(data)
        shot['spec'],shot['status'] = updated,'ready'
        state['setReview'] = None
        return
    if command == 'begin':
        require(shot['status']=='ready','shot not ready; follow existing task/review/repair')
        require(len(shot['attempts']) < 3,'shot attempt limit')
        require(sum(len(s['attempts']) for s in state['shots']) < state['maxSubmissions'],'run attempt limit')
        spent = sum(a['charged'] for s in state['shots'] for a in s['attempts'])
        require(number(data.get('estimate')) and data['estimate']>0,'positive live estimate required')
        require(spent+data['estimate'] <= state['creditBudget'],'credit budget limit')
        checked = spec(shot['spec'])
        shot['attempts'].append(dict(number=len(shot['attempts'])+1,spec=checked,charged=data['estimate'],status='reserved'))
        shot['status']='recover-task'
        return
    require(shot['attempts'], 'no attempt')
    attempt = shot['attempts'][-1]
    if command == 'attach':
        require(shot['status']=='recover-task','not following task')
        require(data.get('taskId'),'taskId required')
        require(not attempt.get('taskId') or attempt['taskId']==data['taskId'],'cannot replace task')
        attempt['taskId']=data['taskId']
        attempt['status']=data.get('status','pending')
        if 'cost' in data:
            require(number(data['cost']) and data['cost']>=0,'invalid cost')
            attempt['charged']=data['cost']
        if attempt['status']=='succeeded':
            from PIL import Image
            artifact=data['artifact']
            actual=digest(artifact['path'])
            require(actual==artifact['sha256'],'output hash mismatch')
            with Image.open(artifact['path']) as im:
                im.load()
                artifact['dimensions']=list(im.size)
            attempt['artifact']=artifact
            shot['status']='needs-review'
        # Definite provider failures remain recovery-blocked; never blindly resubmit.
        return
    if command == 'review':
        require(shot['status'] in ('needs-review','needs-evidence'),'review not pending')
        artifact=attempt['artifact']
        require(data.get('sha256')==artifact['sha256']==digest(artifact['path']),'review artifact mismatch')
        require(data.get('inspected') is True and data.get('reviewer'), 'actual visual inspection required')
        total,passed=review_result(data, attempt['spec'].get('scaleRequired',False))
        attempt['review']=dict(data,total=total,passed=passed)
        unknown=any(v['status']=='unknown' for v in data['gates'].values())
        shot['status']='needs-evidence' if unknown else ('passed' if passed else ('exhausted' if len(shot['attempts'])>=3 else 'needs-repair'))
        return
    raise ValueError('unknown command')

def run(root, command, data=None, expected=None):
    root=Path(root)
    if command in ('status','export'):
        state=load(root)
        if command=='status':
            return summary(state)
        require(all(s['status']=='passed' for s in state['shots']) and state.get('setReview') and not state['setReview']['reopen'],'set incomplete')
        result=[]
        for shot in state['shots']:
            a=shot['attempts'][-1]
            require(digest(a['artifact']['path'])==a['artifact']['sha256'],'final artifact changed')
            result.append(dict(shotId=shot['id'],taskId=a['taskId'],artifact=a['artifact'],review=a['review']))
        return dict(ok=True,complete=True,files=result)
    root.mkdir(parents=True,exist_ok=True)
    lock=root/'.lock'
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        if command=='init':
            require(not list(root.glob('*.json')),'loop already exists')
            require(data.get('authorized') is True and data.get('authorizationEvidence'),'bounded generation authorization required')
            require(len(data['shots'])==8 and len({s['id'] for s in data['shots']})==8,'eight unique shots required')
            require(number(data.get('creditBudget')) and data['creditBudget']>0,'creditBudget required')
            state=copy.deepcopy(data)
            state.update(revision=0,maxAttemptsPerShot=3,maxSubmissions=24,setReview=None)
            for shot in state['shots']:
                require(shot.get('purpose') and shot.get('acceptance'),'shot purpose/acceptance required')
                shot.update(spec=spec(shot['spec']),status='ready',attempts=[],repairs=[])
        else:
            state=load(root)
            require(expected==state['revision'],'revision conflict')
            change(state,command,copy.deepcopy(data))
        state['revision']+=1
        state['updatedAt']=datetime.now(timezone.utc).isoformat()
        state['event']=dict(command=command,input=data)
        dest=root/f"{state['revision']:08d}.json"
        with dest.open('x') as f:
            json.dump(state,f,ensure_ascii=False,indent=2)
            f.flush();os.fsync(f.fileno())
        return summary(state)
    finally:
        os.close(fd)
        lock.unlink()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['init','status','begin','attach','review','revise','set-review','export'])
    p.add_argument('--root',required=True)
    p.add_argument('--input',help='JSON event path')
    p.add_argument('--expect-revision',type=int)
    args=p.parse_args()
    try:
        data=json.loads(Path(args.input).read_text()) if args.input else None
        print(json.dumps(run(args.root,args.command,data,args.expect_revision),ensure_ascii=False))
    except (ValueError,KeyError,OSError,TypeError) as e:
        print(json.dumps(dict(ok=False,error=str(e)),ensure_ascii=False))
        raise SystemExit(1)

if __name__=='__main__':
    main()
