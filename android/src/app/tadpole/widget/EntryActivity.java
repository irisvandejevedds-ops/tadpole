package app.tadpole.widget;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** The box you type into. Opened by the widget's entry bar (or its Symptom button), it shows the keyboard at once and sends the line to the diary. */
public class EntryActivity extends Activity {
    private static final Pattern SYMPTOM = Pattern.compile("bloat|\\bgas\\b|gassy|cramp|\\bpain|ache\\b|aches\\b|achy|nause|vomit|reflux|heartburn|indigestion|diarrh|constipat|stomach|tummy|headache|migraine|dizz|fatigue|exhaust|rash|hives|itch|swell|flare|brain fog|\\bsick\\b|\\bsymptom", Pattern.CASE_INSENSITIVE);
    private static final Pattern CLEAR = Pattern.compile("\\b(no|zero|none|without)\\b.{0,12}\\bsymptoms?\\b|\\bsymptom[- ]?free\\b|\\b(feel(ing)?|felt)\\s+(fine|great|good|well|normal)\\b|\\ball\\s+good\\b", Pattern.CASE_INSENSITIVE);
    private static final Pattern NUMBER = Pattern.compile("(\\d{1,2})\\s*(?:/|out of)\\s*10|(?<![\\d.:/$])\\b(10|\\d)\\b(?![\\d.:%/])");

    /** A text watcher that just calls back; a named class because anonymous classes trip this build's dex step. */
    static final class Watch implements TextWatcher {
        private final Runnable r;
        Watch(Runnable r) { this.r = r; }
        @Override public void beforeTextChanged(CharSequence s, int a, int b, int c) {}
        @Override public void onTextChanged(CharSequence s, int a, int b, int c) { r.run(); }
        @Override public void afterTextChanged(Editable s) {}
    }

    private EditText input;
    private TextView preview;
    private Button send;
    private HorizontalScrollView sevRow;
    private final Button[] chips = new Button[11];
    private int severity = -1;
    private boolean forceSymptom;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        forceSymptom = getIntent().getBooleanExtra("symptom", false);
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_VISIBLE | WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        int ink = Color.parseColor("#16351F"), pad = dp(18);
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setPadding(pad, pad, pad, pad);
        col.setBackgroundColor(Color.parseColor("#DCEEC2"));

        TextView title = new TextView(this);
        title.setText(forceSymptom ? "What are you feeling?" : "What happened?");
        title.setTextSize(20);
        title.setTypeface(Pixel.face(this), android.graphics.Typeface.BOLD);
        title.setTextColor(Color.parseColor("#1F5E2E"));
        col.addView(title);

        input = new EditText(this);
        input.setTypeface(Pixel.face(this));
        input.setTextColor(ink);
        input.setHintTextColor(Color.parseColor("#7C9A84"));
        input.setHint(forceSymptom ? "bloating, cramps, headache..." : "Oatmeal with banana, coffee");
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        input.setMinLines(2);
        input.setMaxLines(4);
        input.setGravity(Gravity.TOP | Gravity.START);
        input.setBackgroundColor(Color.parseColor("#FBFEF2"));
        input.setPadding(dp(10), dp(10), dp(10), dp(10));
        if (forceSymptom) input.setText("symptom: ");
        input.setSelection(input.getText().length());
        input.addTextChangedListener(new Watch(this::refresh));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(10);
        col.addView(input, lp);

        preview = new TextView(this);
        preview.setTypeface(Pixel.face(this));
        preview.setTextSize(14);
        preview.setTextColor(Color.parseColor("#44704F"));
        preview.setPadding(0, dp(8), 0, dp(4));
        col.addView(preview);

