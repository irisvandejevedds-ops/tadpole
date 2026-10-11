package app.tadpole.widget;

import android.app.job.JobParameters;
import android.app.job.JobService;

/** Refreshes the widget from the server as a background job, so it still gets network when the phone is idle. */
public class SyncService extends JobService {
    @Override
    public boolean onStartJob(final JobParameters params) {
        new Thread(() -> {
            try {
                Sync.flush(SyncService.this);
                Sync.state(SyncService.this);
            } finally {
                PondWidget.refreshAll(SyncService.this);
                jobFinished(params, false);
            }
        }).start();
        return true;
    }

    @Override
    public boolean onStopJob(JobParameters params) { return false; }
}
