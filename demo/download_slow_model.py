"""Download a verified local experimental text generator from its public model page."""
import concurrent.futures
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = 'Qwen/Qwen2.5-0.5B-Instruct'
ROOT = Path(__file__).resolve().parent / 'models' / 'qwen25-05b-instruct'
API = 'https://modelscope.cn/api/v1/models/' + REPO
FILES = {'LICENSE', 'README.md', 'config.json', 'generation_config.json', 'merges.txt',
         'model.safetensors', 'tokenizer.json', 'tokenizer_config.json', 'vocab.json'}
PINNED_WEIGHT_SHA = 'fdf756fa7fcbe7404d5c60e26bff1a0c8b8aa1f72ced49e7dd0210fe288fb7fe'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(8 * 1024 * 1024), b''): h.update(part)
    return h.hexdigest()


def fetch(spec):
    dest = ROOT / spec['Path']
    if dest.exists() and dest.stat().st_size == spec['Size'] and digest(dest) == spec['Sha256']:
        return {'file': dest.name, 'verified': True, 'existing': True}
    url = API + '/repo?' + urllib.parse.urlencode({'Revision': 'master', 'FilePath': spec['Path']})
    partial = dest.with_name(dest.name + '.partial')
    count, last = 0, time.monotonic()
    with urllib.request.urlopen(url, timeout=45) as response, partial.open('wb') as f:
        while True:
            block = response.read(2 * 1024 * 1024)
            if not block: break
            f.write(block); count += len(block)
            if count > spec['Size']: raise RuntimeError('Unexpected download size')
            if time.monotonic() - last > 15:
                print(f'{dest.name}: {count/1e6:.0f}/{spec["Size"]/1e6:.0f} MB', flush=True)
                last = time.monotonic()
    if count != spec['Size'] or digest(partial) != spec['Sha256']:
        raise RuntimeError('Downloaded file failed integrity check: ' + dest.name)
    os.replace(partial, dest)
    return {'file': dest.name, 'verified': True, 'bytes': count}


if __name__ == '__main__':
    ROOT.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(API + '/repo/files?Revision=master&Recursive=true', timeout=30) as f:
        metadata = json.load(f)
    specs = [r for r in metadata['Data']['Files'] if r['Path'] in FILES]
    if {r['Path'] for r in specs} != FILES: raise RuntimeError('Missing model files')
    if next(r for r in specs if r['Path'] == 'model.safetensors')['Sha256'] != PINNED_WEIGHT_SHA:
        raise RuntimeError('Unexpected model checkpoint')
    (ROOT / 'source_metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(fetch, specs): print(json.dumps(result), flush=True)
    (ROOT / 'verified_manifest.json').write_text(json.dumps({'repo': REPO, 'verified': True,
        'weight_sha256': PINNED_WEIGHT_SHA, 'files': specs,
        'scope': 'Local experimental System 2 substitute; not ICBC or a domain-trained credit model'},
        ensure_ascii=False, indent=2), encoding='utf-8')
    print('All slow model artifacts verified.', flush=True)
