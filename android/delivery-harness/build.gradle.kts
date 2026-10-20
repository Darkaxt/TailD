import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
  alias(libs.plugins.android.application)
  alias(libs.plugins.ktfmt)
}

repositories {
  google()
  mavenCentral()
}

kotlin { compilerOptions { jvmTarget = JvmTarget.JVM_17 } }

android {
  namespace = "io.github.darkaxt.taild.delivery"
  compileSdk = providers.gradleProperty("androidApiLevel").get().toInt()
  defaultConfig {
    applicationId = "io.github.darkaxt.taild.delivery"
    minSdk = 26
    targetSdk = 35
    versionCode = 1
    versionName = "1"
    testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
  }
  compileOptions {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
  }
}

dependencies {
  androidTestImplementation(libs.androidx.test.runner)
  androidTestImplementation(libs.androidx.test.ext.junit)
  androidTestImplementation(libs.androidx.test.uiautomator)
  androidTestImplementation(libs.junit)
  androidTestImplementation(libs.kotlinx.coroutines.core)
  androidTestImplementation(libs.kotlinx.serialization.json)
  androidTestImplementation(libs.kotlin.stdlib)
}
