package app.tadpole.widget;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;
import java.util.UUID;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/** The phone's own copy of the diary. The app, the widget and the sync all read and write here. */
final class Db extends SQLiteOpenHelper {
    private static Db inst;

    static synchronized Db get(Context c) {
        if (inst == null) inst = new Db(c.getApplicationContext());
        return inst;
    }

    private Db(Context c) { super(c, "tadpole.db", null, 1); }

    @Override
    public void onCreate(SQLiteDatabase d) {
        d.execSQL("CREATE TABLE entries(id TEXT PRIMARY KEY, ts TEXT NOT NULL, kind TEXT, text TEXT NOT NULL, severity INTEGER, source TEXT NOT NULL DEFAULT 'app', "
                + "details TEXT, removed_at TEXT, updated_at TEXT NOT NULL, dirty INTEGER NOT NULL DEFAULT 1)");
        d.execSQL("CREATE INDEX ix_entries_ts ON entries(ts)");
        d.execSQL("CREATE INDEX ix_entries_dirty ON entries(dirty)");
        d.execSQL("CREATE TABLE settings(k TEXT PRIMARY KEY, v TEXT NOT NULL)");
        d.execSQL("CREATE TABLE docs(slug TEXT PRIMARY KEY, title TEXT NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL, sort INTEGER NOT NULL DEFAULT 0)");
    }

    @Override
    public void onUpgrade(SQLiteDatabase d, int a, int b) {}

    static String nowIso() { return iso(new Date()); }

