// SPDX-License-Identifier: GPL-3.0-only
// Original restricted Windows host for the Portmaster-derived Angular component.
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Text;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace TailD;

internal sealed class BridgeError(string state) : Exception
{
    public string State {get;}=state is "invalid-query" or "resource-limit" or "invalid-settings" or
        "explicit-provider-required" or "backpressure" or "write-error" or "credential-not-accepted" or
        "read-only-confirmation-required" or "invalid-command" or "stopping" ? state:"unavailable";
}

internal static class Program
{
    [STAThread]
    static void Main(string[] args)
    {
        ApplicationConfiguration.Initialize();
        try
        {
            if(new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator))
                throw new UnauthorizedAccessException("unelevated-owner-required");
            var options = new Dictionary<string,string>();
            for (var i=0;i<args.Length;i+=2) options.Add(args[i],args[i+1]);
            var instance=options["--instance"];
            if (!System.Text.RegularExpressions.Regex.IsMatch(instance,"\\A[A-Za-z0-9-]{1,96}\\z"))
                throw new InvalidDataException();
            var pid=uint.Parse(options["--collector-pid"]);
            var data=Path.GetFullPath(options["--user-data"]);
            var sid=WindowsIdentity.GetCurrent().User!.Value;
            using var mutex=new Mutex(false,"Local\\Darkaxt.TailD.Desktop."+sid+"."+instance,out bool created);
            if(!created)return;
            Application.Run(new CollectionWindow(instance,pid,data,options));
        }
        catch(Exception)
        {
            MessageBox.Show("TailD could not open its collection controls. Check the owning-user collector and reopen TailD.",
                "TailD",MessageBoxButtons.OK,MessageBoxIcon.Warning);
        }
    }
}

