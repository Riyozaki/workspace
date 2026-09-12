"""Small local tests; no network, no Git mutation or test repositories."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import workspace_health as h


class HealthTests(unittest.TestCase):
    def test_empty_git_blob(self):
        self.assertEqual(h.blob_id(b'', 'sha1'), 'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391')

    def test_sha256_blob(self):
        self.assertEqual(h.blob_id(b'abc', 'sha256'), hashlib.sha256(b'blob 3\0abc').hexdigest())

    def test_nul_tree_keeps_unicode_and_newlines(self):
        name = 'папка/строка\nтаб\t.md'
        row = b'100644 blob ' + b'a' * 40 + b'\t' + name.encode() + b'\0'
        self.assertEqual(list(h.entries(row)), [('100644', 'blob', 'a' * 40, name)])

    def fixture(self, mode='100644', kind='blob'):
        cache = h.ROOT / '.cache'
        cache.mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=cache)
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / 'source.md').write_bytes(b'preserved\n')
        oid = h.blob_id(b'preserved\n', 'sha1')
        tree = f'{mode} {kind} {oid}\tsource.md\0'.encode()
        def fake_git(*args):
            return b'sha1\n' if args[0] == 'rev-parse' else tree
        return root, fake_git

    def test_preserved_source(self):
        root, fake_git = self.fixture()
        with patch.object(h, 'ROOT', root), patch.object(h, 'git', fake_git):
            r = h.compare_base('base', [])
        self.assertTrue(r['passed'])
        self.assertEqual(r['unchanged'], 1)

    def test_changed_source_needs_explicit_allowlist(self):
        root, fake_git = self.fixture()
        (root / 'source.md').write_bytes(b'new\n')
        with patch.object(h, 'ROOT', root), patch.object(h, 'git', fake_git):
            self.assertFalse(h.compare_base('base', [])['passed'])
            self.assertTrue(h.compare_base('base', ['source.md'])['passed'])

    def test_allowlist_cannot_permit_deletion(self):
        root, fake_git = self.fixture()
        (root / 'source.md').unlink()
        with patch.object(h, 'ROOT', root), patch.object(h, 'git', fake_git):
            r = h.compare_base('base', ['source.md'])
        self.assertFalse(r['passed'])
        self.assertEqual(r['missing'], ['source.md'])

    def test_unsupported_entry_is_not_silent_success(self):
        root, fake_git = self.fixture(mode='160000', kind='commit')
        with patch.object(h, 'ROOT', root), patch.object(h, 'git', fake_git):
            self.assertFalse(h.compare_base('base', [])['passed'])

    def test_symlink_mismatch_detected_even_with_same_content(self):
        root, fake_git = self.fixture(mode='120000')
        with patch.object(h, 'ROOT', root), patch.object(h, 'git', fake_git):
            self.assertEqual(h.compare_base('base', [])['unexpected_changed'], ['source.md'])


if __name__ == '__main__':
    unittest.main()
