"""Windowed fixed-operation installer helper, hosted by Inno Setup."""
import installer
import argparse
import json
from pathlib import Path
import traceback


def main(argv=None):
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--result',type=Path)
    options,arguments=parser.parse_known_args(argv)
    result={'ok':True};code=0
    try:installer.main(arguments)
    except Exception as error:
        code=1
        result={'ok':False,'error_type':type(error).__name__,
            'winerror':getattr(error,'winerror',None),
            'frames':[{'file':Path(frame.filename).name,'line':frame.lineno,'function':frame.name}
                      for frame in traceback.extract_tb(error.__traceback__)]}
        if isinstance(error,installer.manifest.PackageError):result['state']=str(error)
    if options.result:
        with options.result.open('x',encoding='utf-8') as f:json.dump(result,f)
    return code

if __name__=='__main__':
    raise SystemExit(main())
