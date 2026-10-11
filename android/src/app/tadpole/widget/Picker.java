package app.tadpole.widget;

import android.app.PendingIntent;
import android.app.job.JobInfo;
import android.app.job.JobScheduler;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.net.Uri;
import android.view.View;
import android.widget.RemoteViews;

/** The stool, neuroinflammation and meal pickers, drawn inside the widget's own frame in place of the pond. Taps arrive as broadcasts to PondWidget. */
final class Picker {
    private Picker() {}

    static final String ACTION = "app.tadpole.widget.PICK";
    // Bristol: 3 and 4 are the normal middle, both ends are the problem.
    private static final String[] STOOL_COLORS = {"#C2452D", "#E9953B", "#8FCB5A", "#4FB85A", "#E3C93F", "#E9953B", "#C2452D"};
    private static final String[] NEURO_COLORS = {"#4FB85A", "#8FCB5A", "#C9D24A", "#E3C93F", "#E9953B", "#D8663A", "#B33A28"};
    // neuroinflammation 1 to 7 on the diary's 0 to 10 symptom scale
    private static final int[] NEURO_SEVERITY = {1, 3, 4, 6, 7, 9, 10};
    private static final String[] SIZE_NOTE = {"500", "1000", "1500", "2000"};
    private static final int[] TILE_IDS = {R.id.t0, R.id.t1, R.id.t2, R.id.t3, R.id.t4, R.id.t5, R.id.t6, R.id.t7};

