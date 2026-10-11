package app.tadpole.widget;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

/** Connects the widget to the app (via the link on the Widget page, or by pasting an address and key). */
public class MainActivity extends Activity {
    private TextView status;
    private EditText url, token;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        Pixel.load(this);
        getWindow().setStatusBarColor(Color.parseColor("#2F8442"));
        handle(getIntent());
        if (getIntent().getBooleanExtra("open_web", false) && Store.connected(this)) {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(Store.url(this))));
            finish();
            return;
        }
        build();
    }

    @Override
    protected void onNewIntent(Intent i) {
        super.onNewIntent(i);
        setIntent(i);
        handle(i);
        refreshStatus();
    }

    private void handle(Intent i) {
        Uri d = i == null ? null : i.getData();
        if (d != null && "tadpole".equals(d.getScheme()) && "setup".equals(d.getHost())) {
            String u = d.getQueryParameter("url"), t = d.getQueryParameter("token");
            if (u != null && t != null && u.startsWith("https://") && t.startsWith("tpw_")) {
                Store.saveConn(this, u, t);
                new Thread(this::saveAndTest).start();
                Toast.makeText(this, "Connected. Add the widget from your home screen.", Toast.LENGTH_LONG).show();
            }
        }
    }

    private TextView text(String s, int sp, int color) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(sp);
        t.setTextColor(color);
        t.setTypeface(Pixel.face(this));
        t.setPadding(0, 8, 0, 8);
        return t;
    }

    private Button button(String s, View.OnClickListener l) {
        Button bt = new Button(this);
        bt.setText(s);
        bt.setTypeface(Pixel.face(this), android.graphics.Typeface.BOLD);
        bt.setAllCaps(true);
        bt.setTextColor(Color.WHITE);
        bt.setBackgroundColor(Color.parseColor("#2F8442"));
        bt.setOnClickListener(l);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = 16;
        bt.setLayoutParams(lp);
        return bt;
    }

    private void build() {
        int ink = Color.parseColor("#16351F");
        ScrollView sv = new ScrollView(this);
        sv.setBackgroundColor(Color.parseColor("#DCEEC2"));
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setPadding(36, 80, 36, 60);
        sv.addView(col);

        LinearLayout head = new LinearLayout(this);
        head.setOrientation(LinearLayout.HORIZONTAL);
        head.setGravity(Gravity.CENTER_VERTICAL);
        TextView title = text("Tadpole", 34, Color.parseColor("#1F5E2E"));
        title.setTypeface(Pixel.face(this), android.graphics.Typeface.BOLD);
        head.addView(title, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        final TextView help = text("To add the widget: press and hold an empty spot on your home screen, choose Widgets, find Tadpole, and drag it out. "
                + "Tap the box on the widget to type an entry.", 14, ink);
        help.setBackgroundColor(Color.parseColor("#F3E56F"));
        help.setPadding(20, 16, 20, 16);
        help.setVisibility(View.GONE);
        Button info = new Button(this);
        info.setText("i");
        info.setTypeface(Pixel.face(this), android.graphics.Typeface.BOLD);
        info.setAllCaps(false);
        info.setTextColor(Color.parseColor("#1F5E2E"));
        info.setBackgroundColor(Color.parseColor("#FBFEF2"));
        info.setMinWidth(0);
        info.setMinimumWidth(0);
        info.setOnClickListener(v -> help.setVisibility(help.getVisibility() == View.GONE ? View.VISIBLE : View.GONE));
        head.addView(info, new LinearLayout.LayoutParams(96, 96));
        col.addView(head);
        col.addView(help);
        status = text("", 15, ink);
        col.addView(status);

        col.addView(text("Address", 12, Color.parseColor("#44704F")));
        url = new EditText(this);
        url.setTypeface(Pixel.face(this));
        url.setSingleLine(true);
        url.setHint("https://your-machine.ts.net:8444");
        url.setInputType(InputType.TYPE_TEXT_VARIATION_URI);
        url.setText(Store.url(this));
        col.addView(url);
        col.addView(text("Key", 12, Color.parseColor("#44704F")));
        token = new EditText(this);
        token.setTypeface(Pixel.face(this));
        token.setSingleLine(true);
        token.setHint("tpw_...");
        token.setText(Store.token(this));
        col.addView(token);

        col.addView(button("Save and test", v -> {
            Store.saveConn(this, url.getText().toString(), token.getText().toString());
            new Thread(this::saveAndTest).start();
        }));
        col.addView(button("Send saved entries now", v -> new Thread(this::sendAll).start()));
        col.addView(button("Open Tadpole", v -> { if (Store.connected(this)) startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(Store.url(this)))); }));
        setContentView(sv);
        refreshStatus();
    }

    private void note(String msg) {
        runOnUiThread(() -> { if (msg != null) Toast.makeText(this, msg, Toast.LENGTH_LONG).show(); refreshStatus(); });
    }

    private void saveAndTest() {
        Sync.state(this, true);
        boolean reached = Sync.lastError == null;
        PondWidget.refreshAll(this);
        Sync.ensurePeriodic(this);
        note(reached ? "Connected." : "Could not reach Tadpole: " + Sync.lastError + ". Is Tailscale on?");
    }

    private void sendAll() {
        Sync.flush(this);
        PondWidget.refreshAll(this);
        note(null);
    }

    private void refreshStatus() {
        if (status == null) return;
        int n = Store.pending(this);
        status.setText((Store.connected(this) ? "Connected to " + Store.url(this) : "Not connected yet.") + (n > 0 ? "\n" + n + (n == 1 ? " entry" : " entries") + " waiting to be sent." : ""));
    }
}
