package app.tadpole.widget;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.os.Bundle;
import android.view.View;
import android.widget.RemoteViews;
import org.json.JSONException;
import org.json.JSONObject;

public class PondWidget extends AppWidgetProvider {
    @Override
    public void onUpdate(Context c, AppWidgetManager m, int[] ids) {
        paint(c, m, ids);
        Local.ensurePeriodic(c);
    }

    @Override
    public void onReceive(Context c, Intent i) {
        if (Picker.ACTION.equals(i.getAction())) { Picker.handle(c, i); return; }
        super.onReceive(c, i);
    }

    @Override
    public void onEnabled(Context c) { Local.ensurePeriodic(c); }

    @Override
    public void onAppWidgetOptionsChanged(Context c, AppWidgetManager m, int id, Bundle options) {
        paint(c, m, new int[]{id});
    }

    static void refreshAll(Context c) {
        AppWidgetManager m = AppWidgetManager.getInstance(c);
        int[] ids = m.getAppWidgetIds(new ComponentName(c, PondWidget.class));
        if (ids.length > 0) paint(c, m, ids);
    }

    private static void paint(Context c, AppWidgetManager m, int[] ids) {
        for (int id : ids) m.updateAppWidget(id, build(c, m, id));
    }

    /** Swap the refresh arrow for the spinner (or back) without redrawing anything else. */
    static void setLoading(Context c, boolean on) {
        AppWidgetManager m = AppWidgetManager.getInstance(c);
        int[] ids = m.getAppWidgetIds(new ComponentName(c, PondWidget.class));
        if (ids.length == 0) return;
        RemoteViews rv = new RemoteViews(c.getPackageName(), R.layout.widget);
        rv.setViewVisibility(R.id.spin, on ? View.VISIBLE : View.GONE);
        rv.setViewVisibility(R.id.refresh, on ? View.GONE : View.VISIBLE);
        m.partiallyUpdateAppWidget(ids, rv);
    }

    /** Keep the spinner visible long enough to be noticed. */
    static void holdSpinner(long startedAt) {
        long left = 900 - (System.currentTimeMillis() - startedAt);
        if (left > 0) { try { Thread.sleep(left); } catch (InterruptedException e) { Thread.currentThread().interrupt(); } }
    }

    private static PendingIntent open(Context c, int code, Intent i) {
        return PendingIntent.getActivity(c, code, i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_NO_ANIMATION),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    static RemoteViews build(Context c, AppWidgetManager m, int id) {
        Pixel.load(c);
        float d = c.getResources().getDisplayMetrics().density;
        Bundle o = m.getAppWidgetOptions(id);
        boolean land = c.getResources().getConfiguration().orientation == android.content.res.Configuration.ORIENTATION_LANDSCAPE;
        int wDp = o.getInt(land ? AppWidgetManager.OPTION_APPWIDGET_MAX_WIDTH : AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 320);
        int hDp = o.getInt(land ? AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT : AppWidgetManager.OPTION_APPWIDGET_MAX_HEIGHT, 110);
        int W = Math.round(wDp * d), H = Math.round(hDp * d);
        int pad = Math.round(8 * d), gap = Math.round(4 * d), barH = Math.round(38 * d), sq = Math.round(38 * d), refreshW = Math.round(36 * d);

        JSONObject st = null;
        st = Local.state(c);
        String color = st.optString("color", "green");
        int stage = st.optInt("stage", 0);
        boolean stale = Desk.stale(c);

        String mode = Store.pick(c);
        if (!mode.isEmpty()) return Picker.view(c, W, H, mode, color);

        RemoteViews rv = new RemoteViews(c.getPackageName(), R.layout.widget);
        rv.setImageViewBitmap(R.id.bg, Pixel.pond(c, color, W, H));

        int innerW = W - 2 * pad, innerH = H - 2 * pad;
        int topH = Math.max(Math.round(40 * d), innerH - barH - gap);
        int frogW = Math.round((innerW - refreshW) * 0.3f), textW = innerW - refreshW - frogW;
        int cell = Math.max(2, Math.min(frogW / 32, (topH - 2) / 25));
        rv.setImageViewBitmap(R.id.f0, Pixel.frog(c, stage, color, cell, 0));
        rv.setImageViewBitmap(R.id.f1, Pixel.frog(c, stage, color, cell, 1));

        String line1 = st.optString("stage_name", "Tadpole");
        String line2 = "Last entry " + st.optString("ago", "");
        String line3 = "Symptoms: " + st.optString("control", "not enough yet");
        String[] lines = topH < Math.round(60 * d) ? new String[]{line1, line2} : new String[]{line1, line2, line3};
        rv.setImageViewBitmap(R.id.info, Pixel.text(c, color, lines, textW, topH));
        rv.setImageViewBitmap(R.id.refresh, Pixel.refresh(c, stale));
        rv.setViewVisibility(R.id.refresh, View.VISIBLE);
        rv.setViewVisibility(R.id.spin, View.GONE);
        rv.setOnClickPendingIntent(R.id.refresh, open(c, 2, new Intent(c, RefreshActivity.class)));
        rv.setOnClickPendingIntent(R.id.flip, open(c, 5, new Intent(c, MainActivity.class).putExtra("open_web", true)));
        rv.setOnClickPendingIntent(R.id.info, open(c, 5, new Intent(c, MainActivity.class).putExtra("open_web", true)));

        int inputW = innerW - 4 * (sq + gap);
        String hint = inputW < Math.round(120 * d) ? "Type..." : "Type an entry...";
        int edge = Color.parseColor("#0A2228");
        rv.setImageViewBitmap(R.id.input, Pixel.bar(c, hint, Color.parseColor("#FBFEF2"), edge, Color.parseColor("#44704F"), inputW, barH, true));
        rv.setImageViewBitmap(R.id.b_stool, Pixel.glyphButton(c, Pixel.G_STOOL, Color.parseColor("#E9D5B4"), edge, Color.parseColor("#4A2E14"), sq));
        rv.setImageViewBitmap(R.id.b_neuro, Pixel.glyphButton(c, Pixel.G_BRAIN, Color.parseColor("#F8C7B0"), edge, Color.parseColor("#3A1410"), sq));
        rv.setImageViewBitmap(R.id.b_meal, Pixel.glyphButton(c, Pixel.G_MEAL, Color.parseColor("#F3EFB8"), edge, Color.parseColor("#3D3510"), sq));
        rv.setImageViewBitmap(R.id.b_clear, Pixel.glyphButton(c, Pixel.G_CHECK, Color.parseColor("#CDEFA2"), edge, Color.parseColor("#16351F"), sq));
        rv.setOnClickPendingIntent(R.id.input, open(c, 3, new Intent(c, EntryActivity.class)));
        rv.setOnClickPendingIntent(R.id.b_stool, Picker.act(c, "stool"));
        rv.setOnClickPendingIntent(R.id.b_neuro, Picker.act(c, "neuro"));
        rv.setOnClickPendingIntent(R.id.b_meal, Picker.act(c, "meal"));
        rv.setOnClickPendingIntent(R.id.b_clear, open(c, 4, new Intent(c, QuickActivity.class)));
        return rv;
    }
}
