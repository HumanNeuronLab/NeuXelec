from __future__ import annotations

import logging
import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget

from . import __version__
from .logging_config import configure_logging
from .updater import UpdateChecker, prompt_and_install
from .utils.resources import resource_path

logger = logging.getLogger(__name__)

# When running as a PyInstaller bundle, Qt resolves url() in stylesheets
# relative to the CWD. Set CWD to _MEIPASS so relative paths like
# url(resources/images/...) resolve correctly in all stylesheets.
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    os.chdir(sys._MEIPASS)  # type: ignore[attr-defined]

from .ui.project_loading_window import ProjectLoadingWindow


def _resolve_project_files(
    data: dict,
    project_path: str,
    mode: str,
    project_loader: ProjectLoadingWindow | None = None,
) -> bool:
    """Find the project's files again before a single image is read.

    A project stores absolute paths. Moving the patient folder, changing a drive
    letter or opening the project on another machine invalidates all of them, and
    until now every failed read was swallowed silently: the project opened with
    its electrodes but no images, and said nothing.

    Everything that can be resolved on its own is, quietly. The user is asked
    only when a file the project actually needs is still missing. Returns False
    when they chose not to open the project at all.
    """
    from PySide6.QtWidgets import QDialog

    from .project_paths import apply_resolutions, resolve_project_paths

    try:
        report = resolve_project_paths(data, project_path)
    except Exception:
        logger.warning("Could not check the project files", exc_info=True)
        return True

    update_project = False
    if report.needs_user_input:
        from .ui.relocate_files_dialog import RelocateFilesDialog

        accepted = True
        if project_loader is not None:
            project_loader.hide()
        try:
            dialog = RelocateFilesDialog(
                report,
                offer_project_update=(str(mode).lower().strip() == "edit"),
            )
            accepted = dialog.exec() == QDialog.Accepted
            update_project = accepted and dialog.update_project_requested
        except Exception:
            # A broken dialog must not make the project unopenable.
            logger.warning("Could not ask where the missing files went", exc_info=True)
        finally:
            if project_loader is not None:
                project_loader.show()
                QApplication.processEvents()

        if not accepted:
            return False

    changed = apply_resolutions(data, report)
    if changed:
        logger.info("Project paths resolved: %s", report.summary())

    # The project file is only rewritten when the user asked for it in the
    # dialog. A silent relocation needs no rewrite: the relative paths keep
    # working, and the next ordinary save records the new locations anyway.
    if changed and update_project:
        try:
            from .project_io import write_project_dict

            write_project_dict(data, project_path)
        except Exception:
            logger.warning("Could not update the project file", exc_info=True)
    return True


