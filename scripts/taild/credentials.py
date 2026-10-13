"""Optional, user-bound Windows credential storage; no provider or service changes."""
import argparse
import ctypes
from ctypes import wintypes
import getpass
import json
import os
import sys
import warnings

TARGET = 'Darkaxt/TailD/ControlD/ReadToken/v1'


class CredentialError(RuntimeError):
    pass


def validate(token):
    if (not isinstance(token, str) or not token.strip() or
            any(ord(c) < 33 or ord(c) > 126 for c in token) or len(token.encode('utf-8')) > 2560):
        raise CredentialError('Expected a nonempty Read API token without whitespace/control characters')
    return token


def prompt_read_token():
    # getpass must not degrade to echoed stdin in redirected/noninteractive hosts.
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            return validate(getpass.getpass('Control D READ token (hidden input): '))
    except (getpass.GetPassWarning, EOFError, KeyboardInterrupt):
        raise CredentialError('Secure entry unavailable or canceled; no credential changed') from None


class _Credential(ctypes.Structure):
    _fields_ = [('Flags', wintypes.DWORD), ('Type', wintypes.DWORD),
                ('TargetName', wintypes.LPWSTR), ('Comment', wintypes.LPWSTR),
                ('LastWritten', wintypes.FILETIME), ('CredentialBlobSize', wintypes.DWORD),
                ('CredentialBlob', ctypes.POINTER(ctypes.c_ubyte)), ('Persist', wintypes.DWORD),
                ('AttributeCount', wintypes.DWORD), ('Attributes', ctypes.c_void_p),
                ('TargetAlias', wintypes.LPWSTR), ('UserName', wintypes.LPWSTR)]


class CredentialStore:
    def __init__(self, target=TARGET):
        if os.name != 'nt':
            raise CredentialError('Persistent credentials require the owning Windows user vault')
        if target != TARGET and not target.startswith('TailD/test/'):
            raise CredentialError('Unsupported TailD credential target')
        self.target = target
        self.api = ctypes.WinDLL('advapi32', use_last_error=True)
        self.api.CredWriteW.argtypes = [ctypes.POINTER(_Credential), wintypes.DWORD]
        self.api.CredWriteW.restype = wintypes.BOOL
        self.api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                       ctypes.POINTER(ctypes.POINTER(_Credential))]
        self.api.CredReadW.restype = wintypes.BOOL
        self.api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        self.api.CredDeleteW.restype = wintypes.BOOL
        self.api.CredFree.argtypes = [ctypes.c_void_p]
        self.api.CredFree.restype = None

    def replace(self, token):
        raw = validate(token).encode('utf-8')
        blob = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
        value = _Credential(Type=1, TargetName=self.target, Comment='TailD Control D Read credential',
                            CredentialBlobSize=len(raw), CredentialBlob=blob, Persist=2,
                            UserName='TailD Read-only')
        try:
            if not self.api.CredWriteW(ctypes.byref(value), 0):
                raise CredentialError('Windows credential replacement failed; no plaintext fallback')
        finally:
            ctypes.memset(blob, 0, len(blob))

    def read(self):
        pointer = ctypes.POINTER(_Credential)()
        if not self.api.CredReadW(self.target, 1, 0, ctypes.byref(pointer)):
            if ctypes.get_last_error() == 1168:  # ERROR_NOT_FOUND
                return None
            raise CredentialError('Windows credential read failed; no environment/transcript fallback')
        try:
            value = pointer.contents
            if not 1 <= value.CredentialBlobSize <= 2560:
                raise CredentialError('Invalid TailD credential size')
            return validate(ctypes.string_at(value.CredentialBlob, value.CredentialBlobSize).decode('utf-8'))
        except UnicodeError:
            raise CredentialError('Invalid TailD credential encoding') from None
        finally:
            if pointer.contents.CredentialBlob and pointer.contents.CredentialBlobSize <= 2560:
                ctypes.memset(pointer.contents.CredentialBlob, 0, pointer.contents.CredentialBlobSize)
            self.api.CredFree(pointer)

    def remove(self):
        if not self.api.CredDeleteW(self.target, 1, 0) and ctypes.get_last_error() != 1168:
            raise CredentialError('Windows credential removal failed')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['set', 'status', 'remove'])
    parser.add_argument('--confirm-read-only', action='store_true', help='Confirm the entered token has Read permission')
    args = parser.parse_args(argv)
    try:
        if args.command == 'set' and not args.confirm_read_only:
            raise CredentialError('Create a Read token and confirm its permission with --confirm-read-only')
        store = CredentialStore()
        if args.command == 'set':
            store.replace(prompt_read_token())
            print(json.dumps({'stored': True, 'storage': 'Windows Credential Manager', 'scope': 'current-user/local-machine'}))
        elif args.command == 'status':
            print(json.dumps({'configured': store.read() is not None, 'scope': 'current-user/local-machine'}))
        else:
            store.remove()
            print(json.dumps({'removed': True, 'provider_revocation': 'not-performed'}))
        return 0
    except CredentialError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
