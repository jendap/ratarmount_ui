#!/usr/bin/env python3

from __future__ import annotations
import sys
import os
import shlex
import signal
import subprocess
from typing import Callable
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio, Gdk, Pango, GObject, GLib  # noqa: E402

try:
    gi.require_version("Nautilus", "4.1")
    from gi.repository import Nautilus  # noqa: E402
except ImportError:
    Nautilus = None


class SourceRow(Gtk.ListBoxRow):
    def __init__(
        self,
        path: str = "",
        parent_window: "RatarmountWindow" | None = None,
        remove_callback: Callable[["SourceRow"], None] | None = None,
    ):
        super().__init__()
        self.parent_window = parent_window
        self.remove_callback = remove_callback

        self.hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.set_child(self.hbox)

        # Drag Handle
        self.drag_handle = Gtk.Image.new_from_icon_name("list-drag-handle-symbolic")
        self.drag_handle.set_cursor(Gdk.Cursor.new_from_name("grab", None))
        self.hbox.append(self.drag_handle)

        drag_source = Gtk.DragSource()
        drag_source.set_actions(Gdk.DragAction.MOVE)
        drag_source.connect("prepare", self.on_drag_prepare)
        drag_source.connect("drag-begin", self.on_drag_begin)
        drag_source.connect("drag-end", self.on_drag_end)
        self.drag_handle.add_controller(drag_source)

        # Path Entry
        self.entry = Gtk.Entry()
        self.entry.set_text(path)
        self.entry.set_hexpand(True)
        self.entry.connect("changed", self.on_changed)
        self.hbox.append(self.entry)

        # Browse Button
        self.browse_btn = Gtk.Button(label="...")
        self.browse_btn.connect("clicked", self.on_browse)
        self.hbox.append(self.browse_btn)

        # Remove Button
        self.remove_btn = Gtk.Button(label="✕")
        self.remove_btn.connect(
            "clicked",
            lambda x: self.remove_callback(self) if self.remove_callback else None,
        )
        self.hbox.append(self.remove_btn)

    def on_drag_prepare(self, source: Gtk.DragSource, x: float, y: float) -> Gdk.ContentProvider:
        return Gdk.ContentProvider.new_for_value("RATARMOUNT_ROW")

    def on_drag_begin(self, source: Gtk.DragSource, drag: Gdk.Drag) -> None:
        if self.parent_window:
            self.parent_window.dragged_row = self
            paintable = Gtk.WidgetPaintable.new(self)
            source.set_icon(paintable, 0, 0)

    def on_drag_end(self, source: Gtk.DragSource, drag: Gdk.Drag, delete_data: bool) -> None:
        if self.parent_window:
            self.parent_window.dragged_row = None

    def on_changed(self, widget: Gtk.Widget) -> None:
        path = self.entry.get_text()
        if path and not os.path.isfile(path):
            self.entry.add_css_class("error")
        else:
            self.entry.remove_css_class("error")

        if self.parent_window:
            self.parent_window.on_source_changed(self)
            self.parent_window.on_ui_change(widget)

    def on_browse(self, widget: Gtk.Widget) -> None:
        dialog = Gtk.FileChooserNative(
            title="Choose Source",
            transient_for=self.get_root(),
            action=Gtk.FileChooserAction.OPEN,
            accept_label="_Open",
            cancel_label="_Cancel",
        )
        dialog.connect("response", self.on_file_response)
        dialog.show()

    def on_file_response(self, dialog: Gtk.FileChooserNative, response: int) -> None:
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            if file:
                self.entry.set_text(file.get_path())
                # on_changed will be called by set_text, which triggers on_source_changed
        dialog.destroy()

    def get_path(self) -> str:
        return self.entry.get_text()


