package app.tadpole.widget;

import android.app.job.JobParameters;
import android.app.job.JobService;

public class RetryService extends JobService {
    @Override
    public boolean onStartJob(final JobParameters params) {
        new Thread(() -> {
            int left = Sync.flush(RetryService.this);
            if (left == 0) Sync.state(RetryService.this);
            PondWidget.refreshAll(RetryService.this);
            jobFinished(params, left > 0);
        }).start();
        return true;
    }

    @Override
    public boolean onStopJob(JobParameters params) { return true; }
}
