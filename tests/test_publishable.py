from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from check_publishable import audit


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        subprocess.run(['git', 'init', '--quiet', str(self.root)], check=True)

    def stage(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        subprocess.run(['git', '-C', str(self.root), 'add', '--', name], check=True)
        return path

    def test_preserved_context_metadata_is_allowed(self):
        self.stage('export/generated/ozumo2/context.csv', b'address,name\n0x80080400,entry\n')
        self.stage('runtime/game/README.md', b'Integration notes\n')
        self.assertEqual(audit(self.root), [])

    def test_renamed_rom_magic_is_rejected(self):
        self.stage('reports/innocent.md', bytes.fromhex('80371240') + b'synthetic fixture')
        self.assertEqual(len(audit(self.root)), 1)

    def test_unstaged_text_cannot_hide_staged_binary(self):
        path = self.stage('docs/note.md', b'\x7fELFsynthetic fixture')
        path.write_text('This is only an unstaged replacement.\n')
        self.assertEqual(len(audit(self.root)), 1)

    def test_unstaged_private_data_is_not_published(self):
        path = self.stage('docs/note.md', b'Original staged documentation\n')
        path.write_bytes(bytes.fromhex('80371240') + b'unstaged fixture')
        self.assertEqual(audit(self.root), [])

    def test_generated_source_and_private_capture_are_rejected(self):
        self.stage('generated/ozumo2/recomp/function.c', b'void synthetic(void) {}\n')
        self.stage('local/traces/ozumo2/events.jsonl', b'{}\n')
        self.assertEqual(len(audit(self.root)), 2)


if __name__ == '__main__':
    unittest.main()
