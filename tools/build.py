#!/usr/bin/env python3
"""Reproducible SDK 1.0 tar/index builder from the documented wire format.
Run official csdk lint/test/build as well before promoting a release.
"""
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'packages/welcome-light'
SITE = ROOT / 'repository'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build():
    manifest = json.loads((PACKAGE / 'coilshift.json').read_text())
    # Match JSON Compact without reordering keys or HTML escaping.
    compact = json.dumps(manifest, separators=(',', ':'), ensure_ascii=False).encode()
    for hook in [manifest['hooks']['apply'], manifest['hooks']['remove']] + manifest['hooks']['service']:
        p = PACKAGE / hook['run']
        if not p.is_file() or not p.stat().st_mode & 0o111:
            raise ValueError('Missing executable hook: ' + str(p))
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w', format=tarfile.USTAR_FORMAT) as archive:
        for p in sorted(PACKAGE.rglob('*')):
            if p.is_symlink() or not (p.is_dir() or p.is_file()):
                raise ValueError('Unsupported archive entry: ' + str(p))
            name = p.relative_to(PACKAGE).as_posix()
            entry = tarfile.TarInfo(name + '/' if p.is_dir() else name)
            entry.mode = 0o755 if p.is_dir() or p.stat().st_mode & 0o111 else 0o644
            if p.is_dir():
                entry.type = tarfile.DIRTYPE
                archive.addfile(entry)
            else:
                data = p.read_bytes()
                entry.size = len(data)
                archive.addfile(entry, io.BytesIO(data))
    data = stream.getvalue()
    digest = sha(data)
    (SITE / 'pool').mkdir(parents=True, exist_ok=True)
    (SITE / 'pool' / digest).write_bytes(data)
    # Fixed timestamp for this prerelease keeps rebuilding deterministic.
    published = 1794614400
    index = {'schema': 1, 'repository': {'name': 'Appenetic CS Extensions',
             'homepage': 'https://github.com/appenetic/cs-extensions'},
             'generated_unix': published, 'packages': [{
             'id': manifest['id'], 'version': manifest['version'], 'sdk': manifest['sdk'],
             'title': manifest['title'], 'published_unix': published, 'withdrawn': False,
             'manifest': manifest, 'manifest_sha256': sha(compact),
             'archive': {'url': 'pool/' + digest, 'sha256': digest, 'bytes': len(data)}}]}
    (SITE / 'index.json').write_text(json.dumps(index, indent=2, ensure_ascii=False) + '\n')
    print(f'{digest} {len(data)} bytes')


if __name__ == '__main__':
    build()
