"""Predefined investigation steps for the eMudhra certificate workbench.

Every command here is fixed. The UI can only execute commands from this
registry by (step_id, command_id) — arbitrary command execution is not
possible through the API.
"""

TARGET_HOST = "sha256.badssl.com:443"

STEPS = [
    {
        "id": "step-0",
        "num": 0,
        "title": "Environment setup",
        "summary": "Verify the tools on this Mac and create the investigation workspace.",
        "explain": [
            "Every investigation starts by recording the environment: the OS, the OpenSSL build, curl, and Python. Results later in the run depend on these versions, so they are captured first.",
            "The workspace is ~/eMudhra with three directories: certificates/ for extracted PEM files, evidence/ for raw command output, and reports/ for the final summary.",
        ],
        "commands": [
            {
                "id": "0.1",
                "label": "Check installed tools",
                "cmd": 'echo "== sw_vers =="; sw_vers; echo; echo "== openssl =="; openssl version -a; echo; echo "== curl =="; curl --version | head -n 2; echo; echo "== python3 =="; python3 --version',
                "breakdown": [
                    ["echo \"== sw_vers ==\"", "Prints a section header so each tool's output stays easy to find."],
                    ["sw_vers", "macOS command that prints the operating system name and version."],
                    ["openssl version -a", "Prints the OpenSSL version and how it was built."],
                    ["curl --version", "Prints the curl version and the protocols it supports."],
                    ["| head -n 2", "Keeps only the first 2 lines of curl's output."],
                    ["python3 --version", "Prints the installed Python version."],
                    [";", "Runs the commands one after another."],
                ],
                "note": "Confirm sw_vers, openssl, curl and python3 are present. macOS usually ships curl and python3; OpenSSL may come from Homebrew.",
            },
            {
                "id": "0.2",
                "label": "Create investigation workspace",
                "cmd": 'pwd && mkdir -p certificates evidence reports evidence/runs && ls -la',
                "breakdown": [
                    ["pwd", "Prints the current directory — the workspace everything lands in."],
                    ["&&", "Runs the next command only if the previous one succeeded."],
                    ["mkdir -p ...", "Creates the investigation folders. -p also creates parent folders and never fails if they already exist."],
                    ["ls -la", "Lists the folder contents in long format to confirm the folders exist."],
                ],
                "note": "Creates ~/eMudhra/{certificates,evidence,reports}. All later commands run from this directory.",
            },
            {
                "id": "0.3",
                "label": "Record the environment",
                "cmd": '{ echo "Investigation started: $(date -u)"; echo "Operating system:"; sw_vers; echo "OpenSSL:"; openssl version; echo "curl:"; curl --version | head -n 2; } 2>&1 | tee evidence/environment.txt',
                "breakdown": [
                    ["{ ... }", "Groups the commands so their combined output can be captured together."],
                    ["$(date -u)", "Inserts the current date and time in UTC."],
                    ["sw_vers / openssl / curl", "Records the OS and tool versions, same as the previous command."],
                    ["2>&1", "Merges error output into normal output so nothing is lost."],
                    ["| tee evidence/environment.txt", "Displays on screen while also saving to the file."],
                ],
                "note": "Saves a dated environment record to evidence/environment.txt — the baseline for the evidence bundle.",
                "evidence": "evidence/environment.txt",
            },
        ],
    },
    {
        "id": "step-1",
        "num": 1,
        "title": "Inspect live HTTPS",
        "summary": "Resolve the target, inspect the TLS handshake, capture the served chain.",
        "explain": [
            "This step observes the live server. DNS resolution comes first, then curl shows the TLS negotiation and HTTP response, then openssl s_client captures the exact certificate chain the server presents.",
            "The -servername flag sends SNI so the server selects the right certificate. -showcerts prints the certificates themselves — displaying a chain is not the same as proving it is trusted.",
            "The final command runs OpenSSL's built-in verification: look for 'Verify return code: 0 (ok)'. The result depends on your OpenSSL build, local trust store, and the server's current chain.",
        ],
        "commands": [
            {
                "id": "1.1",
                "label": "Check DNS resolution",
                "cmd": "dig sha256.badssl.com",
                "breakdown": [
                    ["dig", "DNS lookup tool — asks the name server which IP address a host has."],
                    ["sha256.badssl.com", "The hostname being investigated."],
                ],
                "fallback": "python3 -c \"import socket; print(socket.getaddrinfo('sha256.badssl.com', 443))\"",
                "fallback_note": "dig is not installed on this Mac — running the Python resolver fallback instead.",
                "note": "Resolves the target host. If dig is unavailable, the Python socket fallback performs the same lookup.",
            },
            {
                "id": "1.2",
                "label": "Inspect HTTPS response and TLS details",
                "cmd": "curl -Iv https://sha256.badssl.com/ 2>&1 | tee evidence/step1-curl.txt",
                "breakdown": [
                    ["curl", "Tool for performing communication such as HTTP/HTTPS."],
                    ["-I", "Sends a HEAD request — retrieves only the HTTP response headers."],
                    ["-v", "Displays detailed information such as the TLS connection and certificate verification."],
                    ["https://sha256.badssl.com/", "The web server to connect to."],
                    ["2>&1", "Merges error output (where the TLS details are printed) into normal output."],
                    ["| tee evidence/step1-curl.txt", "Displays on screen while also saving to a file."],
                ],
                "note": "Look for TLS version, certificate subject and issuer, verification result, and the HTTP response. Saved to evidence/step1-curl.txt.",
                "evidence": "evidence/step1-curl.txt",
            },
            {
                "id": "1.3",
                "label": "Capture the certificate chain",
                "cmd": "openssl s_client -connect sha256.badssl.com:443 -servername sha256.badssl.com -showcerts </dev/null 2>&1 | tee evidence/step1-sclient.txt",
                "breakdown": [
                    ["openssl s_client", "OpenSSL tool that connects to a server as a TLS client."],
                    ["-connect sha256.badssl.com:443", "The server address and port to connect to."],
                    ["-servername sha256.badssl.com", "Sends the hostname (SNI) so the server returns the right certificate."],
                    ["-showcerts", "Prints every certificate the server presents, in PEM text form."],
                    ["</dev/null", "Feeds empty input so the command exits instead of waiting for keystrokes."],
                    ["2>&1 | tee evidence/step1-sclient.txt", "Merges the output streams and saves the full exchange to the evidence file."],
                ],
                "note": "Saves every certificate the server sends to evidence/step1-sclient.txt. Step 2 splits this file into individual PEM files.",
                "evidence": "evidence/step1-sclient.txt",
            },
            {
                "id": "1.4",
                "label": "Run OpenSSL built-in verification",
                "cmd": "openssl s_client -connect sha256.badssl.com:443 -servername sha256.badssl.com -verify_return_error -verify_hostname sha256.badssl.com </dev/null 2>&1 | tee evidence/step1-verify.txt",
                "breakdown": [
                    ["openssl s_client -connect ... -servername ...", "Connects to the live server as a TLS client, same as command 1.3."],
                    ["-verify_return_error", "Turns a certificate verification failure into a connection failure."],
                    ["-verify_hostname sha256.badssl.com", "Additionally checks the certificate is valid for this exact hostname."],
                    ["</dev/null 2>&1 | tee evidence/step1-verify.txt", "Captures the whole verification exchange into the evidence file."],
                ],
                "note": "-verify_return_error turns a verification failure into a connection failure. Success means 'Verify return code: 0 (ok)'.",
                "evidence": "evidence/step1-verify.txt",
            },
        ],
    },
    {
        "id": "step-2",
        "num": 2,
        "title": "Inspect certificate details",
        "summary": "Split the captured chain and inspect subject, issuer, dates, SANs, extensions, fingerprints.",
        "explain": [
            "Subject is the identity the certificate represents; issuer is the authority that signed it. An issuer name alone never proves the signature is valid — that is what Step 4 tests.",
            "Validity dates bound the certificate's lifetime, and SAN lists the DNS names it may serve. basicConstraints, keyUsage and extendedKeyUsage separate ordinary server certificates from CA certificates permitted to sign others.",
            "Fingerprints identify certificates across reports and sources. A matching fingerprint means the same certificate — not that it is trusted.",
        ],
        "commands": [
            {
                "id": "2.1",
                "label": "Split chain into PEM files",
                "cmd": """awk '
/-----BEGIN CERTIFICATE-----/ {
  n++
  file=sprintf("certificates/cert-%d.pem", n-1)
  inside=1
}
inside { print > file }
/-----END CERTIFICATE-----/ {
  close(file)
  inside=0
}
' evidence/step1-sclient.txt && ls -lh certificates/ && echo "---- certificate count ----" && grep -c "BEGIN CERTIFICATE" evidence/step1-sclient.txt""",
                "breakdown": [
                    ["awk '...'", "Text-processing tool that scans the capture line by line."],
                    ["/-----BEGIN CERTIFICATE-----/", "Pattern matching the start of a PEM certificate block."],
                    ["n++", "Counts the certificates as they appear."],
                    ['file=sprintf("certificates/cert-%d.pem", n-1)', "Builds the output file name: cert-0.pem, cert-1.pem, and so on."],
                    ["inside { print > file }", "While inside a certificate block, writes each line to the current file."],
                    ["/-----END CERTIFICATE-----/ { close(file) }", "At the end of a block, closes the file."],
                    ["&& ls -lh certificates/", "Then lists the created files with their sizes."],
                    ['grep -c "BEGIN CERTIFICATE"', "Counts how many certificates were found in the capture."],
                ],
                "requires": ["evidence/step1-sclient.txt"],
                "requiresNote": "Run step 1.3 first — this step splits the chain captured from the live server.",
                "note": "cert-0.pem is the server certificate; higher indices are intermediates closer to the root.",
            },
            {
                "id": "2.2",
                "label": "Subject and issuer of each certificate",
                "cmd": 'for cert in certificates/cert-*.pem; do echo "========================================"; echo "FILE: $cert"; openssl x509 -in "$cert" -noout -subject -issuer; done 2>&1 | tee evidence/step2-subject-issuer.txt',
                "breakdown": [
                    ["for cert in certificates/cert-*.pem; do ... done", "Repeats the inspection for every extracted certificate file."],
                    ["openssl x509", "Tool for reading and displaying X.509 certificate files."],
                    ['-in "$cert"', "The certificate file to read this iteration."],
                    ["-noout", "Does not print the PEM text itself."],
                    ["-subject", "Prints who the certificate belongs to."],
                    ["-issuer", "Prints who signed the certificate."],
                    ["2>&1 | tee evidence/step2-subject-issuer.txt", "Merges output and saves it to the evidence file."],
                ],
                "requires": ["certificates/cert-0.pem"],
                "requiresNote": "No certificates extracted yet — run steps 1.3 and 2.1 first.",
                "note": "Each certificate's subject should match the next certificate's issuer if the chain is contiguous.",
                "evidence": "evidence/step2-subject-issuer.txt",
            },
            {
                "id": "2.3",
                "label": "Validity dates",
                "cmd": 'for cert in certificates/cert-*.pem; do echo "=== $cert ==="; openssl x509 -in "$cert" -noout -dates; done 2>&1 | tee evidence/step2-validity.txt',
                "breakdown": [
                    ["for cert in certificates/cert-*.pem; do ... done", "Repeats for every extracted certificate file."],
                    ["openssl x509 -in \"$cert\" -noout", "Reads the certificate without printing the PEM text."],
                    ["-dates", "Prints notBefore and notAfter — the certificate's valid lifetime."],
                    ["2>&1 | tee evidence/step2-validity.txt", "Merges output and saves it to the evidence file."],
                ],
                "requires": ["certificates/cert-0.pem"],
                "requiresNote": "No certificates extracted yet — run steps 1.3 and 2.1 first.",
                "note": "notBefore and notAfter for every certificate in the chain. An expired link breaks validation.",
                "evidence": "evidence/step2-validity.txt",
            },
            {
                "id": "2.4",
                "label": "Subject Alternative Name (SAN)",
                "cmd": 'for cert in certificates/cert-*.pem; do echo "=== $cert ==="; openssl x509 -in "$cert" -noout -ext subjectAltName; done 2>&1 | tee evidence/step2-san.txt',
                "breakdown": [
                    ["for cert in certificates/cert-*.pem; do ... done", "Repeats for every extracted certificate file."],
                    ["openssl x509 -in \"$cert\" -noout", "Reads the certificate without printing the PEM text."],
                    ["-ext subjectAltName", "Prints the extension listing the DNS names the certificate may serve."],
                    ["2>&1 | tee evidence/step2-san.txt", "Merges output and saves it to the evidence file."],
                ],
                "requires": ["certificates/cert-0.pem"],
                "requiresNote": "No certificates extracted yet — run steps 1.3 and 2.1 first.",
                "note": "SAN holds the DNS names the certificate may serve — modern TLS clients check SAN, not the legacy CN.",
                "evidence": "evidence/step2-san.txt",
            },
            {
                "id": "2.5",
                "label": "Key usage and constraints",
                "cmd": 'for cert in certificates/cert-*.pem; do echo "=== $cert ==="; openssl x509 -in "$cert" -noout -ext basicConstraints -ext keyUsage -ext extendedKeyUsage; done 2>&1 | tee evidence/step2-extensions.txt',
                "breakdown": [
                    ["for cert in certificates/cert-*.pem; do ... done", "Repeats for every extracted certificate file."],
                    ["openssl x509 -in \"$cert\" -noout", "Reads the certificate without printing the PEM text."],
                    ["-ext basicConstraints", "Prints whether the certificate may sign others (CA:TRUE/FALSE)."],
                    ["-ext keyUsage", "Prints what operations the certificate's key may be used for."],
                    ["-ext extendedKeyUsage", "Prints the intended roles, e.g. TLS web server authentication."],
                    ["2>&1 | tee evidence/step2-extensions.txt", "Merges output and saves it to the evidence file."],
                ],
                "requires": ["certificates/cert-0.pem"],
                "requiresNote": "No certificates extracted yet — run steps 1.3 and 2.1 first.",
                "note": "basicConstraints CA:TRUE marks a certificate permitted to sign others — the property at the heart of the eMudhra report.",
                "evidence": "evidence/step2-extensions.txt",
            },
            {
                "id": "2.6",
                "label": "Signature algorithm and public key",
                "cmd": 'for cert in certificates/cert-*.pem; do echo "=== $cert ==="; openssl x509 -in "$cert" -noout -text | grep -E "Signature Algorithm|Public Key Algorithm|Public-Key:|ASN1 OID:"; done 2>&1 | tee evidence/step2-crypto.txt',
                "breakdown": [
                    ["for cert in certificates/cert-*.pem; do ... done", "Repeats for every extracted certificate file."],
                    ["openssl x509 -in \"$cert\" -noout -text", "Prints the full certificate contents."],
                    ['grep -E "Signature Algorithm|..."', "Keeps only the lines about the signature scheme and public key."],
                    ["2>&1 | tee evidence/step2-crypto.txt", "Merges output and saves it to the evidence file."],
                ],
                "requires": ["certificates/cert-0.pem"],
                "requiresNote": "No certificates extracted yet — run steps 1.3 and 2.1 first.",
                "note": "Shows the signature scheme (e.g. sha256WithRSAEncryption) and key type/size for each certificate.",
                "evidence": "evidence/step2-crypto.txt",
            },
            {
                "id": "2.7",
                "label": "SHA-256 fingerprints",
                "cmd": 'for cert in certificates/cert-*.pem; do echo "=== $cert ==="; openssl x509 -in "$cert" -noout -fingerprint -sha256; done 2>&1 | tee evidence/step2-fingerprints.txt',
                "breakdown": [
                    ["for cert in certificates/cert-*.pem; do ... done", "Repeats for every extracted certificate file."],
                    ["openssl x509 -in \"$cert\" -noout", "Reads the certificate without printing the PEM text."],
                    ["-fingerprint -sha256", "Prints the certificate's SHA-256 hash — its unique identifier."],
                    ["2>&1 | tee evidence/step2-fingerprints.txt", "Merges output and saves it to the evidence file."],
                ],
                "requires": ["certificates/cert-0.pem"],
                "requiresNote": "No certificates extracted yet — run steps 1.3 and 2.1 first.",
                "note": "Fingerprints let you compare these certificates against any other report or source later.",
                "evidence": "evidence/step2-fingerprints.txt",
            },
        ],
    },
    {
        "id": "step-3",
        "num": 3,
        "title": "Understand the chain",
        "summary": "Map who signed whom, and check which certificates are allowed to sign.",
        "explain": [
            "The article's example chain: ISRG Root X1 (trust anchor) signs Root YR, which signs the Let's Encrypt YR1 intermediate, which signs the *.badssl.com server certificate. 'Root YR' is named like a root but acts as an intermediate here.",
            "basicConstraints is the decisive extension: only certificates with CA:TRUE may issue other certificates. A server certificate with CA:FALSE must never be used to sign.",
            "This is the chain described in the source material — the live server may present something different today. Step 6 compares the two.",
        ],
        "commands": [
            {
                "id": "3.1",
                "label": "Compact chain summary",
                "cmd": 'for cert in certificates/cert-*.pem; do echo; echo "=== $cert ==="; openssl x509 -in "$cert" -noout -subject -issuer -serial -dates; done 2>&1 | tee evidence/step3-chain.txt',
                "breakdown": [
                    ["for cert in certificates/cert-*.pem; do ... done", "Repeats for every extracted certificate file."],
                    ["openssl x509 -in \"$cert\" -noout", "Reads the certificate without printing the PEM text."],
                    ["-subject / -issuer", "Who the certificate belongs to / who signed it."],
                    ["-serial", "Prints the serial number the issuer assigned to this certificate."],
                    ["-dates", "Prints the valid lifetime (notBefore / notAfter)."],
                    ["2>&1 | tee evidence/step3-chain.txt", "Merges output and saves it to the evidence file."],
                ],
                "requires": ["certificates/cert-0.pem"],
                "requiresNote": "No certificates extracted yet — run steps 1.3 and 2.1 first.",
                "note": "Subject, issuer, serial and dates side by side — the map of the chain in front of you.",
                "evidence": "evidence/step3-chain.txt",
            },
            {
                "id": "3.2",
                "label": "Is cert-1 a CA certificate?",
                "cmd": "openssl x509 -in certificates/cert-1.pem -noout -ext basicConstraints",
                "breakdown": [
                    ["openssl x509 -in certificates/cert-1.pem", "Reads the second certificate in the chain (the first intermediate)."],
                    ["-noout", "Does not print the PEM text itself."],
                    ["-ext basicConstraints", "Prints whether this certificate may sign others — the decisive extension."],
                ],
                "requires": ["certificates/cert-1.pem"],
                "requiresNote": "certificates/cert-1.pem does not exist yet — run steps 1.3 and 2.1 first (the live chain may have fewer than two certificates).",
                "note": "Expect CA:TRUE on intermediates and CA:FALSE (or absent) on the server certificate.",
            },
            {
                "id": "3.3",
                "label": "Full certificate text — cert-1",
                "cmd": "openssl x509 -in certificates/cert-1.pem -noout -text",
                "breakdown": [
                    ["openssl x509 -in certificates/cert-1.pem", "Reads the second certificate in the chain."],
                    ["-noout", "Does not print the PEM text itself."],
                    ["-text", "Prints the complete certificate: every extension, the signature, and the public key."],
                ],
                "requires": ["certificates/cert-1.pem"],
                "requiresNote": "certificates/cert-1.pem does not exist yet — run steps 1.3 and 2.1 first.",
                "note": "The complete ASN.1 dump: extensions, signature, public key. The pager is disabled so output streams into the panel.",
            },
        ],
    },
    {
        "id": "step-4",
        "num": 4,
        "title": "Verify signatures",
        "summary": "Reproduce the article's signature-verification tests with its exact certificate files.",
        "explain": [
            "These tests use the article's own certificate files — kept under certificates/article/, separate from the live evidence. Do not assume the live certificates from Step 2 are identical.",
            "Test 4A trusts the YR1 intermediate directly (-partial_chain lets verification stop at a non-self-signed anchor): the server certificate must validate. This is a deliberately configured test, not proof of browser trust.",
            "Test 4B moves the anchor up to Root YR, supplying YR1 as an untrusted intermediate. If the signatures match the article's example, OpenSSL reports OK.",
            "Neither test checks revocation or hostname, and neither establishes the full path to ISRG Root X1 — that is Step 5.",
        ],
        "commands": [
            {
                "id": "4.0",
                "label": "Identify the article's certificates",
                "cmd": 'for cert in certificates/article/cert-0.pem certificates/article/cert-1.pem certificates/article/cert-2.pem; do echo "=== $cert ==="; openssl x509 -in "$cert" -noout -subject -issuer -fingerprint -sha256; done',
                "breakdown": [
                    ["for cert in certificates/article/cert-0.pem ...", "Loops over the article's three certificate files."],
                    ["openssl x509 -in \"$cert\" -noout", "Reads each certificate without printing the PEM text."],
                    ["-subject / -issuer", "Who the certificate belongs to / who signed it."],
                    ["-fingerprint -sha256", "Prints the certificate's unique SHA-256 identifier."],
                ],
                "requires": [
                    "certificates/article/cert-0.pem",
                    "certificates/article/cert-1.pem",
                    "certificates/article/cert-2.pem",
                ],
                "requiresNote": "Place the article's three test certificates under ~/eMudhra/certificates/article/ as cert-0.pem (server), cert-1.pem (YR1), cert-2.pem (Root YR) — then re-run.",
                "note": "Confirms which certificates the tests will use before any verification runs.",
            },
            {
                "id": "4a",
                "label": "Test 4A — trust YR1 directly",
                "cmd": "openssl verify -trusted certificates/article/cert-1.pem -partial_chain -show_chain certificates/article/cert-0.pem 2>&1 | tee evidence/tls-step4.txt",
                "breakdown": [
                    ["openssl verify", "Verifies whether a certificate chains up to a trusted anchor."],
                    ["-trusted certificates/article/cert-1.pem", "Treats the YR1 intermediate itself as the trust anchor."],
                    ["-partial_chain", "Allows verification to stop at a non-self-signed anchor instead of requiring a root."],
                    ["-show_chain", "Prints the chain that was used for the verdict."],
                    ["certificates/article/cert-0.pem", "The certificate being verified — the server certificate."],
                    ["2>&1 | tee evidence/tls-step4.txt", "Displays the verdict and saves it to the evidence file."],
                ],
                "requires": [
                    "certificates/article/cert-0.pem",
                    "certificates/article/cert-1.pem",
                ],
                "requiresNote": "Requires the article's cert-0.pem and cert-1.pem under ~/eMudhra/certificates/article/ — run 4.0 first.",
                "note": "Expected per the article: 'cert-0.pem: OK', with YR1 terminating the chain as the configured trust anchor.",
                "evidence": "evidence/tls-step4.txt",
            },
            {
                "id": "4b",
                "label": "Test 4B — trust anchor at Root YR",
                "cmd": "openssl verify -trusted certificates/article/cert-2.pem -untrusted certificates/article/cert-1.pem -partial_chain -show_chain certificates/article/cert-0.pem 2>&1 | tee evidence/tls-step4-2.txt",
                "breakdown": [
                    ["openssl verify", "Verifies whether a certificate chains up to a trusted anchor."],
                    ["-trusted certificates/article/cert-2.pem", "Trusts Root YR as the anchor for this test."],
                    ["-untrusted certificates/article/cert-1.pem", "Supplies YR1 as a helper intermediate without trusting it."],
                    ["-partial_chain", "Allows the chain to terminate at the configured (non-self-signed) anchor."],
                    ["-show_chain", "Prints the chain that was used for the verdict."],
                    ["certificates/article/cert-0.pem", "The server certificate being verified."],
                    ["2>&1 | tee evidence/tls-step4-2.txt", "Displays the verdict and saves it to the evidence file."],
                ],
                "requires": [
                    "certificates/article/cert-0.pem",
                    "certificates/article/cert-1.pem",
                    "certificates/article/cert-2.pem",
                ],
                "requiresNote": "Requires the article's cert-0.pem, cert-1.pem and cert-2.pem under ~/eMudhra/certificates/article/ — run 4.0 first.",
                "note": "Expected per the article: 'cert-0.pem: OK' — server cert, YR1 untrusted intermediate, Root YR as anchor.",
                "evidence": "evidence/tls-step4-2.txt",
            },
        ],
    },
    {
        "id": "step-5",
        "num": 5,
        "title": "Verify full trust path",
        "summary": "Test the complete path from the server certificate to ISRG Root X1.",
        "explain": [
            "The article describes this as a further test; it does not establish the outcome of a completed verification. The root and intermediates must come from a reliable CA source and be fingerprint-checked before use.",
            "Unlike 4A/4B, this runs without -partial_chain: verification must reach a self-signed root present in the supplied CAfile.",
            "If this fails, do not conclude the reported vulnerability exists. Investigate the specific error — file mix-ups, chain order, dates, or verification settings are all more likely explanations.",
        ],
        "commands": [
            {
                "id": "5.1",
                "label": "Check ISRG Root X1 identity",
                "cmd": "openssl x509 -in certificates/article/isrg-root-x1.pem -noout -subject -issuer -fingerprint -sha256",
                "breakdown": [
                    ["openssl x509 -in certificates/article/isrg-root-x1.pem", "Reads the ISRG Root X1 certificate obtained from the CA's official source."],
                    ["-noout", "Does not print the PEM text itself."],
                    ["-subject / -issuer", "The root's identity — a root is self-signed, so subject and issuer match."],
                    ["-fingerprint -sha256", "Prints the fingerprint to compare against the value the CA publishes."],
                ],
                "requires": ["certificates/article/isrg-root-x1.pem"],
                "requiresNote": "Obtain ISRG Root X1 from letsencrypt.org and save it as ~/eMudhra/certificates/article/isrg-root-x1.pem, then re-run.",
                "note": "The fingerprint must match the value published by the CA before the root is used as an anchor.",
            },
            {
                "id": "5.2",
                "label": "Verify full path to ISRG Root X1",
                "cmd": 'cat certificates/article/cert-1.pem certificates/article/cert-2.pem > certificates/article/intermediates.pem && openssl verify -CAfile certificates/article/isrg-root-x1.pem -untrusted certificates/article/intermediates.pem -show_chain certificates/article/cert-0.pem 2>&1 | tee evidence/tls-step5-full-chain.txt',
                "breakdown": [
                    ["cat cert-1.pem cert-2.pem > intermediates.pem", "Combines the two intermediate certificates into one file."],
                    ["openssl verify", "Verifies whether a certificate chains up to a trusted anchor."],
                    ["-CAfile certificates/article/isrg-root-x1.pem", "The trust store for this run: ISRG Root X1."],
                    ["-untrusted certificates/article/intermediates.pem", "Uses the combined intermediates to build the path, without trusting them."],
                    ["-show_chain", "Prints the full verified path."],
                    ["certificates/article/cert-0.pem", "The server certificate being verified."],
                    ["no -partial_chain", "Verification must reach the self-signed root in the CAfile — it may not stop early."],
                ],
                "requires": [
                    "certificates/article/cert-0.pem",
                    "certificates/article/cert-1.pem",
                    "certificates/article/cert-2.pem",
                    "certificates/article/isrg-root-x1.pem",
                ],
                "requiresNote": "Requires all four article files including isrg-root-x1.pem — run 4.0 and 5.1 first.",
                "note": "No -partial_chain here: the chain must terminate at the self-signed ISRG Root X1 in the CAfile.",
                "evidence": "evidence/tls-step5-full-chain.txt",
            },
        ],
    },
    {
        "id": "step-6",
        "num": 6,
        "title": "Compare certificates",
        "summary": "Compare the live server's certificate against the article's copy.",
        "explain": [
            "Keeping the live observation separate from the historical test is what makes the comparison meaningful.",
            "If the fingerprints differ, the certificates are not identical: the live server may have rotated certificates, or the article may document a different point in time. Either way, the article's tests say nothing about the chain served today.",
        ],
        "commands": [
            {
                "id": "6.1",
                "label": "Live server certificate fingerprint",
                "cmd": "openssl s_client -connect sha256.badssl.com:443 -servername sha256.badssl.com -showcerts </dev/null 2>/dev/null | openssl x509 -noout -fingerprint -sha256 -subject -issuer",
                "breakdown": [
                    ["openssl s_client -connect ... -showcerts", "Connects to the live server and prints the certificates it presents."],
                    ["</dev/null 2>/dev/null", "Discards the TLS log — only the certificate matters here."],
                    ["| openssl x509", "Extracts the first certificate from the connection."],
                    ["-noout -fingerprint -sha256 -subject -issuer", "Prints the live server certificate's identity and unique identifier."],
                ],
                "note": "Reads the first certificate the live server presents — the server certificate itself.",
            },
            {
                "id": "6.2",
                "label": "Article server certificate fingerprint",
                "cmd": "openssl x509 -in certificates/article/cert-0.pem -noout -fingerprint -sha256 -subject -issuer",
                "breakdown": [
                    ["openssl x509 -in certificates/article/cert-0.pem", "Reads the article's copy of the server certificate."],
                    ["-noout", "Does not print the PEM text itself."],
                    ["-fingerprint -sha256 -subject -issuer", "Prints identity and SHA-256 identifier for comparison with the live one."],
                ],
                "requires": ["certificates/article/cert-0.pem"],
                "requiresNote": "Requires the article's cert-0.pem under ~/eMudhra/certificates/article/ — run 4.0 first.",
                "note": "Compare this fingerprint line-by-line against 6.1. Equal fingerprints mean the same certificate.",
            },
        ],
    },
    {
        "id": "step-7",
        "num": 7,
        "title": "Generate report",
        "summary": "Assemble the evidence bundle and write the final investigation report.",
        "explain": [
            "The report aggregates the dated environment record, the live TLS verification, the article tests 4A/4B, and the full-chain test into one timestamped file: ~/eMudhra/reports/investigation-summary.txt.",
            "A certificate chain's validity depends on signatures, intermediates, and a trust anchor. A reported CA private-key compromise is a separate claim that requires incident-specific evidence — these commands investigate certificate trust; they do not retrieve private keys or independently prove the reported compromise.",
        ],
        "commands": [
            {
                "id": "7.1",
                "label": "List captured evidence",
                "cmd": "find evidence reports -type f -maxdepth 2 -print | sort",
                "breakdown": [
                    ["find evidence reports", "Searches the evidence and reports folders."],
                    ["-type f", "Lists only files, not folders."],
                    ["-maxdepth 2", "Looks at most two levels deep."],
                    ["-print | sort", "Prints the paths in alphabetical order."],
                ],
                "requires": ["evidence"],
                "requiresNote": "Nothing captured yet — run the earlier steps first.",
                "note": "Everything that will feed the report. The per-run logs under evidence/runs/ hold full output, exit codes and timestamps.",
            },
            {
                "id": "7.2",
                "label": "Build investigation summary",
                "cmd": """{
  echo "eMudhra investigation summary"
  echo "Generated: $(date -u)"
  echo
  echo "Environment:"
  cat evidence/environment.txt 2>/dev/null || echo "environment record missing (step 0.3 not run)"
  echo
  echo "Live TLS verification:"
  cat evidence/step1-verify.txt 2>/dev/null || echo "live verification not run (step 1.4)"
  echo
  echo "Article verification test 4A:"
  cat evidence/tls-step4.txt 2>/dev/null || echo "test 4A not run"
  echo
  echo "Article verification test 4B:"
  cat evidence/tls-step4-2.txt 2>/dev/null || echo "test 4B not run"
  echo
  echo "Full-chain test:"
  cat evidence/tls-step5-full-chain.txt 2>/dev/null || echo "Full-chain test has not been run."
} > reports/investigation-summary.txt && echo "written: reports/investigation-summary.txt\"""",
                "breakdown": [
                    ["{ ... } > reports/investigation-summary.txt", "Groups the report sections and writes them all into the report file."],
                    ['echo "..."', "Writes a section heading."],
                    ["$(date -u)", "Inserts the generation timestamp."],
                    ["cat evidence/....txt", "Includes the content of that evidence file."],
                    ['2>/dev/null || echo "..."', "If the evidence file is missing, prints a placeholder note instead of an error."],
                    ['&& echo "written: ..."', "Confirms the report path once writing finished."],
                ],
                "requires": ["evidence"],
                "requiresNote": "Nothing captured yet — run the earlier steps first.",
                "note": "Assembles reports/investigation-summary.txt from every evidence file captured so far.",
                "evidence": "reports/investigation-summary.txt",
            },
            {
                "id": "7.3",
                "label": "Read the report",
                "cmd": "cat reports/investigation-summary.txt",
                "breakdown": [
                    ["cat reports/investigation-summary.txt", "Prints the finished report so you can read it in the panel."],
                ],
                "requires": ["reports/investigation-summary.txt"],
                "requiresNote": "Run 7.2 first — the report has not been generated yet.",
                "note": "The final artifact, ready to walk through on camera.",
            },
        ],
    },
]

INDEX = {(s["id"], c["id"]): (s, c) for s in STEPS for c in s["commands"]}
