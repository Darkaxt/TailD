// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Separate READ/Write ciphertext and Keystore identities; no plaintext preferences or backups. */
class ControlDCredentials(context: Context) {
  private val preferences =
      context.getSharedPreferences("taild.controld.vault", Context.MODE_PRIVATE)

  enum class Access {
    READ,
    WRITE,
  }

  private fun alias(access: Access) = "taild.controld." + access.name.lowercase()

  private fun keyStore() = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }

  @Synchronized fun contains(access: Access) = preferences.contains(access.name)

  @Synchronized
  fun read(access: Access): String? {
    val encoded = preferences.getString(access.name, null) ?: return null
    try {
      val key =
          keyStore().getKey(alias(access), null) as? SecretKey
              ?: throw ControlDFailure(
                  "credentials",
                  "The credential key is unavailable. Re-enter the credential in setup.",
              )
      val bytes = Base64.decode(encoded, Base64.NO_WRAP)
      cdRequire(bytes.size > 28)
      val cipher = Cipher.getInstance("AES/GCM/NoPadding")
      cipher.init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, bytes.copyOfRange(0, 12)))
      return cipher
          .doFinal(bytes.copyOfRange(12, bytes.size))
          .toString(Charsets.UTF_8)
          .also(::validate)
    } catch (_: Exception) {
      throw ControlDFailure(
          "credentials",
          "The saved credential cannot be read. Re-enter it in setup; history is preserved.",
      )
    }
  }

  @Synchronized
  fun save(access: Access, token: String) {
    validate(token)
    try {
      val store = keyStore()
      val key =
          (store.getKey(alias(access), null) as? SecretKey)
              ?: KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
                  .apply {
                    init(
                        KeyGenParameterSpec.Builder(
                                alias(access),
                                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
                            )
                            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                            .setRandomizedEncryptionRequired(true)
                            .build()
                    )
                  }
                  .generateKey()
      val cipher = Cipher.getInstance("AES/GCM/NoPadding")
      cipher.init(Cipher.ENCRYPT_MODE, key)
      check(cipher.iv.size == 12)
      val wrapped = cipher.iv + cipher.doFinal(token.trim().toByteArray(Charsets.UTF_8))
      check(
          preferences
              .edit()
              .putString(access.name, Base64.encodeToString(wrapped, Base64.NO_WRAP))
              .commit()
      )
    } catch (_: Exception) {
      throw ControlDFailure("credentials", "The credential could not be saved securely")
    }
  }

  @Synchronized
  fun remove(access: Access) {
    try {
      check(preferences.edit().remove(access.name).commit())
      keyStore().deleteEntry(alias(access))
    } catch (_: Exception) {
      throw ControlDFailure("credentials", "Credential removal could not be confirmed")
    }
  }

  companion object {
    fun validate(token: String) {
      cdRequire(
          token.trim().length in 1..8192 && token.none { it.code < 32 || it.code == 127 },
          "Invalid API credential",
      )
    }
  }
}
