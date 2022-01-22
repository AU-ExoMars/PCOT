from passthrough.extensions.pt.datetime import PDSDatetime


class ApplicableCameraMixin:
    """Allow `DataProduct`s to evaluate applicability based on `psa:Sub-Instrument`.

    Note: both products must be able to resolve the "camera" meta key, which is not
    defined in DataProduct's base map (but is for instance mapped to
    `psa:Sub-Instrument/psa:identifier` for PanCam subclass maps). As this is a pretty
    niche feature, we might want to move this mixin to the pancam subpackage in the
    future.
    """

    def is_applicable(self, other: "ApplicableCameraMixin"):
        return other.meta.camera == self.meta.camera  # type: ignore


class SortByStartTimeMixin:
    """Allow `DataProduct`s to be sorted by `pds:start_date_time`."""

    def __lt__(self, other: "SortByStartTimeMixin"):
        return (
            PDSDatetime(self.meta.start).datetime  # type: ignore
            < PDSDatetime(other.meta.start).datetime  # type: ignore
        )