    static String iso(Date d) {
        SimpleDateFormat f = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US);
        f.setTimeZone(TimeZone.getTimeZone("UTC"));
        return f.format(d);
    }

    static long parseIso(String s) {
        try {
            SimpleDateFormat f = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US);
            f.setTimeZone(TimeZone.getTimeZone("UTC"));
            return f.parse(s).getTime();
        } catch (Exception e) { return 0; }
    }

    static String uuid() { return UUID.randomUUID().toString(); }

    // ---------- entries ----------
    private static JSONObject row(Cursor c) throws JSONException {
        JSONObject o = new JSONObject();
        o.put("id", c.getString(0)).put("ts", c.getString(1));
        o.put("kind", c.isNull(2) ? JSONObject.NULL : c.getString(2));
        o.put("text", c.getString(3));
        o.put("severity", c.isNull(4) ? JSONObject.NULL : c.getInt(4));
        o.put("source", c.getString(5));
        Object det = JSONObject.NULL;
        if (!c.isNull(6)) { try { det = new JSONObject(c.getString(6)); } catch (JSONException e) { det = JSONObject.NULL; } }
        o.put("details", det);
        o.put("removedAt", c.isNull(7) ? JSONObject.NULL : c.getString(7));
        o.put("updatedAt", c.getString(8));
        return o;
    }

    private static final String COLS = "id, ts, kind, text, severity, source, details, removed_at, updated_at";

    synchronized JSONArray entries(boolean dirtyOnly) {
        JSONArray out = new JSONArray();
        try (Cursor c = getReadableDatabase().rawQuery("SELECT " + COLS + " FROM entries" + (dirtyOnly ? " WHERE dirty=1" : "") + " ORDER BY ts, id", null)) {
            while (c.moveToNext()) out.put(row(c));
        } catch (JSONException e) { /* skip */ }
        return out;
    }

    /** Insert or replace an entry as the phone's own change (it will be sent on the next sync). */
    synchronized void put(JSONObject e) throws JSONException {
        write(e, 1);
    }

    private void write(JSONObject e, int dirty) throws JSONException {
        ContentValues v = new ContentValues();
        v.put("id", e.getString("id"));
        v.put("ts", e.getString("ts"));
        if (e.isNull("kind") || e.optString("kind").isEmpty()) v.putNull("kind"); else v.put("kind", e.getString("kind"));
        v.put("text", e.getString("text"));
        if (e.isNull("severity")) v.putNull("severity"); else v.put("severity", e.getInt("severity"));
        v.put("source", e.optString("source", "app").isEmpty() ? "app" : e.optString("source", "app"));
        Object det = e.opt("details");
        if (det == null || det == JSONObject.NULL) v.putNull("details"); else v.put("details", det.toString());
        if (e.isNull("removedAt") || e.optString("removedAt").isEmpty()) v.putNull("removed_at"); else v.put("removed_at", e.getString("removedAt"));
        v.put("updated_at", e.optString("updatedAt", nowIso()));
        v.put("dirty", dirty);
        getWritableDatabase().insertWithOnConflict("entries", null, v, SQLiteDatabase.CONFLICT_REPLACE);
    }

    /** An entry that came from the computer: kept unless the phone has a later edit of the same one. */
    synchronized boolean putFromDesk(JSONObject e) throws JSONException {
        try (Cursor c = getReadableDatabase().rawQuery("SELECT updated_at FROM entries WHERE id=?", new String[]{e.getString("id")})) {
            if (c.moveToFirst() && c.getString(0).compareTo(e.optString("updatedAt", "")) >= 0) return false;
        }
        write(e, 0);
        return true;
    }

    /** After a successful push: the entries that were sent no longer need sending, unless they changed again meanwhile. */
    synchronized void markSent(JSONArray sent) {
        SQLiteDatabase d = getWritableDatabase();
        for (int i = 0; i < sent.length(); i++) {
            JSONObject e = sent.optJSONObject(i);
            if (e != null) d.execSQL("UPDATE entries SET dirty=0 WHERE id=? AND updated_at=?", new Object[]{e.optString("id"), e.optString("updatedAt")});
        }
    }

    /** Epoch millis of the newest entry that has not been removed, or 0. */
    synchronized long lastEntryMillis() {
        try (Cursor c = getReadableDatabase().rawQuery("SELECT MAX(ts) FROM entries WHERE removed_at IS NULL", null)) {
            return c.moveToFirst() && !c.isNull(0) ? parseIso(c.getString(0)) : 0;
        }
    }

    // ---------- settings and documents ----------
    synchronized String setting(String k) {
        try (Cursor c = getReadableDatabase().rawQuery("SELECT v FROM settings WHERE k=?", new String[]{k})) { return c.moveToFirst() ? c.getString(0) : null; }
    }

    synchronized void setSetting(String k, String v) {
        ContentValues cv = new ContentValues();
        cv.put("k", k); cv.put("v", v);
        getWritableDatabase().insertWithOnConflict("settings", null, cv, SQLiteDatabase.CONFLICT_REPLACE);
    }

    synchronized JSONObject settings() {
        JSONObject o = new JSONObject();
        try (Cursor c = getReadableDatabase().rawQuery("SELECT k, v FROM settings", null)) { while (c.moveToNext()) o.put(c.getString(0), c.getString(1)); } catch (JSONException e) { /* skip */ }
        return o;
    }

    synchronized JSONArray docs() {
        JSONArray out = new JSONArray();
        try (Cursor c = getReadableDatabase().rawQuery("SELECT slug, title, kind, body FROM docs ORDER BY sort, slug", null)) {
            while (c.moveToNext()) out.put(new JSONObject().put("slug", c.getString(0)).put("title", c.getString(1)).put("kind", c.getString(2)).put("body", c.getString(3)));
        } catch (JSONException e) { /* skip */ }
        return out;
    }

    synchronized void replaceDocs(JSONArray docs) throws JSONException {
        SQLiteDatabase d = getWritableDatabase();
        d.beginTransaction();
        try {
            d.delete("docs", null, null);
            for (int i = 0; i < docs.length(); i++) {
                JSONObject o = docs.getJSONObject(i);
                ContentValues cv = new ContentValues();
                cv.put("slug", o.getString("slug")); cv.put("title", o.getString("title")); cv.put("kind", o.getString("kind")); cv.put("body", o.optString("body", "")); cv.put("sort", o.optInt("sort", i));
                d.insert("docs", null, cv);
            }
            d.setTransactionSuccessful();
        } finally { d.endTransaction(); }
    }

    synchronized void deleteAll() {
        SQLiteDatabase d = getWritableDatabase();
        d.delete("entries", null, null); d.delete("docs", null, null); d.delete("settings", null, null);
    }
}
