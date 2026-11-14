# Validation record and remaining work

Status: prototype; requested pre-unlock welcome lighting is not implemented or
physically verified. Do not describe this release as working on a car.

## Evidence from 2026.38.5.12

Static inspection of the user-supplied firmware established these candidate names:
`GUI_halloweenLightSwitchRequest`, `GUI_approachLightingRequest`,
`GUI_daytimeRunningLightsRequest`, `VAPI_isLocked`, `VAPI_driverPresent`, and
`VAPI_shiftState`. A symbol's existence does not establish API availability.

`LightSwitchRequestNameMap` in QtCarVehicle maps 0 to `Auto`, 1 to `On`,
2 to `ParkingLights`, and 3 to `Off`. This prototype uses the temporary
Halloween switch override rather than the saved user switch setting.

The SDK documentation says `/v1/dv/{name}` delegates to
`com.tesla.Debug.get_data_value` / `set_data_value`. Static inspection indicates
QtCarServer can have listener copies of GUI DataValues, while vehicle control
consumes values published by QtCar. Propagation of this particular Debug write
has not been established. Reading back the written value in QtCarServer is
insufficient evidence.

QtCar exports `com.tesla.CenterDisplayDbus.requestSetDataValueFromReleaseNotes`,
but its implementation in libQtCarGUI (function address 0x257aa70 in this dump)
allows only `GUI_displayVehicleIntro`, `GUI_autoNav`, and
`GUI_enableNavSuggestions`. It is not a generic light setter.
`com.tesla.Automation.invokeObjectMethod` calls QObjectInspector, whose service
entry has configuration gates. Neither route is used by this package.

## Local verification

- Bash 3.2 state-machine cases: startup unlocked, disabled, missing telemetry,
  single unlock, timeout, cooldown, occupancy, re-lock, leaving Park, HTTP-write
  failure, failed restoration retry, and malformed duration.
- Transport test uses the real curl command and a fake Unix HTTP server. It
  explicitly skips if a sandbox denies socket creation. A skip is unverified.
- Archive/index tests verify manifest and archive hashes, executable hooks,
  deterministic rebuilding, and agreement between archive and index manifests.
- Official `csdk` and `csdk-harness` have not been obtained or run in this session.
- An isolated firmware VM boot was performed (details below); no physical car test has been performed.

## Required before promoting a working release

1. Run official SDK lint and harness tests against the package. Check the manifest
   and index with the actual CoilShift daemon.
2. In the offline MCU VM, confirm the three read routes return the documented
   bare text (`P`, `true`, `false`) and assess whether Debug light writes reach
   the publisher and vehicle process. Verify release restores an invalid prior
   correctly, and interrupted-service ledger entries are cleaned up.
3. Establish a readable phone-key approach signal, including unknown/range/auth
   semantics and fresh timestamps. Replace the unlock fallback with an
   authenticated approach edge. Verify sleep and wake behavior.
4. On a parked car, verify the exact front DRL and rear tail-light combination,
   bounded duration, restoration, manual light control, re-lock, occupant entry,
   disable/remove, API loss and process termination. Record firmware, model,
   observations and timing. A VM cannot prove these lamp outputs.
5. If Debug writes do not propagate, implement and validate an appropriate
   supported publisher-side path before enabling the package. Do not mask a
   nonworking path with a keeper loop or report an API write as physical success.

## Offline VM investigation, 2026-11-14

Booted the supplied `ZEN3-2026.38.5.12.ssq` read-only in QEMU using the existing
TeslaMCU project's Alpine kernel and initramfs, `-nic none`, and a RAM overlay.
The serial shell identified x86_64 firmware userland and GNU Bash 3.2.57.
`dbus-daemon`, `dbus-send`, `curl`, and `socat` were present; `python3` was not
found on PATH.

QtCarServer initially failed without its UI library path. With the library path
set it initialized services, but the first launch lacked the system bus. A later
launch did not expose `com.tesla.Debug` in the captured system-bus name list.
The environment was incomplete: no vehicle backend or QtCar publisher was
running. No DataValue write, SDK transport verification, or lamp validation was
completed. The interactive tool session later ceased to exist; the process state
could not be inspected because host process enumeration was denied. Do not infer
successful service shutdown or physical control from these observations.

A static reference scan of `GUI_approachLightingRequest` located publisher/listener
registration and object initialization in QtCar and QtCarVehicle. It did not
establish a callable native approach-lighting implementation. Dynamic name-based
access remains possible, so this is not proof that the DataValue is unused.

`tools/probe-sdk.sh` provides bounded, read-only checks for the specific candidate
DataValues using an existing package SDK environment. It prints HTTP status and
bare response values, never the token. Its output can establish route availability;
it cannot establish signal freshness, authenticated approach semantics, publisher
propagation, or physical lamps.

