"""Existing-window activation must not probe an occupied analytics pipe."""
import unittest
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock

import desktop


class DesktopActivationTest(unittest.TestCase):
    def test_activation_binds_instance_owner_path_and_process_identity(self):
        shell = Path(__file__).resolve()
        for scenario in ('valid', 'other-instance', 'other-path', 'other-owner', 'pid-changed'):
            with self.subTest(scenario=scenario):
                process = Mock()
                process.__int__ = Mock(return_value=91)
                token = Mock()
                gui = Mock()
                gui.IsWindowVisible.return_value = True
                gui.GetWindowText.return_value = 'TailD · Network analytics'
                gui.IsIconic.return_value = True
                gui.EnumWindows.side_effect = lambda callback, arg: callback(12, arg)
                native = Mock()
                native.GetPropW.return_value = 0 if scenario == 'other-instance' else 1
                def query(_handle, _flags, name, _size):
                    name.value = str(shell.parent) if scenario == 'other-path' else str(shell)
                    return True
                native.QueryFullProcessImageNameW.side_effect = query
                security = Mock()
                security.OpenProcessToken.return_value = token
                security.GetTokenInformation.return_value = ['sid-object']
                security.ConvertSidToStringSid.return_value = 'other' if scenario == 'other-owner' else 'owner'
                api = Mock()
                api.OpenProcess.return_value = process
                processes = Mock()
                processes.GetWindowThreadProcessId.side_effect = [(1, 43), (1, 99 if scenario == 'pid-changed' else 43)]
                modules = {'win32api': api, 'win32gui': gui, 'win32process': processes,
                    'win32security': security, 'win32con': SimpleNamespace(TOKEN_QUERY=8, SW_RESTORE=9)}
                with patch.dict(sys.modules, modules), \
                     patch.object(desktop.ctypes, 'WinDLL', return_value=native, create=True), \
                     patch.object(desktop.reader, 'current_sid', return_value='owner'):
                    if scenario == 'pid-changed':
                        with self.assertRaises(desktop.reader.ReaderError):
                            desktop.activate_existing(shell, 'owner-instance')
                    else:
                        self.assertEqual(desktop.activate_existing(shell, 'owner-instance'), scenario == 'valid')
                if scenario == 'valid':
                    gui.ShowWindow.assert_called_once_with(12, 9)
                    gui.SetForegroundWindow.assert_called_once_with(12)
                else:
                    gui.ShowWindow.assert_not_called()
                    gui.SetForegroundWindow.assert_not_called()
                if scenario != 'other-instance':
                    process.Close.assert_called_once()
                native.GetPropW.assert_called_once_with(12, 'Darkaxt.TailD.Instance.owner-instance')

    def test_existing_window_returns_before_busy_collector_probe(self):
        shell = Path(__file__).resolve()
        with patch.object(desktop.history, 'private_directory', return_value=shell.parent), \
             patch.dict(sys.modules, {'pywintypes': Mock(), 'win32api': Mock(), 'win32event': Mock()}), \
             patch.object(desktop.reader, 'current_sid', return_value='S-1-5-21-123'), \
             patch.object(desktop, 'activate_existing', return_value=True, create=True) as activate, \
             patch.object(desktop, 'server_pid', side_effect=AssertionError('occupied pipe must not be probed')), \
             patch.object(desktop.subprocess, 'run') as launch:
            self.assertEqual(desktop.main(['--shell', str(shell), '--history', str(shell.parent),
                '--reader-instance', 'test-reader']), 0)
        activate.assert_called_once()
        launch.assert_not_called()

    def test_native_window_exposes_instance_identity(self):
        source = (Path(__file__).resolve().parents[2] / 'desktop/native/Program.cs').read_text(encoding='utf-8')
        self.assertIn('"Darkaxt.TailD.Instance."+instance', source)
        self.assertIn('SetProp(Handle', source)
        self.assertIn('RemoveProp(Handle', source)


if __name__ == '__main__':
    unittest.main()
