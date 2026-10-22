package sa.urtv.screensaver;

import android.util.Base64;

import java.security.KeyFactory;
import java.security.PublicKey;
import java.security.Signature;
import java.security.spec.X509EncodedKeySpec;

/**
 * Checks a downloaded page against the owner's page-signing key (ECDSA P-256, SHA-256). The public key is built
 * into the app from android/app/page-key.pub; the private key never leaves the owner's computer
 * (optimize/sign-page.sh). No key in the build = every downloaded page is refused and the built-in page is used.
 */
final class PageKey {
    private PageKey() {}

    /** sig: dist/tv.html.sig, the base64 of a DER-encoded ECDSA signature. */
    static boolean verify(byte[] page, byte[] sig) {
        if (BuildConfig.PAGE_KEY.isEmpty()) return false;
        try {
            PublicKey key = KeyFactory.getInstance("EC")
                .generatePublic(new X509EncodedKeySpec(Base64.decode(BuildConfig.PAGE_KEY, Base64.DEFAULT)));
            Signature s = Signature.getInstance("SHA256withECDSA");
            s.initVerify(key);
            s.update(page);
            return s.verify(Base64.decode(new String(sig, "US-ASCII").trim(), Base64.DEFAULT));
        } catch (Exception e) {
            return false;
        }
    }
}
