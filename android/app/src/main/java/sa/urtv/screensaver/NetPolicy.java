package sa.urtv.screensaver;

import android.net.Uri;
import android.webkit.WebResourceResponse;

import java.io.ByteArrayInputStream;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

/**
 * The only places the screen page may reach: its data APIs and this repo. Anything else (the page's CORS-proxy
 * fallbacks for plain browsers, or anything a changed page might add) gets an empty 403 instead of a request.
 */
final class NetPolicy {
    private static final Set<String> HOSTS = new HashSet<>(Arrays.asList(
        "api.aladhan.com",                  // prayer times
        "api.open-meteo.com",               // weather
        "air-quality-api.open-meteo.com",
        "api.coingecko.com",                // markets
        "query1.finance.yahoo.com",
        "api.tvmaze.com",                   // episodes
        "www.thesportsdb.com",              // matches
        "www.wikidata.org"));               // Arabic club names
    private static final String REPO = "/SultanBajaifer/UrTV/";

    private NetPolicy() {}

    static boolean allowed(Uri u) {
        String scheme = u.getScheme(), host = u.getHost(), path = u.getPath();
        if ("file".equals(scheme) || "data".equals(scheme) || "blob".equals(scheme)) return true;
        if (!"https".equals(scheme) || host == null) return false;
        if ("raw.githubusercontent.com".equals(host)) return path != null && path.startsWith(REPO);
        return HOSTS.contains(host);
    }

    static WebResourceResponse blocked() {
        return new WebResourceResponse("text/plain", "utf-8", 403, "Blocked", null, new ByteArrayInputStream(new byte[0]));
    }
}
