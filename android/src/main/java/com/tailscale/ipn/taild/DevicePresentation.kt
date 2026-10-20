// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.tailscale.ipn.R
import com.tailscale.ipn.ui.model.Ipn
import com.tailscale.ipn.ui.model.Tailcfg
import com.tailscale.ipn.ui.theme.off
import com.tailscale.ipn.ui.theme.on

fun deviceOperatingSystem(node: Tailcfg.Node, selfId: String?): String? =
    // SelfChange can omit Hostinfo.OS, but this native client knows its platform.
    // Keep unknown remote platforms unknown instead of guessing from their names.
    if (node.StableID == selfId) "android" else node.Hostinfo.OS?.lowercase()

fun taildropCapability(node: Tailcfg.Node, selfId: String?): Boolean? {
  if (node.Online != true || node.StableID == selfId) return null
  // Exact ipnstate.TaildropTargetStatus from the pinned core. Node capabilities
  // alone omit same-owner eligibility, peer API and the sender's policy.
  return when (node.TaildropTarget) {
    1 -> true
    4,
    7,
    8,
    9 -> false
    else -> null
  }
}

@Composable
fun DevicePresenceName(
    node: Tailcfg.Node,
    selfId: String?,
    state: Ipn.State,
    modifier: Modifier = Modifier,
) {
  val self = node.StableID == selfId
  val online = if (self && state == Ipn.State.Running) true else node.Online
  val presence =
      when (online) {
        true -> "Online"
        false -> "Offline"
        null -> "Unknown"
      }
  val color =
      when (online) {
        true -> MaterialTheme.colorScheme.on
        false -> MaterialTheme.colorScheme.off
        null -> MaterialTheme.colorScheme.outline
      }
  Row(
      modifier,
      verticalAlignment = Alignment.CenterVertically,
      horizontalArrangement = Arrangement.spacedBy(8.dp),
  ) {
    Box(
        Modifier.size(16.dp)
            .background(color.copy(alpha = 0.15f), RoundedCornerShape(3.dp))
            .semantics { contentDescription = presence },
        contentAlignment = Alignment.Center,
    ) {
      Box(Modifier.size(6.dp).background(color, RoundedCornerShape(50)))
    }
    Text(
        node.displayName,
        style = MaterialTheme.typography.titleMedium,
        modifier = Modifier.weight(1f, fill = false),
        overflow = TextOverflow.Ellipsis,
        maxLines = 2,
    )
    val os = deviceOperatingSystem(node, selfId)
    val icon =
        when (os) {
          "android" -> R.drawable.android
          "windows" -> R.drawable.taild_os_windows
          "macos",
          "darwin",
          "ios",
          "ipados" -> R.drawable.taild_os_apple
          "linux" -> R.drawable.taild_os_linux
          else -> R.drawable.computer
        }
    Icon(
        painterResource(icon),
        os ?: "Unknown operating system",
        Modifier.size(18.dp),
    )
  }
}

@Composable
fun DeviceLastOnline(node: Tailcfg.Node, isSelf: Boolean = false) {
  var exact by remember(node.StableID) { mutableStateOf(false) }
  val relative =
      if (node.Online == true || isSelf) "Online now" else relativeLastSeen(node.LastSeen)
  val description = stringResource(R.string.taild_last_online, relative, node.LastSeen ?: "Unknown")
  Text(
      relative,
      style = MaterialTheme.typography.bodySmall,
      modifier =
          Modifier.heightIn(min = 48.dp)
              .widthIn(min = 48.dp)
              .clickable { exact = true }
              .semantics { contentDescription = description },
  )
  if (exact) {
    AlertDialog(
        onDismissRequest = { exact = false },
        title = { Text("Last online") },
        text = { Text("$relative\n${node.LastSeen ?: "No exact timestamp reported"}") },
        confirmButton = { TextButton(onClick = { exact = false }) { Text("Close") } },
    )
  }
  taildropCapability(node, if (isSelf) node.StableID else null)?.let {
    Text(
        if (it) "TailDrop · Enabled" else "TailDrop · Disabled",
        style = MaterialTheme.typography.bodySmall,
    )
  }
}
