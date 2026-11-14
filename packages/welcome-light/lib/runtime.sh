#!/bin/bash
# Bash 3.2. The SDK ledger owns restoration; never force lights to Off.
api() {
    local method=$1 path=$2
    shift 2
    curl --silent --show-error --fail --connect-timeout 1 --max-time 2 \
        --unix-socket "$CSDK_API_SOCKET" \
        -H "Authorization: Bearer $CSDK_TOKEN" -H 'Content-Type: application/json' \
        -X "$method" "http://csdk/v1$path" "$@"
}
status() {
    # Messages are fixed source strings, never vehicle or user input.
    api PUT /status --data-binary "{\"state\":\"$1\",\"reason\":\"$2\"}" >/dev/null || :
}
setting() {
    local value
    value=$(cat "$CSDK_SETTINGS/$1" 2>/dev/null) || value=$2
    printf '%s' "$value"
}
release() {
    # Always attempt release, including after a timed-out PUT whose result is unknown.
    if api DELETE /dv/GUI_halloweenLightSwitchRequest >/dev/null; then
        active=0
        return 0
    fi
    return 1
}
reset_state() { armed=0; active=0; deadline=0; last_lock=unknown; cooldown=0; }
step() {
    local now=$1 enabled=$2 duration=$3 gear=$4 locked=$5 present=$6
    case "$duration" in 5|10|15|20|30) ;; *) duration=15 ;; esac
    # Missing telemetry or disabling the package releases the override immediately.
    if [ "$enabled" != true ] || [ "$gear" != P ] || [ "$present" != false ] || \
       { [ "$locked" != true ] && [ "$locked" != false ]; }; then
        armed=0; last_lock=unknown
        if [ "$active" = 1 ]; then release || return 1; fi
        return 0
    fi
    if [ "$active" = 1 ]; then
        if [ "$locked" = true ] || [ "$now" -ge "$deadline" ]; then
            release || return 1
        fi
    fi
    # Require a locked baseline in this process; startup-unlocked never fires.
    if [ "$locked" = true ] && [ "$active" = 0 ] && [ "$now" -ge "$cooldown" ]; then
        armed=1
    fi
    if [ "$locked" = false ] && [ "$last_lock" = true ] && [ "$armed" = 1 ]; then
        armed=0
        # This is an experimental firmware request. A successful HTTP response
        # proves only the SDK write, never physical lamp operation.
        active=1; deadline=$((now + duration)); cooldown=$((now + duration + 30))
        if ! api PUT /dv/GUI_halloweenLightSwitchRequest \
            --data-binary '{"value":"ParkingLights","hold":false}' >/dev/null; then
            release || return 1
            return 1
        fi
    fi
    last_lock=$locked
}
