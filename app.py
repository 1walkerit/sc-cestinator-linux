import os
import re
import sys
import json
import shutil
import tempfile
import zipfile
import webbrowser
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
    QCheckBox,
)

APP_NAME = "SC Češtinátor Linux"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
BANNER_PATH = ASSETS_DIR / "SplashScreen.png"
CONFIG_DIR = Path.home() / ".config" / "sc-cestinator"
CONFIG_FILE = CONFIG_DIR / "config.json"

GITHUB_REPO = "https://github.com/JarredSC/Star-Citizen-CZ-lokalizace"
LATEST_ZIP_URL = (
    "https://github.com/JarredSC/Star-Citizen-CZ-lokalizace/"
    "releases/latest/download/Localization.zip"
)
GITHUB_API_LATEST = (
    "https://api.github.com/repos/JarredSC/Star-Citizen-CZ-lokalizace/releases/latest"
)

RSI_URL = "https://robertsspaceindustries.com/"
RSI_ACCOUNT_URL = "https://robertsspaceindustries.com/account/settings"
RSI_HANGAR_URL = "https://robertsspaceindustries.com/account/pledges"
SPECTRUM_URL = "https://robertsspaceindustries.com/spectrum/community/SC"
ISSUE_COUNCIL_URL = "https://issue-council.robertsspaceindustries.com/"
SC_WIKI_URL = "https://starcitizen.tools/"
FINDER_URL = "https://finder.cstone.space/"
ISSUE_URL = "https://github.com/JarredSC/Star-Citizen-CZ-lokalizace/issues"


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(data: dict) -> None:
    ensure_config_dir()
    CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_text_from_url(url: str, timeout: int = 20) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": "SC-Cestinator-Linux/1.0",
            "Accept": "application/json, text/plain, */*",
        },
    )
    with urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def download_file(url: str, destination: Path, timeout: int = 60) -> None:
    req = Request(url, headers={"User-Agent": "SC-Cestinator-Linux/1.0"})
    with urlopen(req, timeout=timeout) as response, open(destination, "wb") as out:
        shutil.copyfileobj(response, out)


def parse_version_line(text: str) -> str | None:
    if not text:
        return None

    lines = text.splitlines()
    if not lines:
        return None

    first_line = lines[0].strip().lstrip("﻿")
    if not first_line:
        return None

    # Očekávaný formát např. ;0.9v nebo #0.9v
    if first_line.startswith((";", "#")):
        first_line = first_line[1:].strip()

    if not first_line:
        return None

    token = first_line.split()[0].strip()
    return token or None


def fetch_remote_global_ini_version() -> str | None:
    raw_url = (
        "https://raw.githubusercontent.com/"
        "JarredSC/Star-Citizen-CZ-lokalizace/main/Localization/english/global.ini"
    )
    try:
        content = read_text_from_url(raw_url)
        return parse_version_line(content)
    except Exception:
        return None


def read_local_version(global_ini_path: Path) -> str | None:
    if not global_ini_path.exists():
        return None
    try:
        content = global_ini_path.read_text(encoding="utf-8", errors="replace")
        return parse_version_line(content)
    except Exception:
        return None


def read_version_from_zip(zip_path: Path) -> str | None:
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                normalized = name.replace("\\", "/")
                if normalized.endswith("Localization/english/global.ini"):
                    with zf.open(name) as fh:
                        content = fh.read().decode("utf-8", errors="replace")
                        return parse_version_line(content)
    except Exception:
        return None
    return None


def fetch_latest_release_info() -> tuple[str | None, str | None]:
    """
    Vrací dvojici:
    - release label (tag_name nebo name)
    - verze češtiny z raw global.ini v repozitáři
    """
    release_label = None
    remote_version = None

    try:
        raw = read_text_from_url(GITHUB_API_LATEST)
        data = json.loads(raw)
        release_label = data.get("tag_name") or data.get("name")
    except Exception:
        release_label = None

    remote_version = fetch_remote_global_ini_version()

    return release_label, remote_version


