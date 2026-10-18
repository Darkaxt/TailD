"""Reviewed TailD build overlay against the inherited exact core, never a fork copy.

Only distribution identity/update dispatch/recovery and desktop activation change.
DNS, protocol identifiers, operational right-click controls/icons and service
identity come from the pinned source. Production TailD hides its diagnostic
Rebuild command.
"""
import argparse
import json
from pathlib import Path

PIN='28b0deb78057'
SOURCE_FILES=(
    'clientupdate/taildnsupdate/start_windows.go',
    'feature/clientupdate/clientupdate.go',
    'client/systray/systray.go','client/systray/preferences.go',
    'client/systray/preferences_test.go',
    'cmd/taildns-ipn/main_windows.go',
    'cmd/taildns-installer/main.go','cmd/taildns-installer/main_test.go',
    'cmd/taildns-installer/install_windows.go','cmd/taildns-installer/install_windows_test.go',
)


def replace_once(source,before,after):
    if source.count(before)!=1:raise ValueError('Inherited recovery lifecycle drift')
    return source.replace(before,after,1)


def recovery_overlay(source):
    source=replace_once(source,
        'func platformRollback() (installResult, error) {',
        'func platformRollback() (installResult, error) { return rollbackDeployment(false) }\n\n'
        'func platformUnmigrate() (installResult, error) { return rollbackDeployment(true) }\n\n'
        'func rollbackDeployment(original bool) (installResult, error) {')
    source=replace_once(source,
        '\tactivationStarted = true\n\tif err := terminateProcessesByPath(paths.Tray);',
        '\t// Durable immediate-predecessor recovery, written before activation.\n'
        '\tif err := writeRecord(paths.Record+".previous", active); err != nil { return result, err }\n'
        '\tif err := writeRecord(paths.Record+".rollback", rollback); err != nil { return result, err }\n'
        '\tactivationStarted = true\n\tif err := terminateProcessesByPath(paths.Tray);')
    # Read the immediately preceding update snapshot, not the original
    # TailDNS-to-TailD migration snapshot. Both are needed for actual rollback.
    before='\trecord, err := readRecord(paths.Record)\n\tif err != nil {\n\t\treturn installResult{}, err\n\t}\n\tif config.BinaryPathName != record.ServicePath {'
    after='\t// An interrupted uninstall may have already restored the baseline. Never accept a TailD daemon with its recovery record missing.\n'
    after+='\tif _, err := os.Stat(paths.Record); original && errors.Is(err, os.ErrNotExist) {\n'
    after+='\t\tvar installed versionJSON; if err := commandJSON(paths.CLI, &installed, "version", "--json"); err != nil { return installResult{}, err }; if strings.Contains(installed.Long, "-taild.") { return installResult{}, errors.New("TailD recovery record missing") }; identity, err := readIdentity(paths.CLI); if err != nil { return installResult{}, err }; return installResult{Action:"alreadyUnmigrated", Identity:identity}, nil\n\t}\n'
    after+='\trecordPath := paths.Record\n\tvar previous *deploymentRecord\n'
    after+='\tif _, err := os.Stat(paths.Record+".rollback"); !original && err == nil {\n'
    after+='\t\told, readErr := readRecord(paths.Record+".previous"); if readErr != nil { return installResult{}, readErr }; previous = &old; recordPath += ".rollback"\n'
    after+='\t} else if err != nil && !errors.Is(err, os.ErrNotExist) { return installResult{}, err }\n'
    after+='\trecord, err := readRecord(recordPath)\n\tif err != nil { return installResult{}, err }\n'
    after+='\tif config.BinaryPathName != record.ServicePath {'
    source=replace_once(source,before,after)
    before='\tif err := os.Remove(paths.Record); err != nil && !errors.Is(err, os.ErrNotExist) {\n\t\treturn installResult{}, fmt.Errorf("removing active deployment record after rollback: %w", err)\n\t}'
    after='\tif previous != nil {\n\t\tif err := writeRecord(paths.Record, *previous); err != nil { return installResult{}, err }\n'
    after+='\t\t// A completed rollback remains idempotently recoverable if the parent installer exits before recording completion.\n'
    after+='\t\trecord.Version = previous.Version\n'
    after+='\t} else {\n'
    after+='\t\t// Remove only the two fixed superseded metadata files before the active record, so an interrupted unmigration stays repeatable.\n'
    after+='\t\tif original { for _, suffix := range []string{".rollback", ".previous"} { if err := os.Remove(paths.Record+suffix); err != nil && !errors.Is(err, os.ErrNotExist) { return installResult{}, err } } }\n'
    after+='\t\tif err := os.Remove(paths.Record); err != nil && !errors.Is(err, os.ErrNotExist) { return installResult{}, err }\n\t}'
    source=replace_once(source,before,after)
    before='\tif record.OfficialGUIRunning {\n\t\tif err := winutil.StartProcessAsCurrentGUIUser(paths.GUI, nil);'
    after='\tif record.TailDRunValue.Existed && record.TailDRunValue.Value == tailDNSRunCommand(paths.Tray) {\n'
    after+='\t\tif err := winutil.StartProcessAsCurrentGUIUser(paths.Tray, nil); err != nil { return err }\n\t}\n'
    after+=before
    return replace_once(source,before,after)


