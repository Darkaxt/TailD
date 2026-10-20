package com.tailscale.ipn.taild

import android.content.Intent
import android.net.LocalServerSocket
import android.os.Build
import android.os.Bundle
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.By
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.Until
import com.tailscale.ipn.App
import com.tailscale.ipn.MainActivity
import java.io.DataInputStream
import java.time.Instant
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test

/** Explicit opt-in live READ acceptance. No WRITE token or non-GET exchange is permitted. */
class TailDControlDLiveReadTest {
  @get:Rule val compose = createEmptyComposeRule()

  @Test
  fun selectedEndpointBindingPolicyAndHistoryUseActualProvider() = runBlocking {
    assumeTrue(Build.HARDWARE in listOf("ranchu", "goldfish"))
    assumeTrue(InstrumentationRegistry.getArguments().getString("taild_live_read") == "true")
    val endpointName =
        requireNotNull(InstrumentationRegistry.getArguments().getString("endpoint_name"))
    val profileName =
        requireNotNull(InstrumentationRegistry.getArguments().getString("profile_name"))
    require(endpointName.isNotBlank() && profileName.isNotBlank())
    val instrumentation = InstrumentationRegistry.getInstrumentation()
    val context = instrumentation.targetContext
    val isolated = context.createDeviceProtectedStorageContext()
    val app = App.get()
    val job = SupervisorJob()
    val vault = ControlDCredentials(isolated)
    // Only the task-owned emulator's isolated fixture storage is reset.
    isolated.deleteDatabase("taild-dns.sqlite")
    isolated.getSharedPreferences("taild.controld.settings", 0).edit().clear().commit()
    vault.remove(ControlDCredentials.Access.READ)
    vault.remove(ControlDCredentials.Access.WRITE)
    val methods = java.util.concurrent.ConcurrentLinkedQueue<String>()
    val client =
        okhttp3.OkHttpClient.Builder()
            .addNetworkInterceptor { chain ->
              check(chain.request().method == "GET") { "Live acceptance is READ only" }
              methods.add(chain.request().method)
              chain.proceed(chain.request())
            }
            .build()
    val model =
        ControlDModel(
            isolated,
            CoroutineScope(job + Dispatchers.Default),
            app.tailDHistory,
            ControlDApi(client),
            vault,
        )
    val wasRecording = app.tailDHistory.enabled.value
    app.setControlDForEmulatorTest(model)
    try {
      val token =
          LocalServerSocket("taild-r37-live-read").use { server ->
            instrumentation.sendStatus(
                0,
                Bundle().apply { putString("taild_phase", "live-read-ready") },
            )
            withContext(Dispatchers.IO) {
              server.accept().use { socket ->
                val input = DataInputStream(socket.inputStream)
                val length = input.readInt()
                check(length in 1..8192)
                val bytes = ByteArray(length)
                input.readFully(bytes)
                val value = bytes.toString(Charsets.UTF_8)
                bytes.fill(0)
                ControlDCredentials.validate(value)
                socket.outputStream.write(1)
                socket.outputStream.flush()
                value
              }
            }
          }
      app.tailDHistory.setEnabled(true)
      app.tailDHistory.awaitIdle()
      model.configureRead(token, null)
      var state = model.state.first { !it.busySetup && (it.hasRead || it.error != null) }
      assertNull("Live inventory read: ${state.error}", state.error)
      assertFalse(state.hasWrite)
      assertTrue("READ ciphertext round trip", vault.read(ControlDCredentials.Access.READ) == token)
      val target = state.inventory!!.endpoints.single { it.name.equals(endpointName, true) }
      assertTrue(
          "Selected profile association",
          profileName == state.inventory!!.profiles[target.profile],
      )
      model.select(target)
      state =
          model.state.first {
            !it.busySetup &&
                !it.busyHistory &&
                !it.busyPolicy &&
                (it.error != null ||
                    it.historyError != null ||
                    (it.policy != null && (it.page.lastRead != null || it.transient != null)))
          }
      assertNull("Live policy read: ${state.error}", state.error)
      assertTrue("Current selected profile", profileName == state.policy!!.profileName)
      val resources = state.policy!!.resources.mapValues { it.value.state }
      assertTrue(
          "Live category availability: $resources",
          resources.values.all { it == "available" },
      )
      assertTrue(
          "History has a terminal provider result",
          state.historyError == null || state.historyError!!.contains("incomplete"),
      )
      val facts =
          state.transient?.map { it.fact }
              ?: model.store
                  .facts(
                      state.binding!!,
                      Instant.now().minusMillis(TailDHistory.RETENTION_MILLIS),
                      Instant.now(),
                  )
                  .second
                  .map { it.fact }
      assertTrue("Provider returned matching retained DNS observations", facts.isNotEmpty())
      assertTrue(
          "Every observation matches the verified endpoint",
          facts.all { it.raw["endpointId"] == target.id },
      )
      assertTrue("Only GET was issued", methods.isNotEmpty() && methods.all { it == "GET" })
      assertFalse(model.state.value.unresolved)
      context.getSharedPreferences("introScreen", 0).edit().putBoolean("seen", true).commit()
      context.startActivity(
          Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
      )
      val device = UiDevice.getInstance(instrumentation)
      val destination =
          device.wait(Until.findObject(By.text("Control D").pkg(context.packageName)), 30_000)
      assertNotNull(destination)
      destination!!.click()
      assertNotNull(
          device.wait(Until.findObject(By.text(endpointName).pkg(context.packageName)), 30_000)
      )
      assertNotNull(
          device.wait(Until.findObject(By.text(profileName).pkg(context.packageName)), 30_000)
      )
      instrumentation.sendStatus(
          0,
          Bundle().apply {
            putString(
                "taild_live_read",
                "Selected endpoint/profile verified; matching facts present; policy categories=${resources.size}; GET only; write credential absent",
            )
          },
      )
    } finally {
      job.cancelAndJoin()
      app.setControlDForEmulatorTest(null)
      vault.remove(ControlDCredentials.Access.READ)
      vault.remove(ControlDCredentials.Access.WRITE)
      isolated.deleteDatabase("taild-dns.sqlite")
      isolated.getSharedPreferences("taild.controld.settings", 0).edit().clear().commit()
      app.tailDHistory.setEnabled(wasRecording)
      app.tailDHistory.awaitIdle()
      client.connectionPool.evictAll()
      client.dispatcher.executorService.shutdown()
    }
  }
}
