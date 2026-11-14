#!/bin/bash
set -u
. "$CSDK_PACKAGE_DIR/lib/runtime.sh"
reset_state
trap 'release || :; exit 0' TERM INT
trap 'release || :' EXIT
# Clear an interrupted previous run before reading any trigger.
if ! release; then
    status failed 'Could not release a previous light request; retrying on service restart.'
    exit 1
fi
if [ "$CSDK_FIRMWARE" != 2026.38.5.12 ]; then
    status unsupported 'This experimental package has only been statically inspected against 2026.38.5.12.'
    exit 0
fi
status degraded 'Experimental: physical lights and proximity are unverified; disabled by default. Trigger is unlock only.'
while :; do
    enabled=$(setting enabled false)
    duration=$(setting duration 15)
    gear=$(api GET /vehicle/gear) || gear=unknown
    locked=$(api GET /dv/VAPI_isLocked) || locked=unknown
    present=$(api GET /dv/VAPI_driverPresent) || present=unknown
    # /proc/uptime is monotonic and does not jump with clock synchronization.
    read -r uptime rest < /proc/uptime || exit 1
    now=${uptime%%.*}
    if ! step "$now" "$enabled" "$duration" "$gear" "$locked" "$present"; then
        status failed 'Light request or restoration failed; release will be retried on service restart.'
        exit 1
    fi
    sleep 1 & wait $! || :
done