def normalize_live_path(user_path: str) -> Path:
    path = Path(user_path).expanduser().resolve()
    if path.name.upper() == "LIVE":
        return path
    return path / "LIVE"


def build_paths(user_path: str) -> dict[str, Path]:
    live_path = normalize_live_path(user_path)
    data_path = live_path / "data"
    localization_path = data_path / "Localization"
    english_path = localization_path / "english"
    global_ini_path = english_path / "global.ini"
    return {
        "live": live_path,
        "data": data_path,
        "localization": localization_path,
        "english": english_path,
        "global_ini": global_ini_path,
    }


def compare_versions(local_version: str | None, remote_version: str | None) -> str:
    if not local_version and not remote_version:
        return "Verzi se nepodařilo zjistit"
    if not local_version:
        return "Čeština není nainstalovaná"
    if not remote_version:
        return "Nelze zjistit vzdálenou verzi"
    if local_version == remote_version:
        return "Čeština je aktuální"
    return "K dispozici je jiná / novější verze"


class MainWindow(QMainWindow):
    def set_status_label(self, label: QLabel, text: str, state: str = "neutral") -> None:
        styles = {
            "ok": "color: #2e7d32; font-weight: 700;",
            "warn": "color: #e65100; font-weight: 700;",
            "error": "color: #c62828; font-weight: 700;",
            "neutral": "font-weight: 600;",
        }
        label.setText(text)
        label.setStyleSheet(styles.get(state, styles["neutral"]))

    def _make_link_button(self, text: str, url: str) -> QPushButton:
        button = QPushButton(text)
        button.clicked.connect(lambda: webbrowser.open(url))
        return button

    def _create_banner(self) -> QLabel | None:
        if not BANNER_PATH.exists():
            return None
        pixmap = QPixmap(str(BANNER_PATH))
        if pixmap.isNull():
            return None
        label = QLabel()
        label.setAlignment(Qt.AlignCenter)
        label.setPixmap(pixmap.scaledToHeight(220, Qt.SmoothTransformation))
        label.setStyleSheet("padding: 4px;")
        self.banner_source = pixmap
        return label

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if getattr(self, "banner", None) and getattr(self, "banner_source", None):
            self.banner.setPixmap(self.banner_source.scaledToHeight(220, Qt.SmoothTransformation))

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(860, 620)

        self.config = load_config()

        self.last_release_label: str | None = None
        self.last_remote_version: str | None = None

        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Např. /mnt/games/StarCitizen nebo přímo /mnt/games/StarCitizen/LIVE")
        self.path_input.setText(self.config.get("game_path", ""))
        self.path_input.editingFinished.connect(self.auto_refresh_from_path)

        self.browse_button = QPushButton("Procházet…")
        self.browse_button.clicked.connect(self.choose_folder)

        self.check_button = QPushButton("Zkontrolovat")
        self.check_button.clicked.connect(self.check_installation)

        self.github_button = QPushButton("Zkontrolovat online")
        self.github_button.clicked.connect(self.check_github_version)

        self.install_button = QPushButton("Instalovat / aktualizovat")
        self.install_button.clicked.connect(self.install_or_update)

        self.open_live_button = QPushButton("Otevřít složku LIVE")
        self.open_live_button.clicked.connect(self.open_live_folder)

        self.open_loc_button = QPushButton("Otevřít Localization")
        self.open_loc_button.clicked.connect(self.open_localization_folder)

        self.backup_checkbox = QCheckBox("Před aktualizací vytvořit zálohu stávající Localization")
        self.backup_checkbox.setChecked(self.config.get("create_backup", True))

        self.banner = None
        self.banner_source = None

        self.live_path_value = QLabel("-")
        self.data_status_value = QLabel("-")
        self.global_ini_status_value = QLabel("-")
        self.local_version_value = QLabel("-")
        self.release_value = QLabel("-")
        self.remote_version_value = QLabel("-")
        self.compare_value = QLabel("-")

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)

        self._build_ui()
        self.log("Aplikace spuštěna.")
        self.auto_initial_check()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)

        self.banner = self._create_banner()
        if self.banner:
            layout.addWidget(self.banner)

        path_group = QGroupBox("Umístění hry")
        path_layout = QHBoxLayout(path_group)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_button)

        status_group = QGroupBox("Stav instalace")
        status_layout = QGridLayout(status_group)
        row = 0
        status_layout.addWidget(QLabel("Cílová LIVE cesta:"), row, 0)
        status_layout.addWidget(self.live_path_value, row, 1)
        row += 1
        status_layout.addWidget(QLabel("Adresář data:"), row, 0)
        status_layout.addWidget(self.data_status_value, row, 1)
        row += 1
        status_layout.addWidget(QLabel("Soubor global.ini:"), row, 0)
        status_layout.addWidget(self.global_ini_status_value, row, 1)
        row += 1
        status_layout.addWidget(QLabel("Lokální verze češtiny:"), row, 0)
        status_layout.addWidget(self.local_version_value, row, 1)
        row += 1
        status_layout.addWidget(QLabel("GitHub release:"), row, 0)
        status_layout.addWidget(self.release_value, row, 1)
        row += 1
        status_layout.addWidget(QLabel("Verze na GitHubu:"), row, 0)
        status_layout.addWidget(self.remote_version_value, row, 1)
        row += 1
        status_layout.addWidget(QLabel("Porovnání:"), row, 0)
        status_layout.addWidget(self.compare_value, row, 1)

        action_group = QGroupBox("Akce")
        action_layout = QVBoxLayout(action_group)

        action_row_1 = QHBoxLayout()
        action_row_1.addWidget(self.check_button)
        action_row_1.addWidget(self.github_button)
        action_row_1.addWidget(self.install_button)
        action_layout.addLayout(action_row_1)

        action_row_2 = QHBoxLayout()
        action_row_2.addWidget(self.open_live_button)
        action_row_2.addWidget(self.open_loc_button)
        action_layout.addLayout(action_row_2)

        action_layout.addWidget(self.backup_checkbox)

        links_group = QGroupBox("Užitečné odkazy")
        links_layout = QVBoxLayout(links_group)

        sc_links_group = QGroupBox("Star Citizen")
        sc_links_layout = QHBoxLayout(sc_links_group)
        sc_links_layout.addWidget(self._make_link_button("RSI", RSI_URL))
        sc_links_layout.addWidget(self._make_link_button("Můj RSI účet", RSI_ACCOUNT_URL))
        sc_links_layout.addWidget(self._make_link_button("Můj RSI hangár", RSI_HANGAR_URL))
        sc_links_layout.addWidget(self._make_link_button("Spectrum", SPECTRUM_URL))
        sc_links_layout.addWidget(self._make_link_button("Issue Council", ISSUE_COUNCIL_URL))

        cz_links_group = QGroupBox("Čeština")
        cz_links_layout = QHBoxLayout(cz_links_group)
        cz_links_layout.addWidget(self._make_link_button("GitHub projektu", GITHUB_REPO))
        cz_links_layout.addWidget(self._make_link_button("Poslední release", LATEST_ZIP_URL))
        cz_links_layout.addWidget(self._make_link_button("Nahlásit problém", ISSUE_URL))

        tools_links_group = QGroupBox("Nástroje")
        tools_links_layout = QHBoxLayout(tools_links_group)
        tools_links_layout.addWidget(self._make_link_button("SC Wiki", SC_WIKI_URL))
        tools_links_layout.addWidget(self._make_link_button("Finder", FINDER_URL))

        links_layout.addWidget(sc_links_group)
        links_layout.addWidget(cz_links_group)
        links_layout.addWidget(tools_links_group)

        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)
        log_layout.addWidget(self.log_output)

        layout.addWidget(path_group)
        layout.addWidget(status_group)
        layout.addWidget(action_group)
        layout.addWidget(links_group)
        layout.addWidget(log_group)

        root.setStyleSheet(
            """
            QGroupBox {
                font-weight: 600;
                margin-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QPushButton {
                min-height: 30px;
            }
            QLabel {
                font-size: 14px;
            }
            QLineEdit {
                min-height: 30px;
                font-size: 14px;
            }
            QPlainTextEdit {
                font-family: monospace;
            }
            """
        )
        self.setCentralWidget(root)

    def log(self, message: str) -> None:
        self.log_output.appendPlainText(message)

    def choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Vyber kořen Star Citizenu nebo přímo LIVE")
        if folder:
            self.path_input.setText(folder)
            self.log(f"Vybraná cesta: {folder}")
            self.auto_refresh_from_path()

    def get_paths(self) -> dict[str, Path] | None:
        raw_path = self.path_input.text().strip()
        if not raw_path:
            QMessageBox.warning(self, "Chybí cesta", "Nejprve zadej cestu ke hře.")
            return None
        try:
            paths = build_paths(raw_path)
            self.live_path_value.setText(str(paths["live"]))
            return paths
        except Exception as exc:
            QMessageBox.critical(self, "Chyba cesty", f"Neplatná cesta: {exc}")
            return None

    def update_compare_label(self) -> None:
        local_text = self.local_version_value.text() if self.local_version_value.text() != "-" else None
        remote_text = self.remote_version_value.text() if self.remote_version_value.text() != "-" else None
        result = compare_versions(local_text, remote_text)
        state = "neutral"
        if result == "Čeština je aktuální":
            state = "ok"
        elif "jiná / novější verze" in result:
            state = "warn"
        elif result in ("Čeština není nainstalovaná", "Nelze zjistit vzdálenou verzi", "Verzi se nepodařilo zjistit"):
            state = "warn"
        self.set_status_label(self.compare_value, result, state)

    def auto_initial_check(self) -> None:
        if self.path_input.text().strip():
            self.log("Provádím automatickou kontrolu po spuštění…")
            self.check_installation()
            self.check_github_version()

    def auto_refresh_from_path(self) -> None:
        if not self.path_input.text().strip():
            return
        self.log("Cesta změněna, provádím automatickou kontrolu…")
        self.check_installation()
        self.check_github_version()

    def check_installation(self) -> None:
        paths = self.get_paths()
        if not paths:
            return

        live_exists = paths["live"].exists()
        data_exists = paths["data"].exists()
        global_exists = paths["global_ini"].exists()
        local_version = read_local_version(paths["global_ini"])

        self.set_status_label(
            self.data_status_value,
            "Existuje" if data_exists else "Neexistuje",
            "ok" if data_exists else "error",
        )
        self.set_status_label(
            self.global_ini_status_value,
            "Existuje" if global_exists else "Neexistuje",
            "ok" if global_exists else "error",
        )
        self.set_status_label(
            self.local_version_value,
            local_version or "-",
            "ok" if local_version else "warn",
        )
        self.update_compare_label()

        self.log(f"Kontrola LIVE cesty: {paths['live']}")
        self.log("LIVE cesta existuje." if live_exists else "LIVE cesta neexistuje.")
        self.log("Adresář data existuje." if data_exists else "Adresář data neexistuje.")
        self.log(
            "global.ini nalezen." if global_exists else "global.ini nenalezen."
        )
        if local_version:
            self.log(f"Lokální verze češtiny: {local_version}")

    def check_github_version(self) -> None:
        self.log("Zjišťuji verzi na GitHubu…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            release_label, zip_version = fetch_latest_release_info()
            self.last_release_label = release_label
            self.last_remote_version = zip_version

            self.set_status_label(
                self.release_value,
                release_label or "-",
                "ok" if release_label else "warn",
            )
            self.set_status_label(
                self.remote_version_value,
                zip_version or "-",
                "ok" if zip_version else "warn",
            )
            self.update_compare_label()

            self.log(f"GitHub release: {release_label or 'nezjištěn'}")
            self.log(f"Verze v repozitáři: {zip_version or 'nezjištěna'}")
        except (HTTPError, URLError) as exc:
            QMessageBox.critical(self, "Chyba sítě", f"Nepodařilo se kontaktovat GitHub:\n{exc}")
            self.log(f"Chyba sítě: {exc}")
        except Exception as exc:
            QMessageBox.critical(self, "Chyba", f"Nepodařilo se zjistit verzi:\n{exc}")
            self.log(f"Obecná chyba: {exc}")
        finally:
            QApplication.restoreOverrideCursor()

    def install_or_update(self) -> None:
        paths = self.get_paths()
        if not paths:
            return

        live_path = paths["live"]
        if not live_path.exists():
            QMessageBox.warning(
                self,
                "LIVE nenalezeno",
                "Cílová složka LIVE neexistuje. Zadej správnou cestu ke hře nebo přímo ke složce LIVE.",
            )
            self.log(f"Instalace zrušena: LIVE neexistuje: {live_path}")
            return

        create_backup = self.backup_checkbox.isChecked()
        self.config["game_path"] = self.path_input.text().strip()
        self.config["create_backup"] = create_backup
        save_config(self.config)

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            paths["data"].mkdir(parents=True, exist_ok=True)
            self.log(f"Adresář data připraven: {paths['data']}")

            if create_backup and paths["localization"].exists():
                backup_path = paths["data"] / "Localization.bak"
                if backup_path.exists():
                    shutil.rmtree(backup_path)
                shutil.copytree(paths["localization"], backup_path)
                self.log(f"Vytvořena záloha: {backup_path}")

            with tempfile.TemporaryDirectory(prefix="sc-cestinator-install-") as tmp:
                tmp_dir = Path(tmp)
                zip_path = tmp_dir / "Localization.zip"
                unpack_dir = tmp_dir / "unzipped"
                unpack_dir.mkdir(parents=True, exist_ok=True)

                self.log("Stahuji Localization.zip…")
                download_file(LATEST_ZIP_URL, zip_path, timeout=120)
                self.log(f"Staženo do: {zip_path}")

                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(unpack_dir)
                self.log("Archiv byl rozbalen.")

                extracted_loc = unpack_dir / "Localization"
                if not extracted_loc.exists():
                    candidates = list(unpack_dir.rglob("Localization"))
                    extracted_loc = candidates[0] if candidates else None

                if not extracted_loc or not extracted_loc.exists():
                    raise RuntimeError("V archivu nebyla nalezena složka Localization.")

                target_loc = paths["localization"]
                if target_loc.exists():
                    shutil.rmtree(target_loc)
                    self.log(f"Původní Localization odstraněna: {target_loc}")

                shutil.copytree(extracted_loc, target_loc)
                self.log(f"Nová lokalizace zkopírována do: {target_loc}")

            local_version = read_local_version(paths["global_ini"])
            self.set_status_label(self.data_status_value, "Existuje", "ok")
            self.set_status_label(
                self.global_ini_status_value,
                "Existuje" if paths["global_ini"].exists() else "Neexistuje",
                "ok" if paths["global_ini"].exists() else "error",
            )
            self.set_status_label(
                self.local_version_value,
                local_version or "-",
                "ok" if local_version else "warn",
            )
            self.update_compare_label()

            QMessageBox.information(self, "Hotovo", "Čeština byla nainstalována / aktualizována.")
            self.log(f"Hotovo. Lokální verze po instalaci: {local_version or 'nezjištěna'}")

        except Exception as exc:
            QMessageBox.critical(self, "Chyba instalace", str(exc))
            self.log(f"Chyba instalace: {exc}")
        finally:
            QApplication.restoreOverrideCursor()

    def open_live_folder(self) -> None:
        paths = self.get_paths()
        if not paths:
            return
        self._open_path(paths["live"])

    def open_localization_folder(self) -> None:
        paths = self.get_paths()
        if not paths:
            return
        self._open_path(paths["localization"])

    def _open_path(self, path: Path) -> None:
        try:
            if not path.exists():
                QMessageBox.warning(self, "Cesta neexistuje", f"Tato cesta neexistuje:\n{path}")
                return
            os.system(f'xdg-open "{path}" >/dev/null 2>&1 &')
            self.log(f"Otevírám: {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Chyba", f"Nepodařilo se otevřít cestu:\n{exc}")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
