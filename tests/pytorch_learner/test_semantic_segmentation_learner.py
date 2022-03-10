from typing import Any, Callable
import unittest
from tempfile import TemporaryDirectory
from uuid import uuid4
import logging

import numpy as np

from rastervision.core.data import (
    ClassConfig, DatasetConfig, RasterioSourceConfig, MultiRasterSourceConfig,
    SubRasterSourceConfig, ReclassTransformerConfig, SceneConfig,
    SemanticSegmentationLabelSourceConfig)
from rastervision.core.rv_pipeline import SemanticSegmentationConfig
from rastervision.pytorch_backend import PyTorchSemanticSegmentationConfig
from rastervision.pytorch_learner import (
    SemanticSegmentationModelConfig, SolverConfig,
    SemanticSegmentationGeoDataConfig, PlotOptions, GeoDataWindowConfig)
from tests import data_file_path


def make_scene(num_channels: int, num_classes: int) -> SceneConfig:
    path = data_file_path('multi_raster_source/const_100_600x600.tiff')
    rs_cfgs_img = []
    for _ in range(num_channels):
        rs_cfg = RasterioSourceConfig(
            uris=[path],
            channel_order=[0],
            transformers=[
                ReclassTransformerConfig(
                    mapping={100: np.random.randint(0, 256)})
            ])
        rs_cfgs_img.append(rs_cfg)
    rs_cfg_img = MultiRasterSourceConfig(
        raster_sources=[
            SubRasterSourceConfig(raster_source=rs_cfg, target_channels=[i])
            for i, rs_cfg in enumerate(rs_cfgs_img)
        ],
        channel_order=list(range(num_channels)))
    rs_cfg_label = RasterioSourceConfig(
        uris=[path],
        channel_order=[0],
        transformers=[
            ReclassTransformerConfig(
                mapping={100: np.random.randint(0, num_classes)})
        ])
    scene_cfg = SceneConfig(
        id=str(uuid4()),
        raster_source=rs_cfg_img,
        label_source=SemanticSegmentationLabelSourceConfig(
            raster_source=rs_cfg_label))
    return scene_cfg


class TestSemanticSegmentationLearner(unittest.TestCase):
    def assertNoError(self, fn: Callable, msg: str = ''):
        try:
            fn()
        except Exception:
            self.fail(msg)

    def test_learner(self):
        self.assertNoError(lambda: self._test_learner(3, None))
        self.assertNoError(
            lambda: self._test_learner(6, [(0, 1, 2), (3, 4, 5)]))

    def _test_learner(self,
                      num_channels: int,
                      channel_display_groups: Any,
                      num_classes: int = 5):
        """Tests whether the learner can be instantiated correctly and
        produce plots."""
        logging.disable(logging.CRITICAL)

        with TemporaryDirectory() as tmp_dir:
            class_config = ClassConfig(
                names=[f'class_{i}' for i in range(num_classes)])
            dataset_cfg = DatasetConfig(
                class_config=class_config,
                train_scenes=[
                    make_scene(
                        num_channels=num_channels, num_classes=num_classes)
                    for _ in range(4)
                ],
                validation_scenes=[
                    make_scene(
                        num_channels=num_channels, num_classes=num_classes)
                    for _ in range(2)
                ],
                test_scenes=[])
            data_cfg = SemanticSegmentationGeoDataConfig(
                scene_dataset=dataset_cfg,
                window_opts=GeoDataWindowConfig(size=20, stride=20),
                class_names=class_config.names,
                class_colors=class_config.colors,
                plot_options=PlotOptions(
                    channel_display_groups=channel_display_groups),
                num_workers=0)
            backend_cfg = PyTorchSemanticSegmentationConfig(
                data=data_cfg,
                model=SemanticSegmentationModelConfig(pretrained=False),
                solver=SolverConfig(),
                log_tensorboard=False)
            pipeline_cfg = SemanticSegmentationConfig(
                root_uri=tmp_dir, dataset=dataset_cfg, backend=backend_cfg)
            pipeline_cfg.update()
            backend = backend_cfg.build(pipeline_cfg, tmp_dir)
            learner = backend.learner_cfg.build(tmp_dir, training=True)
            learner.plot_dataloaders()
            learner.plot_predictions(split='valid')


if __name__ == '__main__':
    unittest.main()