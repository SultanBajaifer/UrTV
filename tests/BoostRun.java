package sa.urtv.home;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;

/**
 * For tests/boost_test.py: BoostText.java on tests/boost_cases.tsv. A line is
 *   stop    PACKAGE launchable(0|1)              -> 1 or 0
 *   result  BEFORE_MB AFTER_MB SDK               -> the message
 *   keep                                         -> every kept package, one per line
 */
public final class BoostRun {
    public static void main(String[] args) throws IOException {
        StringBuilder out = new StringBuilder();
        for (String line : Files.readAllLines(Paths.get(args[0]), StandardCharsets.UTF_8)) {
            if (line.isEmpty() || line.startsWith("#")) continue;
            String[] f = line.split("\t", -1);
            long mb = 1024L * 1024L;
            switch (f[0]) {
                case "stop": out.append(BoostText.mayStop(f[1], "1".equals(f[2])) ? "1" : "0"); break;
                case "result": out.append(BoostText.result(Long.parseLong(f[1]) * mb, Long.parseLong(f[2]) * mb, Integer.parseInt(f[3]))); break;
                default: out.append(String.join(" ", new java.util.TreeSet<>(BoostText.KEEP)));
            }
            out.append('\n');
        }
        System.out.write(out.toString().getBytes(StandardCharsets.UTF_8));
        System.out.flush();
    }
}
