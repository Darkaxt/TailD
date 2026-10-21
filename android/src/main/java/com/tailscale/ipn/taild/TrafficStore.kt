// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

import android.content.Context
import android.content.pm.PackageManager
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import android.os.Build
import java.math.BigInteger
import java.security.MessageDigest
import org.json.JSONArray
import org.json.JSONObject

data class TrafficRow(
    val first: Long,
    val last: Long,
    val bytes: Long,
    val packets: Long,
    val metadata: String,
    val lookupFirst: Long,
    val lookupLast: Long,
) {
  val fact: JSONObject
    get() = JSONObject(metadata)

  val identity: String
    get() = fact.getJSONObject("identity").getString("label")

  val uid: Int
    get() = fact.getInt("uid")

  val upload: Boolean
    get() = fact.getBoolean("upload")
}

/** Immutable query result. Detail and export always use these exact rows and UTC boundaries. */
data class TrafficSnapshot(
    val from: Long,
    val until: Long,
    val revision: Long,
    val rows: List<TrafficRow>,
    val boundaryBytes: Long,
    val coverage: String,
    val sessions: String,
    val osUsage: String? = null,
) {
  val sent
    get() = rows.filter { it.upload }.sumOf { it.bytes }

  val received
    get() = rows.filter { !it.upload }.sumOf { it.bytes }

  fun export(selectedIdentity: String? = null): String {
    val facts = JSONArray()
    rows
        .filter {
          selectedIdentity == null ||
              it.fact.getJSONObject("identity").toString() == selectedIdentity ||
              it.fact.optJSONObject("dns")?.optJSONObject("queryIdentity")?.toString() ==
                  selectedIdentity
        }
        .forEach { row ->
          val fact = row.fact
          val candidates = fact.optJSONArray("candidates") ?: JSONArray()
          val estimates = JSONArray()
          for (i in 0 until candidates.length()) {
            estimates.put(
                JSONObject()
                    .put("domain", candidates.getJSONObject(i).getString("name"))
                    .put("byteNumerator", BigInteger.valueOf(row.bytes).toString())
                    .put("byteDenominator", candidates.length().toString())
            )
          }
          facts.put(
              JSONObject()
                  .put("firstAt", row.first)
                  .put("lastAt", row.last)
                  .put("packets", row.packets)
                  .put("ownerLookupFirstAt", row.lookupFirst)
                  .put("ownerLookupLastAt", row.lookupLast)
                  .put("measuredBytes", row.bytes)
                  .put("unmatchedBytes", if (candidates.length() == 0) row.bytes else 0)
                  .put("equalWeightEstimates", estimates)
                  .put("source", fact)
          )
        }
    return JSONObject()
        .put("format", "TailD-Android-traffic-v1")
        .put("dnsComparison", "strict-ascii-v1")
        .put("fromInclusive", from)
        .put("untilExclusive", until)
        .put("revision", revision)
        .put("coverage", coverage)
        .put("boundaryUnallocatedBytes", boundaryBytes)
        .put("sessions", JSONArray(sessions))
        .put("osUsage", osUsage?.let { JSONObject(it) } ?: JSONObject.NULL)
        .put("facts", facts)
        .toString(2)
  }
}

