"""Download only pinned model artifacts, validate sizes + Git/LFS hashes."""
import concurrent.futures
import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = 'aimeigaoshou/agent-jev'
REVISION = '0e2593e6e6c0eade0700712ac13c4389aa7654cc'
ENDPOINT = 'https://hf-mirror.com'
FILES = {'config.json', 'model.safetensors', 'tokenizer.json', 'tokenizer_config.json',
         'vocab.json', 'merges.txt', 'README.md', 'temperatures.json'}
DEST = ROOT / 'models' / 'agentjev-public'


def request(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'JevCreditPrototype/0.1'}), timeout=45)


def verify(path, spec):
    if not path.exists() or path.stat().st_size != spec['size']:
        return False
    if spec.get('lfs'):
        h = hashlib.sha256()
        target = spec['lfs']['sha256']
    else:
        h = hashlib.sha1(f"blob {spec['size']}\0".encode())
        target = spec['blobId']
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest() == target


def fetch(spec):
    name = spec['rfilename']
    dest = DEST / name
    if verify(dest, spec):
        return {'file': name, 'status': 'verified_existing', 'bytes': spec['size']}
    partial = dest.with_suffix(dest.suffix + '.partial')
    last_log = time.monotonic()
    total = 0
    url = f'{ENDPOINT}/{REPO}/resolve/{REVISION}/{name}?download=true'
    with request(url) as response, partial.open('wb') as f:
        while True:
            data = response.read(4 * 1024 * 1024)
            if not data:
                break
            total += len(data)
            if total > spec['size']:
                raise RuntimeError(f'Unexpected size for {name}')
            f.write(data)
            if time.monotonic() - last_log > 15:
                print(f'{name}: {total / 1e6:.0f}/{spec["size"] / 1e6:.0f} MB', flush=True)
                last_log = time.monotonic()
    if not verify(partial, spec):
        raise RuntimeError(f'Integrity check failed: {name}')
    os.replace(partial, dest)
    return {'file': name, 'status': 'downloaded_verified', 'bytes': total}


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    with request(f'{ENDPOINT}/api/models/{REPO}/revision/{REVISION}?blobs=true') as response:
        metadata = json.load(response)
    if metadata['sha'] != REVISION:
        raise RuntimeError('Model revision mismatch')
    specs = [s for s in metadata['siblings'] if s['rfilename'] in FILES]
    if {s['rfilename'] for s in specs} != FILES:
        raise RuntimeError('Missing required files')
    (DEST / 'source_metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Downloading pinned checkpoint: {sum(s["size"] for s in specs)/1e9:.2f} GB', flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(fetch, s) for s in specs]
        for future in concurrent.futures.as_completed(futures):
            print(json.dumps(future.result()), flush=True)
    manifest = {'repo': REPO, 'revision': REVISION, 'mirror': ENDPOINT,
                'verified': True, 'files': specs, 'bank_domain_calibrated': False,
                'note': 'Public upstream checkpoint only; no bank training or performance assertion.'}
    (DEST / 'verified_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('All selected files verified.', flush=True)


if __name__ == '__main__':
    main()
