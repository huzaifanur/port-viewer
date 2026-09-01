"""GTK 4 interface for Port Viewer."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from importlib.resources import files

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from .scanner import PortEntry, ScanError, scan_ports


APP_ID = "io.github.portviewer.PortViewer"


class PortRow(Gtk.Box):
    def __init__(self, entry: PortEntry) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self.add_css_class("port-row")
        self.entry = entry

        port = Gtk.Label(label=str(entry.port), xalign=0)
        port.add_css_class("port-number")
        port.set_size_request(72, -1)

        protocol = Gtk.Label(label=entry.protocol)
        protocol.add_css_class(f"protocol-{entry.protocol.lower()}")
        protocol.add_css_class("protocol-pill")
        protocol.set_size_request(62, -1)
        protocol.set_valign(Gtk.Align.CENTER)

        address_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        address = Gtk.Label(label=entry.address, xalign=0, ellipsize=3)
        address.add_css_class("primary-text")
        state = Gtk.Label(label=entry.state, xalign=0)
        state.add_css_class("secondary-text")
        address_box.append(address)
        address_box.append(state)

        process_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        process = Gtk.Label(label=entry.process or "Process hidden", xalign=0, ellipsize=3)
        process.add_css_class("primary-text")
        if not entry.process:
            process.add_css_class("hidden-process")
        pid = Gtk.Label(
            label=f"PID {entry.pid}" if entry.pid is not None else "Try an admin scan",
            xalign=0,
        )
        pid.add_css_class("secondary-text")
        process_box.append(process)
        process_box.append(pid)

        details = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=20,
            homogeneous=True,
        )
        details.set_hexpand(True)
        details.append(address_box)
        details.append(process_box)

        self.append(port)
        self.append(protocol)
        self.append(details)

        self.set_tooltip_text(
            f"{entry.protocol} port {entry.port} on {entry.address} — {entry.process_label}"
        )


class PortViewerWindow(Adw.ApplicationWindow):
    def __init__(self, application: Gtk.Application) -> None:
        super().__init__(application=application, title="Port Viewer")
        self.set_default_size(760, 620)
        self.set_size_request(560, 420)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="port-scan")
        self._entries: list[PortEntry] = []
        self._scan_generation = 0

        self._build_ui()
        self.connect("close-request", self._on_close)
        GLib.idle_add(self.refresh)

    def _build_ui(self) -> None:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.add_css_class("app-root")

        header = Adw.HeaderBar()
        title = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        title.append(Gtk.Label(label="Port Viewer", css_classes=["title-label"]))
        self.subtitle = Gtk.Label(
            label="Checking occupied ports…",
            css_classes=["subtitle", "dim-label"],
        )
        title.append(self.subtitle)
        header.set_title_widget(title)

        self.admin_button = Gtk.Button(icon_name="changes-prevent-symbolic")
        self.admin_button.set_tooltip_text("Scan as administrator to reveal hidden processes")
        self.admin_button.update_property(
            [Gtk.AccessibleProperty.LABEL], ["Scan as administrator"]
        )
        self.admin_button.connect("clicked", lambda _button: self.refresh(as_admin=True))
        header.pack_start(self.admin_button)

        self.refresh_button = Gtk.Button(icon_name="view-refresh-symbolic")
        self.refresh_button.set_tooltip_text("Refresh ports")
        self.refresh_button.update_property(
            [Gtk.AccessibleProperty.LABEL], ["Refresh ports"]
        )
        self.refresh_button.connect("clicked", lambda _button: self.refresh())
        header.pack_end(self.refresh_button)
        root.append(header)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        toolbar.add_css_class("toolbar")
        self.search = Gtk.SearchEntry(placeholder_text="Filter ports or processes")
        self.search.set_hexpand(True)
        self.search.connect("search-changed", lambda _entry: self._render_entries())
        toolbar.append(self.search)

        self.protocol_filter = Gtk.DropDown.new_from_strings(["All protocols", "TCP", "UDP"])
        self.protocol_filter.set_tooltip_text("Filter by protocol")
        self.protocol_filter.connect("notify::selected", lambda *_args: self._render_entries())
        toolbar.append(self.protocol_filter)
        root.append(toolbar)

        headings = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        headings.add_css_class("column-headings")
        for text, width in (("PORT", 72), ("TYPE", 62)):
            label = Gtk.Label(label=text, xalign=0)
            label.set_size_request(width, -1)
            headings.append(label)
        detail_headings = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=20,
            homogeneous=True,
        )
        detail_headings.set_hexpand(True)
        detail_headings.append(Gtk.Label(label="ADDRESS", xalign=0))
        detail_headings.append(Gtk.Label(label="PROCESS", xalign=0))
        headings.append(detail_headings)
        root.append(headings)

        self.stack = Gtk.Stack()
        self.stack.add_css_class("content-stack")
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        self.spinner = Gtk.Spinner(spinning=True, width_request=36, height_request=36)
        loading = self._status_page(self.spinner, "Scanning open sockets…")
        self.stack.add_named(loading, "loading")

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list_box.add_css_class("ports-list")
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(self.list_box)
        self.stack.add_named(scroller, "list")

        empty_icon = Gtk.Image.new_from_icon_name("network-offline-symbolic")
        empty_icon.set_pixel_size(48)
        self.empty_title = Gtk.Label(label="No matching ports", css_classes=["empty-title"])
        self.empty_detail = Gtk.Label(
            label="Try changing the search or protocol filter.",
            css_classes=["secondary-text"],
        )
        empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        empty_box.set_halign(Gtk.Align.CENTER)
        empty_box.set_valign(Gtk.Align.CENTER)
        empty_box.append(empty_icon)
        empty_box.append(self.empty_title)
        empty_box.append(self.empty_detail)
        self.stack.add_named(empty_box, "empty")

        self.error_label = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        retry = Gtk.Button(label="Try Again", css_classes=["suggested-action"])
        retry.set_halign(Gtk.Align.CENTER)
        retry.connect("clicked", lambda _button: self.refresh())
        error_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        error_box.set_halign(Gtk.Align.CENTER)
        error_box.set_valign(Gtk.Align.CENTER)
        error_icon = Gtk.Image.new_from_icon_name("dialog-error-symbolic")
        error_icon.set_pixel_size(48)
        error_box.append(error_icon)
        error_box.append(self.error_label)
        error_box.append(retry)
        self.stack.add_named(error_box, "error")

        root.append(self.stack)
        self.set_content(root)

    @staticmethod
    def _status_page(widget: Gtk.Widget, text: str) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.append(widget)
        box.append(Gtk.Label(label=text, css_classes=["secondary-text"]))
        return box

    def refresh(self, as_admin: bool = False) -> bool:
        self._scan_generation += 1
        generation = self._scan_generation
        self.stack.set_visible_child_name("loading")
        self.spinner.start()
        self.refresh_button.set_sensitive(False)
        self.admin_button.set_sensitive(False)
        self.subtitle.set_text("Requesting administrator access…" if as_admin else "Scanning…")

        future = self._executor.submit(scan_ports, as_admin)

        def completed(done_future) -> None:
            try:
                entries = done_future.result()
                error = None
            except (ScanError, Exception) as exc:
                entries = []
                error = str(exc)
            GLib.idle_add(self._finish_refresh, generation, entries, error, as_admin)

        future.add_done_callback(completed)
        return GLib.SOURCE_REMOVE

    def _finish_refresh(
        self,
        generation: int,
        entries: list[PortEntry],
        error: str | None,
        as_admin: bool,
    ) -> bool:
        if generation != self._scan_generation:
            return GLib.SOURCE_REMOVE

        self.spinner.stop()
        self.refresh_button.set_sensitive(True)
        self.admin_button.set_sensitive(True)
        if error:
            self.error_label.set_text(error)
            self.subtitle.set_text("Scan failed")
            self.stack.set_visible_child_name("error")
            return GLib.SOURCE_REMOVE

        self._entries = entries
        hidden = sum(entry.process is None for entry in entries)
        source = " · admin scan" if as_admin else ""
        hidden_note = f" · {hidden} hidden" if hidden else ""
        self.subtitle.set_text(f"{len(entries)} occupied sockets{hidden_note}{source}")
        self._render_entries()
        return GLib.SOURCE_REMOVE

    def _render_entries(self) -> None:
        query = self.search.get_text().strip().casefold()
        protocol_index = self.protocol_filter.get_selected()
        wanted_protocol = {1: "TCP", 2: "UDP"}.get(protocol_index)

        visible = []
        for entry in self._entries:
            haystack = " ".join(
                (
                    str(entry.port),
                    entry.protocol,
                    entry.address,
                    entry.state,
                    entry.process or "",
                    str(entry.pid or ""),
                )
            ).casefold()
            if query and query not in haystack:
                continue
            if wanted_protocol and entry.protocol != wanted_protocol:
                continue
            visible.append(entry)

        while child := self.list_box.get_first_child():
            self.list_box.remove(child)
        for entry in visible:
            self.list_box.append(PortRow(entry))

        if visible:
            self.stack.set_visible_child_name("list")
        else:
            has_filters = bool(query or wanted_protocol)
            self.empty_title.set_text("No matching ports" if has_filters else "No occupied ports")
            self.empty_detail.set_text(
                "Try changing the search or protocol filter."
                if has_filters
                else "No bound TCP or UDP sockets were found."
            )
            self.stack.set_visible_child_name("empty")

    def _on_close(self, _window: Gtk.Window) -> bool:
        self._executor.shutdown(wait=False, cancel_futures=True)
        return False


class PortViewerApplication(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_path(str(files("port_viewer").joinpath("style.css")))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        icon_theme.add_search_path(str(files("port_viewer").joinpath("icons")))
        Gtk.Window.set_default_icon_name(APP_ID)

    def do_activate(self) -> None:
        window = self.props.active_window
        if window is None:
            window = PortViewerWindow(self)
        window.present()


def main() -> int:
    GLib.set_application_name("Port Viewer")
    GLib.set_prgname(APP_ID)
    return PortViewerApplication().run(None)
