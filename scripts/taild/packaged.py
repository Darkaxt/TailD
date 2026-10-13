"""Toolchain-free Windows entrypoint for the existing owner runtime and desktop.

No Python/Node/Go installation, automatic opt-in, updater or VPN installation.
Privileged reader setup belongs to the installer; normal launch never elevates.
"""
import ctypes
import json
import os
from pathlib import Path
import sys

import desktop
import history
import reader
import runtime


def installation_directory():
    return Path(sys.executable).resolve().parent


def reader_instance(sid):
    return 'glasswire-'+history.digest([sid])[:32]


def launch_arguments(directory,local_data,sid,cli):
    directory=Path(directory).resolve(strict=True)
    args=['--shell',str(directory/'desktop'/'TailD.Desktop.exe'),
          '--history',str(Path(local_data)/'TailD'/'history'),
          '--reader-instance',reader_instance(sid)]
    if Path(cli).is_file():args+=['--cli',str(cli)]
    return args


def main(argv=None):
    arguments=list(sys.argv[1:] if argv is None else argv)
    if not arguments and getattr(sys,'frozen',False) and Path(sys.executable).name=='TailD.Background.exe':
        arguments=['background']
    if arguments and arguments[0]=='collector':
        return runtime.main(arguments[1:])
    if arguments and arguments[0]=='reader':
        return reader.main(arguments[1:])
    if arguments==['reader-service']:
        import reader_service
        return reader_service.main()
    if arguments==['background']:
        directory=installation_directory()
        metadata=json.loads((directory/'installation.json').read_bytes())
        if metadata['owner_sid']!=reader.current_sid():return
        home=Path(os.environ['LOCALAPPDATA'])/'TailD'/'history'
        saved=home/'runtime.json'
        if not saved.exists():return
        config=runtime.settings(reader.decode_message(saved.read_bytes()))
        if not config['traffic'] and not config['dns']:return
        sid=reader.current_sid();instance='owner-'+history.digest([sid,str(home).casefold()])[:32]
        cli=directory.parent/'tailscale.exe'
        # Runtime's owning-user mutex refuses a duplicate collector. Retained
        # opt-in settings are read unchanged; no UI or new startup task appears.
        return runtime.main(['run','--history',str(home),'--reader-instance',reader_instance(sid),
            '--instance',instance,'--cli',str(cli)])
    if arguments and arguments[0]=='desktop':
        # Explicit arguments support isolated package verification; the normal
        # shortcut below uses only installed deterministic paths.
        return desktop.main(arguments[1:])
    if arguments:
        raise ValueError('invalid-command')
    cli=Path(os.environ['ProgramFiles'])/'Tailscale'/'tailscale.exe'
    history.private_directory(Path(os.environ['LOCALAPPDATA'])/'TailD')
    return desktop.main(launch_arguments(installation_directory(),os.environ['LOCALAPPDATA'],reader.current_sid(),cli))


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception:
        # Windowed bootloaders have no stdout/stderr. No exception traceback,
        # source paths, account content or credential is exposed in a dialog.
        if Path(sys.executable).name!='TailD.Background.exe':
            ctypes.windll.user32.MessageBoxW(None,
                'TailD could not start. Check the owning-user installation and reopen TailD.',
                'TailD',0x10)
        raise SystemExit(1)
