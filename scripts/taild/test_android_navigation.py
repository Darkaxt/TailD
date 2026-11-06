"""Source wiring guards for the fork hooks most exposed by navigation inheritance.

The inherited Kotlin build/tests establish API compatibility. These guards keep
an otherwise compiling upstream merge from replacing the TailD shell or losing
its preference return, device selection and presence presentation boundaries.
"""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[2]/'android/src/main/java/com/tailscale/ipn'


class AndroidNavigationTest(unittest.TestCase):
    def test_typed_graph_keeps_taild_shell_and_preference_returns(self):
        source=(ROOT/'MainActivity.kt').read_text(encoding='utf-8')
        self.assertTrue(re.search(r'composable<MainRoute>[^\n]*\{\s*com\.tailscale\.ipn\.taild\.TailDTailscaleView\(',source),
            'The typed main destination must render the TailD shell')
        self.assertTrue('val backToPreferences: () -> Unit = { navController.popBackStack() }' in source,
            'Preference pages must return to the actual originating TailD page')
        for route,view in (('DNSSettings','DNSSettingsView'),('BugReport','BugReportView'),
                ('SplitTunneling','SplitTunnelAppPickerView'),('TailnetLock','TailnetLockSetupView'),
                ('SubnetRouting','SubnetRoutingView'),('About','AboutView'),
                ('MDMSettings','MDMSettingsDebugView'),('ManagedBy','ManagedByView')):
            self.assertTrue(re.search(r'composable<'+route+r'Route>\s*\{\s*'+view+r'\(backToPreferences\)',source),
                route+' must keep its fork preference return')
        self.assertTrue('onNavigateToExitNodes = { navController.navigate(ExitNodesRoute) }' in source)
        self.assertTrue('onNavigateToRunAsExitNode = { navController.navigate(RunExitNodeRoute) }' in source)
        self.assertTrue('destinationState = taildDestination' in source and 'tabState = taildTailscaleTab' in source)
        self.assertFalse(re.search(r'(?:composable|navController\.navigate|backTo)\("',source),
            'String destinations cannot coexist with the inherited typed graph')

    def test_device_links_and_search_keep_fork_device_presentation(self):
        links=(ROOT/'ui/util/DeepLinkNavigator.kt').read_text(encoding='utf-8')
        self.assertTrue(re.search(r'showDevices\(\)\s*navigateOverMain\(PeerDetailsRoute\(node\.StableID\)\)',links),
            'A peer deep link must activate the TailD device section before opening details')
        self.assertTrue(re.search(r'private fun showDeviceList\(\)\s*\{\s*showDevices\(\)\s*popToMain\(\)',links))
        search=(ROOT/'ui/view/SearchView.kt').read_text(encoding='utf-8')
        self.assertTrue('DevicePresenceName(peer, netmap?.SelfNode?.StableID, ipnState)' in search,
            'Typed search navigation must retain accurate fork presence labels')
        self.assertTrue('navController.navigate(PeerDetailsRoute(peer.StableID))' in search)
        for source in (links,search):
            self.assertFalse(re.search(r'^(?:<<<<<<<|=======|>>>>>>>)',source,re.M),
                'Inherited source must contain no unresolved conflict')


if __name__=='__main__':unittest.main()
