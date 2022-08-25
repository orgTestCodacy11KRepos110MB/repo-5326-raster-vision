from typing import Optional, List

from rastervision.pipeline.config import (Config, ConfigError, register_config,
                                          Field)
from rastervision.core.data.raster_source import RasterSourceConfig
from rastervision.core.data.label_source import LabelSourceConfig
from rastervision.core.data.label_store import LabelStoreConfig
from rastervision.core.data.scene import Scene
from rastervision.core.data.vector_source import GeoJSONVectorSource
from rastervision.core.data.utils import geojson_to_geoms


def scene_config_upgrader(cfg_dict: dict, version: int) -> dict:
    if version == 4:
        try:
            # removed in version 5
            if cfg_dict.get('aoi_geometries') is not None:
                raise ConfigError(
                    'SceneConfig.aoi_geometries is deprecated. '
                    'To use this config again, manually edit it to use '
                    'SceneConfig.aoi_uris instead.')
            del cfg_dict['aoi_geometries']
        except KeyError:
            pass
    return cfg_dict


@register_config('scene', upgrader=scene_config_upgrader)
class SceneConfig(Config):
    """Config for Scene which comprises raster data and labels for an AOI."""
    id: str
    raster_source: RasterSourceConfig
    label_source: Optional[LabelSourceConfig] = None
    label_store: Optional[LabelStoreConfig] = None
    aoi_uris: Optional[List[str]] = Field(
        None,
        description='List of URIs of GeoJSON files that define the AOIs for '
        'the scene. Each polygon defines an AOI which is a piece of the scene '
        'that is assumed to be fully labeled and usable for training or '
        'validation. The AOIs are assumed to be in EPSG:4326 coordinates.')

    def build(self, class_config, tmp_dir, use_transformers=True) -> Scene:
        raster_source = self.raster_source.build(
            tmp_dir, use_transformers=use_transformers)
        crs_transformer = raster_source.get_crs_transformer()
        extent = raster_source.get_extent()

        label_source = (self.label_source.build(class_config, crs_transformer,
                                                extent, tmp_dir)
                        if self.label_source is not None else None)
        label_store = (self.label_store.build(class_config, crs_transformer,
                                              extent, tmp_dir)
                       if self.label_store is not None else None)

        aoi_polygons = []
        if self.aoi_uris is not None:
            for uri in self.aoi_uris:
                aoi_geojson = GeoJSONVectorSource(
                    uri=uri,
                    ignore_crs_field=True,
                    crs_transformer=crs_transformer).get_geojson()
                aoi_polygons += list(geojson_to_geoms(aoi_geojson))

        return Scene(
            self.id,
            raster_source,
            ground_truth_label_source=label_source,
            prediction_label_store=label_store,
            aoi_polygons=aoi_polygons)

    def update(self, pipeline=None):
        super().update()

        self.raster_source.update(pipeline=pipeline, scene=self)
        if self.label_source is not None:
            self.label_source.update(pipeline=pipeline, scene=self)
        if self.label_store is None and pipeline is not None:
            self.label_store = pipeline.get_default_label_store(scene=self)
        if self.label_store is not None:
            self.label_store.update(pipeline=pipeline, scene=self)
