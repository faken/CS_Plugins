#!/bin/bash
set -eu
. "$CSDK_PACKAGE_DIR/lib/runtime.sh"
status degraded 'Experimental: disabled by default. Unlock detection and light requests require parked-car validation.'
