# window.py
#
# Copyright 2026 Hobbies
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import time
import queue
import shutil
import threading
from datetime import datetime

from gi.repository import Adw, Gtk, Gio, GLib, Gdk, Pango

# Helper: Format size elegantly
def format_size(size_bytes):
    if size_bytes <= 0:
        return "0 Bytes"
    units = ["Bytes", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(units) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.1f} {units[i]}"

# Helper: Format time elapsed
def format_time_ago(timestamp):
    if not timestamp:
        return "Unknown"
    now = time.time()
    diff = now - timestamp
    if diff < 0:
        diff = 0
    if diff < 60:
        return "Just now"
    elif diff < 3600:
        minutes = int(diff / 60)
        return f"{minutes}m ago" if minutes > 1 else "1m ago"
    elif diff < 86400:
        hours = int(diff / 3600)
        return f"{hours}h ago" if hours > 1 else "1h ago"
    elif diff < 2592000:
        days = int(diff / 86400)
        return f"{days}d ago" if days > 1 else "1d ago"
    elif diff < 31536000:
        months = int(diff / 2592000)
        return f"{months}mo ago" if months > 1 else "1mo ago"
    else:
        years = int(diff / 31536000)
        return f"{years}y ago" if years > 1 else "1y ago"

# Native directory scanning in background thread
class NodeModulesScanner:
    def __init__(self, base_path, scan_queue):
        self.base_path = os.path.abspath(base_path)
        self.scan_queue = scan_queue
        self.is_running = False
        self._thread = None

    def start(self):
        self.is_running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self.is_running = False

    def _get_dir_size_and_modified(self, path):
        total_size = 0
        latest_mod = 0
        stack = [path]
        while stack and self.is_running:
            curr = stack.pop()
            try:
                with os.scandir(curr) as it:
                    for entry in it:
                        if not self.is_running:
                            break
                        try:
                            if entry.is_symlink():
                                continue

                            if entry.is_dir():
                                stack.append(entry.path)
                            else:
                                stat = entry.stat()
                                total_size += stat.st_size
                                if stat.st_mtime > latest_mod:
                                    latest_mod = stat.st_mtime
                        except Exception:
                            pass
            except Exception:
                pass
        return total_size, latest_mod

    def _run(self):
        stack = [self.base_path]
        node_projects = set()

        while stack and self.is_running:
            curr = stack.pop()

            # Periodically feed scanned path progress
            self.scan_queue.put({"type": "progress", "path": curr})

            try:
                has_package_json = False
                subdirs = []

                with os.scandir(curr) as it:
                    for entry in it:
                        if not self.is_running:
                            break
                        try:
                            if entry.is_symlink():
                                continue

                            if entry.is_file():
                                if entry.name == 'package.json':
                                    has_package_json = True
                            elif entry.is_dir():
                                if entry.name == 'node_modules':
                                    full_path = entry.path
                                    size, mtime = self._get_dir_size_and_modified(full_path)
                                    self.scan_queue.put({
                                        "type": "found",
                                        "path": full_path,
                                        "size": size,
                                        "mtime": mtime
                                    })
                                # Skip common massive build, cache, and system directories
                                elif entry.name.startswith('.') or entry.name in (
                                    'build', 'dist', 'out', 'target', 'venv', '.venv', 'env',
                                    'Library', 'Cache', 'Caches', 'tmp'
                                ):
                                    continue
                                else:
                                    subdirs.append(entry.path)
                        except Exception:
                            pass

                if has_package_json:
                    node_projects.add(curr)
                    self.scan_queue.put({"type": "project_found", "path": curr})

                # Scan subdirectories
                for sd in subdirs:
                    stack.append(sd)

            except Exception:
                pass

        self.scan_queue.put({"type": "finished"})


