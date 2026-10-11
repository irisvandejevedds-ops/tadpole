package app.tadpole.widget;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

final class Store {
    private Store() {}

    private static SharedPreferences p(Context c) { return c.getSharedPreferences("tadpole", Context.MODE_PRIVATE); }

    static boolean connected(Context c) { return !url(c).isEmpty() && !token(c).isEmpty(); }
    static String url(Context c) { return p(c).getString("url", ""); }
    static String token(Context c) { return p(c).getString("token", ""); }

    static void saveConn(Context c, String url, String token) {
        url = url.trim();
        while (url.endsWith("/")) url = url.substring(0, url.length() - 1);
        p(c).edit().putString("url", url).putString("token", token.trim()).apply();
    }

    static String cache(Context c) { return p(c).getString("cache", ""); }
    static void saveCache(Context c, String json) { p(c).edit().putString("cache", json).putLong("cache_ts", System.currentTimeMillis()).apply(); }
    /** For a change made while offline that only adjusts the saved copy: it is still as old as it was. */
    static void saveCacheKeepAge(Context c, String json) { p(c).edit().putString("cache", json).apply(); }
    static long cacheAgeMs(Context c) { long t = p(c).getLong("cache_ts", 0); return t == 0 ? Long.MAX_VALUE : System.currentTimeMillis() - t; }

    static synchronized JSONArray queue(Context c) {
        try { return new JSONArray(p(c).getString("queue", "[]")); } catch (JSONException e) { return new JSONArray(); }
    }
    static synchronized void saveQueue(Context c, JSONArray q) { p(c).edit().putString("queue", q.toString()).apply(); }
    static synchronized void enqueue(Context c, JSONObject item) { JSONArray q = queue(c); q.put(item); saveQueue(c, q); }
    static synchronized int pending(Context c) { return queue(c).length(); }

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
