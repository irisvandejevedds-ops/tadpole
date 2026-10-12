package app.tadpole.widget;

import android.app.Activity;
import android.os.Bundle;
import android.widget.Toast;

/** One tap, no typing: records "No symptoms" for now. Invisible; it closes at once. */
public class QuickActivity extends Activity {
    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        Local.add(this, "No symptoms", 0, "clear");
        Toast.makeText(this, "Noted: no symptoms.", Toast.LENGTH_SHORT).show();
        finish();
        overridePendingTransition(0, 0);
    }
}
