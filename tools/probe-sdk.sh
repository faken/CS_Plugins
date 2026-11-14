#!/bin/bash
# Read-only diagnostic. Run only with the package's existing SDK environment.
# Never prints the bearer token or any environment dump.
set -eu
: "${CSDK_API_SOCKET:?Set the package SDK socket}"
: "${CSDK_TOKEN:?Use the package SDK token}"
probe() {
    local path=$1 output code
    output=$(mktemp "${TMPDIR:-/tmp}/welcome-probe.XXXXXX")
    code=$(curl --silent --show-error --connect-timeout 1 --max-time 3 \
        --unix-socket "$CSDK_API_SOCKET" \
        -H "Authorization: Bearer $CSDK_TOKEN" \
        -o "$output" -w '%{http_code}' "http://csdk/v1$path") || {
        rm -f "$output"
        printf '%s transport-error\n' "$path"
        return
    }
    printf '%s HTTP %s\n' "$path" "$code"
    # These named reads contain state only, no car identity or account data.
    head -c 1024 "$output"
    printf '\n'
    rm -f "$output"
}
probe /vehicle/gear
for name in VAPI_isLocked VAPI_driverPresent GUI_halloweenLightSwitchRequest \
    GUI_approachLightingRequest GUI_daytimeRunningLightsRequest \
    VAPI_lockRequestType VAPI_userPresenceState; do
    probe "/dv/$name"
done
