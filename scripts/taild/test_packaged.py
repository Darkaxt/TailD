"""Production launcher path/identity contracts without installed mutations."""
import unittest
from pathlib import Path

import history
import packaged


class PackagedTest(unittest.TestCase):
    def test_launch_is_owner_scoped_and_does_not_select_developer_runtime(self):
        root=Path(__file__).resolve().parents[2]
        cli=root/'does-not-exist.exe'
        args=packaged.launch_arguments(root,root/'private-data','S-1-5-21-123',cli)
        self.assertEqual(args,['--shell',str(root/'desktop'/'TailD.Desktop.exe'),
            '--history',str(root/'private-data'/'TailD'/'history'),
            '--reader-instance','glasswire-'+history.digest(['S-1-5-21-123'])[:32]])
        self.assertNotEqual(packaged.reader_instance('S-1-5-21-123'),packaged.reader_instance('S-1-5-21-124'))

    def test_unknown_command_cannot_launch_script_or_shell(self):
        with self.assertRaisesRegex(ValueError,'invalid-command'):
            packaged.main(['powershell','-Command','anything'])


if __name__=='__main__':unittest.main()
