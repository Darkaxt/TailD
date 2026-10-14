"""Production launcher path/identity contracts without installed mutations."""
import unittest
import ast
from pathlib import Path

import history
import packaged


class PackagedTest(unittest.TestCase):
    def test_both_frozen_entrypoints_include_pywin32_filetime_dependency(self):
        spec=Path(__file__).resolve().parents[2]/'desktop/TailD.spec'
        analyses=[node for node in ast.walk(ast.parse(spec.read_text()))
                  if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='Analysis']
        self.assertEqual(len(analyses),2)
        for node in analyses:
            imports=next((ast.literal_eval(k.value) for k in node.keywords if k.arg=='hiddenimports'),[])
            self.assertIn('win32timezone',imports,'FILETIME handle inspection needs win32timezone in each separate PYZ')

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
