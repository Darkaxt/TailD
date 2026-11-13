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
    def test_peer_modernization_keeps_fork_presence_and_details(self):
        source=(ROOT/'ui/view/PeerDetails.kt').read_text(encoding='utf-8')
        for marker in ('fun PeerDetailsView(', 'dataSource: PeerDetailsDataSource',
                'PeerDetailsViewModelFactory(nodeId, pingViewModel, dataSource)',
                'Notifier.state.collectAsStateWithLifecycle()',
                'DevicePresenceName(', 'state.connectionState',
                'peerDetailsViewModel.startPing()', 'peerDetailsViewModel.togglePin()',
                'peerDetailsViewModel.onPingDismissal()',
                'item(key = "taildOwner")', 'item(key = "taildPresence")',
                'item(key = "taildLastSeen")', 'item(key = "taildRoutes")',
                'item(key = "taildTags")'):
            self.assertIn(marker,source)
        self.assertFalse(re.search(r'(?<![.\w])model\.',source))
        self.assertFalse(re.search(r'^(?:<<<<<<<|=======|>>>>>>>)',source,re.M))

    def test_tv_component_inheritance_keeps_fork_preferences_and_accessibility(self):
        settings=(ROOT/'ui/view/SettingsView.kt').read_text(encoding='utf-8')
        self.assertTrue(re.search(r'if \(!(?:state\.)?embedded\)\s*Header\([^)]*settings_title',settings))
        for marker in ('isTv = isAndroidTV()', 'R.string.taild_collect_analytics',
                'R.string.taild_delete_history',
                'R.string.taild_use_exit_node', 'managedExit.value.isNullOrEmpty()',
                'TailDAboutDialog(', 'contentDescription = label'):
            self.assertIn(marker,settings)
        if 'private fun SettingsScreen(' in settings:
            for marker in ('onRecordingChange = history::setEnabled',
                    'onToggle = onRecordingChange', 'onDeleteHistory = { showDeleteHistoryDialog = true }',
                    'onSourceHealth = { showSourceHealth = true }',
                    'onClick = nav.onNavigateToRunAsExitNode',
                    'settingsNav.onNavigateToExitNodes()',
                    'val factory = remember(dataSource) { SettingsViewModelFactory(dataSource) }',
                    'dataSource.prefs.collectAsStateWithLifecycle()',
                    'dataSource.netmap.collectAsStateWithLifecycle()',
                    'embedded = embedded', 'if (!state.embedded)',
                    'history.deleteHistory()', 'tailDControlD.clearHistory()'):
                self.assertIn(marker,settings)
            shell=(ROOT/'taild/TailDTailscaleView.kt').read_text(encoding='utf-8')
            for marker in ('remember { SettingsDataSourceImpl() }', 'dataSource = settingsDataSource',
                    'mainViewModel = viewModel', 'embedded = true'):
                self.assertIn(marker,shell)
        else:
            for marker in ('onToggle = history::setEnabled',
                    'settingsNav.onNavigateToExitNodes', 'settingsNav.onNavigateToRunAsExitNode'):
                self.assertIn(marker,settings)
        avatar=(ROOT/'ui/view/Avatar.kt').read_text(encoding='utf-8')
        for marker in ('isTv: Boolean', 'sizeIn(minWidth = 48.dp, minHeight = 48.dp)',
                'contentDescription = actionLabel', '.conditional(isTv, { padding(4.dp) })'):
            self.assertIn(marker,avatar)
        self.assertNotIn('AndroidTVUtil',avatar)

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
            block=re.search(r'composable<'+route+r'Route>\s*\{(.*?)(?=\n              composable<|\n            \})',source,re.S)
            self.assertIsNotNone(block,route+' destination must remain present')
            body=block[1]
            if route in ('DNSSettings','TailnetLock','SubnetRouting') and 'val dataSource = remember' in body:
                factory={'DNSSettings':'DNSSettingsDataSourceImpl',
                         'TailnetLock':'TailnetLockSetupDataSourceImpl',
                         'SubnetRouting':'SubnetRoutingDataSourceImpl'}[route]
                self.assertIn('val dataSource = remember { '+factory+'() }',body)
                self.assertIn(view+'(',body)
                self.assertIn('backToSettings = backToPreferences',body)
                self.assertIn('dataSource = dataSource',body)
            else:
                self.assertIn(view+'(backToPreferences)',body,
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
