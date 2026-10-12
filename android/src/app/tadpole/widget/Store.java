package app.tadpole.widget;

import android.content.Context;
import android.content.SharedPreferences;

/** Small widget-only state: which picker the widget is showing, and a secret that the widget's own taps carry. */
final class Store {
    private Store() {}

    private static SharedPreferences p(Context c) { return c.getSharedPreferences("tadpole", Context.MODE_PRIVATE); }

    // The picker the widget is showing in place of the pond (stool, neuro, size, trig), kept for a short while so a forgotten one clears itself.
    private static final long PICK_MS = 90000;
    static String pick(Context c) {
        SharedPreferences s = p(c);
        return System.currentTimeMillis() - s.getLong("pick_ts", 0) > PICK_MS ? "" : s.getString("pick", "");
    }
    static int pickSize(Context c) { return p(c).getInt("pick_size", 0); }
    static int pickMask(Context c) { return p(c).getInt("pick_mask", 0); }
    static void setPick(Context c, String mode, int size, int mask) {
        p(c).edit().putString("pick", mode).putInt("pick_size", size).putInt("pick_mask", mask).putLong("pick_ts", System.currentTimeMillis()).commit();
    }

    /** A random string made on first use and carried in the widget's own taps, so other apps cannot press its buttons. */
    static synchronized String nonce(Context c) {
        String n = p(c).getString("nonce", "");
        if (n.isEmpty()) {
            n = java.util.UUID.randomUUID().toString();
            p(c).edit().putString("nonce", n).commit();
        }
        return n;
    }
}
