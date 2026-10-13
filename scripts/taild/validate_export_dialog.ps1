param([Parameter(Mandatory=$true)][int]$OwnerPid,[Parameter(Mandatory=$true)][string]$Destination)
$ErrorActionPreference='Stop'
Add-Type -TypeDefinition @'
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
public static class TailDExportDialogProbe {
  delegate void WinEvent(IntPtr hook,uint evt,IntPtr hwnd,int obj,int child,uint thread,uint time);
  delegate bool EnumChild(IntPtr hwnd,IntPtr state);
  [StructLayout(LayoutKind.Sequential)] struct Message {public IntPtr hwnd;public uint message;public UIntPtr wParam;public IntPtr lParam;public uint time;public int x,y;public uint extra;}
  [DllImport("user32.dll")] static extern IntPtr SetWinEventHook(uint first,uint last,IntPtr module,WinEvent callback,uint pid,uint thread,uint flags);
  [DllImport("user32.dll")] static extern bool UnhookWinEvent(IntPtr hook);
  [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr parent,EnumChild callback,IntPtr state);
  [DllImport("user32.dll")] static extern int GetDlgCtrlID(IntPtr hwnd);
  [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr hwnd,StringBuilder text,int maximum);
  [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr hwnd,StringBuilder text,int maximum);
  [DllImport("user32.dll")] static extern IntPtr GetAncestor(IntPtr hwnd,uint flags);
  [DllImport("user32.dll",CharSet=CharSet.Unicode,EntryPoint="SendMessageW")] static extern IntPtr SetText(IntPtr hwnd,uint message,IntPtr w,string value);
  [DllImport("user32.dll",CharSet=CharSet.Unicode,EntryPoint="SendMessageW")] static extern IntPtr ReadText(IntPtr hwnd,uint message,IntPtr w,StringBuilder value);
  [DllImport("user32.dll")] static extern bool PostMessage(IntPtr hwnd,uint message,IntPtr w,IntPtr l);
  [DllImport("user32.dll")] static extern int GetMessage(out Message message,IntPtr hwnd,uint first,uint last);
  [DllImport("user32.dll")] static extern bool PeekMessage(out Message message,IntPtr hwnd,uint first,uint last,uint remove);
  [DllImport("user32.dll")] static extern void PostQuitMessage(int result);
  [DllImport("user32.dll")] static extern bool PostThreadMessage(uint thread,uint message,IntPtr w,IntPtr l);
  [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
  public static int Run(int pid,string path) {
    int result=1;bool dispatched=false;
    Message ignored;PeekMessage(out ignored,IntPtr.Zero,0,0,0);
    var thread=GetCurrentThreadId();
    using(var owner=Process.GetProcessById(pid)) {
      var watcher=new Thread(()=>{owner.WaitForExit();PostThreadMessage(thread,0x12,IntPtr.Zero,IntPtr.Zero);});watcher.IsBackground=true;watcher.Start();
      WinEvent callback=(hook,evt,hwnd,obj,child,eventThread,time)=>{
        if(dispatched||hwnd==IntPtr.Zero)return;
        try {
          var window=GetAncestor(hwnd,2);
          var title=new StringBuilder(256);GetWindowText(window,title,title.Capacity);
          if(title.ToString()!="Export private TailD evidence")return;
          IntPtr file=IntPtr.Zero,save=IntPtr.Zero;
          EnumChildWindows(window,(control,state)=>{var id=GetDlgCtrlID(control);var kind=new StringBuilder(64);GetClassName(control,kind,kind.Capacity);
            if(id==1001&&kind.ToString()=="Edit")file=control;if(id==1&&kind.ToString()=="Button")save=control;return true;},IntPtr.Zero);
          // This Windows dialog reuses ID 1001 for an address toolbar, and its
          // filename edit exposes no UIA ValuePattern. Bind class+ID and actual
          // filename focus; operate the native edit/button event paths directly.
          if(file==IntPtr.Zero||save==IntPtr.Zero)return;
          if(hwnd!=file)return; // Earlier directory/dialog focus precedes filename initialization.
          dispatched=true;
          // SetWindowText/GetWindowText do not access another process's edit
          // contents. Use their documented cross-process native text messages.
          if(SetText(file,0x0c,IntPtr.Zero,path)==IntPtr.Zero)throw new InvalidOperationException("Filename input failed");
          var value=new StringBuilder(32768);ReadText(file,0x0d,(IntPtr)value.Capacity,value);
          if(value.ToString()!=path)throw new InvalidOperationException("Filename input did not match");
          if(!PostMessage(save,0xf5,IntPtr.Zero,IntPtr.Zero))throw new InvalidOperationException("Save action failed");
          result=0;PostQuitMessage(0);
        } catch(Exception error) {Console.Error.WriteLine("Native export dialog probe: "+error.GetType().Name);PostQuitMessage(1);}
      };
      var subscription=SetWinEventHook(0x8005,0x8005,IntPtr.Zero,callback,(uint)pid,0,0);
      if(subscription==IntPtr.Zero)throw new InvalidOperationException("Dialog event subscription failed");
      try {Console.WriteLine("ready");Console.Out.Flush();Message message;while(GetMessage(out message,IntPtr.Zero,0,0)>0){}return result;}
      finally {UnhookWinEvent(subscription);GC.KeepAlive(callback);}
    }
  }
}
'@
exit [TailDExportDialogProbe]::Run($OwnerPid,$Destination)