        sevRow = new HorizontalScrollView(this);
        sevRow.setHorizontalScrollBarEnabled(false);
        LinearLayout chipRow = new LinearLayout(this);
        chipRow.setOrientation(LinearLayout.HORIZONTAL);
        for (int i = 0; i <= 10; i++) {
            final int n = i;
            Button c = new Button(this);
            c.setText(String.valueOf(i));
            c.setTypeface(Pixel.face(this));
            c.setAllCaps(false);
            c.setMinWidth(0);
            c.setMinimumWidth(dp(42));
            c.setPadding(dp(4), 0, dp(4), 0);
            c.setOnClickListener(v -> { severity = severity == n ? -1 : n; refresh(); });
            LinearLayout.LayoutParams cp = new LinearLayout.LayoutParams(dp(42), dp(42));
            cp.rightMargin = dp(4);
            chipRow.addView(c, cp);
            chips[i] = c;
        }
        sevRow.addView(chipRow);
        col.addView(sevRow);

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.END);
        Button cancel = button("Cancel", "#EAF5D6", "#1F5E2E");
        cancel.setOnClickListener(v -> finish());
        send = button("Add", "#2F8442", "#FFFFFF");
        send.setOnClickListener(v -> submit());
        row.addView(cancel);
        row.addView(send);
        LinearLayout.LayoutParams rp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        rp.topMargin = dp(10);
        col.addView(row, rp);
        setContentView(col);
        input.requestFocus();
        refresh();
    }

    private int dp(int v) { return Math.round(v * getResources().getDisplayMetrics().density); }

    private Button button(String label, String bg, String fg) {
        Button bt = new Button(this);
        bt.setText(label);
        bt.setAllCaps(true);
        bt.setTypeface(Pixel.face(this), android.graphics.Typeface.BOLD);
        bt.setTextColor(Color.parseColor(fg));
        bt.setBackgroundColor(Color.parseColor(bg));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, dp(46));
        lp.leftMargin = dp(10);
        bt.setLayoutParams(lp);
        return bt;
    }

    /** What the line looks like it will be saved as. The server decides for certain; this is only a guide. */
    private String guess(String text) {
        String t = text.trim();
        String low = t.toLowerCase();
        if (low.startsWith("symptom:") || low.startsWith("s:") || forceSymptom) return "symptom";
        if (low.startsWith("note:") || low.startsWith("n:")) return "note";
        if (low.startsWith("food:") || low.startsWith("f:")) return "food";
        if (CLEAR.matcher(t).find() && !SYMPTOM.matcher(CLEAR.matcher(t).replaceAll("")).find()) return "clear";
        return SYMPTOM.matcher(t).find() ? "symptom" : "food";
    }

    private void refresh() {
        String text = input.getText().toString();
        String kind = guess(text);
        boolean symptom = "symptom".equals(kind);
        sevRow.setVisibility(symptom ? View.VISIBLE : View.GONE);
        for (int i = 0; i <= 10; i++) {
            boolean on = i == severity;
            chips[i].setBackgroundColor(Color.parseColor(on ? "#B33A28" : "#F8C7B0"));
            chips[i].setTextColor(Color.parseColor(on ? "#FFFFFF" : "#3A1410"));
        }
        String what;
        if (text.trim().isEmpty()) what = "Type it like a note.";
        else if (symptom) {
            Matcher m = NUMBER.matcher(text);
            String typed = m.find() ? (m.group(1) != null ? m.group(1) : m.group(2)) : null;
            String n = severity >= 0 ? String.valueOf(severity) : typed;
            what = "Saved as: symptom" + (n != null ? " " + n + "/10" : " (tap how bad)");
        } else what = "Saved as: " + ("clear".equals(kind) ? "all clear" : kind);
        preview.setText(what);
        send.setEnabled(!text.trim().isEmpty());
        send.setAlpha(text.trim().isEmpty() ? 0.5f : 1f);
    }

    private void submit() {
        final String text = input.getText().toString().trim();
        if (text.isEmpty()) return;
        final Integer sev = severity >= 0 ? Integer.valueOf(severity) : null;
        Local.add(this, text, sev, forceSymptom ? "symptom" : null);
        Toast.makeText(this, "Saved.", Toast.LENGTH_SHORT).show();
        finish();
    }
}
