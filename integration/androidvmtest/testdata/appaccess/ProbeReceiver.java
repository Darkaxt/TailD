package io.github.darkaxt.taild.fixture;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import java.net.HttpURLConnection;
import java.net.URL;

/** Installed only on the owned VM, under real fixture package/UID identities. */
public final class ProbeReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        String target = intent.getStringExtra("url");
        if (target == null || !target.matches("http://10\\.0\\.2\\.2:[0-9]+/app-access/[a-z0-9-]+")) {
            setResultData("INVALID_TEST_TARGET");
            return;
        }
        PendingResult result = goAsync();
        new Thread(() -> {
            HttpURLConnection connection = null;
            try {
                connection = (HttpURLConnection) new URL(target).openConnection();
                // This external HTTP observation boundary bounds a deliberately denied probe.
                // It never controls the app's firewall mutation or recovery lifecycle.
                connection.setConnectTimeout(5000);
                connection.setReadTimeout(5000);
                result.setResultData("HTTP_" + connection.getResponseCode());
            } catch (Exception error) {
                result.setResultData("FAILED_" + error.getClass().getSimpleName());
            } finally {
                if (connection != null) connection.disconnect();
                result.finish();
            }
        }, "taild-owned-network-probe").start();
    }
}