    static PendingIntent act(Context c, String cmd) {
        Intent i = new Intent(c, PondWidget.class).setAction(ACTION).setData(Uri.parse("tadpole://pick/" + cmd)).putExtra("cmd", cmd).putExtra("n", Store.nonce(c));
        return PendingIntent.getBroadcast(c, cmd.hashCode(), i, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    static String mealText(int size, int mask) {
        int n = Integer.bitCount(mask);
        StringBuilder sb = new StringBuilder("Meal size " + size + " (~" + SIZE_NOTE[size - 1] + " kcal) - FODMAP triggers: " + n);
        boolean first = true;
        for (int i = 0; i < Pixel.FOOD_NAMES.length; i++)
            if ((mask & (1 << i)) != 0) {
                sb.append(first ? " (" : ", ").append(Pixel.FOOD_NAMES[i]);
                first = false;
            }
        return first ? sb.toString() : sb.append(")").toString();
    }

    /** Handle one tap on a picker. Taps that do not fit what is on screen (a stale or double tap) are ignored. */
    static void handle(Context c, Intent in) {
        if (!Store.nonce(c).equals(in.getStringExtra("n"))) return;
        String cmd = in.getStringExtra("cmd");
        if (cmd == null || !Store.connected(c)) return;
        String mode = Store.pick(c);
        int size = Store.pickSize(c), mask = Store.pickMask(c);
        if (cmd.equals("stool") || cmd.equals("neuro")) { Store.setPick(c, cmd, 0, 0); expireLater(c); }
        else if (cmd.equals("meal")) { Store.setPick(c, "size", 0, 0); expireLater(c); }
        else if (cmd.equals("close")) Store.setPick(c, "", 0, 0);
        else if (cmd.startsWith("score:") && (mode.equals("stool") || mode.equals("neuro"))) {
            int n = Integer.parseInt(cmd.substring(6));
            if (n >= 1 && n <= 7) {
                if (mode.equals("stool")) Sync.addQueued(c, "Stool, Bristol " + n, null, "stool");
                else Sync.addQueued(c, "Neuroinflammation " + n + "/7", NEURO_SEVERITY[n - 1], "symptom");
                Store.setPick(c, "", 0, 0);
            }
        } else if (cmd.startsWith("size:") && mode.equals("size")) {
            int n = Integer.parseInt(cmd.substring(5));
            if (n >= 1 && n <= 4) Store.setPick(c, "trig", n, 0);
        } else if (cmd.startsWith("t:") && mode.equals("trig")) {
            Store.setPick(c, "trig", size, mask ^ (1 << Integer.parseInt(cmd.substring(2))));
        } else if (cmd.equals("save") && mode.equals("trig") && size >= 1) {
            Sync.addQueued(c, mealText(size, mask), null, "food");
            Store.setPick(c, "", 0, 0);
        } else return;
        PondWidget.refreshAll(c);
    }

    /** Put the pond back by itself if the picker is forgotten: a background job repaints the widget once the picker has expired. */
    private static void expireLater(Context c) {
        JobScheduler js = (JobScheduler) c.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if (js == null) return;
        js.schedule(new JobInfo.Builder(11, new ComponentName(c, SyncService.class)).setMinimumLatency(95000).setOverrideDeadline(180000).build());
    }

    static RemoteViews view(Context c, int W, int H, String mode, String color) {
        float d = c.getResources().getDisplayMetrics().density;
        int u = Math.max(2, Math.round(1.5f * d));
        int pad = Math.round(8 * d), gap = Math.round(4 * d), margin = Math.round(2 * d);
        int innerW = W - 2 * pad, innerH = H - 2 * pad;
        int tileH = Math.max(Math.round(40 * d), Math.min(Math.round(64 * d), Math.round(innerH * 0.6f)));
        int titleH = Math.max(Math.round(24 * d), innerH - tileH - gap);
        int closeW = Math.round(36 * d);
        int edge = Color.parseColor("#0A2228"), ink = Color.parseColor("#16351F");
        int cream = Color.parseColor("#FBFEF2"), amber = Color.parseColor("#F2B24A");

        RemoteViews rv = new RemoteViews(c.getPackageName(), R.layout.widget_pick);
        rv.setImageViewBitmap(R.id.bg, Pixel.pond(c, color, W, H));
        rv.setImageViewBitmap(R.id.p_x, Pixel.glyphButton(c, Pixel.G_X, Color.parseColor("#EAF5D6"), edge, ink, Math.min(titleH, closeW)));
        rv.setOnClickPendingIntent(R.id.p_x, act(c, "close"));

        String[] lines;
        int n;
        int size = Store.pickSize(c), mask = Store.pickMask(c);
        if (mode.equals("stool")) { lines = new String[]{"Stool quality", "1 lumps  3-4 normal  7 watery"}; n = 7; }
        else if (mode.equals("neuro")) { lines = new String[]{"Neuroinflammation", "1 barely there  7 can't work"}; n = 7; }
        else if (mode.equals("size")) { lines = new String[]{"How big was the meal?", "each step is about 500 kcal"}; n = 4; }
        else {
            StringBuilder names = new StringBuilder();
            for (int i = 0; i < Pixel.FOOD_NAMES.length; i++)
                if ((mask & (1 << i)) != 0) names.append(names.length() > 0 ? ", " : "").append(Pixel.FOOD_NAMES[i]);
            lines = new String[]{"FODMAP triggers in it?", names.length() == 0 ? "tap any that were in it" : names.toString()};
            n = 8;
        }
        rv.setImageViewBitmap(R.id.p_title, Pixel.text(c, color, lines, innerW - closeW, titleH));

        int w = innerW / n - 2 * margin;
        for (int i = 0; i < 8; i++) {
            if (i >= n) { rv.setViewVisibility(TILE_IDS[i], View.GONE); continue; }
            rv.setViewVisibility(TILE_IDS[i], View.VISIBLE);
            Bitmap bm;
            String cmd;
            if (mode.equals("stool") || mode.equals("neuro")) {
                int fill = Color.parseColor((mode.equals("stool") ? STOOL_COLORS : NEURO_COLORS)[i]);
                bm = Pixel.tile(c, w, tileH, fill, ink, String.valueOf(i + 1), null);
                cmd = "score:" + (i + 1);
            } else if (mode.equals("size")) {
                int cell = Math.max(1, Math.min((w - 6 * u) / 10, (tileH - 6 * u - Math.round(14 * d)) / 8));
                bm = Pixel.tile(c, w, tileH, cream, ink, (i + 1) + "  ~" + SIZE_NOTE[i], Pixel.bowl(i + 1, cell));
                cmd = "size:" + (i + 1);
            } else if (i < 7) {
                int cell = Math.max(1, Math.min((w - 6 * u) / 8, (tileH - 6 * u) / 8));
                bm = Pixel.tile(c, w, tileH, (mask & (1 << i)) != 0 ? amber : cream, ink, null, Pixel.food(i, cell));
                cmd = "t:" + i;
            } else {
                int k = Integer.bitCount(mask);
                bm = Pixel.tile(c, w, tileH, Color.parseColor("#2F8442"), Color.WHITE, k == 0 ? "Save" : "Save " + k, null);
                cmd = "save";
            }
            rv.setImageViewBitmap(TILE_IDS[i], bm);
            rv.setOnClickPendingIntent(TILE_IDS[i], act(c, cmd));
        }
        return rv;
    }
}