# Beautiful customized native Adw.ActionRow
class NodeModuleRow(Adw.ActionRow):
    def __init__(self, path, size, mtime):
        super().__init__()
        self.path = path
        self.size = size
        self.mtime = mtime
        self.project_name = os.path.basename(os.path.dirname(path))

        # Configure native ActionRow properties
        self.set_title(self.project_name)
        self.set_icon_name("folder-symbolic")

        # Custom prefix: Selection Checkbox
        self.checkbox = Gtk.CheckButton()
        self.checkbox.set_valign(Gtk.Align.CENTER)
        self.add_prefix(self.checkbox)

        # Suffix Horizontal Box
        suffix_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        suffix_box.set_valign(Gtk.Align.CENTER)

        # Last Modified time label
        time_text = format_time_ago(mtime)
        self.time_label = Gtk.Label(label=time_text)
        self.time_label.set_css_classes(["dim-label", "caption"])
        suffix_box.append(self.time_label)

        # Size Badge
        size_text = format_size(size)
        self.size_badge = Gtk.Label(label=size_text)
        self.size_badge.set_css_classes(["bold", "numeric", "size-badge"])
        suffix_box.append(self.size_badge)

        # Open directory reveal button
        self.open_btn = Gtk.Button()
        self.open_btn.set_icon_name("document-open-symbolic")
        self.open_btn.set_css_classes(["flat"])
        self.open_btn.set_tooltip_text("Open Project Folder")
        suffix_box.append(self.open_btn)

        # Trash delete button
        self.delete_btn = Gtk.Button()
        self.delete_btn.set_icon_name("user-trash-symbolic")
        self.delete_btn.set_css_classes(["destructive-action", "flat"])
        self.delete_btn.set_tooltip_text("Delete Node Modules")
        suffix_box.append(self.delete_btn)

        self.add_suffix(suffix_box)

# Premium customized row for Node Projects Explorer
class NodeProjectRow(Adw.ActionRow):
    def __init__(self, path, has_node_modules):
        super().__init__()
        self.path = path
        self.has_node_modules = has_node_modules
        self.project_name = os.path.basename(path)

        # Configure row properties
        self.set_title(self.project_name)
        self.set_subtitle(path)
        self.set_icon_name("folder-symbolic")

        # Suffix Horizontal Box
        suffix_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        suffix_box.set_valign(Gtk.Align.CENTER)

        # Status badge label
        self.status_badge = Gtk.Label()
        if has_node_modules:
            self.status_badge.set_text("Available")
            self.status_badge.set_css_classes(["dim-label", "bold"])
        else:
            pass

        suffix_box.append(self.status_badge)

        # Open directory folder button
        self.open_btn = Gtk.Button()
        self.open_btn.set_icon_name("document-open-symbolic")
        self.open_btn.set_css_classes(["flat"])
        self.open_btn.set_tooltip_text("Open Project Folder")
        self.open_btn.connect("clicked", lambda _: self.open_folder(path))
        suffix_box.append(self.open_btn)

        self.add_suffix(suffix_box)

    def open_folder(self, path):
        file_obj = Gio.File.new_for_path(path)
        try:
            Gio.AppInfo.launch_default_for_uri(file_obj.get_uri(), None)
        except Exception:
            pass
