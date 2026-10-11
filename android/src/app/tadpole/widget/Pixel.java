package app.tadpole.widget;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.Typeface;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.Random;
import org.json.JSONArray;
import org.json.JSONObject;

/** Draws the widget's pixel-art pieces: the pond, the tadpole or frog, text, buttons. Everything is drawn at its final pixel size. */
final class Pixel {
    private Pixel() {}

    private static Typeface pixelFace;
    private static JSONObject sprite;

    static synchronized void load(Context c) {
        if (sprite != null) return;
        try {
            pixelFace = Typeface.createFromAsset(c.getAssets(), "pixel.ttf");
            InputStream in = c.getAssets().open("tadpole.json");
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] b = new byte[4096];
            int n;
            while ((n = in.read(b)) > 0) out.write(b, 0, n);
            in.close();
            sprite = new JSONObject(out.toString("UTF-8"));
        } catch (Exception e) {
            sprite = new JSONObject();
        }
    }

    static Typeface face(Context c) { load(c); return pixelFace; }

    private static Paint flat() {
        Paint p = new Paint();
        p.setAntiAlias(false);
        p.setFilterBitmap(false);
        return p;
    }

    static int accent(String color) {
        return Color.parseColor("yellow".equals(color) ? "#A8921C" : "red".equals(color) ? "#B33A28" : "#2F8442");
    }

    static int accentDark(String color) {
        return Color.parseColor("yellow".equals(color) ? "#6F600E" : "red".equals(color) ? "#78221A" : "#1F5E2E");
    }

    static int accentLight(String color) {
        return Color.parseColor("yellow".equals(color) ? "#F3E56F" : "red".equals(color) ? "#F28C70" : "#8EE27B");
    }

    // ---- the frame: cells with quarter-circle corners that follow the launcher's own rounding

    static float systemRadius(Context c) {
        float d = c.getResources().getDisplayMetrics().density;
        try {
            int id = android.content.res.Resources.getSystem().getIdentifier("system_app_widget_background_radius", "dimen", "android");
            if (id != 0) {
                float r = android.content.res.Resources.getSystem().getDimension(id);
                if (r > 0) return r;
            }
        } catch (RuntimeException e) { /* fall through */ }
        return 28 * d;
    }

    static boolean[][] shape(int cols, int rows, double radCells) {
        boolean[][] g = new boolean[rows][cols];
        for (int y = 0; y < rows; y++) {
            for (int x = 0; x < cols; x++) {
                double cx = Math.min(x + 0.5, cols - x - 0.5), cy = Math.min(y + 0.5, rows - y - 0.5);
                boolean in = true;
                if (cx < radCells && cy < radCells) in = Math.hypot(radCells - cx, radCells - cy) <= radCells;
                g[y][x] = in;
            }
        }
        return g;
    }

    static boolean[][] erode(boolean[][] g) {
        int rows = g.length, cols = g[0].length;
        boolean[][] n = new boolean[rows][cols];
        for (int y = 0; y < rows; y++)
            for (int x = 0; x < cols; x++) {
                boolean ok = g[y][x] && y > 0 && y < rows - 1 && x > 0 && x < cols - 1;
                for (int dy = -1; ok && dy <= 1; dy++) for (int dx = -1; ok && dx <= 1; dx++) ok = g[y + dy][x + dx];
                n[y][x] = ok;
            }
        return n;
    }

    static Path cells(boolean[][] g, int u, int w, int h) {
        Path p = new Path();
        for (int y = 0; y < g.length; y++) {
            int x = 0;
            while (x < g[y].length) {
                if (!g[y][x]) { x++; continue; }
                int x0 = x;
                while (x < g[y].length && g[y][x]) x++;
                p.addRect(x0 * u, y * u, Math.min(w, x * u), Math.min(h, (y + 1) * u), Path.Direction.CW);
            }
        }
        return p;
    }

    /** The pond: dark water with ripples inside a frame in the tadpole's colour. */
    static Bitmap pond(Context c, String color, int w, int h) {
        float d = c.getResources().getDisplayMetrics().density;
        int u = Math.max(2, Math.round(1.5f * d));
        Bitmap bm = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
        Canvas cv = new Canvas(bm);
        Paint p = flat();
        int cols = (w + u - 1) / u, rows = (h + u - 1) / u;
        boolean[][] outer = shape(cols, rows, systemRadius(c) / u), frame = erode(outer), edge = erode(frame), face = erode(edge);
        p.setColor(Color.parseColor("#0A2228")); cv.drawPath(cells(outer, u, w, h), p);
        p.setColor(accent(color)); cv.drawPath(cells(frame, u, w, h), p);
        p.setColor(accentDark(color)); cv.drawPath(cells(edge, u, w, h), p);
        cv.save();
        cv.clipPath(cells(face, u, w, h));
        p.setColor(Color.parseColor("#123A43"));
        cv.drawRect(0, 0, w, h, p);
        Random rnd = new Random(11);
        for (int i = 0; i < (w * h) / (u * u * 160); i++) {
            int x = rnd.nextInt(Math.max(1, cols - 8)) * u, y = rnd.nextInt(rows) * u, len = (3 + rnd.nextInt(5)) * u;
            p.setColor(rnd.nextBoolean() ? Color.parseColor("#1A4D58") : Color.parseColor("#175059"));
            cv.drawRect(x, y, x + len, y + u, p);
        }
        cv.restore();
        return bm;
    }

    /** The tadpole or frog for a stage and colour. dy shifts it down by that many cells (for the bob). */
    static Bitmap frog(Context c, int stage, String color, int cell, int dy) {
        load(c);
        int gw = sprite.optInt("w", 32), gh = sprite.optInt("h", 24);
        Bitmap bm = Bitmap.createBitmap(gw * cell, (gh + 1) * cell, Bitmap.Config.ARGB_8888);
        Canvas cv = new Canvas(bm);
        try {
            JSONArray rows = sprite.getJSONArray("stages").getJSONArray(Math.max(0, Math.min(5, stage)));
            JSONObject pal = sprite.getJSONObject("palettes").optJSONObject(color);
            if (pal == null) pal = sprite.getJSONObject("palettes").getJSONObject("green");
            Paint p = flat();
            for (int y = 0; y < rows.length(); y++) {
                String row = rows.getString(y);
                for (int x = 0; x < row.length(); x++) {
                    char ch = row.charAt(x);
                    if (ch == '.') continue;
                    p.setColor(Color.parseColor(pal.getString(String.valueOf(ch))));
                    cv.drawRect(x * cell, (y + dy) * cell, (x + 1) * cell, (y + dy + 1) * cell, p);
                }
            }
        } catch (Exception e) { /* draw nothing */ }
        return bm;
    }

    /** A few lines of text, the first one bold and in the accent colour. Sized so the longest line fits. */
    static Bitmap text(Context c, String color, String[] lines, int w, int h) {
        load(c);
        float d = c.getResources().getDisplayMetrics().density;
        Bitmap bm = Bitmap.createBitmap(Math.max(1, w), Math.max(1, h), Bitmap.Config.ARGB_8888);
        Canvas cv = new Canvas(bm);
        Paint t = new Paint();
        t.setAntiAlias(true);
        t.setTypeface(pixelFace);
        float size = Math.min(17 * d, h / (lines.length * 1.35f));
        t.setTextSize(size);
        for (String s : lines) while (t.measureText(s) > w - 4 * d && t.getTextSize() > 8 * d) t.setTextSize(t.getTextSize() - 1);
        float sz = t.getTextSize();
        float y = (h - sz * 1.35f * lines.length) / 2f + sz;
        for (int i = 0; i < lines.length; i++) {
            t.setColor(i == 0 ? accentLight(color) : Color.parseColor("#CFE9D8"));
            t.setFakeBoldText(i == 0);
            t.setShadowLayer(0.1f, 2 * d, 2 * d, Color.parseColor("#0A2228"));
            cv.drawText(lines[i], 2 * d, y, t);
            y += sz * 1.35f;
        }
        return bm;
    }

    /** A pixel-cornered bar with a border, used for the entry box and the buttons. */
    static Bitmap bar(Context c, String label, int fill, int edge, int ink, int w, int h, boolean left) {
        load(c);
        float d = c.getResources().getDisplayMetrics().density;
        int u = Math.max(2, Math.round(1.5f * d));
        Bitmap bm = Bitmap.createBitmap(Math.max(1, w), Math.max(1, h), Bitmap.Config.ARGB_8888);
        Canvas cv = new Canvas(bm);
        Paint p = flat();
        p.setColor(edge); cv.drawPath(stepped(0, 0, w, h, u), p);
        p.setColor(fill); cv.drawPath(stepped(2 * u, 2 * u, w - 2 * u, h - 2 * u, u), p);
        Paint t = new Paint();
        t.setAntiAlias(true);
        t.setTypeface(pixelFace);
        t.setColor(ink);
        t.setFakeBoldText(true);
        float size = Math.min(15 * d, (h - 6 * u) * 0.78f);
        t.setTextSize(size);
        while (t.measureText(label) > w - 10 * u && t.getTextSize() > 8 * d) t.setTextSize(t.getTextSize() - 1);
        float x = left ? 5 * u : (w - t.measureText(label)) / 2f;
        cv.drawText(label, x, (h + t.getTextSize() * 0.62f) / 2f, t);
        return bm;
    }

    static Path stepped(float l, float t, float r, float b, float n) {
        Path p = new Path();
        p.moveTo(l, t + 2 * n); p.lineTo(l + n, t + 2 * n); p.lineTo(l + n, t + n); p.lineTo(l + 2 * n, t + n); p.lineTo(l + 2 * n, t);
        p.lineTo(r - 2 * n, t); p.lineTo(r - 2 * n, t + n); p.lineTo(r - n, t + n); p.lineTo(r - n, t + 2 * n); p.lineTo(r, t + 2 * n);
        p.lineTo(r, b - 2 * n); p.lineTo(r - n, b - 2 * n); p.lineTo(r - n, b - n); p.lineTo(r - 2 * n, b - n); p.lineTo(r - 2 * n, b);
        p.lineTo(l + 2 * n, b); p.lineTo(l + 2 * n, b - n); p.lineTo(l + n, b - n); p.lineTo(l + n, b - 2 * n); p.lineTo(l, b - 2 * n);
        p.close();
        return p;
    }

    static final String[] G_X = {"........", ".kk..kk.", "..kkkk..", "...kk...", "...kk...", "..kkkk..", ".kk..kk.", "........"};
    static final String[] G_CHECK = {"........", ".......k", "......kk", "k....kk.", "kk..kk..", ".kkkk...", "..kk....", "........"};
    static final String[] G_STOOL = {"........", "....k...", "...kkk..", "....kk..", "..kkkkk.", ".kkkkkkk", "kkkkkkkk", "........"};
    static final String[] G_BRAIN = {"..kk.kk.", ".kkkkkkk", "kkk.kkkk", "kkkkk.kk", "kk.kkkkk", ".kkkkkkk", "..kkkkk.", "....k..."};
    static final String[] G_MEAL = {"k.k.k.kk", "k.k.k.kk", "kkkkk.kk", ".kkk..kk", "..k...kk", "..k....k", "..k....k", "..k....k"};

    /** A small square button with a one-colour pixel glyph in it. */
    static Bitmap glyphButton(Context c, String[] g, int fill, int edge, int ink, int size) {
        float d = c.getResources().getDisplayMetrics().density;
        int u = Math.max(2, Math.round(1.5f * d));
        Bitmap bm = Bitmap.createBitmap(Math.max(1, size), Math.max(1, size), Bitmap.Config.ARGB_8888);
        Canvas cv = new Canvas(bm);
        Paint p = flat();
        p.setColor(edge); cv.drawPath(stepped(0, 0, size, size, u), p);
        p.setColor(fill); cv.drawPath(stepped(2 * u, 2 * u, size - 2 * u, size - 2 * u, u), p);
        int cell = Math.max(2, (size - 8 * u) / 8);
        int ox = (size - 8 * cell) / 2, oy = (size - 8 * cell) / 2;
        p.setColor(ink);
        for (int r = 0; r < 8; r++)
            for (int col = 0; col < 8; col++)
                if (g[r].charAt(col) == 'k') cv.drawRect(ox + col * cell, oy + r * cell, ox + (col + 1) * cell, oy + (r + 1) * cell, p);
        return bm;
    }

    /** A bordered tile with an optional pixel icon above and an optional label below (or the label alone, large, when there is no icon). */
    static Bitmap tile(Context c, int w, int h, int fill, int ink, String label, Bitmap icon) {
        load(c);
        float d = c.getResources().getDisplayMetrics().density;
        int u = Math.max(2, Math.round(1.5f * d));
        Bitmap bm = Bitmap.createBitmap(Math.max(1, w), Math.max(1, h), Bitmap.Config.ARGB_8888);
        Canvas cv = new Canvas(bm);
        Paint p = flat();
        p.setColor(Color.parseColor("#0A2228")); cv.drawPath(stepped(0, 0, w, h, u), p);
        p.setColor(fill); cv.drawPath(stepped(2 * u, 2 * u, w - 2 * u, h - 2 * u, u), p);
        Paint t = new Paint();
        t.setAntiAlias(true);
        t.setTypeface(pixelFace);
        t.setFakeBoldText(true);
        t.setColor(ink);
        if (icon != null) {
            float labelH = label == null ? 0 : 14 * d;
            cv.drawBitmap(icon, (w - icon.getWidth()) / 2f, (h - labelH - icon.getHeight()) / 2f + (label == null ? 0 : 1 * d), flat());
        }
        if (label != null) {
            float size = icon != null ? 11 * d : Math.min(24 * d, h * 0.46f);
            t.setTextSize(size);
            while (t.measureText(label) > w - 6 * u && t.getTextSize() > 7 * d) t.setTextSize(t.getTextSize() - 1);
            float y = icon != null ? h - 4 * u - 1 * d : (h + t.getTextSize() * 0.62f) / 2f;
            cv.drawText(label, (w - t.measureText(label)) / 2f, y, t);
        }
        return bm;
    }

    /** Representative foods for the FODMAP groups, in the order the meal dialog lists them. */
    static final String[] FOOD_NAMES = {"wheat", "onion/garlic", "beans", "dairy", "apple/honey", "mushroom", "stone fruit"};
    private static final String[][] FOODS = {
        {"...yy...", "..yyyy..", "...yd...", "..yyyy..", "...yd...", "..yyyy..", "....g...", "....g..."},
        {"....g...", "....g...", "...oo...", "..oooo..", ".oooOoo.", ".oooooO.", "..oOOo..", "...oo..."},
        {"......GG", ".....GlG", "....GlGG", "..GGlGG.", ".GlGlG..", "GllGG...", "GGGG....", "........"},
        {"..wwww..", ".wwwwww.", ".wBBBBw.", ".wBBBBw.", ".wBBBBw.", ".wwwwww.", ".wwwwww.", "..wwww.."},
        {"....g...", "...gg...", ".rr.rr..", "rrrrrrr.", "rrRrrrr.", "rrrrrrr.", ".rrrrr..", "..r.r..."},
        {"..cccc..", ".cCcccc.", "cccCcccc", "cccccccc", "..tttt..", "...tt...", "...tt...", "...tt..."},
        {"...gg...", "..g.....", ".pppppp.", "ppppPppp", "pppppppP", "ppppppPp", ".pppPP..", "..pppp.."}};

    private static int foodColor(char ch) {
        switch (ch) {
            case 'y': return 0xFFE8B93A; case 'd': return 0xFFB88717; case 'g': return 0xFF4FA050; case 'o': return 0xFFE9B369;
            case 'O': return 0xFFC98A3E; case 'r': return 0xFFC2452D; case 'R': return 0xFF8E2A1C; case 'w': return 0xFFF4F4EC;
            case 'B': return 0xFF4A7FC2; case 'c': return 0xFFB07A4A; case 'C': return 0xFF8C5A32; case 't': return 0xFFEADFC4;
            case 'l': return 0xFF8EE27B; case 'G': return 0xFF2F7A3A; case 'p': return 0xFFF2A25C; case 'P': return 0xFFD9743A; default: return 0;
        }
    }

    /** A food icon (0 to 6) drawn at cell pixels per dot. */
    static Bitmap food(int i, int cell) {
        Bitmap bm = Bitmap.createBitmap(8 * cell, 8 * cell, Bitmap.Config.ARGB_8888);
        Canvas cv = new Canvas(bm);
        Paint p = flat();
        for (int r = 0; r < 8; r++)
            for (int col = 0; col < 8; col++) {
                int k = foodColor(FOODS[i][r].charAt(col));
                if (k == 0) continue;
                p.setColor(k);
                cv.drawRect(col * cell, r * cell, (col + 1) * cell, (r + 1) * cell, p);
            }
        return bm;
    }

    /** A bowl filled to level 1 to 4 (a quarter per level), for the meal size picker. */
    static Bitmap bowl(int level, int cell) {
        Bitmap bm = Bitmap.createBitmap(10 * cell, 8 * cell, Bitmap.Config.ARGB_8888);
        Canvas cv = new Canvas(bm);
        Paint p = flat();
        p.setColor(0xFFC98A3E);
        for (int r = 0; r < 4; r++)
            if (r >= 4 - level) cv.drawRect(cell, r * cell, 9 * cell, (r + 1) * cell, p);
        p.setColor(0xFF1F5E2E);
        cv.drawRect(0, 4 * cell, 10 * cell, 5 * cell, p);
        cv.drawRect(cell, 5 * cell, 9 * cell, 6 * cell, p);
        cv.drawRect(2 * cell, 6 * cell, 8 * cell, 7 * cell, p);
        cv.drawRect(3 * cell, 7 * cell, 7 * cell, 8 * cell, p);
        return bm;
    }

    private static final String[] REFRESH = {
        "..kkkk..", ".k....k.", "k..kkkkk", "k...kkk.", "k....k..", "k.......", ".k....k.", "..kkkk.."};

    static Bitmap refresh(Context c, boolean stale) {
        float d = c.getResources().getDisplayMetrics().density;
        int cell = Math.max(2, Math.round(2 * d));
        Bitmap bm = Bitmap.createBitmap(8 * cell, 8 * cell, Bitmap.Config.ARGB_8888);
        Canvas cv = new Canvas(bm);
        Paint p = flat();
        p.setColor(stale ? Color.parseColor("#FFB04A") : Color.parseColor("#CFE9D8"));
        for (int r = 0; r < 8; r++)
            for (int col = 0; col < 8; col++)
                if (REFRESH[r].charAt(col) == 'k') cv.drawRect(col * cell, r * cell, (col + 1) * cell, (r + 1) * cell, p);
        return bm;
    }
}