class RatarmountWindow(Gtk.ApplicationWindow):
    def __init__(
        self,
        app: "RatarmountApp",
        initial_args: list[str] | None = None,
        auto_run: bool = False,
    ):
        super().__init__(application=app, title="Ratarmount UI")
        self.set_default_size_from_font()

        self.sources: list[SourceRow] = []
        self.extra_args: list[str] = []
        self.updating_preview = False
        self.updating_ui = False
        self.dragged_row: SourceRow | None = None
        self.subprocess: subprocess.Popen | None = None
        self.return_code: int | None = None
        self.is_hidden_execution = False

        # Header Bar
        header = Gtk.HeaderBar()
        self.set_titlebar(header)

        # Menu Button
        menu = Gio.Menu()
        menu.append("Help", "win.help")
        menu.append("About", "win.about")

        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_menu_model(menu)
        header.pack_end(menu_button)

        # Actions
        action_help = Gio.SimpleAction.new("help", None)
        action_help.connect("activate", self.on_help)
        self.add_action(action_help)
        action_about = Gio.SimpleAction.new("about", None)
        action_about.connect("activate", self.on_about)
        self.add_action(action_about)

        # Main Stack
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.set_child(self.stack)

        # --- Config Page ---
        vbox_config = self._create_main_vbox()
        self.stack.add_named(vbox_config, "config")

        # Mount Sources
        hbox_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        vbox_config.append(hbox_header)

        hbox_header.append(Gtk.Label(label="Mount Sources:", xalign=0))

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.set_vexpand(True)

        # Drop Target for Reordering
        drop_target = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
        drop_target.connect("drop", self.on_drop)
        drop_target.connect("motion", self.on_drag_motion)
        drop_target.connect("leave", self.on_drag_leave)
        self.listbox.add_controller(drop_target)

        # Scrolled window for listbox
        scrolled_list = Gtk.ScrolledWindow()
        scrolled_list.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_list.set_child(self.listbox)
        scrolled_list.set_min_content_height(200)
        scrolled_list.set_vexpand(True)
        vbox_config.append(scrolled_list)

        # Mount Point
        hbox_mount = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, margin_start=16, margin_end=16)
        vbox_config.append(hbox_mount)

        hbox_mount.append(Gtk.Label(label="Mount Point:", xalign=0, width_chars=16))

        self.mount_entry = Gtk.Entry()
        self.mount_entry.set_placeholder_text("Folder where to mount (optional)")
        self.mount_entry.connect("changed", self.on_ui_change)
        self.mount_entry.set_hexpand(True)
        hbox_mount.append(self.mount_entry)

        btn_browse_mount = Gtk.Button(label="...")
        btn_browse_mount.connect("clicked", self.on_browse_mount)
        hbox_mount.append(btn_browse_mount)

        vbox_config.append(Gtk.Separator())

        # Expander for Advanced Options
        expander = Gtk.Expander(label="Advanced")
        vbox_config.append(expander)

        vbox_advanced = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_start=16, margin_end=16)
        expander.set_child(vbox_advanced)

        # Scrollable Options Container
        scrolled_options = Gtk.ScrolledWindow()
        scrolled_options.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_options.set_min_content_height(160)
        vbox_advanced.append(scrolled_options)

        vbox_options = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        scrolled_options.set_child(vbox_options)

        # Password Option
        hbox_password = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        vbox_options.append(hbox_password)

        hbox_password.append(Gtk.Label(label="Password:", xalign=0, width_chars=16))

        self.entry_password = Gtk.Entry()
        self.entry_password.set_placeholder_text("Archive password (optional)")
        self.entry_password.set_visibility(False)
        self.entry_password.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self.entry_password.set_hexpand(True)
        self.entry_password.connect("changed", self.on_ui_change)
        hbox_password.append(self.entry_password)

        # Recursive Options
        hbox_recursive = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        vbox_options.append(hbox_recursive)

        hbox_recursive.append(Gtk.Label(label="Recursive:", xalign=0, width_chars=16))

        self.check_recursive = Gtk.CheckButton(label="Recursive (-r)")
        self.check_recursive.connect("toggled", self.on_recursive_toggled)
        hbox_recursive.append(self.check_recursive)

        self.lbl_depth = Gtk.Label(label="Depth:")
        hbox_recursive.append(self.lbl_depth)
        self.spin_depth = Gtk.SpinButton.new_with_range(0, 100, 1)
        self.spin_depth.set_value(0)
        self.spin_depth.set_tooltip_text("Depth of recursive mount (0 means unlimited)")
        self.spin_depth.connect("value-changed", self.on_ui_change)
        hbox_recursive.append(self.spin_depth)

        self.check_lazy = Gtk.CheckButton(label="Lazy (-l)")
        self.check_lazy.connect("toggled", self.on_ui_change)
        hbox_recursive.append(self.check_lazy)

        self.check_strip = Gtk.CheckButton(label="Strip Extension (-s)")
        self.check_strip.connect("toggled", self.on_ui_change)
        hbox_recursive.append(self.check_strip)

        # Write Overlay
        hbox_overlay = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        vbox_options.append(hbox_overlay)

        hbox_overlay.append(Gtk.Label(label="Write Overlay:", xalign=0, width_chars=16))

        self.entry_write_overlay = Gtk.Entry()
        self.entry_write_overlay.set_placeholder_text("Path to overlay folder (optional)")
        self.entry_write_overlay.set_hexpand(True)
        self.entry_write_overlay.connect("changed", self.on_ui_change)
        hbox_overlay.append(self.entry_write_overlay)

        btn_browse_overlay = Gtk.Button(label="...")
        btn_browse_overlay.connect("clicked", self.on_browse_overlay)
        hbox_overlay.append(btn_browse_overlay)

        # Union Mount
        hbox_union = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        vbox_options.append(hbox_union)

        hbox_union.append(Gtk.Label(label="Mount Type:", xalign=0, width_chars=16))

        self.check_union = Gtk.CheckButton(label="Union Mount")
        self.check_union.set_active(True)  # Default True
        self.check_union.set_tooltip_text("Uncheck to add --disable-union-mount")
        self.check_union.connect("toggled", self.on_ui_change)
        hbox_union.append(self.check_union)

        # Command Preview
        vbox_advanced.append(Gtk.Separator())

        self.preview_text = Gtk.TextView()
        self.preview_text.set_editable(True)
        self.preview_text.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.preview_text.add_css_class("monospace")
        self.preview_text.get_buffer().connect("changed", self.on_preview_changed)

        scrolled_preview = Gtk.ScrolledWindow()
        scrolled_preview.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_preview.set_child(self.preview_text)
        scrolled_preview.set_min_content_height(60)
        vbox_advanced.append(scrolled_preview)

        # Action Buttons
        hbox_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox_actions.set_halign(Gtk.Align.END)
        vbox_config.append(hbox_actions)

        btn_cancel = Gtk.Button(label="Cancel")
        btn_cancel.connect("clicked", lambda *args: self.on_cancel())
        hbox_actions.append(btn_cancel)

        btn_mount = Gtk.Button(label="Mount")
        btn_mount.add_css_class("suggested-action")
        btn_mount.connect("clicked", lambda *args: self.on_mount())
        hbox_actions.append(btn_mount)

        # --- Execution Page ---
        vbox_exec = self._create_main_vbox()
        self.stack.add_named(vbox_exec, "execution")

        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.log_view.add_css_class("monospace")

        scrolled_log = Gtk.ScrolledWindow()
        scrolled_log.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_log.set_child(self.log_view)
        scrolled_log.set_vexpand(True)
        vbox_exec.append(scrolled_log)

        hbox_exec_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox_exec_actions.set_halign(Gtk.Align.END)
        vbox_exec.append(hbox_exec_actions)

        self.btn_abort = Gtk.Button(label="Abort")
        self.btn_abort.add_css_class("destructive-action")
        self.btn_abort.connect("clicked", self.on_abort)
        hbox_exec_actions.append(self.btn_abort)

        btn_close = Gtk.Button(label="Close")
        btn_close.connect("clicked", self.on_close_clicked)
        hbox_exec_actions.append(btn_close)

        # Shortcuts
        shortcuts = Gtk.ShortcutController()
        self.add_controller(shortcuts)
        shortcuts.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("Escape"),
                Gtk.CallbackAction.new(lambda *args: self.on_cancel()),
            )
        )
        shortcuts.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("Return"),
                Gtk.CallbackAction.new(lambda *args: self.on_mount()),
            )
        )

        self.update_ui_from_args(initial_args if initial_args is not None else [])

        if auto_run:
            self.is_hidden_execution = True
            # Construct command from initial_args
            cmd = ["ratarmount"] + (initial_args if initial_args else [])
            self.start_execution(cmd)
            GLib.timeout_add(1000, self.check_show_window)

    def _create_main_vbox(self) -> Gtk.Box:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_top(20)
        vbox.set_margin_bottom(20)
        vbox.set_margin_start(20)
        vbox.set_margin_end(20)
        return vbox

    def on_recursive_toggled(self, widget: Gtk.Widget) -> None:
        active = self.check_recursive.get_active()
        self.lbl_depth.set_sensitive(active)
        self.spin_depth.set_sensitive(active)
        self.check_lazy.set_sensitive(active)
        self.check_strip.set_sensitive(active)
        self.on_ui_change(widget)

    def on_browse_overlay(self, widget: Gtk.Widget) -> None:
        dialog = Gtk.FileChooserNative(
            title="Choose Overlay Folder",
            transient_for=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            accept_label="_Select",
            cancel_label="_Cancel",
        )
        dialog.connect("response", self.on_overlay_response)
        dialog.show()

    def on_overlay_response(self, dialog: Gtk.FileChooserNative, response: int) -> None:
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            if file:
                self.entry_write_overlay.set_text(file.get_path())
        dialog.destroy()

    def _create_author(self, project: str, author: str, uri: str) -> Gtk.Widget:
        hbox_author = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox_author.append(Gtk.Label(label=f"<b>{project}</b> by {author}", use_markup=True))
        hbox_author.append(Gtk.LinkButton(uri=uri, label=uri))
        return hbox_author

    def _create_cmd_output(self, label: str, cmd: list[str]) -> Gtk.Widget:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.append(Gtk.Label(label=label, xalign=0))

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text_view.add_css_class("monospace")
        scrolled.set_child(text_view)

        try:
            output = subprocess.check_output(cmd, text=True)
            text_view.get_buffer().set_text(output)
        except Exception as e:
            text_view.get_buffer().set_text(f"Failed to run {cmd}: {e}")

        vbox.append(scrolled)
        return vbox

    def on_help(self, *args) -> None:
        help_window = Gtk.Window(transient_for=self)
        help_window.set_title("Ratarmount Help")
        help_window.set_modal(True)
        help_window.set_default_size(640, 480)

        vbox = self._create_main_vbox()
        help_window.set_child(vbox)
        vbox.append(self._create_cmd_output("ratarmount --help", ["ratarmount", "--help"]))

        help_window.present()

    def on_about(self, *args) -> None:
        about_window = Gtk.Window(transient_for=self)
        about_window.set_title("About Ratarmount UI")
        about_window.set_modal(True)
        about_window.set_default_size(640, 480)

        vbox = self._create_main_vbox()
        about_window.set_child(vbox)
        vbox.append(self._create_author("Ratarmount UI", "Jan Prach", "https://github.com/jendap/ratarmount-ui"))
        vbox.append(self._create_author("Ratarmount", "Maximillian Knespel", "https://github.com/mxmlnkn/ratarmount"))
        vbox.append(self._create_cmd_output("Open Source Attributions:", ["ratarmount", "--oss-attributions-short"]))

        about_window.present()

    def on_drag_motion(self, target: Gtk.DropTarget, x: float, y: float) -> Gdk.DragAction:
        row = self.listbox.get_row_at_y(int(y))
        if row:
            self.listbox.drag_highlight_row(row)
        else:
            self.listbox.drag_unhighlight_row()
        return Gdk.DragAction.MOVE

    def on_drag_leave(self, target: Gtk.DropTarget) -> None:
        self.listbox.drag_unhighlight_row()

    def on_drop(self, target: Gtk.DropTarget, value: any, x: float, y: float) -> bool:
        self.listbox.drag_unhighlight_row()

        if not self.dragged_row:
            return False

        target_row = self.listbox.get_row_at_y(int(y))
        if not target_row:
            # Dropped below last item?
            # We can just move to end if dropped in empty space
            target_row = self.sources[-1] if self.sources else None

        if target_row and target_row != self.dragged_row:
            source_idx = self.sources.index(self.dragged_row)
            target_idx = self.sources.index(target_row)

            # Move in list
            self.sources.pop(source_idx)
            self.sources.insert(target_idx, self.dragged_row)

            # Move in UI
            self.listbox.remove(self.dragged_row)
            self.listbox.insert(self.dragged_row, target_idx)

            self.update_preview()
            return True

        return False

    def set_default_size_from_font(self) -> None:
        try:
            ctx = self.get_pango_context()
            metrics = ctx.get_metrics(ctx.get_font_description(), ctx.get_language())
            scale = Pango.SCALE
            w_char = metrics.get_approximate_char_width() / scale
            h_char = (metrics.get_ascent() + metrics.get_descent()) / scale

            # Target ~80x32 characters, but at least 800x600 logical pixels
            width = max(int(w_char * 80), 800)
            height = max(int(h_char * 32), 600)

            self.set_default_size(width, height)
        except Exception:
            self.set_default_size(800, 600)

    def update_ui_from_args(self, args: list[str], from_preview: bool = False) -> None:
        self.updating_ui = True
        try:
            # Reset UI
            while self.sources:
                self.listbox.remove(self.sources.pop())
            self.check_recursive.set_active(False)
            self.lbl_depth.set_sensitive(False)
            self.spin_depth.set_value(0)
            self.check_lazy.set_active(False)
            self.check_strip.set_active(False)
            self.entry_write_overlay.set_text("")
            self.check_union.set_active(True)
            self.entry_password.set_text("")
            self.mount_entry.set_text("")
            self.extra_args = []

            positional = []

            i = 0
            while i < len(args):
                arg = args[i]
                if arg in ("-r", "--recursive"):
                    self.check_recursive.set_active(True)
                elif arg == "--recursion-depth":
                    if i + 1 < len(args):
                        try:
                            self.spin_depth.set_value(int(args[i + 1]))
                            i += 1
                        except ValueError:
                            self.extra_args.append(arg)
                    else:
                        self.extra_args.append(arg)
                elif arg in ("-l", "--lazy"):
                    self.check_lazy.set_active(True)
                elif arg in ("-s", "--strip-recursive-tar-extension"):
                    self.check_strip.set_active(True)
                elif arg == "--write-overlay":
                    if i + 1 < len(args):
                        self.entry_write_overlay.set_text(args[i + 1])
                        i += 1
                    else:
                        self.extra_args.append(arg)
                elif arg == "--password":
                    if i + 1 < len(args):
                        self.entry_password.set_text(args[i + 1])
                        i += 1
                    else:
                        self.extra_args.append(arg)
                elif arg == "--disable-union-mount":
                    self.check_union.set_active(False)
                elif arg.startswith("-"):
                    self.extra_args.append(arg)
                else:
                    positional.append(arg)
                i += 1

            sources_data = []
            mount_point = ""

            if len(positional) >= 2:
                last_arg_path = positional[-1]
                # User rule: The last positional argument should go to 'Mount Point' only if
                # the path does not exists or if it is a directory.
                # Otherwise (exists and is not directory -> file), it should be in Mount Sources.
                if os.path.exists(last_arg_path) and not os.path.isdir(last_arg_path):
                    sources_data = positional
                else:
                    mount_point = last_arg_path
                    sources_data = positional[:-1]
            elif len(positional) == 1:
                sources_data = positional

            for src in sources_data:
                self.add_source_row(src)

            # Ensure there is always one empty row at the end
            self.ensure_empty_row()

            self.mount_entry.set_text(mount_point)
            self.on_recursive_toggled(self.check_recursive)  # Update sensitivity
        finally:
            self.updating_ui = False
            if not from_preview:
                self.update_preview()

    def on_preview_changed(self, widget: Gtk.TextBuffer) -> None:
        if self.updating_preview:
            return

        buffer = self.preview_text.get_buffer()
        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

        try:
            args = shlex.split(text)
        except ValueError:
            return  # Incomplete string

        if args and args[0] == "ratarmount":
            args = args[1:]

        self.update_ui_from_args(args, from_preview=True)

    def ensure_empty_row(self) -> None:
        if not self.sources or self.sources[-1].get_path() != "":
            self.add_source_row("")

    def on_source_changed(self, row: SourceRow) -> None:
        # If the changed row is the last one and it is not empty, add a new empty row
        if row == self.sources[-1] and row.get_path() != "":
            self.add_source_row("")

    def add_source_row(self, path: str) -> None:
        row = SourceRow(path, parent_window=self, remove_callback=self.on_remove_source)
        self.sources.append(row)
        self.listbox.append(row)

    def on_remove_source(self, row: SourceRow) -> None:
        if row in self.sources:
            self.sources.remove(row)
            self.listbox.remove(row)

            # If we removed the last row, or if the list is empty, ensure we have an empty row
            self.ensure_empty_row()

            self.update_preview()

    def on_ui_change(self, widget: Gtk.Widget) -> None:
        # Validate Mount Point
        mount_point = self.mount_entry.get_text()
        if mount_point:
            parent = mount_point
            while parent and not os.path.exists(parent):
                parent = os.path.dirname(parent)

            if parent and (not os.path.isdir(parent) or not os.access(parent, os.W_OK)):
                self.mount_entry.add_css_class("error")
            else:
                self.mount_entry.remove_css_class("error")
        else:
            self.mount_entry.remove_css_class("error")

        # Validate Write Overlay
        overlay = self.entry_write_overlay.get_text()
        if overlay and (not os.path.isdir(overlay) or not os.access(overlay, os.W_OK)):
            self.entry_write_overlay.add_css_class("error")
        else:
            self.entry_write_overlay.remove_css_class("error")

        if not self.updating_ui:
            self.update_preview()

    def on_browse_mount(self, widget: Gtk.Widget) -> None:
        dialog = Gtk.FileChooserNative(
            title="Choose Mount Point",
            transient_for=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            accept_label="_Select",
            cancel_label="_Cancel",
        )
        dialog.connect("response", self.on_mount_response)
        dialog.show()

    def on_mount_response(self, dialog: Gtk.FileChooserNative, response: int) -> None:
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            if file:
                self.mount_entry.set_text(file.get_path())
        dialog.destroy()

    def update_preview(self) -> None:
        if self.updating_ui:
            return

        cmd = ["ratarmount"]

        password = self.entry_password.get_text()
        if password:
            cmd.extend(["--password", password])

        if self.check_recursive.get_active():
            cmd.append("--recursive")
            depth = int(self.spin_depth.get_value())
            if depth > 0:
                cmd.extend(["--recursion-depth", str(depth)])
            if self.check_lazy.get_active():
                cmd.append("--lazy")
            if self.check_strip.get_active():
                cmd.append("--strip-recursive-tar-extension")

        write_overlay = self.entry_write_overlay.get_text()
        if write_overlay:
            cmd.extend(["--write-overlay", write_overlay])

        if not self.check_union.get_active():
            cmd.append("--disable-union-mount")

        cmd.extend(self.extra_args)

        sources_args = []
        for row in self.sources:
            path = row.get_path()
            if path:
                sources_args.append(path)

        cmd.extend(sources_args)

        mount_point = self.mount_entry.get_text()
        if mount_point:
            cmd.append(mount_point)

        self.updating_preview = True
        self.preview_text.get_buffer().set_text(shlex.join(cmd))
        self.updating_preview = False

    def on_mount(self) -> None:
        buffer = self.preview_text.get_buffer()
        cmd_str = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

        try:
            cmd = shlex.split(cmd_str)
        except ValueError:
            # TODO: Show error
            return

        if not cmd:
            return

        self.start_execution(cmd)

    def start_execution(self, cmd: list[str]) -> None:
        # Switch to execution view
        self.stack.set_visible_child_name("execution")
        self.log_view.get_buffer().set_text("")
        self.btn_abort.set_visible(True)

        print(f"Executing: {cmd}")
        try:
            pid, stdin_fd, stdout_fd, stderr_fd = GLib.spawn_async(
                cmd,
                flags=GLib.SpawnFlags.SEARCH_PATH | GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                standard_output=True,
                standard_error=True,
            )
            self.child_pid = pid

            # We don't use stdin, close it
            if stdin_fd is not None:
                os.close(stdin_fd)

            GLib.child_watch_add(GLib.PRIORITY_DEFAULT, pid, self.on_child_exit)

            if stdout_fd is not None:
                GLib.io_add_watch(
                    stdout_fd, GLib.PRIORITY_DEFAULT, GLib.IO_IN | GLib.IO_HUP, self.on_output, sys.stdout
                )

            if stderr_fd is not None:
                GLib.io_add_watch(
                    stderr_fd, GLib.PRIORITY_DEFAULT, GLib.IO_IN | GLib.IO_HUP, self.on_output, sys.stderr
                )

        except Exception as e:
            self.log_view.get_buffer().set_text(f"Error starting command: {e}")
            self.btn_abort.set_visible(False)
            if self.is_hidden_execution:
                self.present()

    def on_output(self, source, condition, stream) -> bool:
        if condition & GLib.IO_IN:
            try:
                chunk = os.read(source, 4096)
                if chunk:
                    text = chunk.decode("utf-8", errors="replace")
                    self._append_log(text)
                    stream.write(text)
                    stream.flush()
                    return True
            except OSError:
                pass

        # EOF or Error, close FD and remove source
        try:
            os.close(source)
        except OSError:
            pass
        return False

    def on_child_exit(self, pid: int, status: int) -> None:
        self.child_pid = None
        self.btn_abort.set_visible(False)

        # Close the pid handle
        GLib.spawn_close_pid(pid)

        # Decode status
        return_code = 0
        if os.WIFEXITED(status):
            return_code = os.WEXITSTATUS(status)
        elif os.WIFSIGNALED(status):
            return_code = -os.WTERMSIG(status)

        self.return_code = return_code

        if return_code == 0:
            sys.exit(0)
        else:
            # Error occurred
            if self.is_hidden_execution:
                self.is_hidden_execution = False
                self.present()
            # Do NOT close, let user see the error

    def check_show_window(self) -> bool:
        if self.child_pid is not None:
            # Still running after timeout, show window
            self.is_hidden_execution = False
            self.present()
        return False

    def _append_log(self, text: str) -> None:
        buffer = self.log_view.get_buffer()
        iter_end = buffer.get_end_iter()
        buffer.insert(iter_end, text)
        # Scroll to end
        adj = self.log_view.get_parent().get_vadjustment()
        if adj:
            adj.set_value(adj.get_upper() - adj.get_page_size())

    def on_abort(self, btn: Gtk.Button) -> None:
        if self.child_pid:
            try:
                os.kill(self.child_pid, signal.SIGINT)
            except OSError:
                pass

    def on_close_clicked(self, btn: Gtk.Button) -> None:
        sys.exit(self.return_code if self.return_code is not None else 0)

    def on_cancel(self) -> None:
        self.on_close_clicked(None)


