# If something goes wrong

| Problem | What to do |
|---|---|
| Where is the log? | `hueshot_log.txt` in the game folder holds the last run. The four runs before are `hueshot_log.1.txt` (the last) to `.4.txt`. Started from a terminal, the game prints there instead. Every 600 frames it has a `vk: status:` line: the video memory in use of what the driver allows, and DLSS's details while it draws; `vk: over the driver's video-memory allowance` says when the game passed it |
| A place has a wrong texture, or a floor or wall is missing | Look for `hueshot_damaged_files.txt` in the game folder. The build writes it when your game dump is incomplete (about 23.3 GB, a complete one is about 23.8 GB): it lists each damaged game file and the file put in its place. Dump the game again and build from the new dump; the file is then removed |
| Linux Builder Play closed before the game log appeared | After the game exits, check `hueshot_startup.log` in the game folder for up to 64 KiB of startup stderr and its exit status. |
| "Hueshot supports build e0f3ccfa" or "This version isn't supported" | Check that you chose the right game with its update installed |
| The game opens and closes, or the log says "device lost" | Update your graphics driver. On AMD cards there are known crashes (#708, #614) |
| Parts of the picture are missing, or a message says your card has no mesh shader support | The card or its driver has no mesh shaders. Update the driver; older cards are not supported ([#640](https://git.notrexed.dev/Hookshot/Hookshot/commit/07773abd1dc7d79d56a690207e9bc7db7272076d)) |
| AMD: blocky textures, solid rectangles in the sky or unusually dark courtyard surfaces | Try the [RGBA8 texture workaround](#amd-texture-workaround). It uses more graphics memory |
| Linux: the game does not start or the picture is broken | The game needs a Vulkan 1.3 driver with mesh shaders. Check with `vulkaninfo \| grep mesh`: it should list `VK_EXT_mesh_shader`. Update Mesa or the NVIDIA driver |
| Steam Deck: the game freezes and closes in Kokiri Forest or the Great Deku Tree (`gfx_0.0.0 timeout` in `journalctl -k`) | `RX_VK_MESH_NOCULL=2c56dc1006942f74` in `hueshot_env.txt` gets past it with every model drawn (the culling pass that runs for seconds is turned off). `RX_VK_SKIP_CODE=2c56dc1006942f74` also gets past it, but the models those draws make go missing (see the [development guide](development.md#switches-for-testing-and-debugging), #817) |
| "Your antivirus removed part of the build tools" | A false alarm on unsigned programs. Restore the files from Windows Security's Protection history, or add `%LOCALAPPDATA%\HueshotBuilder` to its exclusions, then press **Repair** |
| Stutter the first time you see something | Normal for now: shaders are being prepared. It gets better when you pass through the same place again. You can help remove it for everyone: [send your pipeline list](../readme.md#send-your-pipeline-list) |
| Windows, NVIDIA: stutter every start in places you have seen, after the shaders were prepared | The driver's shader cache is too small to keep them all (the first start builds about 2 GB of pipelines into it). In the NVIDIA Control Panel, Manage 3D settings, set **Shader Cache Size** to **Unlimited** (or 10 GB). On Linux the game raises the driver's limit itself |
| The game is in the wrong language | Change the code in `language.txt` in the game folder. The file lists them all, and an update keeps the one you set there |

If the problem continues, [report it](https://github.com/aismor/hueshot/issues/new/choose) with the version, where
you were in the game, your graphics card, `hueshot_log.txt` and a screenshot or video. Never send game files. The
in-game menu's **Gameplay → Bug report** gathers all of it in one press ([In-game menu](menu-reference.md)).

## Low FPS or stutter

Walk through the same spot twice after shader preparation finishes. Note whether the slowdown clears on the
second pass or lasts until you restart the game. For a slowdown after an update, compare the same spot and
settings on both versions if you still have the earlier build. Turn off **Frame generation** for both runs so the
FPS reflects game frames, and keep the resolution, upscaler and frame rate cap the same.

Attach the log from the slow run and, if available, the one from the earlier build. Say where the FPS dropped and
keep the lines around the drop that show `presents`, `GPU time`, `waits for shaders or pipelines`, `VRAM:` and
`memory heaps`. Compare total and per-heap memory use with the driver's allowances. The texture cache has a
separate budget on the `VRAM:` line.

If the GPU time stays high, a separate run with `RX_VK_PASS_TIMING=1` in `hueshot_env.txt` reports which GPU
passes take the time every 600 presents. Keep the unprofiled log for the FPS comparison since the timing itself
adds work. Remove the switch after collecting the log. The [development guide](development.md#time-and-profiles)
has more switches.

## AMD texture workaround

For these AMD texture artifacts, try keeping decoded ASTC textures as RGBA8 instead of re-encoding them to BC3
(#57, #1006).
Turn on **ASTC as RGBA8** in the menu's Debug tab, under Developer, and restart the game. (`RX_VK_ASTC_RGBA8=1` in
`hueshot_env.txt` does the same, as earlier versions of this readme said; while that line is there the row shows its
value and cannot be changed, so remove the line to choose in the menu.)

This is a workaround for some artifacts, not a general lighting fix. It can substantially increase graphics-memory
use and cause stalls when the card runs out of headroom. To undo it, turn the row off (and remove any `RX_VK_ASTC_RGBA8` line from `hueshot_env.txt`) and restart the game.

`RX_VK_ASTC_BC7=1` keeps those big ASTC textures as BC7 instead of BC3. Both are 8 bits a texel, so the graphics memory
is the same; BC7's mode 6 keeps the colours' gradients and alpha much better, and the textures look cleaner where BC3
shows bands or blocks. Off unless set; `RX_VK_ASTC_RGBA8=1` above still wins when both are set.


## Linux: fast GPU memory imports

For fast GPU memory imports, the game user needs read/write access to `/dev/udmabuf` (the kernel's `udmabuf`
module). Without it, Hueshot falls back to host-pointer imports, which can be much slower on AMD/RADV (NVIDIA's
driver refuses these dma-bufs, so on NVIDIA the game uses host-pointer imports, which are not slow there); permission
errors produce a warning on stderr and in `hueshot_log.txt`. With an NVIDIA card on NVIDIA's own driver you do not
need this access and can ignore that warning: the check runs at the start, before the game knows which GPU it has.
Otherwise, check `ls -l /dev/udmabuf` and `id`.

An administrator can add you to the device's owning group, then you must log out and back in. Only use that group if
access to its other devices is intended: `kvm` also grants virtualization access. For an active local desktop session
using systemd-logind, prefer a device-specific rule in `/etc/udev/rules.d/70-hueshot-udmabuf.rules`:
`SUBSYSTEM=="misc", KERNEL=="udmabuf", TAG+="uaccess"` (before `73-seat-late.rules`). This grants access to the active
local user, not SSH or service users. For those, an administrator can instead create a dedicated `udmabuf` group, add
only the game user, and use `SUBSYSTEM=="misc", KERNEL=="udmabuf", GROUP="udmabuf", MODE="0660"` in that file. Reload
with `sudo udevadm control --reload-rules` and apply with
`sudo udevadm trigger --action=add /sys/class/misc/udmabuf`; restart the session/service after a group change. If the
device is absent, the distribution must provide/load the module first (`sudo modprobe udmabuf`). Do not run the game as
root or make the device world-writable.
