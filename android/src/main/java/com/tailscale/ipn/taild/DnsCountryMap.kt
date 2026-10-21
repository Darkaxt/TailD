// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

import android.content.res.AssetManager
import android.graphics.Region
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.asAndroidPath
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject

internal data class DnsCountryShape(val code: String, val path: Path, val hit: Region)

internal fun readDnsCountryShapes(assets: AssetManager): List<DnsCountryShape> {
  val data = assets.open("taild-world-map.json").bufferedReader().use { JSONObject(it.readText()) }
  require(
      data.getInt("schema") == 1 && data.getInt("width") == 1000 && data.getInt("height") == 500
  )
  val countries = data.getJSONArray("countries")
  return List(countries.length()) { i ->
    val entry = countries.getJSONObject(i)
    val path = PathParser().parsePathString(entry.getString("path")).toPath()
    DnsCountryShape(
        entry.getString("code"),
        path,
        Region().apply { setPath(path.asAndroidPath(), Region(0, 0, 1000, 500)) },
    )
  }
}

/**
 * Passive offline answer-country display. The existing list supplies accessible country actions.
 */
@Composable
internal fun DnsCountryMap(counts: Map<String, Long>, onCountry: (String) -> Unit) {
  val assets = LocalContext.current.applicationContext.assets
  val shapes by
      produceState<List<DnsCountryShape>?>(null, assets) {
        value = withContext(Dispatchers.Default) { readDnsCountryShapes(assets) }
      }
  val currentOnCountry by rememberUpdatedState(onCountry)
  val currentCounts by rememberUpdatedState(counts)
  val colors = MaterialTheme.colorScheme
  val loaded = shapes
  if (loaded == null) {
    Text("Loading offline country map…")
    return
  }
  val mapped = remember(loaded) { loaded.map { it.code }.toSet() }
  val unknown = counts.filterKeys { it !in mapped }.values.sum()
  val screenHeight = LocalConfiguration.current.screenHeightDp.dp
  BoxWithConstraints {
    Canvas(
        Modifier.fillMaxWidth()
            .height(minOf(maxWidth / 2, screenHeight * 0.4f))
            .background(colors.surfaceContainer)
            .testTag("taild-dns-country-map")
            .semantics {
              contentDescription =
                  "DNS answer-country map. Observed countries are highlighted. Country list below provides equivalent actions."
            }
            .pointerInput(loaded) {
              detectTapGestures { at ->
                val factor = minOf(size.width / 1000f, size.height / 500f)
                val x = ((at.x - (size.width - 1000 * factor) / 2) / factor).toInt()
                val y = ((at.y - (size.height - 500 * factor) / 2) / factor).toInt()
                loaded
                    .firstOrNull { (currentCounts[it.code] ?: 0) > 0 && it.hit.contains(x, y) }
                    ?.let { currentOnCountry(it.code) }
              }
            }
    ) {
      // The packaged projection is already clipped at the antimeridian, with padding.
      val factor = minOf(size.width / 1000, size.height / 500)
      translate((size.width - 1000 * factor) / 2, (size.height - 500 * factor) / 2) {
        scale(factor, factor, pivot = androidx.compose.ui.geometry.Offset.Zero) {
          loaded.forEach { country ->
            drawPath(
                country.path,
                if ((counts[country.code] ?: 0) > 0) colors.primary else colors.outlineVariant,
            )
            drawPath(country.path, colors.surfaceContainer, style = Stroke(0.65f))
          }
        }
      }
    }
  }
  Text(
      "DNS answers · tap a highlighted country",
      style = MaterialTheme.typography.bodySmall,
  )
  if (counts.isEmpty())
      Text(
          "No answer countries observed in this window. Coverage gaps remain unknown.",
          style = MaterialTheme.typography.bodySmall,
      )
  if (unknown > 0)
      Text(
          "Unknown / unmapped · $unknown",
          style = MaterialTheme.typography.bodySmall,
      )
}
