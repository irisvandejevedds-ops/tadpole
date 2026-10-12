package app.tadpole.widget;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import android.os.Environment;
import android.provider.MediaStore;
import android.webkit.JavascriptInterface;
import java.io.OutputStream;
import org.json.JSONException;
import org.json.JSONObject;

/** What the app's web pages can ask the phone to do. Only pages served from the app's own files ever see this object. */
final class Bridge {
    private final Context c;

    Bridge(Context c) { this.c = c.getApplicationContext(); }

    @JavascriptInterface
    public String loadAll() {
        Db db = Db.get(c);
        try { return new JSONObject().put("entries", db.entries(false)).put("settings", db.settings()).put("docs", db.docs()).toString(); }
        catch (JSONException e) { return "{}"; }
    }

    @JavascriptInterface
    public void putEntry(String json) {
        try {
            JSONObject e = new JSONObject(json);
            if (e.optString("id").isEmpty() || e.optString("ts").isEmpty() || !e.has("text")) return;
            Db.get(c).put(e);
            Local.scheduleSync(c);
            PondWidget.refreshAll(c);
        } catch (JSONException e) { /* ignore a malformed entry */ }
    }

    @JavascriptInterface
    public void setSetting(String k, String v) { if (k != null && v != null && k.length() < 60 && v.length() < 200) Db.get(c).setSetting(k, v); }

    @JavascriptInterface
    public void saveSnapshot(String json) {
        if (json == null || json.length() > 4000) return;
        Local.saveSnapshot(c, json);
        PondWidget.refreshAll(c);
    }

    @JavascriptInterface
    public void deleteAll() {
        Db.get(c).deleteAll();
        Local.clearSnapshot(c);
        PondWidget.refreshAll(c);
    }

    /** Save a text file into the Downloads folder. */
    @JavascriptInterface
    public boolean saveFile(String name, String mime, String text) {
        if (name == null || !name.matches("[A-Za-z0-9._-]{1,60}") || text == null || text.length() > 20_000_000) return false;
        try {
            ContentResolver r = c.getContentResolver();
            ContentValues v = new ContentValues();
            v.put(MediaStore.Downloads.DISPLAY_NAME, name);
            v.put(MediaStore.Downloads.MIME_TYPE, mime == null ? "text/plain" : mime);
            v.put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);
            Uri u = r.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
            if (u == null) return false;
            try (OutputStream o = r.openOutputStream(u)) { o.write(text.getBytes("UTF-8")); }
            return true;
        } catch (Exception e) { return false; }
    }

    @JavascriptInterface
    public String syncStatus() { return Desk.status(c).toString(); }

    /** Start a sync in the background and return at once; the page watches syncStatus().running. */
    @JavascriptInterface
    public void syncNow() {
        if (Desk.running) return;
        new Thread(() -> Desk.sync(c)).start();
    }

    @JavascriptInterface
    public void unpair() { Desk.unpair(c); }

    /** Returns "" when paired, otherwise the reason it did not work. A first sync starts at once. */
    @JavascriptInterface
    public String pair(String link) {
        String why = Desk.pair(c, link);
        if (why.isEmpty()) new Thread(() -> Desk.sync(c)).start();
        return why;
    }
}