internal sealed class OwnerBridge : IDisposable
{
    private NamedPipeClientStream? pipe;
    private readonly string name;
    private readonly SemaphoreSlim serial=new(1);
    private readonly uint expectedPid;
    private bool connected;
    [DllImport("kernel32.dll",SetLastError=true)]
    private static extern bool GetNamedPipeServerProcessId(Microsoft.Win32.SafeHandles.SafePipeHandle handle,out uint pid);
    [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
    private static extern Microsoft.Win32.SafeHandles.SafePipeHandle CreateFile(string name,uint access,uint share,
        IntPtr security,uint disposition,uint flags,IntPtr template);
    public OwnerBridge(string instance,uint pid)
    {
        expectedPid=pid;
        name="\\\\.\\pipe\\Darkaxt.TailD."+instance;
    }
    public async Task<JsonElement> Request(string op,JsonElement body)
    {
        // Native allowlist: renderer cannot request a session token, arbitrary
        // query, path, SQL, shell command, source access or filesystem operation.
        if(op is not ("state" or "configure" or "pause" or "resume" or "refresh" or "credential" or "shutdown" or "window-closed"))
            throw new InvalidDataException();
        await serial.WaitAsync();
        try
        {
            if(!connected)
            {
                // GenericWrite includes FILE_CREATE_PIPE_INSTANCE. The server
                // deliberately denies that right: open the exact read/write
                // subset, never broaden its DACL to accommodate a client API.
                var handle=CreateFile(name,0x12019b,0,IntPtr.Zero,3,0x40000000|0x100000|0x10000,IntPtr.Zero);
                if(handle.IsInvalid){handle.Dispose();throw new IOException("collector-unavailable");}
                pipe=new NamedPipeClientStream(PipeDirection.InOut,true,true,handle);
                if(!GetNamedPipeServerProcessId(handle,out var pid)||pid!=expectedPid)
                    throw new UnauthorizedAccessException();
                await Exchange("{\"op\":\"window-opened\"}"u8.ToArray());
                connected=true;
            }
            // Lifecycle exact operations deliberately omit body for protocol ACK hooks.
            var request=op is "shutdown" or "window-closed" ? JsonSerializer.SerializeToUtf8Bytes(new{op}) :
                JsonSerializer.SerializeToUtf8Bytes(new{op,body});
            return await Exchange(request);
        }
        finally {serial.Release();}
    }
    private async Task<JsonElement> Exchange(byte[] request)
    {
        await Write(request);
        var head=new byte[4];await pipe!.ReadExactlyAsync(head);
        var size=System.Buffers.Binary.BinaryPrimitives.ReadUInt32BigEndian(head);
        if(size==0||size>16*1024*1024)throw new InvalidDataException();
        var raw=new byte[size];await pipe.ReadExactlyAsync(raw);
        using var result=JsonDocument.Parse(raw,new JsonDocumentOptions{MaxDepth=24});
        await Write("{\"op\":\"ack\"}"u8.ToArray());
        if(result.RootElement.GetProperty("ok").GetBoolean()!=true)
            throw new BridgeError(result.RootElement.TryGetProperty("state",out var state)?state.GetString()!:"unavailable");
        return result.RootElement.GetProperty("data").Clone();
    }
    private async Task Write(byte[] raw)
    {
        if(raw.Length>65536)throw new InvalidDataException();
        var header=new byte[4];System.Buffers.Binary.BinaryPrimitives.WriteUInt32BigEndian(header,(uint)raw.Length);
        await pipe!.WriteAsync(header);await pipe.WriteAsync(raw);await pipe.FlushAsync();
    }
    public void Dispose(){pipe?.Dispose();serial.Dispose();}
}

internal sealed class CollectionWindow : Form
{
    private readonly WebView2 view=new(){Dock=DockStyle.Fill};
    private readonly OwnerBridge bridge;
    private readonly string userData;
    private readonly Dictionary<string,string> options;
    private readonly string instance;
    private bool disposingWindow;
    private int active;
    private static readonly JsonElement Empty=JsonSerializer.SerializeToElement(new{});
    private const string Origin="https://taild.local/index.html";
    [DllImport("dwmapi.dll")]
    private static extern int DwmSetWindowAttribute(IntPtr handle,int attribute,ref int value,int size);
    protected override void OnHandleCreated(EventArgs e)
    {
        base.OnHandleCreated(e);
        // Match the reference shell's dark native theme while preserving Windows
        // resize, keyboard system-menu, minimize/maximize and accessibility.
        int dark=1,caption=0x1e1e1f,text=0xf6f7f9;
        DwmSetWindowAttribute(Handle,20,ref dark,sizeof(int));
        DwmSetWindowAttribute(Handle,35,ref caption,sizeof(int));
        DwmSetWindowAttribute(Handle,36,ref text,sizeof(int));
    }
    public CollectionWindow(string instance,uint pid,string data,Dictionary<string,string> supplied)
    {
        bridge=new OwnerBridge(instance,pid);userData=data;options=supplied;this.instance=instance;
        Text="TailD · Collection";Width=1200;Height=860;MinimumSize=new Size(800,600);
        StartPosition=FormStartPosition.CenterScreen;BackColor=Color.FromArgb(31,30,30);
        Controls.Add(view);Shown+=Initialize;FormClosing+=ClosingWindow;
    }
    private async void Initialize(object? sender,EventArgs args)
    {
        try
        {
            var environmentOptions=new CoreWebView2EnvironmentOptions();
#if DEBUG
            // Explicit test-only loopback inspector; never part of release behavior.
            if(options.TryGetValue("--debug-port",out var debug)&&int.TryParse(debug,out int port)&&port is >=1024 and <=65535)
                environmentOptions.AdditionalBrowserArguments="--remote-debugging-port="+port+" --remote-debugging-address=127.0.0.1";
#endif
            var environment=await CoreWebView2Environment.CreateAsync(null,userData,environmentOptions);
            await view.EnsureCoreWebView2Async(environment);
            var core=view.CoreWebView2;
            core.Settings.AreDefaultContextMenusEnabled=false;
            core.Settings.AreDefaultScriptDialogsEnabled=false;
            core.Settings.AreBrowserAcceleratorKeysEnabled=false;
            core.Settings.IsStatusBarEnabled=false;
            core.Settings.IsPasswordAutosaveEnabled=false;
            core.Settings.IsGeneralAutofillEnabled=false;
            core.Profile.PreferredColorScheme=CoreWebView2PreferredColorScheme.Dark;
#if !DEBUG
            core.Settings.AreDevToolsEnabled=false;
#endif
            // Do not combine virtual-folder mapping with response interception:
            // WebView2 bypasses WebResourceRequested for mapped hosts. Explicit
            // packaged responses below are the sole asset/CSP authority.
            core.NavigationStarting+=(_,e)=>{if(e.Uri!=Origin)e.Cancel=true;};
            core.FrameNavigationStarting+=(_,e)=>e.Cancel=true;
            core.NewWindowRequested+=(_,e)=>e.Handled=true;
            core.PermissionRequested+=(_,e)=>e.State=CoreWebView2PermissionState.Deny;
            core.DownloadStarting+=(_,e)=>e.Cancel=true;
            core.WebMessageReceived+=Message;
#if DEBUG
            core.NavigationCompleted+=(_,e)=>{
                Console.Error.WriteLine("TailD UI navigation: "+e.IsSuccess+" "+e.WebErrorStatus);
                if(options.TryGetValue("--validation-ready-event",out var name)&&
                    name=="Local\\Darkaxt.TailD.UIReady."+instance)
                {
                    using var ready=EventWaitHandle.OpenExisting(name);ready.Set();
                }
            };
#endif
            core.AddWebResourceRequestedFilter("*",CoreWebView2WebResourceContext.All);
            var assets=Directory.EnumerateFiles(Path.Combine(AppContext.BaseDirectory,"ui"),"*",SearchOption.TopDirectoryOnly)
                .Where(path=>Path.GetExtension(path) is ".html" or ".js" or ".css")
                .ToDictionary(path=>"/"+Path.GetFileName(path),path=>File.ReadAllBytes(path));
            if(assets.Values.Sum(bytes=>bytes.Length)>8*1024*1024)throw new InvalidDataException();
            assets["/"]=assets["/index.html"];
            core.WebResourceRequested+=(_,e)=>{
                var uri=new Uri(e.Request.Uri);
                if(uri.Scheme!="https"||uri.Host!="taild.local"||!uri.IsDefaultPort||e.Request.Method!="GET"||uri.Query!="")
                    e.Response=core.Environment.CreateWebResourceResponse(new MemoryStream(),403,"Forbidden","Content-Type: text/plain");
                else if(assets.TryGetValue(uri.AbsolutePath,out var bytes))
                {
                    var mime=uri.AbsolutePath.EndsWith(".js")?"text/javascript":uri.AbsolutePath.EndsWith(".css")?"text/css":"text/html";
                    e.Response=core.Environment.CreateWebResourceResponse(new MemoryStream(bytes,false),200,"OK",
                        "Content-Type: "+mime+"; charset=utf-8\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n"+
                        "Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "+
                        "connect-src 'none'; img-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'none'");
                }
                else e.Response=core.Environment.CreateWebResourceResponse(new MemoryStream(),404,"Not Found","Content-Type: text/plain");
            };
            core.Navigate(Origin);
        }
        catch(Exception error){
#if DEBUG
            Console.Error.WriteLine("TailD UI initialization: "+error.GetType().Name+" "+error.HResult);
#endif
            await FailAndClose();}
    }
    private async void Message(object? sender,CoreWebView2WebMessageReceivedEventArgs e)
    {
        if(e.Source!=Origin||disposingWindow)return;
        long id=0;
        if(Interlocked.Increment(ref active)>4){Interlocked.Decrement(ref active);return;}
        try
        {
            if(Encoding.UTF8.GetByteCount(e.WebMessageAsJson)>65536)throw new InvalidDataException();
            using var document=JsonDocument.Parse(e.WebMessageAsJson,new JsonDocumentOptions{MaxDepth=24});
            var root=document.RootElement;
            var properties=root.EnumerateObject().Select(p=>p.Name).ToArray();
            if(properties.Length!=3||properties.Distinct().Count()!=3||!properties.Order().SequenceEqual(new[]{"body","id","op"}))
                throw new InvalidDataException();
            id=root.GetProperty("id").GetInt64();var op=root.GetProperty("op").GetString()!;
            var body=root.GetProperty("body");if(body.ValueKind!=JsonValueKind.Object)throw new InvalidDataException();
            var data=await bridge.Request(op,body);
            view.CoreWebView2.PostWebMessageAsJson(JsonSerializer.Serialize(new{id,ok=true,data}));
            if(op=="shutdown"){disposingWindow=true;Close();}
        }
        catch(Exception error){if(!view.IsDisposed)view.CoreWebView2.PostWebMessageAsJson(JsonSerializer.Serialize(new{
            id,ok=false,state=error is BridgeError known?known.State:error is InvalidDataException?"invalid-command":"unavailable"}));}
        finally{Interlocked.Decrement(ref active);}
    }
    private async void ClosingWindow(object? sender,FormClosingEventArgs e)
    {
        if(disposingWindow)return;
        e.Cancel=true;Enabled=false;
        try{await bridge.Request("window-closed",Empty);}
        catch(Exception){ /* Broken pipe: runtime owns terminal/disabled cleanup. */ }
        disposingWindow=true;Close();
    }
    private async Task FailAndClose()
    {
        try{await bridge.Request("window-closed",Empty);}catch(Exception){}
        disposingWindow=true;Close();
    }
    protected override void Dispose(bool disposing)
    {
        if(disposing){view.Dispose();bridge.Dispose();}
        base.Dispose(disposing);
    }
}
