package app.tadpole.widget;

import android.app.job.JobInfo;
import android.app.job.JobScheduler;
import android.content.ComponentName;
import android.content.Context;
import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;
import java.util.UUID;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

final class Sync {
    private Sync() {}

    /** The answer to adding an entry: stored (data), kept for later (queued), or refused (error). */
    static final class Result {
        JSONObject data;
        boolean queued;
        String error;
    }

    /** Why the last fetch fell back to the saved copy, or null when it reached the server. */
    static volatile String lastError = null;

    static String nowIso() {
        SimpleDateFormat f = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US);
        f.setTimeZone(TimeZone.getTimeZone("UTC"));
        return f.format(new Date());
    }

    static JSONObject state(Context c) { return state(c, false); }

    /** Fetch fresh state (one retry); falls back to the saved copy. quick = the owner is waiting, so give up sooner. */
    static JSONObject state(Context c, boolean quick) {
        lastError = null;
        if (Store.connected(c)) {
            for (int attempt = 0; attempt < 2; attempt++) {
                try {
                    JSONObject s = quick ? Api.call(c, "GET", "/api/state", null, 8000, 10000) : Api.call(c, "GET", "/api/state", null);
                    Store.saveCache(c, s.toString());
                    lastError = null;
                    return s;
                } catch (Api.HttpError e) {
                    lastError = e.code == 401 ? "the key was refused (make a new one in the app)" : "the server answered " + e.code;
                    break;
                } catch (IOException | JSONException e) {
                    lastError = e instanceof java.net.SocketTimeoutException ? "it took too long to answer" : "it could not be reached";
                }
            }
        } else lastError = "this widget is not connected yet";
        try { String s = Store.cache(c); return s.isEmpty() ? null : new JSONObject(s); } catch (JSONException e) { return null; }
    }

    /** Add one entry. kind and severity may be null (the server works them out from the words). */
    static Result add(Context c, String text, Integer severity, String kind) {
        Result r = new Result();
        String key = UUID.randomUUID().toString();
        JSONObject body = new JSONObject();
        try {
            body.put("text", text).put("key", key).put("ts", nowIso());
            if (severity != null) body.put("severity", severity);
            if (kind != null) body.put("kind", kind);
        } catch (JSONException e) { r.error = "could not make that entry"; return r; }
        if (!Store.connected(c)) { r.error = "open the Tadpole app once to connect this widget"; return r; }
        try {
            r.data = Api.call(c, "POST", "/api/entry", body, 8000, 8000);
            JSONObject st = r.data.optJSONObject("state");
            if (st != null) Store.saveCache(c, st.toString());
            return r;
        } catch (Api.HttpError e) {
            if (e.code >= 400 && e.code < 500 && e.code != 429) { r.error = e.code == 401 ? "the key was refused" : "that entry was not accepted"; return r; }
        } catch (IOException | JSONException e) { /* offline */ }
        Store.enqueue(c, body);
        applyLocal(c, text);
        scheduleRetry(c);
        r.queued = true;
        return r;
    }

    /** Save an entry without waiting for the network: keep it in the queue and let a background job send it. Used by the widget's own pickers. */
    static void addQueued(Context c, String text, Integer severity, String kind) {
        JSONObject body = new JSONObject();
        try {
            body.put("text", text).put("key", UUID.randomUUID().toString()).put("ts", nowIso());
            if (severity != null) body.put("severity", severity);
            if (kind != null) body.put("kind", kind);
        } catch (JSONException e) { return; }
        Store.enqueue(c, body);
        applyLocal(c, text);
        scheduleSync(c);
    }

    /** Make the saved copy show the entry straight away while offline. */
    static void applyLocal(Context c, String text) {
        try {
            String raw = Store.cache(c);
            JSONObject s = raw.isEmpty() ? new JSONObject() : new JSONObject(raw);
            s.put("color", "green").put("ago", "just now").put("today_count", s.optInt("today_count") + 1);
            s.put("line", "Content. Keep the entries coming.");
            s.put("last", new JSONObject().put("text", text));
            Store.saveCacheKeepAge(c, s.toString());
        } catch (JSONException e) { /* ignore */ }
    }

    /** Send everything kept offline, oldest first. Returns how many are still waiting. */
    static synchronized int flush(Context c) {
        JSONArray q = Store.queue(c);
        JSONArray left = new JSONArray();
        boolean stop = false;
        for (int i = 0; i < q.length(); i++) {
            JSONObject it = q.optJSONObject(i);
            if (it == null) continue;
            if (stop) { left.put(it); continue; }
            try {
                Api.call(c, "POST", "/api/entry", it, 8000, 8000);
            } catch (Api.HttpError e) {
                if (!(e.code >= 400 && e.code < 500 && e.code != 429)) { left.put(it); stop = true; }
            } catch (IOException | JSONException e) { left.put(it); stop = true; }
        }
        Store.saveQueue(c, left);
        return left.length();
    }

    /** Ask for a refresh as a background job. */
    static void scheduleSync(Context c) {
        JobScheduler js = (JobScheduler) c.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if (js == null) return;
        js.schedule(new JobInfo.Builder(10, new ComponentName(c, SyncService.class)).setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).build());
    }

    /** Keep refreshing about every 30 minutes, whether or not Android calls the widget's own update. */
    static void ensurePeriodic(Context c) {
        JobScheduler js = (JobScheduler) c.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if (js == null || js.getPendingJob(9) != null) return;
        js.schedule(new JobInfo.Builder(9, new ComponentName(c, SyncService.class)).setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setPeriodic(30 * 60 * 1000L).build());
    }

    static void scheduleRetry(Context c) {
        JobScheduler js = (JobScheduler) c.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if (js == null) return;
        js.schedule(new JobInfo.Builder(7, new ComponentName(c, RetryService.class)).setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setBackoffCriteria(60000, JobInfo.BACKOFF_POLICY_EXPONENTIAL).setPersisted(false).build());
    }
}
