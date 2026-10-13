param([Parameter(Mandatory=$true)][int]$NativePid,[Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference='Stop'
Add-Type -ReferencedAssemblies UIAutomationClient,UIAutomationTypes,WindowsBase -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading;
using System.Windows.Automation;
public static class TailDReleaseProbe {
  public static object Run(int pid) {
    using(var process=Process.GetProcessById(pid))
    using(var changed=new AutoResetEvent(false)) {
      process.WaitForInputIdle();process.Refresh();
      if(process.MainWindowHandle==IntPtr.Zero)throw new InvalidOperationException("Native window absent");
      var root=AutomationElement.FromHandle(process.MainWindowHandle);
      var reports=new List<object>();bool settings=false;
      StructureChangedEventHandler structure=(s,e)=>changed.Set();
      AutomationPropertyChangedEventHandler property=(s,e)=>changed.Set();
      Automation.AddStructureChangedEventHandler(root,TreeScope.Subtree,structure);
      Automation.AddAutomationPropertyChangedEventHandler(root,TreeScope.Subtree,property,
        AutomationElement.NameProperty,AutomationElement.IsEnabledProperty,AutomationElement.BoundingRectangleProperty);
      process.EnableRaisingEvents=true;process.Exited+=(s,e)=>changed.Set();
      try {
        while(true) {
          if(process.HasExited)throw new InvalidOperationException("Release UI exited before readiness");
          var nodes=root.FindAll(TreeScope.Descendants,Condition.TrueCondition);
          if(nodes.Count>2000)throw new InvalidOperationException("Unexpected UIA scope");
          var snapshot=new List<object>();AutomationElement nav=null,refresh=null,received=null,stop=null;
          for(int i=0;i<nodes.Count;i++) {
            var node=nodes[i];var info=node.Current;var bounds=info.BoundingRectangle;
            snapshot.Add(new {id=info.AutomationId,name=info.Name,role=info.ControlType.ProgrammaticName,
              enabled=info.IsEnabled,offscreen=info.IsOffscreen,focused=info.HasKeyboardFocus,
              bounds=new {x=bounds.X,y=bounds.Y,width=bounds.Width,height=bounds.Height,unit="physical px"}});
            if(info.Name=="Settings"&&info.ControlType==ControlType.Button)nav=node;
            if(info.Name=="Refresh view"&&info.IsEnabled)refresh=node;
            if(info.AutomationId=="received-card"&&info.ControlType==ControlType.Button&&info.IsEnabled)received=node;
            if(info.Name=="Stop collector & close"&&info.ControlType==ControlType.Button&&info.IsEnabled)stop=node;
            if(info.Name.Contains("can’t reach this page")||info.Name.Contains("ERR_ACCESS_DENIED"))
              throw new InvalidOperationException("Release virtual-origin navigation failed");
          }
          if(!settings&&nav!=null&&nav.Current.IsEnabled&&refresh!=null&&received!=null) {
            reports.Add(new {page="Overview",nodes=snapshot});
            ((InvokePattern)nav.GetCurrentPattern(InvokePattern.Pattern)).Invoke();settings=true;
          } else if(settings&&stop!=null) {
            reports.Add(new {page="Settings",nodes=snapshot});
            return new {ok=true,window_handle=root.Current.NativeWindowHandle,native_pid=pid,
              readiness="actual enabled Overview metrics and Settings stop control",pages=reports,
              debug_hooks=false,limitations=new[]{"UIA semantics, not DOM/CSP introspection","No physical presentation timing"}};
          }
          changed.WaitOne();
        }
      } finally {
        Automation.RemoveStructureChangedEventHandler(root,structure);
        Automation.RemoveAutomationPropertyChangedEventHandler(root,property);
      }
    }
  }
}
'@
[TailDReleaseProbe]::Run($NativePid) | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath $Output -Encoding UTF8
