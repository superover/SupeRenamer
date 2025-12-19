import sys
import os
import re
import requests
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTableWidget, QTableWidgetItem, 
                             QPushButton, QLabel, QFileDialog, QAbstractItemView,
                             QProgressBar, QHeaderView, QSplitter, QGroupBox,
                             QLineEdit, QComboBox, QCheckBox, QFormLayout, 
                             QDialog, QDialogButtonBox, QMenu, QMessageBox, QInputDialog)
from PyQt6.QtCore import Qt, QSettings, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QAction, QColor, QBrush, QIcon, QFont
from rapidfuzz import fuzz

# --- ADVANCED UI STYLING ---
SUPERNAMER_STYLE = """
QMainWindow { background-color: #1a1a1a; }
QWidget { color: #cfcfcf; font-family: 'Segoe UI', 'Ubuntu', sans-serif; font-size: 13px; }

/* Table Styling */
QTableWidget { 
    background-color: #242424; 
    alternate-background-color: #2b2b2b;
    gridline-color: #383838; 
    selection-background-color: #0078d4;
    border: 1px solid #333;
    border-radius: 4px;
}
QHeaderView::section { 
    background-color: #333; 
    padding: 10px; 
    border: 1px solid #222; 
    font-weight: bold;
    color: #fff;
}

/* Sidebar & Inputs */
QGroupBox { 
    border: 1px solid #444; 
    margin-top: 15px; 
    font-weight: bold; 
    border-radius: 5px;
    padding-top: 10px;
}
QLineEdit { 
    background-color: #111; 
    border: 1px solid #555; 
    padding: 8px; 
    color: #2ecc71; 
    font-family: 'Consolas', monospace;
    border-radius: 3px;
}

/* Buttons */
QPushButton { 
    background-color: #3d3d3d; 
    border: 1px solid #555; 
    padding: 10px; 
    border-radius: 4px; 
    min-width: 80px;
}
QPushButton:hover { background-color: #4d4d4d; border: 1px solid #777; }
QPushButton#match_btn { background-color: #005a9e; color: white; border: none; font-size: 14px; }
QPushButton#match_btn:hover { background-color: #0078d4; }
QPushButton#rename_btn { background-color: #107c10; color: white; border: none; font-size: 14px; }
QPushButton#rename_btn:hover { background-color: #18a018; }
QPushButton#clear_btn { background-color: #a4262c; color: white; border: none; }
QPushButton#clear_btn:hover { background-color: #d83b01; }

QProgressBar { border: 1px solid #333; height: 6px; text-align: center; border-radius: 3px; background: #111;}
QProgressBar::chunk { background-color: #0078d4; }
"""

class RenameEngine:
    def __init__(self):
        from guessit import guessit
        self.guessit = guessit
        self.api_key = QSettings("TitanSoft", "SupeRenamer").value("tmdb_api", "")

    def clean_filename_for_search(self, filename, show_name):
        name = os.path.splitext(filename)[0]
        name = re.sub(re.escape(show_name), '', name, flags=re.IGNORECASE)
        name = re.sub(r'[-_][a-zA-Z0-9_-]{11}$', '', name)
        name = re.sub(r'[Ee]p\.?\s?\d+', '', name)
        name = re.sub(r'[Ss]\d+[Ee]\d+', '', name)
        clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', name)
        return " ".join(clean.split()).strip()

    def get_match(self, filename):
        info = self.guessit(filename)
        raw_show = info.get('title', 'Unknown')
        s_target = info.get('season', 1)
        e_target = info.get('episode', 1)
        
        if not self.api_key: return raw_show, s_target, e_target, "Set API Key"

        try:
            search_url = f"https://api.themoviedb.org/3/search/tv?api_key={self.api_key}&query={raw_show}"
            res = requests.get(search_url, timeout=10).json()
            if not res.get('results'): return raw_show, s_target, e_target, "Show Not Found"

            target_fragment = self.clean_filename_for_search(filename, raw_show)
            
            for show_result in res['results'][:3]:
                show_id = show_result['id']
                actual_name = show_result['name']
                detail_url = f"https://api.themoviedb.org/3/tv/{show_id}?api_key={self.api_key}"
                detail_res = requests.get(detail_url, timeout=10).json()
                
                season_numbers = [s_target] + [si for si in range(1, detail_res.get('number_of_seasons', 1) + 1) if si != s_target]
                
                for sn in season_numbers:
                    season_url = f"https://api.themoviedb.org/3/tv/{show_id}/season/{sn}?api_key={self.api_key}"
                    s_res = requests.get(season_url, timeout=10).json()
                    for ep in s_res.get('episodes', []):
                        title_score = fuzz.token_sort_ratio(target_fragment.lower(), ep['name'].lower())
                        partial_score = fuzz.partial_ratio(target_fragment.lower(), ep['name'].lower())
                        if title_score > 85 or (partial_score > 95 and len(target_fragment) > 3):
                            return actual_name, sn, ep['episode_number'], ep['name']
            
            return res['results'][0]['name'], s_target, e_target, "Using Guess (No Title Match)"
        except Exception as e: return raw_show, s_target, e_target, f"Error: {str(e)}"

