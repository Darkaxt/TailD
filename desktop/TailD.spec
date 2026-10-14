# GPL-3.0-only frontend/runtime packaging. No one-file extraction or console.
from pathlib import Path
import os
repo=Path(SPECPATH).parent
source=Path(os.environ.get('TAILD_RUNTIME_SOURCE',str(repo/'scripts/taild')))
paths=[str(source)]
owner=Analysis([str(source/'packaged.py')],pathex=paths,hiddenimports=['win32timezone'])
setup=Analysis([str(source/'setup_entry.py')],pathex=paths,hiddenimports=['win32timezone'])
owner_pyz=PYZ(owner.pure)
setup_pyz=PYZ(setup.pure)
app=EXE(owner_pyz,owner.scripts,[],exclude_binaries=True,name='TailD',console=False,
    disable_windowed_traceback=True,upx=False,version=os.environ['TAILD_VERSION_RESOURCE'])
background=EXE(owner_pyz,owner.scripts,[],exclude_binaries=True,name='TailD.Background',console=False,
    disable_windowed_traceback=True,upx=False,version=os.environ['TAILD_VERSION_RESOURCE'])
helper=EXE(setup_pyz,setup.scripts,[],exclude_binaries=True,name='TailD.Setup',console=False,
    disable_windowed_traceback=True,upx=False,version=os.environ['TAILD_VERSION_RESOURCE'])
COLLECT(app,background,helper,owner.binaries,setup.binaries,owner.datas,setup.datas,name='TailD',upx=False)
