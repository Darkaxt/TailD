// SPDX-License-Identifier: BSD-3-Clause
// One-shot isolated verification principal. No UI, source changes or credentials.
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Text.Json;
using Microsoft.Win32.SafeHandles;

static class Probe
{
    [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
    static extern SafeFileHandle CreateFile(string path,uint access,uint sharing,IntPtr security,uint mode,uint flags,IntPtr template);
    [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
    static extern bool CredRead(string target,uint type,uint flags,out IntPtr credential);
    [DllImport("advapi32.dll")] static extern void CredFree(IntPtr value);
    static int Main(string[] args)
    {
        var options=new Dictionary<string,string>();
        for(int i=0;i<args.Length;i+=2)options.Add(args[i],args[i+1]);
        bool historyDenied=false;
        try{using var file=File.OpenRead(options["--history"]);}
        catch(UnauthorizedAccessException){historyDenied=true;}
        using var pipe=CreateFile(options["--pipe"],0x12019b,0,IntPtr.Zero,3,0x100000|0x10000,IntPtr.Zero);
        var pipeError=pipe.IsInvalid?Marshal.GetLastWin32Error():0;
        var credentialRead=CredRead(options["--credential"],1,0,out var credential);
        var credentialError=credentialRead?0:Marshal.GetLastWin32Error();
        if(credentialRead)CredFree(credential); // Never dereference or export a value.
        var sid=WindowsIdentity.GetCurrent().User!.Value;
        var admin=new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator);
        var report=new{pid=Environment.ProcessId,sid,administrator=admin,history_denied=historyDenied,
            pipe_denied=pipeError==5,pipe_error=pipeError,credential_read=credentialRead,credential_error=credentialError};
        File.WriteAllText(options["--output"],JsonSerializer.Serialize(report));
        using var ready=EventWaitHandle.OpenExisting(options["--ready"]);
        using var release=EventWaitHandle.OpenExisting(options["--release"]);
        ready.Set();release.WaitOne(); // Supervisor opens our process handle before permitting exit.
        return sid=="S-1-5-19"&&!admin&&historyDenied&&pipeError==5&&!credentialRead&&credentialError is 1168 or 1312 ? 0:1;
    }
}
