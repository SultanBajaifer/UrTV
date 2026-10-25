package sa.urtv.home;

import android.app.ActivityManager;
import android.content.Context;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.widget.Toast;

/**
 * «تسريع»: frees memory by stopping the background processes of the apps nobody is using (BoostText says which), then
 * says how much was freed. Nothing is uninstalled, disabled or cleared: an app stopped this way starts again normally
 * when it is opened, and keeps its logins and data. Android 14 and newer only let an app stop its own processes, so
 * there it reports what is free and points to optimize/boost.sh (ADB), which can.
 */
final class Boost {
    private static volatile boolean running;

    private Boost() {}

    /** from the pill: works on a thread, then a toast with the result on the main thread */
    static void run(Context context) {
        if (running) return;
        running = true;
        final Context c = context.getApplicationContext();
        Toast.makeText(c, "جاري التسريع…", Toast.LENGTH_SHORT).show();
        new Thread(() -> {
            String msg;
            try {
                msg = Digits.of(free(c));
            } catch (RuntimeException e) {
                msg = "تعذّر التسريع الحين.";
            } finally {
                running = false;
            }
            final String text = msg;
            new Handler(Looper.getMainLooper()).post(() -> Toast.makeText(c, text, Toast.LENGTH_LONG).show());
        }, "boost").start();
    }

    private static String free(Context c) {
        ActivityManager am = (ActivityManager) c.getSystemService(Context.ACTIVITY_SERVICE);
        long before = avail(am);
        if (Build.VERSION.SDK_INT < BoostText.LIMITED_FROM_SDK) {
            PackageManager pm = c.getPackageManager();
            for (ApplicationInfo a : pm.getInstalledApplications(0)) {
                boolean launchable = pm.getLeanbackLaunchIntentForPackage(a.packageName) != null
                    || pm.getLaunchIntentForPackage(a.packageName) != null;
                if (a.enabled && BoostText.mayStop(a.packageName, launchable)) am.killBackgroundProcesses(a.packageName);
            }
            try { Thread.sleep(1500); } catch (InterruptedException ignored) { }   // the memory comes back over a moment
        }
        return BoostText.result(before, avail(am), Build.VERSION.SDK_INT);
    }

    private static long avail(ActivityManager am) {
        ActivityManager.MemoryInfo mi = new ActivityManager.MemoryInfo();
        am.getMemoryInfo(mi);
        return mi.availMem;
    }
}
