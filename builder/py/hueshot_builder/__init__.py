"""Hueshot Builder, in Python: the same window as the WPF builder (builder/HueshotBuilder), run by python.org's own python.exe and
Qt's DLLs (both signed by their makers), with no executable of Hueshot's own to download. It also does what the setup exe did
(builder/setup/setup.c): it reads a release's hueshot-setup.txt, downloads the parts it names, checks each one's SHA-256 and
unpacks them into %LOCALAPPDATA%\\HueshotBuilder\\versions\\<tag>."""
APP_ID = "Aismor.Hueshot.Builder"   # (Windows' AppUserModelID: the taskbar groups and shows the window as Hueshot, not Python)
REPO = "aismor/hueshot"