class ScanWorker(QThread):
    finished = pyqtSignal(list)
    def __init__(self, paths):
        super().__init__()
        self.paths = paths

    def run(self):
        video_exts = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm'}
        found = []
        for path in self.paths:
            if os.path.isfile(path) and os.path.splitext(path)[1].lower() in video_exts:
                found.append(path)
            elif os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for f in files:
                        if os.path.splitext(f)[1].lower() in video_exts:
                            found.append(os.path.join(root, f))
        self.finished.emit(found)

class SupeRenamer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SupeRenamer - Linux Edition")
        self.resize(1300, 850)
        self.setStyleSheet(SUPERNAMER_STYLE)
        self.engine = RenameEngine()
        
        main_layout = QVBoxLayout()
        central = QWidget()
        central.setLayout(main_layout)
        self.setCentralWidget(central)

        # Header Bar
        top_bar = QHBoxLayout()
        btn_add = QPushButton("📁 Add Files/Folders")
        btn_add.clicked.connect(self.import_files)
        
        btn_clear_list = QPushButton("🗑️ Clear List")
        btn_clear_list.setObjectName("clear_btn")
        btn_clear_list.clicked.connect(self.clear_file_list)
        
        btn_api = QPushButton("⚙️ API Key")
        btn_api.clicked.connect(self.set_api_key)
        
        top_bar.addWidget(btn_add)
        top_bar.addWidget(btn_clear_list)
        top_bar.addStretch()
        top_bar.addWidget(btn_api)
        main_layout.addLayout(top_bar)

        # Content Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Table Setup
        self.table = QTableWidget()
        self.setup_table()
        splitter.addWidget(self.table)

        # Sidebar Panel
        sidebar = QWidget()
        sidebar.setFixedWidth(300)
        side_lay = QVBoxLayout(sidebar)
        
        fmt_group = QGroupBox("Rename Pattern")
        fmt_lay = QVBoxLayout()
        self.txt_pattern = QLineEdit("{n} - {s00e00} - {t}")
        fmt_lay.addWidget(QLabel("Pattern Tags:\n{n}=Show | {s00e00}=S01E01 | {t}=Title"))
        fmt_lay.addWidget(self.txt_pattern)
        fmt_group.setLayout(fmt_lay)
        
        side_lay.addWidget(fmt_group)
        side_lay.addStretch()
        
        self.btn_match = QPushButton("🔍 ANALYZE MATCHES")
        self.btn_match.setObjectName("match_btn")
        self.btn_match.setMinimumHeight(50)
        self.btn_match.clicked.connect(self.process_matches)
        
        self.btn_rename = QPushButton("🚀 EXECUTE RENAME")
        self.btn_rename.setObjectName("rename_btn")
        self.btn_rename.setMinimumHeight(50)
        self.btn_rename.clicked.connect(self.execute_rename)
        
        side_lay.addWidget(self.btn_match)
        side_lay.addWidget(self.btn_rename)
        splitter.addWidget(sidebar)
        
        main_layout.addWidget(splitter)

        # Progress & Status
        self.progress = QProgressBar()
        self.progress.hide()
        main_layout.addWidget(self.progress)
        self.status_msg = QLabel("Ready for input. Drag and drop files here.")
        main_layout.addWidget(self.status_msg)
        
        self.setAcceptDrops(True)

    def setup_table(self):
        headers = ["Original Filename", "Detected Show", "S/E", "New Name Preview", "Status"]
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(headers)
        
        # Enable Manual Resizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        
        # Set default widths
        self.table.setColumnWidth(0, 350)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 350)
        
        self.table.verticalHeader().setDefaultSectionSize(35) # Default Row Height
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

    def clear_file_list(self):
        self.table.setRowCount(0)
        self.status_msg.setText("File list cleared.")

    def show_context_menu(self, pos):
        menu = QMenu()
        remove_action = menu.addAction("Remove Selected Rows")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == remove_action:
            indices = self.table.selectionModel().selectedRows()
            for index in sorted(indices, reverse=True):
                self.table.removeRow(index.row())

    def set_api_key(self):
        key, ok = QInputDialog.getText(self, 'TMDB Setup', 'Enter TMDB API Key (v3):')
        if ok:
            QSettings("TitanSoft", "SupeRenamer").setValue("tmdb_api", key)
            self.engine.api_key = key
            self.status_msg.setText("API Key saved.")

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.accept()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls()]
        self.load_files(paths)

    def import_files(self):
        path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if path: self.load_files([path])

    def load_files(self, paths):
        self.status_msg.setText("Scanning...")
        self.worker = ScanWorker(paths)
        self.worker.finished.connect(self.add_rows)
        self.worker.start()

    def add_rows(self, files):
        for f in files:
            row = self.table.rowCount()
            self.table.insertRow(row)
            item = QTableWidgetItem(os.path.basename(f))
            item.setData(Qt.ItemDataRole.UserRole, f)
            self.table.setItem(row, 0, item)
            self.table.setItem(row, 4, QTableWidgetItem("Ready"))
        self.status_msg.setText(f"Loaded {len(files)} new files.")

    def process_matches(self):
        count = self.table.rowCount()
        if count == 0: return
        self.progress.show()
        self.progress.setRange(0, count)
        for i in range(count):
            full_path = self.table.item(i, 0).data(Qt.ItemDataRole.UserRole)
            filename = os.path.basename(full_path)
            ext = os.path.splitext(filename)[1]
            
            show, s, e, title = self.engine.get_match(filename)
            
            new_name = self.txt_pattern.text().replace("{n}", show).replace("{s00e00}", f"S{str(s).zfill(2)}E{str(e).zfill(2)}").replace("{t}", title) + ext
            
            self.table.setItem(i, 1, QTableWidgetItem(show))
            self.table.setItem(i, 2, QTableWidgetItem(f"S{s}E{e}"))
            
            preview_item = QTableWidgetItem(new_name)
            preview_item.setForeground(QBrush(QColor("#2ecc71"))) # Success Green
            self.table.setItem(i, 3, preview_item)
            
            self.table.setItem(i, 4, QTableWidgetItem("Matched ✅"))
            self.progress.setValue(i + 1)
            QApplication.processEvents()
        self.progress.hide()
        self.status_msg.setText("Analysis complete. Review filenames in green.")

    def execute_rename(self):
        success_count = 0
        for i in range(self.table.rowCount()):
            old_path = self.table.item(i, 0).data(Qt.ItemDataRole.UserRole)
            new_name = self.table.item(i, 3).text()
            if new_name and "Matched" in self.table.item(i, 4).text():
                try:
                    new_path = os.path.join(os.path.dirname(old_path), new_name)
                    os.rename(old_path, new_path)
                    self.table.setItem(i, 4, QTableWidgetItem("Renamed!"))
                    success_count += 1
                except Exception as e:
                    self.table.setItem(i, 4, QTableWidgetItem("Error"))
        QMessageBox.information(self, "Success", f"Successfully renamed {success_count} files.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = SupeRenamer()
    win.show()
    sys.exit(app.exec())
