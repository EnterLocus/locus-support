# Capturing product screenshots

The website uses five 16:9 master captures. Five is enough to explain the
current product without repeating the same state:

1. `virtual-space-desk-wide` — the wide hero frame inside a Virtual Space, with
   the desk edge and a browser window visible;
2. `virtual-space` — a second authored Room composition;
3. `room-portal` — the deterministic surface chooser;
4. `room-portal-open` — the deterministic opened-surface state;
5. `place-library` — installed Place packages.

These captures can be repeated automatically after a Debug build has been
installed on a visionOS simulator. Set `SIMULATOR_ID` to an already selected
simulator, and always use the development bundle identity. Each launch must
terminate the previous process so the new launch arguments are read.

```sh
xcrun simctl launch --terminate-running-process "$SIMULATOR_ID" \
  com.enterlocus.locus.development \
  --auto-scene experience.horizon-atelier-clarens-midday \
  --experience-mode virtual-space --simulator-head-pose \
  --safe-head-debug inside --workspace-windows
sleep 12
xcrun simctl io "$SIMULATOR_ID" screenshot virtual-space-desk-wide.png

xcrun simctl launch --terminate-running-process "$SIMULATOR_ID" \
  com.enterlocus.locus.development \
  --auto-scene experience.atrium-loft-venice-sunset \
  --experience-mode virtual-space --simulator-head-pose \
  --safe-head-debug inside
sleep 12
xcrun simctl io "$SIMULATOR_ID" screenshot virtual-space.png

xcrun simctl launch --terminate-running-process "$SIMULATOR_ID" \
  com.enterlocus.locus.development \
  --auto-scene experience.your-room-clarens-midday \
  --experience-mode room-portal --safe-head-debug inside \
  --room-portal-debug chooser
sleep 10
xcrun simctl io "$SIMULATOR_ID" screenshot room-portal.png

xcrun simctl launch --terminate-running-process "$SIMULATOR_ID" \
  com.enterlocus.locus.development \
  --auto-scene experience.your-room-clarens-midday \
  --experience-mode room-portal --safe-head-debug inside \
  --room-portal-debug fade
sleep 12
xcrun simctl io "$SIMULATOR_ID" screenshot room-portal-open.png

xcrun simctl launch --terminate-running-process "$SIMULATOR_ID" \
  com.enterlocus.locus.development --workspace-page library
sleep 5
xcrun simctl io "$SIMULATOR_ID" screenshot place-library.png

xcrun simctl terminate "$SIMULATOR_ID" \
  com.enterlocus.locus.development
```

Allow the requested interface or immersive state to settle before each
screenshot. Keep the hero master at the simulator's full 16:9 frame; do not
crop it back to the default-room composition. The deterministic fixtures make
framing repeatable, but simulator captures never replace physical Apple Vision
Pro acceptance for tracking, passthrough, occlusion, presence, performance, or
comfort.