Remaining required evidence is unchanged: a genuine pre-unlock approach trigger,
a working publisher-side light request for DRLs plus tail lights, official SDK
validation, and a parked-car lamp test. The unlock prototype does not satisfy
these requirements.

## Target-userland smoke test result

Ran `tools/test-target-vm.py` with the supplied firmware, the local TeslaMCU
kernel and initramfs, and QEMU TCG. It injects only a temporary test script into
a copy of the initramfs, uses a read-only firmware drive, disables networking,
and powers the guest off after the test. It does not launch a vehicle backend.

Observed markers on the clean final run:

```
WELCOME_TARGET_TRANSPORT_PASS
WELCOME_TARGET_STATE_PASS
WELCOME_TARGET_DONE
```

The transport check used the firmware's actual Bash, curl and socat. A fake
Unix HTTP server received `GET /v1/vehicle/gear HTTP/1.1` and the expected
nonsecret test authorization header, then returned the expected response body.
The state check executed a locked baseline, an unlock request, and a timed
release using the current runtime code with a recording API stub. Both checks
passed and the guest powered off without a kernel panic. An earlier exploratory
run passed the same checks but failed to power off because that userland lacks
a `poweroff` executable; the final runner uses the isolated guest's SysRq poweroff.

This verifies target-userland compatibility for those checks. It does not
validate the real CoilShift daemon, the actual gear text it returns, D-Bus
publisher propagation, authenticated approach detection, DRLs, or tail lights.
The host Python transport test remains skipped because the host sandbox denies
Unix socket binding; the separate target smoke test supplies narrower transport
evidence for a successful GET, not the host test's HTTP-error case.

Reproduce with paths to your existing local artifacts:

```
python3 tools/test-target-vm.py --kernel /path/to/vmlinuz-virt \
  --initrd /path/to/initramfs.cpio.gz --firmware /path/to/ZEN3-2026.38.5.12.ssq \
  --log /tmp/welcome-target-validation.log
```

## Expanded QEMU validation, 2026-11-14

Two additional suites now run against the supplied read-only firmware image:

```
python3 tools/test-target-vm.py --suite service --kernel /path/to/vmlinuz-virt \
  --initrd /path/to/initramfs.cpio.gz --firmware /path/to/ZEN3-2026.38.5.12.ssq
python3 tools/test-target-vm.py --suite firmware --kernel /path/to/vmlinuz-virt \
  --initrd /path/to/initramfs.cpio.gz --firmware /path/to/ZEN3-2026.38.5.12.ssq
```

The **service** suite executes the current production `service.sh`, `runtime.sh`,
apply and remove hooks without modifying their code, with an HTTP test double
for the SDK daemon. This covers the real settings files, curl transport, service
loop, monotonic clock, and termination traps inside the firmware userland.
Observed pass markers cover timeout, leaving Park, occupancy, disable, unknown
telemetry, TERM cleanup, rejection of HTTP 503, authorization headers, and
repeated apply/remove hooks. PUT requests are checked for the exact
`{"value":"ParkingLights","hold":false}` body. All nine checks passed.
This remains a simulated SDK server and unlock input, not a vehicle backend.

The **firmware** suite starts the actual QtCarServer against an isolated D-Bus
instance in the RAM-only guest. Creating `/tmp/dvaccess` and providing the private
bus allows native service registration, unlike the earlier incomplete launch.
It verified all of the following against the real firmware process:

- `com.tesla.Debug` registers on D-Bus.
- `GUI_halloweenLightSwitchRequest` initially reads `<invalid>`.
- Setting it to `ParkingLights` returns true and reads back `ParkingLights`.
- Setting it back to `<invalid>` returns true and reads back `<invalid>`.
- An invented DataValue name returns false and an empty string.
- `VAPI_isLocked`, `VAPI_driverPresent`, and `VAPI_lockRequestType` return true
  with `<invalid>` in this guest. This proves name availability here, not valid
  live telemetry. In particular, earlier static concerns that lockRequestType
  might be absent are superseded by this direct runtime observation.
- `GUI_approachLightingRequest` already reads `true` in this environment. This
  is a request/setting value, not proof of an authenticated approach event.

Both suites completed and powered the guest off cleanly. The firmware runner
requires the Debug bus name and write/restore readbacks to be present; it fails
if those expectations are missing. It captures diagnostics in the optional
`--log` file. The guest has no vehicle or QtCar publisher backend, and its logs
report missing VIN and CenterDisplay services. No actual CoilShift daemon,
QtCar-to-vehicle propagation, proximity event, or physical lamp output is proven.
The package remains an experimental unlock prototype, disabled by default.
