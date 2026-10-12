package app.tadpole.widget;

import android.app.job.JobInfo;
import android.app.job.JobScheduler;
import android.content.ComponentName;
import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONException;
import org.json.JSONObject;

/** What the widget shows, worked out from the phone's own data, and the one way the widget adds an entry. */
final class Local {
    private Local() {}

    private static SharedPreferences prefs(Context c) { return c.getSharedPreferences("tadpole-local", Context.MODE_PRIVATE); }

    /** The app saves its latest pond summary here after every change; the widget fills in the parts that depend on the clock. */
    static void saveSnapshot(Context c, String json) { prefs(c).edit().putString("snapshot", json).commit(); }
    static void clearSnapshot(Context c) { prefs(c).edit().remove("snapshot").commit(); }

    static String agoText(double hours) {
        if (hours < 1) return Math.max(1, (int) (hours * 60)) + " min ago";
        if (hours < 48) return (int) hours + " h ago";
        return (int) (hours / 24) + " days ago";
    }

    /** {color, stage, stage_name, ago, control}. Colour and "ago" always follow the clock; the stage and the weekly label are as of the last time the app was open. */
    static JSONObject state(Context c) {
        JSONObject snap = new JSONObject();
        try { String s = prefs(c).getString("snapshot", ""); if (!s.isEmpty()) snap = new JSONObject(s); } catch (JSONException e) { snap = new JSONObject(); }
        long last = Db.get(c).lastEntryMillis();
        String color = "green", ago = "nothing written yet";
        if (last > 0) {
            double h = (System.currentTimeMillis() - last) / 3600000.0;
            color = h <= 18 ? "green" : h <= 42 ? "yellow" : "red";
            ago = agoText(Math.max(0, h));
        }
        JSONObject o = new JSONObject();
        try {
            o.put("color", color).put("ago", ago).put("stage", snap.optInt("stage", 0)).put("stage_name", snap.optString("stage_name", "Tadpole")).put("control", snap.optString("control", "not enough yet"));
        } catch (JSONException e) { /* cannot happen */ }
        return o;
    }

    /** Save an entry from the widget. kind may be null (free text: the app sorts it out when it opens, and so does the computer). Never touches the network. */
    static void add(Context c, String text, Integer severity, String kind) {
        try {
            String now = Db.nowIso();
            JSONObject e = new JSONObject().put("id", Db.uuid()).put("ts", now).put("kind", kind == null ? JSONObject.NULL : kind).put("text", text.trim())
                    .put("severity", severity == null ? JSONObject.NULL : severity).put("source", "widget").put("details", JSONObject.NULL).put("removedAt", JSONObject.NULL).put("updatedAt", now);
            Db.get(c).put(e);
        } catch (JSONException e) { return; }
        scheduleSync(c);
        PondWidget.refreshAll(c);
    }

    static final int JOB_SYNC = 10, JOB_PERIODIC = 9, JOB_EXPIRE = 11;

    /** Ask for a sync soon (only does anything when a computer is paired). */
    static void scheduleSync(Context c) {
        if (!Desk.paired(c)) return;
        JobScheduler js = (JobScheduler) c.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if (js == null) return;
        js.schedule(new JobInfo.Builder(JOB_SYNC, new ComponentName(c, SyncService.class)).setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).build());
    }

    /** Repaint about every 30 minutes (the colour changes with the clock), and sync if paired. Needs no network to run. */
    static void ensurePeriodic(Context c) {
        JobScheduler js = (JobScheduler) c.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if (js == null || js.getPendingJob(JOB_PERIODIC) != null) return;
        js.schedule(new JobInfo.Builder(JOB_PERIODIC, new ComponentName(c, SyncService.class)).setPeriodic(30 * 60 * 1000L).build());
    }
}
