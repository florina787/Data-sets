# Automatic Teams/Zoom meeting detection and privacy mode — implementation plan

**Status (v0.1.1): not implemented.** v0.1.1 ships only a *manual* "Hide VEENA from screen sharing" switch
(Electron `setContentProtection`; Windows 10 2004+ and macOS; not Linux). It does not detect meetings and
does not guarantee invisibility. Nothing below is shipped or verified yet.

## Goal

When the user shares their screen in Microsoft Teams or Zoom, VEENA automatically protects its own window
(and optionally minimizes), shows that it did so, and restores everything when sharing stops. A user-controlled
presentation-privacy feature: VEENA never records, joins or reads meetings because of this feature.

## 1. Signals (what can actually be observed, per platform)

A running Teams/Zoom process is **not** evidence of a meeting. Three separate signals are needed:

| State | Windows | macOS | Linux |
|---|---|---|---|
| Meeting app running | Process list (`ms-teams.exe`, `Zoom.exe`) | Bundle IDs `com.microsoft.teams2`, `us.zoom.xos` | Process names |
| **In a call** | Microphone/camera in use *by that app*: `CapabilityAccessManager\ConsentStore\microphone` registry, `LastUsedTimeStop == 0` (packaged and non-packaged keys) | CoreAudio `kAudioDevicePropertyDeviceIsRunningSomewhere` plus the meeting app frontmost/active; macOS 14+ mic indicator state is not exposed to apps | PipeWire/PulseAudio source-output owned by the meeting app (`pw-dump`) |
| **Sharing** | The meeting app's share toolbar/border window exists (Zoom floating share toolbar; Teams "sharing control bar"/red border); enumerated with `EnumWindows` (title + class) | `CGWindowListCopyWindowInfo` owner + window names of the share toolbar (needs Screen Recording permission for names) | X11: EWMH `_NET_CLIENT_LIST` names. Wayland: an active xdg-desktop-portal ScreenCast session (`pw-dump` shows a screencast node) — app-agnostic |

Window titles and class names change between Teams/Zoom versions, so they live in a **versioned signature
table** (data, not code) that can be updated without changing the detector.

Implementation location: the Python backend already runs per user, so signals use the standard library and
`ctypes` (Windows `user32`/registry, macOS CoreGraphics/CoreAudio) — no new third-party dependency. Linux uses
`pw-dump`/`xprop` when present. Polling every 1–2 s only while the feature is enabled.

## 2. State machine

`idle → app_running → in_call → sharing → in_call → idle`, with 2 s debounce and hysteresis (enter after two
consecutive positive samples, leave after three negative ones) to avoid flicker. Unit-tested on recorded
signal traces (fixtures captured from real sessions, never containing meeting content).

## 3. Actions

On `sharing`:
1. `setContentProtection(true)` where supported (Windows display affinity; macOS window sharing type none).
2. Optional (user setting, off by default): minimize VEENA.
3. A visible local indicator ("Privacy mode on — VEENA is hidden from your screen share") and a global
   shortcut to restore immediately.
4. Conversation, notes and any running analysis are preserved.

On sharing stop: restore the previous protection setting and window state (only what VEENA itself changed).

Never: start microphone/system-audio capture, read meeting windows, or record. Audio features keep their
existing explicit start/stop controls and indicators.

## 4. Platform limits to state honestly in the UI

* **Windows:** display affinity (`WDA_EXCLUDEFROMCAPTURE`) needs Windows 10 2004+; older builds show a black box.
* **macOS:** `NSWindowSharingNone` is honoured by the legacy capture APIs; apps capturing with
  ScreenCaptureKit on macOS 15+ may still include the window. Fallback: auto-minimize, or recommend sharing a
  single window / a different display.
* **Linux:** no capture-exclusion mechanism; on Wayland the portal shows the user what is shared. Fallback:
  auto-minimize and a warning.

## 5. Verification plan (real sessions; cannot run on CI)

Needs: Teams and Zoom test accounts, two participants (second machine or account) to view the shared output,
and a person operating the test.

Matrix: Windows 11 (new Teams, Zoom 6.x), macOS 14 and 15 (Teams, Zoom), Ubuntu 24.04 X11 and Wayland (Zoom).

Scenarios per cell: app open without meeting (must stay idle) · waiting room / lobby · meeting without sharing
· share entire screen · share VEENA's display on a second monitor · share another single window · stop sharing
· end meeting · VEENA restarted mid-share · meeting app update (signature drift).

Evidence per scenario: detected state with timestamps, detection latency, the **viewer-side** recording or
screenshot showing whether VEENA's region is hidden, and confirmation that no audio capture started.

Acceptance: ≥ 95 % correct state detection, 0 false "sharing" activations in the no-meeting scenarios over a
one-week dogfood, viewer-side confirmation of hiding on Windows 11 and macOS 14, documented behaviour on
macOS 15 and Linux.

## 6. Milestones

1. Windows signals prototype + trace recorder (fixtures from real sessions).
2. State machine, settings, indicator, restore shortcut; unit tests on traces.
3. macOS signals and fallbacks.
4. Linux (X11 names, PipeWire screencast detection) with honest fallbacks.
5. Real-session verification matrix; ship as opt-in beta only after it passes.
