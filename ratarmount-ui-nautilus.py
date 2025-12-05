from __future__ import annotations
import os
import subprocess
import gi

from gi.repository import GObject

gi.require_version("Nautilus", "4.1")
from gi.repository import Nautilus  # noqa: E402

SUPPORTED_EXTENSIONS = (
    ".7z",
    ".7zip",
    ".a",
    ".apk",
    ".appimage",
    ".ar",
    ".cab",
    ".cpio",
    ".deb",
    ".iso",
    ".jar",
    ".lib",
    ".rar",
    ".rpm",
    ".sqsh",
    ".squashfs",
    ".tar.bz2",
    ".tar.gz",
    ".tar.xz",
    ".tar.zst",
    ".tar",
    ".tbz2",
    ".tgz",
    ".txz",
    ".tzst",
    ".whl",
    ".xar",
    ".zip",
)


def is_archive(file: Nautilus.FileInfo) -> bool:
    name_lower_cased = file.get_name().lower()
    for ext in SUPPORTED_EXTENSIONS:
        if name_lower_cased.endswith(ext):
            return True
    return False


class RatarmountMenuProvider(GObject.GObject, Nautilus.MenuProvider):
    def get_file_items(self, files: list[Nautilus.FileInfo]) -> list[Nautilus.MenuItem]:
        valid_files = [file for file in files if is_archive(file)]

        if not valid_files:
            return []

        item_mount = Nautilus.MenuItem(
            name="RatarmountMenuProvider::Mount",
            label="Mount",
            tip="Mount selected archives with ratarmount",
        )
        item_mount.connect("activate", self.on_mount, valid_files, {"RATARMOUNT_UI_FORCE": "yes"})

        item_mount_ui = Nautilus.MenuItem(
            name="RatarmountMenuProvider::MountUI",
            label="Mount...",
            tip="Open Ratarmount UI with selected archives",
        )
        item_mount_ui.connect("activate", self.on_mount, valid_files)

        return [item_mount, item_mount_ui]

    def on_mount(
        self, menu: Nautilus.Menu, files: list[Nautilus.FileInfo], extra_env: dict[str, str] | None = None
    ) -> None:
        cmd = ["ratarmount-ui"] + [file.get_location().get_path() for file in files]
        cwd = None if len(files) == 0 else files[-1].get_location().get_parent().get_path()
        env = os.environ.copy() | (extra_env or {})
        subprocess.Popen(cmd, cwd=cwd, env=env)


class RatarmountInfoProvider(GObject.GObject, Nautilus.InfoProvider):
    def update_file_info(self, file: Nautilus.FileInfo) -> int:
        if is_archive(file):
            file.add_emblem("package")
        return Nautilus.OperationResult.COMPLETE
