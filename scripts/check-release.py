"""Check the release allowlist, copied-source hashes and Markdown links."""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = [
    ('typesafe_key', re.compile(rb'apikey_[A-Za-z0-9]{16,}_[A-Za-z0-9]{16,}')),
    ('github_token', re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})')),
    ('private_key', re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    ('provider_key', re.compile(rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}')),
]


def files():
    for path in ROOT.rglob('*'):
        relative = path.relative_to(ROOT)
        if path.is_file() and '.git' not in relative.parts and '__pycache__' not in relative.parts:
            yield path, relative


def main():
    errors, count = [], 0
    manifest = json.loads((ROOT / 'release-manifest.json').read_text(encoding='utf-8'))
    for record in manifest['copied_sources']:
        path = ROOT / record['path']
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
            errors.append({'kind': 'source_hash_mismatch', 'path': record['path']})
    for path, relative in files():
        count += 1
        if any(part in {'runtime', 'models', 'node_modules'} for part in relative.parts) or path.suffix in {'.sqlite3', '.db', '.key', '.pem', '.pt', '.safetensors'} or path.name.startswith('.env'):
            errors.append({'kind': 'excluded_file', 'path': relative.as_posix()})
        if path.stat().st_size >= 90_000_000:
            errors.append({'kind': 'github_size_limit', 'path': relative.as_posix()})
        if path.suffix in {'.docx', '.zip'}:
            with ZipFile(path) as archive:
                blobs = [(name, archive.read(name)) for name in archive.namelist() if name.endswith(('.xml', '.rels', '.json', '.txt', '.md'))]
        else:
            blobs = [(relative.as_posix(), path.read_bytes())]
        for member, content in blobs:
            for label, pattern in SECRET_PATTERNS:
                if pattern.search(content):
                    errors.append({'kind': 'credential_pattern', 'path': relative.as_posix(), 'member': member, 'type': label})
        if path.suffix == '.md' and (relative.as_posix() == 'README.md' or relative.parts[0] == 'docs'):
            text = path.read_text(encoding='utf-8-sig')
            for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', text):
                if target.startswith(('https://', 'http://', '#', 'mailto:')):
                    continue
                target = unquote(target.split('#')[0])
                if not (path.parent / target).exists():
                    errors.append({'kind': 'broken_link', 'path': relative.as_posix(), 'target': target})
    result = {'passed': not errors, 'checked_files': count, 'source_copies_checked': len(manifest['copied_sources']),
              'source_hash_checks': True, 'credential_patterns_checked': [x[0] for x in SECRET_PATTERNS],
              'errors': errors, 'network_calls': 0}
    (ROOT / 'docs/qa/release-integrity.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