class RatarmountApp(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="com.github.jendap.ratarmount-ui",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )

    def do_activate(self):
        # This is called when the application is launched without command line arguments
        # or when it's already running and activated again.
        win = self.props.active_window
        if not win:
            win = RatarmountWindow(self)
        win.present()

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> int:
        # This is called when the application is launched with command line arguments.
        # The arguments are passed to the window.
        args = command_line.get_arguments()[1:]  # Skip the program name itself

        force_auto_run = os.environ.get("RATARMOUNT_UI_FORCE") == "yes"

        win = self.props.active_window
        if not win:
            win = RatarmountWindow(self, initial_args=args, auto_run=force_auto_run)
        else:
            win.update_ui_from_args(args)

        if not force_auto_run:
            win.present()

        return 0


if Nautilus is not None:
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
                label="Mount Advanced",
                tip="Open Ratarmount UI with selected archives",
            )
            item_mount_ui.connect("activate", self.on_mount, valid_files)

            return [item_mount, item_mount_ui]

        def on_mount(
            self, menu: Nautilus.Menu, files: list[Nautilus.FileInfo], extra_env: dict[str, str] | None = None
        ) -> None:
            # Spawn this script with files as arguments
            script_path = os.path.abspath(__file__)
            file_paths = [file.get_location().get_path() for file in files]
            cmd = [sys.executable, script_path] + file_paths
            env = os.environ.copy()
            env.update(extra_env or {})
            cwd = None if len(file_paths) == 0 else os.path.dirname(file_paths[-1])
            subprocess.Popen(cmd, env=env, cwd=cwd)

    class RatarmountInfoProvider(GObject.GObject, Nautilus.InfoProvider):
        def update_file_info(self, file: Nautilus.FileInfo) -> int:
            if is_archive(file):
                file.add_emblem("package")
            return Nautilus.OperationResult.COMPLETE


if __name__ == "__main__":
    app = RatarmountApp()
    app.run(sys.argv)  # Pass all arguments to the application