@Gtk.Template(resource_path='/com/x1da49/thenodemodules/window.ui')
class ThenodemodulesWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'ThenodemodulesWindow'

    toast_overlay = Gtk.Template.Child()
    header_bar = Gtk.Template.Child()
    header_choose_btn = Gtk.Template.Child()
    header_scan_btn = Gtk.Template.Child()
    stack = Gtk.Template.Child()
    welcome_status_page = Gtk.Template.Child()
    scan_home_btn = Gtk.Template.Child()
    choose_folder_btn = Gtk.Template.Child()
    scanning_status_page = Gtk.Template.Child()
    progress_bar = Gtk.Template.Child()
    scanning_path_label = Gtk.Template.Child()
    cancel_scan_btn = Gtk.Template.Child()
    select_all_check = Gtk.Template.Child()
    sort_dropdown = Gtk.Template.Child()
    listbox = Gtk.Template.Child()
    projects_listbox = Gtk.Template.Child()
    action_revealer = Gtk.Template.Child()
    action_bar_label = Gtk.Template.Child()
    delete_selected_btn = Gtk.Template.Child()

    total_size_label = Gtk.Template.Child()
    stat_projects_row = Gtk.Template.Child()
    total_projects_label = Gtk.Template.Child()
    stat_count_row = Gtk.Template.Child()
    total_count_label = Gtk.Template.Child()

    disk_total_label = Gtk.Template.Child()
    disk_free_label = Gtk.Template.Child()
    disk_modules_ratio_row = Gtk.Template.Child()
    disk_modules_ratio_label = Gtk.Template.Child()
    disk_modules_progress = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Init state
        self.scanner = None
        self.found_items = []
        self.projects_found_paths = set()
        self.is_bulk_checking = False
        self.scan_queue = queue.Queue()
        self.scan_timeout_id = 0
        self.current_scan_path = ""

        self.setup_ui()
        self.setup_styles()
        self.setup_actions()

    def setup_ui(self):
        # Configure sort options model
        dropdown_strings = ["Size (Largest First)", "Last Modified (Oldest First)", "Project Name (A-Z)"]
        string_list = Gtk.StringList.new(dropdown_strings)
        self.sort_dropdown.set_model(string_list)

        # Connect ListBox sort handlers
        self.listbox.set_sort_func(self.sort_func)

    def setup_styles(self):
        # Clean CSS to enhance the native Libadwaita aesthetic
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            .size-badge {
                background-color: alpha(@accent_color, 0.12);
                color: @accent_color;
                padding: 4px 10px;
                border-radius: 8px;
                font-size: 0.9rem;
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def setup_actions(self):
        # Register clicks & selections
        self.scan_home_btn.connect("clicked", self.on_scan_home_clicked)
        self.choose_folder_btn.connect("clicked", self.on_choose_folder_clicked)
        self.header_choose_btn.connect("clicked", self.on_choose_folder_clicked)
        self.header_scan_btn.connect("clicked", self.on_rescan_clicked)
        self.cancel_scan_btn.connect("clicked", self.on_cancel_scan_clicked)
        self.sort_dropdown.connect("notify::selected", self.on_sort_changed)
        self.select_all_check.connect("toggled", self.on_select_all_toggled)
        self.delete_selected_btn.connect("clicked", self.on_delete_selected_clicked)

    # Search & Sort ListBox Handlers
    def filter_func(self, row):
        return True

    def sort_func(self, row1, row2):
        if not isinstance(row1, NodeModuleRow) or not isinstance(row2, NodeModuleRow):
            return 0
        idx = self.sort_dropdown.get_selected()
        if idx == 0:  # Size Descending
            return 1 if row1.size < row2.size else -1 if row1.size > row2.size else 0
        elif idx == 1:  # Modified Ascending
            return 1 if row1.mtime > row2.mtime else -1 if row1.mtime < row2.mtime else 0
        elif idx == 2:  # Name A-Z
            return 1 if row1.project_name.lower() > row2.project_name.lower() else -1 if row1.project_name.lower() < row2.project_name.lower() else 0
        return 0

    # UI Signal Trigger Callbacks
    def on_scan_home_clicked(self, btn):
        home = os.path.expanduser("~")
        self.start_scan(home)

    def on_choose_folder_clicked(self, btn):
        if hasattr(Gtk, "FileDialog"):
            dialog = Gtk.FileDialog.new()
            dialog.set_title("Select Project or Root Folder to Scan")
            dialog.select_folder(self, None, self.on_folder_selected)
        else:
            dialog = Gtk.FileChooserNative.new(
                "Select Project or Root Folder to Scan",
                self,
                Gtk.FileChooserAction.SELECT_FOLDER,
                "_Select",
                "_Cancel"
            )
            dialog.connect("response", self.on_file_chooser_response)
            dialog.show()

    def on_file_chooser_response(self, dialog, response_id):
        try:
            if response_id == Gtk.ResponseType.ACCEPT:
                file = dialog.get_file()
                if file:
                    path = file.get_path()
                    self.start_scan(path)
        except Exception:
            pass
        dialog.destroy()

    def on_folder_selected(self, dialog, result):
        try:
            file = dialog.select_folder_finish(result)
            if file:
                path = file.get_path()
                self.start_scan(path)
        except Exception:
            pass

    def on_rescan_clicked(self, btn):
        if self.current_scan_path:
            self.start_scan(self.current_scan_path)

    def on_cancel_scan_clicked(self, btn):
        self.stop_scan()
        if self.found_items or self.projects_found_paths:
            self.stack.set_visible_child_name("results_page")
        else:
            self.stack.set_visible_child_name("welcome_page")

    def on_sort_changed(self, dropdown, pspec):
        self.listbox.invalidate_sort()

    def on_select_all_toggled(self, checkbutton):
        if self.is_bulk_checking:
            return
        self.is_bulk_checking = True
        active = checkbutton.get_active()

        row = self.listbox.get_first_child()
        while row is not None:
            if isinstance(row, NodeModuleRow) and self.filter_func(row):
                row.checkbox.set_active(active)
            row = row.get_next_sibling()

        self.is_bulk_checking = False
        self.update_action_bar()

    def on_row_checkbox_toggled(self, check):
        if not self.is_bulk_checking:
            self.update_action_bar()

    # Scanning Core Mechanics
    def start_scan(self, path):
        self.stop_scan()
        self.current_scan_path = os.path.abspath(path)

        # Clear out current visual lists
        row = self.listbox.get_first_child()
        while row is not None:
            next_row = row.get_next_sibling()
            self.listbox.remove(row)
            row = next_row

        row = self.projects_listbox.get_first_child()
        while row is not None:
            next_row = row.get_next_sibling()
            self.projects_listbox.remove(row)
            row = next_row

        self.found_items.clear()
        self.projects_found_paths.clear()

        # Reset counters
        self.update_stats()
        self.select_all_check.set_active(False)
        self.action_revealer.set_reveal_child(False)

        # Transition stack to scanning
        self.stack.set_visible_child_name("scanning_page")
        self.progress_bar.set_fraction(0.0)

        # Configure & trigger background scanner thread
        self.scan_queue = queue.Queue()
        self.scanner = NodeModulesScanner(self.current_scan_path, self.scan_queue)
        self.scanner.start()

        # Enable main loop polling timeout
        self.scan_timeout_id = GLib.timeout_add(100, self.on_scan_timeout)

        # Toggle toolbar items
        self.header_scan_btn.set_visible(False)
        self.header_choose_btn.set_visible(False)

    def stop_scan(self):
        if self.scanner:
            self.scanner.stop()
            self.scanner = None
        if self.scan_timeout_id > 0:
            GLib.source_remove(self.scan_timeout_id)
            self.scan_timeout_id = 0

    def on_scan_timeout(self):
        if not self.scanner:
            return False

        # Pulse progress indicator
        self.progress_bar.pulse()

        added_new = False
        finished = False
        while not self.scan_queue.empty():
            try:
                item = self.scan_queue.get_nowait()
                if item["type"] == "progress":
                    self.scanning_path_label.set_text(item["path"])
                elif item["type"] == "project_found":
                    self.projects_found_paths.add(item["path"])
                    added_new = True
                elif item["type"] == "found":
                    path = item["path"]
                    size = item["size"]
                    mtime = item["mtime"]

                    if any(r.path == path for r in self.found_items):
                        continue

                    row = NodeModuleRow(path, size, mtime)
                    row.checkbox.connect("toggled", self.on_row_checkbox_toggled)
                    row.delete_btn.connect("clicked", lambda _, r=row: self.confirm_and_delete([r]))
                    row.open_btn.connect("clicked", lambda _, p=path: self.open_project_folder(p))

                    self.listbox.append(row)
                    self.found_items.append(row)
                    added_new = True
                elif item["type"] == "finished":
                    finished = True
            except queue.Empty:
                break
            except Exception:
                pass

        if added_new:
            self.update_stats()
            self.listbox.invalidate_filter()
            self.listbox.invalidate_sort()

        if finished:
            self.finish_scan()
            return False

        return True

    def finish_scan(self):
        self.stop_scan()
        self.header_scan_btn.set_visible(True)
        self.header_choose_btn.set_visible(True)

        if self.found_items or self.projects_found_paths:
            # Populate Projects Explorer ("Node Install Products")
            # Clear previous items first
            row = self.projects_listbox.get_first_child()
            while row is not None:
                next_row = row.get_next_sibling()
                self.projects_listbox.remove(row)
                row = next_row

            found_nm_paths = {os.path.dirname(r.path) for r in self.found_items}
            sorted_projects = sorted(list(self.projects_found_paths))
            for proj_path in sorted_projects:
                has_nm = proj_path in found_nm_paths
                row = NodeProjectRow(proj_path, has_nm)
                self.projects_listbox.append(row)

            self.stack.set_visible_child_name("results_page")
            toast = Adw.Toast.new(f"Scan complete. Discovered {len(self.projects_found_paths)} Node projects.")
            self.toast_overlay.add_toast(toast)
        else:
            self.stack.set_visible_child_name("welcome_page")
            toast = Adw.Toast.new("No Node projects found.")
            self.toast_overlay.add_toast(toast)

    def open_project_folder(self, path):
        parent_dir = os.path.dirname(path)
        file_obj = Gio.File.new_for_path(parent_dir)
        try:
            Gio.AppInfo.launch_default_for_uri(file_obj.get_uri(), None)
        except Exception as e:
            toast = Adw.Toast.new(f"Failed to open directory: {e}")
            self.toast_overlay.add_toast(toast)

    # Selection & Statistics Updates
    def update_stats(self):
        # 1. Modules and projects summary
        total_bytes = sum(r.size for r in self.found_items)
        installed_modules = len(self.found_items)
        total_projects = len(self.projects_found_paths)

        self.total_size_label.set_text(format_size(total_bytes))
        self.total_projects_label.set_text(str(total_projects))
        self.total_count_label.set_text(str(installed_modules))

        # Dynamic comparison row subtitle
        self.stat_count_row.set_subtitle(
            f"{installed_modules} out of {total_projects} projects have node_modules installed"
        )

        # 2. System Partition storage metrics
        try:
            target_path = self.current_scan_path or os.path.expanduser("~")
            total_disk, used_disk, free_disk = shutil.disk_usage(target_path)

            self.disk_total_label.set_text(format_size(total_disk))
            self.disk_free_label.set_text(format_size(free_disk))

            if total_disk > 0:
                ratio = (total_bytes / total_disk) * 100
                self.disk_modules_ratio_label.set_text(f"{ratio:.2f}%")
                self.disk_modules_progress.set_fraction(total_bytes / total_disk)
                self.disk_modules_ratio_row.set_subtitle(
                    f"node_modules occupies {format_size(total_bytes)} of your {format_size(total_disk)} partition"
                )
            else:
                self.disk_modules_ratio_label.set_text("0.0%")
                self.disk_modules_progress.set_fraction(0.0)
        except Exception as e:
            print(f"Error updating disk storage metrics: {e}")

    def update_action_bar(self):
        count = 0
        size = 0

        row = self.listbox.get_first_child()
        while row is not None:
            if isinstance(row, NodeModuleRow) and row.checkbox.get_active() and self.filter_func(row):
                count += 1
                size += row.size
            row = row.get_next_sibling()

        if count > 0:
            self.action_bar_label.set_text(f"{count} folders selected ({format_size(size)})")
            self.action_revealer.set_reveal_child(True)
        else:
            self.action_revealer.set_reveal_child(False)

    # Safe Delete Action Core Trigger Flow
    def confirm_and_delete(self, rows):
        count = len(rows)
        if count == 0:
            return

        title = "Delete Node Modules?"
        if count == 1:
            project = rows[0].project_name
            body = f"Are you sure you want to delete the node_modules folder of project '{project}'? You will have to run 'npm install' to recreate it."
        else:
            body = f"Are you sure you want to delete all {count} selected node_modules folders? This will permanently reclaim storage space."

        dialog = Adw.MessageDialog.new(self, title, body)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_dialog_response(diag, response):
            if response == "delete":
                self.perform_deletion(rows)
            diag.destroy()

        dialog.connect("response", on_dialog_response)
        dialog.present()

    def on_delete_selected_clicked(self, btn):
        selected_rows = []
        row = self.listbox.get_first_child()
        while row is not None:
            if isinstance(row, NodeModuleRow) and row.checkbox.get_active() and self.filter_func(row):
                selected_rows.append(row)
            row = row.get_next_sibling()

        self.confirm_and_delete(selected_rows)

    def perform_deletion(self, rows):
        # Deletion runs in background to keep UI fully fluid
        loading_toast = Adw.Toast.new("Cleaning up selected files...")
        loading_toast.set_timeout(0) # Keep toast until manual dismissal
        self.toast_overlay.add_toast(loading_toast)

        def delete_thread_worker():
            deleted_paths = []
            deleted_size = 0

            for r in rows:
                try:
                    if os.path.exists(r.path):
                        shutil.rmtree(r.path)
                    deleted_paths.append(r.path)
                    deleted_size += r.size
                except Exception as e:
                    print(f"Error deleting path {r.path}: {e}")

            GLib.idle_add(self.on_deletion_complete, deleted_paths, deleted_size, loading_toast)

        threading.Thread(target=delete_thread_worker, daemon=True).start()

    def on_deletion_complete(self, deleted_paths, deleted_size, loading_toast):
        loading_toast.dismiss()

        # Remove deleted rows from listbox
        for path in deleted_paths:
            found_row = next((r for r in self.found_items if r.path == path), None)
            if found_row:
                self.listbox.remove(found_row)
                self.found_items.remove(found_row)

        self.update_stats()
        self.update_action_bar()

        toast = Adw.Toast.new(f"Cleaned up {len(deleted_paths)} folders. Reclaimed {format_size(deleted_size)}.")
        self.toast_overlay.add_toast(toast)

        if not self.found_items:
            self.stack.set_visible_child_name("welcome_page")
            self.header_scan_btn.set_visible(False)
            self.header_choose_btn.set_visible(False)
