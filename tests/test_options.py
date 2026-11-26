"""Optional notes must work from CLI and from an empty GUI description."""
import unittest
from unittest.mock import patch
from src.options import read_options


class OptionalNotesTests(unittest.TestCase):
    def test_notes_can_be_omitted_or_empty(self):
        for flags in ([], ['--notes', ''], ['--notes', '   ']):
            with self.subTest(flags=flags), patch('sys.argv', ['stlink-measure', 'capture',
                    '--port', 'COM18', '--name', 'test', *flags]):
                self.assertEqual(read_options().notes, '')

    def test_provided_notes_are_retained(self):
        with patch('sys.argv', ['stlink-measure', 'capture', '--port', 'COM18',
                               '--name', 'test', '--notes', ' NodeMCU; firmware A ']):
            self.assertEqual(read_options().notes, 'NodeMCU; firmware A')
