#!/usr/bin/env python3
"""Validate an application manifest and construct tbcli v1 JSON inputs. No network or publishing."""
import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path


class ContractError(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def require(condition, code, message):
    if not condition:
        raise ContractError(code, message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def validate(manifest):
    try:
        from PIL import Image
    except ImportError as error:
        raise ContractError('DEPENDENCY_UNAVAILABLE', 'Install Pillow in the selected stable Python environment.') from error
    require(isinstance(manifest, dict) and manifest.get('schemaVersion') in (1, 2), 'INVALID_MANIFEST', 'schemaVersion must be 1 or 2.')
    item = manifest.get('itemId')
    require(isinstance(item, str) and re.fullmatch(r'\d{1,30}', item), 'INVALID_ITEM_ID', 'itemId must be a decimal string.')
    shop = manifest.get('shopName')
    require(isinstance(shop, str) and bool(shop.strip()) and shop == shop.strip(), 'INVALID_SHOP', 'shopName is required.')
    mode = manifest.get('mode', 'publish')
    require(mode in ('publish', 'prepare'), 'INVALID_MODE', 'mode must be publish or prepare.')
    name = manifest.get('productName')
    require(isinstance(name, str) and name == name.strip() and 1 <= len(name) <= 9 and not re.search(r'[\\/<>:"|?*\x00-\x1f]', name) and name not in ('.', '..'), 'INVALID_PRODUCT_NAME', 'Use a core product noun of 1–9 characters so folder name fits the CLI limit.')
    day = manifest.get('localDate')
    try:
        require(isinstance(day, str) and date.fromisoformat(day).isoformat() == day, 'INVALID_DATE', 'localDate must be YYYY-MM-DD.')
    except (ValueError, TypeError):
        raise ContractError('INVALID_DATE', 'localDate must be YYYY-MM-DD.')
    for field, lo, hi in [('title', 5, 20), ('body', 10, 1000)]:
        value = manifest.get(field)
        # tbcli uses JavaScript string.length (UTF-16 code units).
        length = len(value.encode('utf-16-le')) // 2 if isinstance(value, str) else 0
        require(isinstance(value, str) and value == value.strip() and lo <= length <= hi, 'INVALID_COPY', f'{field} must contain {lo}–{hi} UTF-16 code units.')
    review = manifest.get('review', {})
    require(isinstance(review, dict), 'REVIEW_REQUIRED', 'review must be an object.')
    require(all(review.get(x) is True for x in ['productIdentity', 'sceneAndUse', 'claims', 'imageText']), 'REVIEW_REQUIRED', 'Review product identity, scene/use, claims and image text before upload.')
    inspection = read_json(manifest['merchantInspection'])
    require(isinstance(inspection, dict), 'IDENTITY_MISMATCH', 'Merchant inspection must be an object.')
    require(inspection.get('status') == 'inspected' and str(inspection.get('itemId')) == item and inspection.get('shopName') == shop, 'IDENTITY_MISMATCH', 'Merchant inspection must match itemId and shopName.')
    require(type(inspection.get('emptySlots')) is int and inspection['emptySlots'] > 0, 'NO_PUBLISH_SLOT', 'Merchant inspection has no available publish slot.')
    images = manifest.get('images')
    require(isinstance(images, list) and 3 <= len(images) <= 8, 'INVALID_IMAGES', 'Select 3–8 ordered images.')
    if manifest['schemaVersion'] == 2:
        from product_ledger import load, find_batch, verify_asset
        proof = manifest.get('selectionProof', {})
        state = load(proof['project'], proof['revision'])
        require(state['itemId'] == item and state['product']['shopName'] == shop, 'STALE_SELECTION', 'Reload and export the current selected batch.')
        _, batch = find_batch(state, proof['directionId'], proof['batchId'])
        current = load(proof['project'])
        _, live_batch = find_batch(current, proof['directionId'], proof['batchId'])
        require(current['product']['shopName'] == shop and live_batch.get('selection') == batch.get('selection') and live_batch.get('copy') == batch.get('copy'), 'STALE_SELECTION', 'The selected batch changed; export its current selection.')
        selection = batch.get('selection', {})
        require(selection.get('confirmedBy') == 'user' and selection.get('version') == proof['version'], 'USER_SELECTION_REQUIRED', 'User-confirmed image selection is required.')
        require([x.get('candidateId') for x in images] == selection['ids'], 'SELECTION_MISMATCH', 'Only selected candidates in confirmed order may be uploaded.')
        candidates = {c['id']: c for c in batch['candidates']}
        require([str(verify_asset(proof['project'], candidates[i])) for i in selection['ids']] == [x['path'] for x in images], 'SELECTION_MISMATCH', 'Image paths must match selected artifacts.')
        cp = batch.get('copy', {})
        require(cp.get('selectionVersion') == proof['version'] and cp.get('title') == manifest['title'] and cp.get('body') == manifest['body'] and cp.get('review') == review, 'STALE_COPY', 'Copy and review must match the selected batch.')
    files, hashes, ratios = [], [], []
    for entry in images:
        require(isinstance(entry, dict) and entry.get('reviewed') is True and bool(str(entry.get('decisionQuestion', '')).strip()), 'REVIEW_REQUIRED', 'Each image needs a reviewed decision question.')
        path = Path(entry.get('path', ''))
        require(path.is_absolute() and not path.is_symlink() and path.is_file(), 'INVALID_FILE', 'Image path must be an absolute ordinary file.')
        size = path.stat().st_size
        require(200*1024 <= size <= 20*1024*1024, 'INVALID_FILE_SIZE', 'Current tbcli upload contract requires 200KB–20MB.')
        with Image.open(path) as image:
            require(image.format in ('JPEG', 'PNG', 'WEBP') and not getattr(image, 'is_animated', False), 'INVALID_IMAGE_FORMAT', 'Use non-animated JPEG, PNG or WebP.')
            width, height = image.size
            require((width == height) or width*4 == height*3, 'INVALID_RATIO', 'Each image must be exactly 1:1 or 3:4.')
            ratios.append('1:1' if width == height else '3:4')
            image.verify()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append(str(path)); hashes.append(digest)
    require(len(set(files)) == len(files) and len(set(hashes)) == len(files), 'DUPLICATE_IMAGES', 'Distinct files and contents are required.')
    require(len(set(ratios)) == 1, 'MIXED_RATIOS', 'Selected images must use the same ratio.')
    return {'mode': mode, 'folderPath': ['搜推素材', name+'_'+day], 'files': files, 'hashes': hashes}


def build(manifest, upload=None):
    checked = validate(manifest)
    common = {'schemaVersion': 1, 'shopName': manifest['shopName']}
    if upload is None:
        return {**common, 'folderPath': checked['folderPath'], 'files': checked['files']}
    require(isinstance(upload, dict), 'UPLOAD_NOT_VERIFIED', 'Upload receipt must be an object.')
    require(upload.get('status') == 'uploaded' and upload.get('folderVerified') is True, 'UPLOAD_NOT_VERIFIED', 'Only a completed verified upload receipt can be used.')
    require(upload.get('shopName') == manifest['shopName'] and upload.get('folderPath') == checked['folderPath'], 'UPLOAD_IDENTITY_MISMATCH', 'Upload shop and folder must match the manifest.')
    names = upload.get('imageNames', [])
    uploaded_files = upload.get('files', [])
    count = len(checked['files'])
    require(isinstance(names, list) and len(names) == count and all(isinstance(n, str) and n for n in names) and len(set(names)) == count, 'UPLOAD_IMAGES_MISMATCH', 'Upload receipt must match selected unique ordered image names.')
    require(isinstance(uploaded_files, list) and len(uploaded_files) == count and all(isinstance(f, dict) for f in uploaded_files), 'UPLOAD_IMAGES_MISMATCH', 'Upload file evidence is incomplete.')
    require([f.get('sha256') for f in uploaded_files] == checked['hashes'] and [f.get('name') for f in uploaded_files] == names, 'UPLOAD_IMAGES_MISMATCH', 'Upload hashes and ordered names must match the current images.')
    return {**common, 'itemId': manifest['itemId'], 'imageNames': names, 'title': manifest['title'], 'body': manifest['body']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['upload-input', 'article-input'])
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--upload-result')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    output = Path(args.out)
    require(not output.exists() and not output.is_symlink(), 'OUTPUT_EXISTS', 'Choose a new output path.')
    require(args.operation != 'article-input' or args.upload_result, 'UPLOAD_REQUIRED', 'article-input needs --upload-result.')
    manifest = read_json(args.manifest)
    receipt = read_json(args.upload_result) if args.operation == 'article-input' else None
    value = build(manifest, receipt)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open('x', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    except FileExistsError as error:
        raise ContractError('OUTPUT_EXISTS', 'Output appeared during validation; preserved.') from error
    print(json.dumps({'ok': True, 'output': str(output.resolve()), 'mode': manifest.get('mode', 'publish'), 'operation': args.operation}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (ContractError, OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'ok': False, 'error': {'code': getattr(error, 'code', 'INVALID_INPUT'), 'message': str(error)}}, ensure_ascii=False))
        sys.exit(1)