def _set_windows_app_id() -> None:
    """
    Give NeuXelec its own Windows AppUserModelID.

    Without an explicit AppUserModelID, Windows groups the window under the
    host process (python.exe / the bootloader) and uses that process icon in
    the taskbar instead of the NeuXelec brain logo. Setting a stable, unique
    ID makes Windows treat NeuXelec as its own application and use the icon we
    assign with QApplication.setWindowIcon().
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("NeuXelec.NeuXelec.App.1")
    except Exception:
        pass


def _app_icon() -> QIcon:
    """Load the NeuXelec brain logo as the application/taskbar icon."""
    ico = resource_path("resources/images/brain_logo.ico")
    if ico.exists():
        return QIcon(str(ico))
    return QIcon(str(resource_path("resources/images/brain_logo.png")))


def _center_window_on_screen(
    window: QWidget,
    app: QApplication,
) -> None:
    """
    Center a window in the available geometry of the primary screen.
    """
    screen = app.primaryScreen()

    if screen is None:
        return

    available = screen.availableGeometry()
    geometry = window.frameGeometry()
    geometry.moveCenter(available.center())

    window.move(geometry.topLeft())


def _install_exception_logging() -> None:
    """Log any uncaught exception before the interpreter exits.

    Without this, an unexpected error in the packaged (windowed) executable
    disappears silently. Logging it to the rotating log file makes post-mortem
    diagnosis possible from a user's machine.
    """
    previous_hook = sys.excepthook

    def _hook(exc_type, exc_value, exc_traceback):  # noqa: ANN001
        logger.critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        previous_hook(exc_type, exc_value, exc_traceback)

    sys.excepthook = _hook


def main() -> int:
    # Configure file logging first so everything below is captured.
    configure_logging()
    _install_exception_logging()
    logger.info("NeuXelec starting up")

    # Must run before QApplication so Windows uses our taskbar identity/icon.
    _set_windows_app_id()

    app = QApplication(sys.argv)
    app.setWindowIcon(_app_icon())

    # Check for a newer version in the background (non-blocking, fail-silent).
    # If one is published in the website manifest, the user is offered to
    # download and install it. Kept referenced for the whole app lifetime.
    update_checker = UpdateChecker(__version__)
    update_checker.update_available.connect(
        lambda info: prompt_and_install(info, app.activeWindow())
    )
    update_checker.start()

    # ------------------------------------------------------------------
    # Initial software launch loader
    # ------------------------------------------------------------------
    # Important:
    # The heavy NeuXelec imports are deliberately performed after this
    # loading window is shown. This allows the brain loader to appear
    # immediately when the software starts.
    launch_loader = ProjectLoadingWindow(
        "NEUXELEC",
        "Starting application",
    )
    launch_loader.show_loading()

    try:
        launch_loader.set_progress(
            0.18,
            "Loading interface components",
        )

        # Keep these imports inside main(), after displaying the loader.
        # Importing NeuxelecWindow also imports the heavy 3D/oblique modules.
        from .main_window import NeuxelecWindow
        from .project_io import create_empty_project_file, load_project_json
        from .ui.startup_dialog import StartupDialog

        launch_loader.set_progress(
            0.72,
            "Opening project selection",
        )

        launch_loader.set_progress(
            0.98,
            "Ready",
        )

        QApplication.processEvents()
        launch_loader.close()

    except Exception:
        launch_loader.close()
        raise

    # ------------------------------------------------------------------
    # Create / Open project selection loop
    # ------------------------------------------------------------------
    while True:
        startup = StartupDialog()

        if startup.exec() == 0 or not startup.result_data:
            return 0

        info = startup.result_data

        action = info["action"]
        project_path = info["project_path"]
        mode = info["mode"]
        patient_id = info["patient_id"]

        if action == "create":
            loader_title = "CREATING PROJECT"
            loader_message = "Initializing patient workspace"
        else:
            loader_title = "OPENING PROJECT"
            loader_message = "Preparing NeuXelec workspace"

        project_loader = ProjectLoadingWindow(
            loader_title,
            loader_message,
        )
        project_loader.show_loading()

        restart_requested = {"value": False}

        try:
            if action == "create":
                project_loader.set_progress(
                    0.14,
                    "Creating project file",
                )
                create_empty_project_file(
                    project_path,
                    patient_id,
                )

            project_loader.set_progress(
                0.24,
                "Reading project data",
            )
            data = load_project_json(project_path)

            project_loader.set_progress(
                0.30,
                "Checking project files",
            )
            if not _resolve_project_files(data, project_path, mode, project_loader):
                # The user preferred not to open a project whose files are
                # missing: back to the project selection, nothing was loaded.
                project_loader.close()
                continue

            project_loader.set_progress(
                0.36,
                "Building NeuXelec interface",
            )
            window = NeuxelecWindow()
            window.resize(1400, 800)

            try:
                window.restart_requested.connect(
                    lambda: restart_requested.__setitem__(
                        "value",
                        True,
                    )
                )
            except Exception:
                pass

            # Center the Main Window only after its final startup size is applied.
            _center_window_on_screen(
                window,
                app,
            )

            project_loader.set_progress(
                0.52,
                "Loading patient data",
            )
            window.load_project_data(
                data,
                project_path=project_path,
                mode=mode,
                progress_callback=project_loader.set_progress,
            )

            project_loader.set_progress(
                0.98,
                "Workspace ready",
            )

            window.show()
            window.raise_()
            window.activateWindow()

            QApplication.processEvents()
            project_loader.close()

            app.exec()

            if restart_requested["value"]:
                # Fully destroy the current window (and its VTK QtInteractors)
                # before building the next project window.
                #
                # On return-to-menu the event loop keeps running, so the old
                # window is only hidden, never destroyed. Its OpenGL render
                # windows linger and VTK later raises "wglMakeCurrent failed"
                # errors that corrupt the 3D views of the next project.
                #
                # Deleting the window here lets Qt finalize the VTK widgets at
                # a safe time (between event loops, with no active rendering),
                # which is exactly what the per-page cleanup code relies on.
                try:
                    window.hide()
                    window.setParent(None)
                    window.deleteLater()
                except Exception:
                    pass

                window = None
                QApplication.processEvents()

                import gc

                gc.collect()
                QApplication.processEvents()

                continue

            return 0

        except Exception:
            project_loader.close()
            raise


if __name__ == "__main__":
    raise SystemExit(main())
