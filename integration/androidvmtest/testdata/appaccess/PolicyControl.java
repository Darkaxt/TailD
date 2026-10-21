package io.github.darkaxt.taild.fixture;

import android.os.IBinder;

/** ADB-shell fixture policy seeding/readback, never included in the product APK. */
public final class PolicyControl {
    public static void main(String[] args) throws Exception {
        if (args.length < 1) throw new IllegalArgumentException("inspect, rule or chain required");
        IBinder binder = (IBinder) Class.forName("android.os.ServiceManager")
                .getMethod("getService", String.class).invoke(null, "connectivity");
        Object service = Class.forName("android.net.IConnectivityManager$Stub")
                .getMethod("asInterface", IBinder.class).invoke(null, binder);
        int chain = Integer.parseInt(args[1]);
        if (chain != 8 && chain != 9) throw new IllegalArgumentException("Only owned test chains 8/9");
        if (args[0].equals("chain") && args.length == 3) {
            service.getClass().getMethod("setFirewallChainEnabled", int.class, boolean.class)
                    .invoke(service, chain, Boolean.parseBoolean(args[2]));
        } else if (args[0].equals("rule") && args.length == 4) {
            int uid = Integer.parseInt(args[2]), rule = Integer.parseInt(args[3]);
            if (uid % 100000 < 10000 || (rule != 1 && rule != 2)) throw new IllegalArgumentException("Invalid fixture UID/rule");
            service.getClass().getMethod("setUidFirewallRule", int.class, int.class, int.class)
                    .invoke(service, chain, uid, rule);
        } else if (args[0].equals("inspect") && args.length == 3) {
            int uid = Integer.parseInt(args[2]);
            Object enabled = service.getClass().getMethod("getFirewallChainEnabled", int.class).invoke(service, chain);
            Object rule = service.getClass().getMethod("getUidFirewallRule", int.class, int.class).invoke(service, chain, uid);
            System.out.println("CHAIN=" + chain + " ENABLED=" + enabled + " UID=" + uid + " RULE=" + rule);
        } else throw new IllegalArgumentException("Unsupported fixture command");
    }
}
