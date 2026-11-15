#!/bin/bash
# A Linux AppImage built from this checkout, uncommitted changes included, to test a change before it is released.
# It is the builder image: it carries the changed sources, builds the Vulkan back end here, and builds the game from
# the user's own dump when asked (no game data goes into the image or the repository).
#
#   scripts/linux/test_appimage.sh                                  -> build-linux/Hueshot-test-<sha>[-dirty]-x86_64.AppImage
#   scripts/linux/test_appimage.sh --update <game folder>           build the image, then build that folder again with it
#   scripts/linux/test_appimage.sh --game <nup or dump folder> --out <game folder>
#   scripts/linux/test_appimage.sh --update <game folder> --play    ... and start the game
#   scripts/linux/test_appimage.sh --play <game folder>             build the image, then start that folder
#
# The image is built in a container (scripts/linux/docker.sh) when Docker or Podman is available and build-linux/deps
# is missing, as docs/development.md recommends on a distribution other than the AppImage's Ubuntu 22.04. Otherwise it
# builds with build-linux/deps on this PC; scripts/linux/deps.sh fetches them when they are missing.
#
# Env: HUESHOT_DOCKER=1|0 (force a container or the host), DOCKER=podman/docker, JOBS, HUESHOT_JOBS,
# HUESHOT_VERSION, HUESHOT_UPDATE_INFO (the image's update information, if not the latest release).
set -euo pipefail
cd "$(dirname "$0")/../.."
ROOT=$PWD

usage() {
    sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'
}

UPDATE=
GAME=
OUT=
PLAY=
PLAY_FOLDER=
while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --update) [ $# -ge 2 ] || { echo "--update needs a game folder" >&2; exit 2; }; UPDATE=$2; shift 2 ;;
        --game) [ $# -ge 2 ] || { echo "--game needs a .nup file or a folder with romfs and exefs" >&2; exit 2; }; GAME=$2; shift 2 ;;
        --out) [ $# -ge 2 ] || { echo "--out needs a folder" >&2; exit 2; }; OUT=$2; shift 2 ;;
        --play)
            PLAY=1
            if [ $# -ge 2 ] && [ "${2#-}" = "$2" ]; then PLAY_FOLDER=$2; shift 2; else shift; fi ;;
        *) echo "unknown argument: $1 (--help for the usage)" >&2; exit 2 ;;
    esac
done
[ -z "$GAME" ] || [ -n "$OUT" ] || { echo "--game needs --out" >&2; exit 2; }
[ -z "$OUT" ] || [ -n "$GAME" ] || { echo "--out needs --game" >&2; exit 2; }
[ -z "$UPDATE" ] || [ -z "$GAME" ] || { echo "choose --update or --game/--out, not both" >&2; exit 2; }
if [ -n "$PLAY_FOLDER" ] && { [ -n "$UPDATE" ] || [ -n "$OUT" ]; }; then
    echo "--play <folder> cannot be combined with --game/--out or --update" >&2; exit 2
fi
[ -z "$PLAY" ] || [ -n "$UPDATE$OUT$PLAY_FOLDER" ] || { echo "--play needs the folder to start" >&2; exit 2; }

# A version of its own: it names the image, and an updater never mistakes a test image for a release.
if git rev-parse --git-dir >/dev/null 2>&1; then
    DIRTY=
    if git status --porcelain | grep -q .; then DIRTY=-dirty; fi
    VERSION=${HUESHOT_VERSION:-test-$(git rev-parse --short HEAD)$DIRTY}
else
    VERSION=${HUESHOT_VERSION:-test-$(date +%Y%m%d-%H%M%S)}
fi

engine=
if [ "${HUESHOT_DOCKER:-auto}" != 0 ]; then
    for e in "${DOCKER:-}" docker podman; do
        if [ -n "$e" ] && command -v "$e" >/dev/null 2>&1; then engine=$e; break; fi
    done
fi
container=
if [ "${HUESHOT_DOCKER:-auto}" = 1 ]; then
    [ -n "$engine" ] || { echo "HUESHOT_DOCKER=1 but Docker/Podman was not found" >&2; exit 1; }
    container=1
elif [ "${HUESHOT_DOCKER:-auto}" = auto ]; then
    [ -n "$engine" ] && [ ! -x build-linux/deps/python/bin/python3 ] && container=1
fi

echo "test image: $VERSION"
if [ -n "$container" ]; then
    echo "building in $engine (scripts/linux/docker.sh): first run fetches and builds the AppImage dependencies"
    DOCKER=$engine HUESHOT_VERSION=$VERSION scripts/linux/docker.sh
else
    if [ ! -x build-linux/deps/python/bin/python3 ]; then
        echo "building the dependencies (scripts/linux/deps.sh): this is the long first run"
        scripts/linux/deps.sh
    fi
    HUESHOT_VERSION=$VERSION scripts/linux/appimage.sh
fi

IMAGE=$ROOT/build-linux/Hueshot-$VERSION-x86_64.AppImage
[ -x "$IMAGE" ] || { echo "the image was not made: $IMAGE" >&2; exit 1; }
echo "image: $IMAGE"

# AppImage needs FUSE on some systems; extract-and-run is the same image without it.
run_image() { APPIMAGE_EXTRACT_AND_RUN=1 "$IMAGE" "$@"; }

if [ -n "$UPDATE" ]; then
    echo "rebuilding $UPDATE with the test image"
    run_image --cli --update "$UPDATE"
elif [ -n "$GAME" ]; then
    echo "building $OUT with the test image"
    run_image --cli --game "$GAME" --out "$OUT"
fi

if [ -n "$PLAY" ]; then
    if [ -n "$PLAY_FOLDER" ]; then exec env APPIMAGE_EXTRACT_AND_RUN=1 "$IMAGE" --play "$PLAY_FOLDER"; fi
    if [ -n "$UPDATE" ]; then exec env APPIMAGE_EXTRACT_AND_RUN=1 "$IMAGE" --play "$UPDATE"; fi
    exec env APPIMAGE_EXTRACT_AND_RUN=1 "$IMAGE" --play "$OUT"
fi
