package app.tadpole.widget;

import android.app.Activity;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.Toast;

/** One tap, no typing: records "No symptoms" for now. Invisible; it only exists so the app is in the foreground while it sends. */
public class QuickActivity extends Activity {
    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        final Handler ui = new Handler(Looper.getMainLooper());
        new Thread(() -> {
            Sync.Result r = Sync.add(this, "No symptoms", 0, "clear");
            final String msg = r.error != null ? "Couldn't save that: " + r.error + "." : r.queued ? "Saved. It will be sent when you are back in range." : "Noted: no symptoms.";
            PondWidget.refreshAll(this);
            ui.post(() -> {
                Toast.makeText(this, msg, Toast.LENGTH_LONG).show();
                finish();
                overridePendingTransition(0, 0);
            });
        }).start();
    }
}
