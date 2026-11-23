import logging
import os
from pathlib import Path
from typing import Callable, Iterable

from env_sg import DB_Config
from maya import cmds

from core.asset import paths_for_asset
from core.shotgrid import ShotGrid
from core.versioning import next_version, versioned_filename
from dcc.maya.util.selection import maintain_selection

from .build import RigBuilder, RigDefinition
from .progress import ProgressStep, TestProgressManager
from .test import RIG_BUILD_TESTS, RigBuildTest, TestRunner

log = logging.getLogger(__name__)

EXPORTED_GEO_SET = "rig_geo_grp"


class RigPublisher:
    def __init__(self) -> None:
        self._conn = ShotGrid.connect(DB_Config)

        self.root_progress = ProgressStep("Build, Publish and Test")
        self.build_progress = ProgressStep("Rig Build", 15)
        self.root_progress.add_child_step(self.build_progress)
        self.test_progress = ProgressStep("Rig Test", 1)
        self.root_progress.add_child_step(self.test_progress)
        self.publish_progress = ProgressStep("Rig Publish", 2)
        self.root_progress.add_child_step(self.publish_progress)
        self.test_progress_manager: TestProgressManager | None = None
        self._test_view_update_callback: Callable[[RigBuildTest, bool], None] | None = (
            None
        )

    def connect_progress(self, progress_slot: Callable[[float], None]):
        """Stores the slot (e.g., progress_bar.update_progress) to connect later."""
        self.root_progress.connect_progress(progress_slot)

    def connect_test_view(
        self, test_view_update_callback: Callable[[RigBuildTest, bool], None]
    ):
        self._test_view_update_callback = test_view_update_callback

    def _on_test_run(self, test: RigBuildTest, passed: bool):
        if self.test_progress_manager is not None:
            self.test_progress_manager.update_progress_from_test_run(test, passed)
        if self._test_view_update_callback is not None:
            self._test_view_update_callback(test, passed)

    def _build_rig(self, rig: RigDefinition) -> bool:
        rig_builder = RigBuilder()
        rig_builder.connect_progress(self.build_progress.update_progress)
        rig_build_result = rig_builder.build_rig(rig)
        cmds.dgdirty(allPlugs=True)
        return rig_build_result

    def _run_tests(self, tests: Iterable[type[RigBuildTest]]) -> bool:
        self.build_progress.finish_step()
        test_objects = [test() for test in tests]
        self.test_progress_manager = TestProgressManager(
            test_objects,
        )
        self.test_progress_manager.progress_changed.connect(
            self.test_progress.update_progress
        )
        test_runner = TestRunner(test_objects, self._on_test_run)
        return test_runner.run_tests()

    def _publish_rig_model(self, rig: RigDefinition):
        RIG_GEO_PATH = "/rig/geo"
        from dcc.maya.publish.usdchaser.export import (
            ExportChaser,
            ExportChaserMode,
        )

        publish_asset = self._conn.get_asset(name=rig.name)
        publish_asset_paths = paths_for_asset(publish_asset)
        rig_model_publish_path = publish_asset_paths.rig_path / "usd/geo.usd"
        with maintain_selection():
            cache_sets = cmds.ls("::" + EXPORTED_GEO_SET, sets=True)
            cmds.select(*cache_sets, replace=True)
            cmds.mayaUSDExport(  # type: ignore
                selection=True,
                chaser=[ExportChaser.ID],
                file=str(rig_model_publish_path),
                chaserArgs=[(ExportChaser.ID, "mode", ExportChaserMode.RIG)],
                exportCollectionBasedBindings=True,
                exportMaterialCollections=True,
                materialCollectionsPath=str(RIG_GEO_PATH),
                shadingMode="useRegistry",
            )
        log.info(
            f"PUBLISH: {rig.name} rig model USD published to {rig_model_publish_path}"
        )

    def _publish_rig(
        self, rig: RigDefinition, publish_message: str | None = None
    ) -> bool:
        publish_asset = self._conn.get_asset(name=rig.name)
        publish_asset_paths = paths_for_asset(publish_asset)
        rig_publish_path = publish_asset_paths.rig_path
        rig_versions_path = publish_asset_paths.rig_versions_path

        version_number = next_version(
            publish_asset_paths.rig_versions_path, stem=rig.name, ext="mb"
        )
        rig_version_filepath = rig_versions_path / versioned_filename(
            stem=rig.name, ext="mb", version=version_number
        )

        cmds.select("rig")
        cmds.file(
            str(rig_version_filepath),
            exportSelected=True,
            type="mayaBinary",
            options="v=0;",
            constructionHistory=True,
            expressions=True,
            constraints=True,
            shader=True,
            channels=True,
            preserveReferences=True,
            exportUnloadedReferences=False,
        )
        log.info(
            f"PUBLISH: {rig.name} was successfully built and published to {rig_version_filepath}"
        )
        rig_publish_filepath = (rig_publish_path / rig.name).with_suffix(".mb")
        if rig_publish_filepath.is_symlink():
            rig_publish_filepath.unlink()
        elif rig_publish_filepath.exists():
            log.error(
                f"PUBLISH: The file at {rig_publish_filepath} already exists and is not a symlink! To avoid data loss symlink creation/updating was cancelled."
            )
            return False
        symlink_relative_path = Path(
            os.path.relpath(rig_version_filepath, rig_publish_filepath.parent)
        )
        rig_publish_filepath.symlink_to(symlink_relative_path)
        log.info(f"PUBLISH: {rig.name} rig symlink updated to {rig_version_filepath}")
        self.publish_progress.finish_step()
        return True

    def _fbx_export(self, rig: RigDefinition) -> None:
        from .fbx_publish import publish_ue_rig

        publish_asset = self._conn.get_asset(name=rig.name)
        publish_asset_paths = paths_for_asset(publish_asset)

        rig_publish_path = publish_asset_paths.rig_path
        fbx_publish_path = rig_publish_path / f"{rig.name}.fbx"

        fbx_publish_path.parent.mkdir(parents=True, exist_ok=True)

        publish_ue_rig(
            path=fbx_publish_path,
            model="geo",
            skel="root_C0_root_jnt",
        )

        log.info(f"PUBLISH: {rig.name} FBX successfully exported to {fbx_publish_path}")

    def build_test_and_publish(
        self, rig: RigDefinition, publish_message: str | None = None
    ):
        build_complete = self._build_rig(rig)
        if not build_complete:
            log.error(f"{rig.name} failed to build properly and wasn't published!")
            return
        tests_passed = self._run_tests(RIG_BUILD_TESTS)
        if not tests_passed:
            log.error(
                f"{rig.name} failed one or more required tests and wasn't published!"
            )
            return
        else:
            self._publish_rig(rig, publish_message)
            self._publish_rig_model(rig)
            self._fbx_export(rig)
