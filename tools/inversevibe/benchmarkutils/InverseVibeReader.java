package org.owasp.benchmarkutils.score.parsers.sarif;

/**
 * Reader for InverseVibe, a static analysis release gate. It reads the SARIF produced by the
 * InverseVibe engine's static-review stage, whose rules carry their CWE as an {@code
 * external/cwe/cwe-NNN} tag.
 */
public class InverseVibeReader extends SarifReader {
    public InverseVibeReader() {
        super("InverseVibe", false, CweSourceType.TAG);
    }
}
