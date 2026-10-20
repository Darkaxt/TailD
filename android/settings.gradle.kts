pluginManagement {
  repositories {
    google()
    mavenCentral()
    gradlePluginPortal()
  }
}

plugins { id("org.gradle.toolchains.foojay-resolver-convention") version "1.0.0" }

rootProject.name = "android"

// A self-targeted harness exercises normally signed, non-debuggable delivery APKs.
if (providers.gradleProperty("taildDeliveryHarness").orNull == "true") {
  include(":delivery-harness")
}
