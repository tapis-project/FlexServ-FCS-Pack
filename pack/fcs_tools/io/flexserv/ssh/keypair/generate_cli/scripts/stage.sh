# Verified Pack script; no host shell fallback.
set -eu
cat > /generate.sh <<'SCRIPT'
#!/bin/bash
set -eu
exec /usr/bin/ssh-keygen -q -t ed25519 -N '' -f "$1"
SCRIPT
printf '%s\n' '{"staged":true}'
