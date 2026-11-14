import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Package(unittest.TestCase):
    def test_archive_index_and_deterministic_build(self):
        def build():
            subprocess.run(['python3', 'tools/build.py'], cwd=ROOT, check=True, capture_output=True)
            index = (ROOT / 'repository/index.json').read_bytes()
            entry = json.loads(index)['packages'][0]
            archive = (ROOT / 'repository' / entry['archive']['url']).read_bytes()
            return index, entry, archive
        index, entry, archive = build()
        self.assertEqual(hashlib.sha256(archive).hexdigest(), entry['archive']['sha256'])
        self.assertEqual(len(archive), entry['archive']['bytes'])
        manifest = entry['manifest']
        compact = json.dumps(manifest, separators=(',', ':'), ensure_ascii=False).encode()
        self.assertEqual(hashlib.sha256(compact).hexdigest(), entry['manifest_sha256'])
        self.assertFalse(next(s for s in manifest['settings'] if s['id'] == 'enabled')['default'])
        self.assertNotIn('dv.write.any', manifest['capabilities'])
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            names = tar.getnames()
            self.assertEqual(names, sorted(names))
            self.assertEqual(len(names), len(set(names)))
            self.assertEqual(json.load(tar.extractfile('coilshift.json')), manifest)
            for member in tar:
                self.assertTrue(member.isfile() or member.isdir())
                self.assertEqual(member.mtime, 0)
                self.assertEqual((member.uid, member.gid), (0, 0))
                self.assertNotIn('..', Path(member.name).parts)
            for hook in [manifest['hooks']['apply'], manifest['hooks']['remove']] + manifest['hooks']['service']:
                self.assertEqual(tar.getmember(hook['run']).mode, 0o755)
        next_index, next_entry, next_archive = build()
        self.assertEqual(index, next_index)
        self.assertEqual(archive, next_archive)

    def test_shell_syntax(self):
        for path in (ROOT / 'packages').rglob('*.sh'):
            subprocess.run(['/bin/bash', '-n', str(path)], check=True)


if __name__ == '__main__':
    unittest.main()
