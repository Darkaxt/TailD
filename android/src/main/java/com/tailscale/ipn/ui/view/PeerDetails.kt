// Copyright (c) Tailscale Inc & AUTHORS
// SPDX-License-Identifier: BSD-3-Clause

package com.tailscale.ipn.ui.view

import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.AnnotatedString
import androidx.lifecycle.viewmodel.compose.viewModel
import com.tailscale.ipn.R
import com.tailscale.ipn.ui.theme.listItem
import com.tailscale.ipn.ui.util.AndroidTVUtil.isAndroidTV
import com.tailscale.ipn.ui.util.Lists
import com.tailscale.ipn.ui.util.itemsWithDividers
import com.tailscale.ipn.ui.viewModel.PeerDetailsViewModel
import com.tailscale.ipn.ui.viewModel.PeerDetailsViewModelFactory
import com.tailscale.ipn.ui.viewModel.PingViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PeerDetails(
    onNavigateBack: () -> Unit,
    nodeId: String,
    pingViewModel: PingViewModel,
    model: PeerDetailsViewModel =
        viewModel(
            factory =
                PeerDetailsViewModelFactory(nodeId, LocalContext.current.filesDir, pingViewModel)
        ),
) {
  val isPinging by model.isPinging.collectAsState()
  val connectionState by com.tailscale.ipn.ui.notifier.Notifier.state.collectAsState()

  model.netmap.collectAsState().value?.let { netmap ->
    model.node.collectAsState().value?.let { node ->
      Scaffold(
          topBar = {
            Header(
                title = {
                  com.tailscale.ipn.taild.DevicePresenceName(
                      node,
                      netmap.SelfNode.StableID,
                      connectionState,
                  )
                },
                actions = {
                  IconButton(onClick = { model.startPing() }) {
                    Icon(
                        painter = painterResource(R.drawable.sensors_24),
                        contentDescription = "Ping device",
                    )
                  }

                  val favorites by model.favorites.collectAsState()
                  val isWriting by model.isWritingFavorites.collectAsState()
                  val isPinned = favorites?.isFavoriteDevice(node.StableID) == true

                  IconButton(enabled = !isWriting, onClick = { model.togglePin() }) {
                    Icon(
                        painterResource(if (isPinned) R.drawable.unpin_24 else R.drawable.pin_24),
                        contentDescription =
                            stringResource(
                                if (isPinned) R.string.unpin_device else R.string.pin_device
                            ),
                    )
                  }
                },
                onBack = onNavigateBack,
            )
          },
      ) { innerPadding ->
        LazyColumn(
            modifier = Modifier.padding(innerPadding),
        ) {
          item(key = "tailscaleAddresses") {
            Lists.MutedHeader(stringResource(R.string.tailscale_addresses))
          }

          itemsWithDividers(node.displayAddresses, key = { it.address }) {
            AddressRow(address = it.address, type = it.typeString)
          }

          item(key = "infoDivider") { Lists.SectionDivider() }

          itemsWithDividers(node.info, key = { "info_${it.titleRes}" }) {
            ValueRow(title = stringResource(id = it.titleRes), value = it.value.getString())
          }
          item(key = "taildOwner") {
            ValueRow(
                title = "Owner",
                value =
                    netmap.userProfile(node.User)?.DisplayName?.ifBlank { null }
                        ?: netmap.userProfile(node.User)?.LoginName
                        ?: "Unknown",
            )
          }
          item(key = "taildPresence") {
            ValueRow(
                title = "Presence",
                value =
                    when (node.Online) {
                      true -> "Online"
                      false -> "Offline"
                      null -> "Unknown"
                    },
            )
          }
          item(key = "taildLastSeen") {
            ValueRow(title = "Last online", value = node.LastSeen ?: "Unknown")
          }
          item(key = "taildRoutes") {
            ValueRow(
                title = "Allowed routes",
                value = node.AllowedIPs?.joinToString("\n") ?: "Unknown",
            )
          }
          item(key = "taildTags") {
            ValueRow(
                title = "Tags",
                value = node.Tags?.joinToString(", ")?.ifEmpty { "None" } ?: "Unknown",
            )
          }
        }
        if (isPinging) {
          ModalBottomSheet(onDismissRequest = { model.onPingDismissal() }) {
            PingView(model = model.pingViewModel)
          }
        }
      }
    }
  }
}

@Composable
fun AddressRow(address: String, type: String) {
  val localClipboardManager = LocalClipboardManager.current

  // Android TV doesn't have a clipboard, nor any way to use the values, so visible only.
  val modifier =
      if (isAndroidTV()) {
        Modifier.focusable(false)
      } else {
        Modifier.clickable { localClipboardManager.setText(AnnotatedString(address)) }
      }

  ListItem(
      modifier = modifier,
      colors = MaterialTheme.colorScheme.listItem,
      headlineContent = { Text(text = address) },
      supportingContent = { Text(text = type) },
      trailingContent = {
        // TODO: there is some overlap with other uses of clipboard, DRY
        if (!isAndroidTV()) {
          Icon(painter = painterResource(id = R.drawable.clipboard), null)
        }
      },
  )
}

@Composable
fun ValueRow(title: String, value: String) {
  ListItem(
      colors = MaterialTheme.colorScheme.listItem,
      headlineContent = { Text(text = title) },
      supportingContent = { Text(text = value) },
  )
}