/** Used only by TailDHistory's existing IO actor. No provider or network access. */
internal class TrafficStore(private val context: Context) :
    SQLiteOpenHelper(context, "taild-traffic.sqlite", null, 1) {
  private val queryIdentities = mutableMapOf<String, JSONObject>()

  init {
    setWriteAheadLoggingEnabled(true)
  }

  override fun onConfigure(db: SQLiteDatabase) {
    db.rawQuery("PRAGMA secure_delete=ON", null).use {
      check(it.moveToFirst() && it.getInt(0) == 1)
    }
  }

  override fun onCreate(db: SQLiteDatabase) {
    db.execSQL(
        "CREATE TABLE facts(key TEXT PRIMARY KEY,first_at INTEGER NOT NULL,last_at INTEGER NOT NULL,bytes INTEGER NOT NULL,packets INTEGER NOT NULL,payload TEXT NOT NULL,lookup_first INTEGER NOT NULL,lookup_last INTEGER NOT NULL)"
    )
    db.execSQL("CREATE INDEX facts_time ON facts(last_at)")
    db.execSQL(
        "CREATE TABLE sessions(id TEXT PRIMARY KEY,sequence INTEGER NOT NULL,first_at INTEGER NOT NULL,last_at INTEGER NOT NULL,dropped INTEGER NOT NULL,unacknowledged INTEGER NOT NULL)"
    )
    db.execSQL("CREATE TABLE metadata(key TEXT PRIMARY KEY,value INTEGER NOT NULL)")
    db.execSQL("INSERT INTO metadata VALUES('revision',0),('prunedBytes',0)")
  }

  override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
    error("Unsupported traffic migration; preserve existing history")
  }

  fun commit(batch: JSONObject, expectedSession: String): Boolean {
    if (batch.getString("session") != expectedSession || expectedSession.isEmpty()) return false
    val db = writableDatabase
    db.beginTransaction()
    try {
      val sequence = batch.getLong("sequence")
      val prior =
          db.rawQuery("SELECT sequence FROM sessions WHERE id=?", arrayOf(expectedSession)).use {
            if (it.moveToFirst()) it.getLong(0) else 0
          }
      if (sequence <= prior) {
        db.setTransactionSuccessful()
        return true
      }
      val facts = batch.getJSONArray("facts")
      val identities = mutableMapOf<Int, JSONObject>()
      var first = Long.MAX_VALUE
      var last = 0L
      for (i in 0 until facts.length()) {
        val fact = facts.getJSONObject(i)
        val at = fact.getLong("at")
        val bytes = fact.getLong("bytes")
        check(bytes >= 0 && bytes <= 65575)
        first = minOf(first, at)
        last = maxOf(last, at)
        val uid = fact.getInt("uid")
        fact.put("identity", identityAtPacket(identities.getOrPut(uid) { identity(uid) }, at))
        fact.optJSONObject("dns")?.let { dns ->
          val queryAt = if (dns.optBoolean("response")) dns.optLong("queryAt") else at
          val key =
              JSONArray(
                      listOf(
                          expectedSession,
                          fact.getJSONObject("scope").getString("id"),
                          fact.optLong("networkGeneration"),
                          fact.getInt("protocol"),
                          fact.getString("local"),
                          fact.getString("remote"),
                          fact.getInt("localPort"),
                          fact.getInt("remotePort"),
                          dns.getInt("id"),
                          dns.optInt("type"),
                          dns.optInt("class"),
                          dns.getString("canonical"),
                          queryAt,
                      )
                  )
                  .toString()
          if (!dns.optBoolean("response")) {
            if (queryIdentities.size >= 4096) queryIdentities.clear()
            queryIdentities[key] = fact.getJSONObject("identity")
          } else if (dns.optBoolean("matched")) {
            // Use the package generation observed with the actual question, never
            // relabel that question from a later UID/package lookup at reply time.
            dns.put(
                "queryIdentity",
                queryIdentities.remove(key)
                    ?: JSONObject()
                        .put("uid", dns.optInt("queryUid", -1))
                        .put("label", "Query app snapshot unavailable")
                        .put("packages", JSONArray()),
            )
          }
        }
        fact.put("session", expectedSession)
        fact.put("minute", at / 60000)
        val lookup = fact.getLong("lookupAt")
        fact.remove("at")
        fact.remove("bytes")
        fact.remove("lookupAt")
        // Keep the actual lookup range as aggregation boundaries, never invent a packet UID.
        fact.put(
            "ownerMethod",
            if (lookup == 0L) "ownership-unavailable"
            else if (Build.VERSION.SDK_INT >= 29) "active-vpn-tuple-lookup"
            else "unsupported-before-api29",
        )
        fact.put(
            "lookupDelayClass",
            if (lookup == 0L) "lookup-not-available"
            else if (lookup >= at && lookup - at <= 1000) "within-1-second"
            else "delayed-or-clock-changed",
        )
        val packets = fact.getLong("packets")
        fact.remove("packets")
        val payload = fact.toString()
        val key = hash(payload)
        db.execSQL(
            "INSERT OR IGNORE INTO facts VALUES(?,?,?,?,?,?,?,?)",
            arrayOf<Any>(key, at, at, 0L, 0L, payload, lookup, lookup),
        )
        db.execSQL(
            "UPDATE facts SET first_at=MIN(first_at,?),last_at=MAX(last_at,?),bytes=bytes+?,packets=packets+?,lookup_first=MIN(lookup_first,?),lookup_last=MAX(lookup_last,?) WHERE key=?",
            arrayOf<Any>(at, at, bytes, packets, lookup, lookup, key),
        )
      }
      if (first == Long.MAX_VALUE) first = System.currentTimeMillis()
      db.execSQL(
          "INSERT OR IGNORE INTO sessions VALUES(?,0,?,?,0,0)",
          arrayOf<Any>(expectedSession, first, last),
      )
      db.execSQL(
          "UPDATE sessions SET sequence=?,first_at=MIN(first_at,?),last_at=MAX(last_at,?),dropped=MAX(dropped,?),unacknowledged=MAX(unacknowledged,?) WHERE id=?",
          arrayOf<Any>(
              sequence,
              first,
              last,
              batch.getLong("dropped"),
              batch.getLong("unacknowledged"),
              expectedSession,
          ),
      )
      prune(db)
      db.execSQL("UPDATE metadata SET value=value+1 WHERE key='revision'")
      db.setTransactionSuccessful()
      return true
    } finally {
      db.endTransaction()
    }
  }

  fun finish(status: String) {
    val data = JSONObject(status)
    val id = data.optString("session")
    if (id.isEmpty()) return
    val db = writableDatabase
    db.beginTransaction()
    try {
      db.execSQL(
          "UPDATE sessions SET dropped=MAX(dropped,?),unacknowledged=MAX(unacknowledged,?) WHERE id=?",
          arrayOf(data.optLong("dropped"), data.optLong("unacknowledged"), id),
      )
      db.execSQL("UPDATE metadata SET value=value+1 WHERE key='revision'")
      db.setTransactionSuccessful()
    } finally {
      db.endTransaction()
    }
  }

  fun clear() {
    queryIdentities.clear()
    val db = writableDatabase
    db.beginTransaction()
    try {
      db.execSQL("DELETE FROM facts")
      db.execSQL("DELETE FROM sessions")
      db.execSQL("UPDATE metadata SET value=CASE WHEN key='revision' THEN value+1 ELSE 0 END")
      db.setTransactionSuccessful()
    } finally {
      db.endTransaction()
    }
  }

  fun snapshot(from: Long, until: Long): TrafficSnapshot {
    val db = writableDatabase
    db.beginTransaction()
    try {
      prune(db)
      db.setTransactionSuccessful()
    } finally {
      db.endTransaction()
    }
    val rows = mutableListOf<TrafficRow>()
    var boundary = 0L
    db.rawQuery(
            "SELECT first_at,last_at,bytes,packets,payload,lookup_first,lookup_last FROM facts WHERE last_at>=? AND first_at<? ORDER BY first_at,key",
            arrayOf(from.toString(), until.toString()),
        )
        .use {
          while (it.moveToNext()) {
            if (it.getLong(0) >= from && it.getLong(1) < until)
                rows +=
                    TrafficRow(
                        it.getLong(0),
                        it.getLong(1),
                        it.getLong(2),
                        it.getLong(3),
                        it.getString(4),
                        it.getLong(5),
                        it.getLong(6),
                    )
            else boundary += it.getLong(2)
          }
        }
    val sessions = JSONArray()
    db.rawQuery(
            "SELECT id,sequence,first_at,last_at,dropped,unacknowledged FROM sessions WHERE last_at>=? AND first_at<? ORDER BY first_at,id",
            arrayOf(from.toString(), until.toString()),
        )
        .use {
          while (it.moveToNext()) sessions.put(
              JSONObject()
                  .put("id", it.getString(0))
                  .put("sequence", it.getLong(1))
                  .put("firstAt", it.getLong(2))
                  .put("lastAt", it.getLong(3))
                  .put("droppedMetadataRecords", it.getLong(4))
                  .put("unacknowledgedMetadataRecords", it.getLong(5))
          )
        }
    val revision =
        db.rawQuery("SELECT value FROM metadata WHERE key='revision'", null).use {
          it.moveToFirst()
          it.getLong(0)
        }
    val pruned =
        db.rawQuery("SELECT value FROM metadata WHERE key='prunedBytes'", null).use {
          it.moveToFirst()
          it.getLong(0)
        }
    return TrafficSnapshot(
        from,
        until,
        revision,
        rows.toList(),
        boundary,
        "This device's VPN IP packets only. Direct/excluded routes, encrypted DNS and pre-TUN firewall drops are unobserved. Tuple ownership is looked up after observation; missing/system owners remain separate. Recording/process gaps and in-flight commits at shutdown are unknown. Loss counters are last recorded metadata observations, not proof of complete packet coverage. $pruned bytes removed by retention/capacity. Partial boundary buckets are unallocated.",
        sessions.toString(),
    )
  }

  private fun prune(db: SQLiteDatabase) {
    val cutoff = System.currentTimeMillis() - TailDHistory.RETENTION_MILLIS
    val keys = mutableListOf<Pair<String, Long>>()
    var count = 0
    var size = 0L
    db.rawQuery(
            "SELECT key,bytes,last_at,length(CAST(payload AS BLOB)) FROM facts ORDER BY last_at DESC,key",
            null,
        )
        .use {
          while (it.moveToNext()) {
            count++
            size += it.getLong(3)
            if (it.getLong(2) < cutoff || count > 20000 || size > 24L * 1024 * 1024)
                keys += it.getString(0) to it.getLong(1)
          }
        }
    for ((key, bytes) in keys) {
      db.execSQL("DELETE FROM facts WHERE key=?", arrayOf(key))
      db.execSQL("UPDATE metadata SET value=value+? WHERE key='prunedBytes'", arrayOf(bytes))
    }
    val sessionsRemoved = db.delete("sessions", "last_at < ?", arrayOf(cutoff.toString()))
    if (keys.isNotEmpty() || sessionsRemoved > 0)
        db.execSQL("UPDATE metadata SET value=value+1 WHERE key='revision'")
  }

  private fun identityAtPacket(identity: JSONObject, at: Long): JSONObject {
    val packages = identity.getJSONArray("packages")
    for (i in 0 until packages.length()) {
      val app = packages.getJSONObject(i)
      if (app.getLong("firstInstallTime") > at || app.getLong("lastUpdateTime") > at)
          return JSONObject()
              .put("uid", identity.getInt("uid"))
              .put(
                  "label",
                  "UID ${identity.getInt("uid")} · installation changed after observation",
              )
              .put("packages", JSONArray())
    }
    return identity
  }

  @Suppress("DEPRECATION")
  private fun identity(uid: Int): JSONObject {
    val result = JSONObject().put("uid", uid)
    if (uid < 0) return result.put("label", "Unassigned app").put("packages", JSONArray())
    if (uid % 100000 < 10000)
        return result.put("label", "System UID $uid").put("packages", JSONArray())
    val pm = context.packageManager
    val packages = JSONArray()
    val labels = mutableListOf<String>()
    for (name in pm.getPackagesForUid(uid).orEmpty().sorted()) {
      try {
        val info =
            pm.getPackageInfo(
                name,
                if (Build.VERSION.SDK_INT >= 28) PackageManager.GET_SIGNING_CERTIFICATES
                else PackageManager.GET_SIGNATURES,
            )
        val signatures =
            if (Build.VERSION.SDK_INT >= 28) info.signingInfo?.apkContentsSigners.orEmpty()
            else info.signatures.orEmpty()
        val label = info.applicationInfo?.loadLabel(pm)?.toString() ?: name
        labels += label
        packages.put(
            JSONObject()
                .put("package", name)
                .put("label", label)
                .put("firstInstallTime", info.firstInstallTime)
                .put("lastUpdateTime", info.lastUpdateTime)
                .put(
                    "versionCode",
                    if (Build.VERSION.SDK_INT >= 28) info.longVersionCode
                    else info.versionCode.toLong(),
                )
                .put("signerSha256", JSONArray(signatures.map { hash(it.toByteArray()) }.sorted()))
        )
      } catch (_: PackageManager.NameNotFoundException) {
        /* Identity changed: do not invent a package. */
      }
    }
    return result
        .put("label", labels.joinToString(" / ").ifEmpty { "UID $uid · package unavailable" })
        .put("packages", packages)
  }

  private fun hash(value: String) = hash(value.toByteArray(Charsets.UTF_8))

  private fun hash(value: ByteArray) =
      MessageDigest.getInstance("SHA-256").digest(value).joinToString("") { "%02x".format(it) }
}
