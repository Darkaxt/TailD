package io.github.darkaxt.taild.delivery

import android.content.Intent
import android.net.Uri
import android.os.Build
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.*
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test

class TailDNavigationDeliveryTest {
  @Test
  fun publicDeviceLinkOpensConnectionFromDashboard() {
    assumeTrue(Build.HARDWARE in listOf("ranchu", "goldfish"))
    val context = InstrumentationRegistry.getInstrumentation().targetContext
    val pkg = "io.github.darkaxt.taildns"
    val device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())
    context.startActivity(
        context.packageManager
            .getLaunchIntentForPackage(pkg)!!
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
    )
    device.wait(Until.findObject(By.text("Tailscale").pkg(pkg)), 30_000)!!.click()
    device.wait(Until.findObject(By.text("Activity").pkg(pkg)), 30_000)!!.click()
    val dashboard = device.wait(Until.findObject(By.text("Dashboard").pkg(pkg)), 30_000)
    assertNotNull(dashboard)
    dashboard!!.click()
    assertTrue(device.wait(Until.hasObject(By.text("TailD · Dashboard").pkg(pkg)), 30_000))
    context.startActivity(
        Intent(Intent.ACTION_VIEW, Uri.parse("taildns://navigate/main/devices"))
            .setPackage(pkg)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    )
    assertTrue(
        "Public device link must select the actual Tailscale destination",
        device.wait(Until.hasObject(By.text("TailD · Tailscale").pkg(pkg)), 30_000),
    )
    val connection = device.wait(Until.findObject(By.text("Connection").pkg(pkg)), 30_000)
    assertNotNull(connection)
    var ancestor: UiObject2? = connection
    var selected = false
    while (ancestor != null) {
      selected = selected || ancestor.isSelected
      ancestor = ancestor.parent
    }
    assertTrue("Connection tab must be selected", selected)
  }
}
