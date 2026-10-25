package sa.urtv.home;

import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

/**
 * «تسريع» (Boost): which apps it may stop, and what it says afterwards. Plain Java, no Android: tests/boost_test.py runs it.
 * Boost.java does the stopping; the Android part is only ActivityManager.killBackgroundProcesses, which stops an app's
 * processes that sit in the background (never the app on screen, music playing in the background, or the system).
 */
public final class BoostText {
    /** Android 14 (API 34) lets an app stop only its own background processes: on those TVs the button can't free others */
    public static final int LIMITED_FROM_SDK = 34;

    /**
     * Never stopped, even in the background: casting, AirPlay, voice, the remote, keyboards, the tuner and inputs, the
     * quick panel, updates, Google services and the home screens. The same packages as optimize/lists/keep.txt (the test
     * checks both match), plus this app and the screensaver.
     */
    static final Set<String> KEEP = new HashSet<>(Arrays.asList(
        "com.tcl.airplay2", "com.google.android.apps.mediashell", "com.tcl.miracast", "com.tcl.magiconnectfree",
        "com.google.android.katniss", "com.google.android.tv.assistant", "com.tcl.micmanager",
        "com.google.android.tv.remote.service", "com.tcl.autopair", "com.tcl.smartalexa",
        "com.tcl.inputmethod.international", "com.google.android.inputmethod.latin",
        "com.tcl.tv", "com.tcl.tvinput", "com.tcl.suspension", "com.tcl.settings", "com.android.tv.settings",
        "com.tcl.systemserver", "com.tcl.versionUpdateApp", "com.tcl.providers.config",
        "com.tcl.android.webview", "com.google.android.webview", "com.android.systemui",
        "com.google.android.gms", "com.google.android.gsf", "com.android.vending", "com.android.location.fused",
        "com.google.android.apps.tv.launcherx", "com.google.android.tvlauncher", "com.google.android.tungsten.setupwraith",
        "com.tcl.keycustomfunctionservice", "com.tcl.hearaid", "com.google.android.marvin.talkback",
        "sa.urtv.home", "sa.urtv.screensaver"));

    private BoostText() {}

    /**
     * may Boost stop this app's background processes? Only apps a person opens from the home screen (Netflix, YouTube,
     * Shahid…), never a kept one: background services without a screen of their own are left to Android.
     */
    public static boolean mayStop(String pkg, boolean launchable) {
        if (pkg == null || pkg.isEmpty() || KEEP.contains(pkg)) return false;
        return launchable;
    }

    /** megabytes, rounded */
    public static long mb(long bytes) { return Math.round(bytes / (1024.0 * 1024.0)); }

    /**
     * what the person reads: the memory freed (never below 0: other apps can grow meanwhile) and what is free now.
     * No count of stopped apps: Android does not say which of them were running.
     */
    public static String result(long beforeAvail, long afterAvail, int sdk) {
        long freed = Math.max(0, mb(afterAvail) - mb(beforeAvail));
        String free = "الذاكرة المتاحة الآن " + mb(afterAvail) + " م.ب";
        if (sdk >= LIMITED_FROM_SDK) {
            return "أندرويد 14 وأحدث ما يسمح لتطبيق يوقف تطبيقات ثانية، والتلفزيون يوقف اللي ما يحتاجه بنفسه. " + free
                + ". للتنظيف الكامل: شغّل optimize/boost.sh من الكمبيوتر.";
        }
        if (freed == 0) return "الذاكرة نظيفة: ما فيه تطبيقات بالخلفية تستاهل توقف. " + free + ".";
        return "تم التسريع: وفّرنا " + freed + " م.ب بإيقاف التطبيقات اللي بالخلفية. " + free + ".";
    }
}
