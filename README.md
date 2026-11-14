# Appenetic CS Extensions

Experimental CoilShift Zero SDK packages for Tesla MCU.

**Welcome Light is an unverified prototype, not a validated approach-light feature.**
It is disabled by default. Its current trigger is a locked-to-unlocked transition;
this can include remote unlock and does not detect your phone before unlocking.
Physical DRL and tail-light operation has not been verified.

The supplied 2026.38.5.12 firmware was inspected as data. It contains a temporary
`GUI_halloweenLightSwitchRequest` override with a `ParkingLights` enum. The SDK
writes through QtCarServer's Debug interface. It has not been established that
writing that listener copy reaches QtCarVehicle, so a successful API response
must not be interpreted as working exterior lights. See [validation](docs/validation.md).

## Package behavior

The experimental service requests `ParkingLights` for 5–30 seconds after unlock,
only with a confirmed `P` gear and `VAPI_driverPresent=false`. It requires a locked
baseline after startup, prevents repeated triggers with a cooldown, and releases
its SDK ledger entry on timeout, re-lock, occupancy, leaving Park, missing data,
disable, service restart, termination, and package removal. A failed release
remains pending and is retried on service restart. The SDK restores the previous
value; the package does not force the car's lighting switch to Off.

There is no proximity-range measurement, MCU wake mechanism, DRL-specific request,
or proof that a parking-light request produces the requested lamp combination.
The process must already be running to see a transition; it cannot detect one
that happened while the MCU was asleep. It refuses firmware other than 2026.38.5.12.

## Repository and installation

After this repository has been pushed publicly to `appenetic/cs-extensions`, the
CoilShift repository base URL is:

```
https://raw.githubusercontent.com/appenetic/cs-extensions/main/repository/
```

The index is `repository/index.json`; archives are content-addressed under
`repository/pool/`. Add the base URL in CoilShift, then select
**Welcome Light (experimental)**. Leave the experimental setting disabled until
the control path has been validated. Installation does not prove physical operation.

## Development

```
python3 -m unittest discover -s tests -v
python3 tools/build.py
```

Tests exercise the Bash state machine and curl against a fake local Unix-socket
HTTP server. They do not simulate the body controller or authenticate phone keys.
When available, also use the SDK's proprietary release tools:

```
csdk lint packages/welcome-light
csdk test packages/welcome-light
csdk build packages/welcome-light -o /tmp/welcome-light.csp
```

`tools/build.py` implements the documented tar/index format with Python's standard
library; it is not a replacement for official SDK validation.

Offline QEMU smoke and full-service tests passed inside the supplied firmware
userland using its Bash and curl. A native QtCarServer test also verified
D-Bus write/readback and restoration of the candidate light override. See the validation record for the exact scope and the
`tools/test-target-vm.py` reproduction command. No SDK binaries,
Tesla binaries, firmware dumps, credentials, or vehicle identifiers are included.