def create(core,output):
    core=core.resolve(strict=True)
    if not core.name.endswith('-'+PIN) or (core/'VERSION.txt').read_text(encoding='utf-8').strip()!='1.105.0':
        raise ValueError('Review TailD overlay against the new inherited core pin before building')
    # Read/transform all inputs before creating output; drift is a build failure,
    # not an invitation to weaken source matching or modify the shared cache.
    sources={name:(core/name).read_text(encoding='utf-8') for name in SOURCE_FILES}
    for name,source in list(sources.items()):
        if name=='clientupdate/taildnsupdate/start_windows.go':
            sources[name]=(Path(__file__).parent/'core-overlay/start_windows.go').read_text(encoding='utf-8')
        elif name=='cmd/taildns-ipn/main_windows.go':
            if source.count('ProductName: "TailDNS"')!=1:raise ValueError('Tray identity drift')
            sources[name]=source.replace('ProductName: "TailDNS"','ProductName: "TailD"')
            sources[name]=replace_once(sources[name],
                '\t\t(&systray.Menu{ProductName: "TailD"}).Run(&local.Client{})',
                '\t\tconfigureDesktopAction()\n\t\t(&systray.Menu{ProductName: "TailD"}).Run(&local.Client{})')
        elif name=='client/systray/systray.go':
            sources[name]=replace_once(source,'\tmenu.rebuildMenu.Enable()',
                '\t// Production TailD exposes no diagnostic repair command.\n\tmenu.rebuildMenu.Hide()').replace('TailDNS','TailD')
        elif name.startswith('cmd/taildns-installer/'):
            # Keep executable/LocalAPI/run-value names for in-place compatibility.
            # Dedicated ProgramData records and manifest product isolate TailD
            # ownership from the preserved TailDNS installation/recovery record.
            sources[name]=source.replace('TailDNS','TailD').replace('-taildns.','-taild.')
            if name=='cmd/taildns-installer/main.go':
                sources[name]=replace_once(sources[name],
                    '\tcase "status":\n\t\tresult, err = platformStatus()',
                    '\tcase "unmigrate":\n\t\tresult, err = platformUnmigrate()\n'
                    '\tcase "resume-analytics":\n\t\tresult, err = platformResumeAnalytics()\n\tcase "status":\n\t\tresult, err = platformStatus()')
            if name.endswith('install_windows.go'):
                sources[name]=sources[name].replace('runValueName = "TailD"','runValueName = "TailDNS"')
                anchor='\tif err := stopService(service, paths.Daemon); err != nil {'
                if source.count(anchor)!=3:raise ValueError('Installer lifecycle drift')
                sources[name]=sources[name].replace(anchor,
                    '\tif err := terminateProcessesByPath(paths.Tray); err != nil { return result, err }\n'+anchor,1)
                sources[name]=recovery_overlay(sources[name])
        elif name=='feature/clientupdate/clientupdate.go':
            if '"-taildns."' not in source:raise ValueError('Updater dispatch drift')
            sources[name]=source.replace('"-taildns."','"-taild."').replace('TailDNS','TailD').replace('doTailDSelfUpdate','doTailDNSSelfUpdate')
        else:
            sources[name]=source.replace('TailDNS','TailD')
    output.mkdir(parents=True,exist_ok=False)
    replacements={}
    sources['cmd/taildns-installer/taild_resume_windows.go']=(Path(__file__).parent/'core-overlay/resume_windows.go').read_text(encoding='utf-8')
    for name in ('desktop_windows.go','desktop_windows_test.go'):
        sources['cmd/taildns-ipn/taild_'+name]=(Path(__file__).parent/'core-overlay'/name).read_text(encoding='utf-8')
    for name,source in sources.items():
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(source,encoding='utf-8')
        replacements[str(core/name)]=str(target.resolve())
    overlay=output/'overlay.json';overlay.write_text(json.dumps({'Replace':replacements}),encoding='utf-8')
    return overlay


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();print(create(args.core,args.output))
