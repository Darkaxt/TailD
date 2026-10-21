package io.github.darkaxt.taild.fixture;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.HttpURLConnection;
import java.net.InetAddress;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;

/** Real fixture UID traffic, confined to the isolated test tailnet. No production component. */
public final class TrafficReceiver extends BroadcastReceiver {
    private static final List<DatagramSocket> sockets = new ArrayList<>();
    @Override public void onReceive(Context context, Intent intent) {
        if ("close".equals(intent.getStringExtra("operation"))) {
            synchronized(sockets) {for(DatagramSocket socket:sockets) socket.close();sockets.clear();}
            setResultData("CLOSED");return;
        }
        String target=intent.getStringExtra("url");
        if(target==null || !target.matches("http://100\\.64\\.[0-9]+\\.[0-9]+:[0-9]+/traffic/[a-z0-9-]+")) {
            setResultData("INVALID_TEST_TARGET");return;
        }
        new Thread(() -> {
            try {
                for(String name:new String[]{"alpha.taild.test","beta.taild.test","blocked.taild.test"}) {
                    // The initial stable path tests the explicit UDP block reply. The
                    // transition path tests TCP recovery; raw UDP has no delivery promise.
                    if(name.startsWith("blocked") && !intent.getBooleanExtra("resolver_block",true)) continue;
                    DatagramSocket socket=new DatagramSocket();
                    synchronized(sockets) {sockets.add(socket);}
                    // Socket stays open until an explicit close broadcast, allowing real owner lookup.
                    ByteArrayOutputStream buffer=new ByteArrayOutputStream();
                    DataOutputStream dns=new DataOutputStream(buffer);
                    dns.writeShort(name.startsWith("alpha")?101:name.startsWith("beta")?102:103);dns.writeShort(0x0100);
                    dns.writeShort(1);dns.writeShort(0);dns.writeShort(0);dns.writeShort(0);
                    for(String label:name.split("\\.")){dns.writeByte(label.length());dns.writeBytes(label);}
                    dns.writeByte(0);dns.writeShort(1);dns.writeShort(1);
                    byte[] query=buffer.toByteArray();
                    InetAddress resolver=InetAddress.getByName(name.startsWith("blocked")?new URL(target).getHost():"100.100.100.100");
                    socket.connect(resolver,53);
                    socket.send(new DatagramPacket(query,query.length,resolver,53));
                    byte[] reply=new byte[4096];socket.receive(new DatagramPacket(reply,reply.length));
                }
                HttpURLConnection connection=(HttpURLConnection)new URL(target).openConnection();
                connection.setRequestMethod("POST");connection.setDoOutput(true);
                byte[] payload=new byte[8192];for(int i=0;i<payload.length;i++)payload[i]=(byte)(i%251);
                connection.setFixedLengthStreamingMode(payload.length);
                connection.getOutputStream().write(payload);
                try(java.io.InputStream input=connection.getInputStream()) {byte[] block=new byte[4096];while(input.read(block)!=-1){}}
                connection.disconnect();
            } catch(Exception error) {android.util.Log.e("TailDTrafficFixture",error.getClass().getSimpleName());}
        },"taild-real-traffic-fixture").start();
        setResultData("STARTED");
    }
}
