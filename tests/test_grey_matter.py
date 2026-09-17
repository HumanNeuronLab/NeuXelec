"""Grey matter classification, the test behind the contact filter."""

import numpy as np

from neuxelec.utils.grey_matter import (
    grey_matter_flags,
    grey_matter_label_ids,
    is_csf_name,
    is_grey_matter_name,
    is_white_matter_name,
)


def test_cortex_and_deep_grey_are_grey_matter():
    for name in (
        "ctx-lh-superiortemporal",
        "ctx_rh_G_temp_sup-Lateral",
        "Left-Cerebral-Cortex",
        "Left-Hippocampus",
        "Right-Amygdala",
        "Left-Thalamus-Proper",
        "Left-Putamen",
        "Left-Insula",
        "Brain-Stem",
        "Left-Cerebellum-Cortex",
    ):
        assert is_grey_matter_name(name), name


def test_white_matter_is_excluded():
    for name in (
        "Left-Cerebral-White-Matter",
        "Right-Cerebral-White-Matter",
        "wm-lh-superiortemporal",
        "wm_rh_precentral",
        "Left-UnsegmentedWhiteMatter",
        "Left-Cerebellum-White-Matter",
        "CC_Posterior",
        "CC_Mid_Anterior",
        "WM-hypointensities",
    ):
        assert is_white_matter_name(name), name
        assert not is_grey_matter_name(name), name


def test_csf_and_background_are_excluded():
    for name in ("Left-Lateral-Ventricle", "3rd-Ventricle", "CSF",
                 "Left-choroid-plexus", "Left-vessel"):
        assert is_csf_name(name), name
        assert not is_grey_matter_name(name), name
    for name in ("Unknown", "", "background"):
        assert not is_grey_matter_name(name), name


def test_unknown_atlas_names_stay_visible():
    """An unfamiliar atlas must not hide contacts: showing too many is safe."""
    assert is_grey_matter_name("Region_42")
    assert is_grey_matter_name("some-custom-atlas-label")


def test_label_ids_skip_background():
    lut = {
        0: "Unknown",
        2: "Left-Cerebral-White-Matter",
        17: "Left-Hippocampus",
        1001: ("ctx-lh-bankssts", (25, 100, 40)),
        4: "Left-Lateral-Ventricle",
    }
    assert grey_matter_label_ids(lut) == {17, 1001}


class _FakeImage:
    """Just enough of a SimpleITK image: physical point to index."""

    def __init__(self, mapping):
        self._mapping = mapping

    def TransformPhysicalPointToIndex(self, point):  # noqa: N802 (sitk naming)
        return self._mapping[tuple(point)]


def test_flags_follow_the_dominant_region():
    # A 5x5x5 volume: hippocampus on one side, white matter on the other.
    volume = np.zeros((5, 5, 5), dtype=np.int32)
    volume[:, :, :2] = 17     # Left-Hippocampus
    volume[:, :, 2:] = 2      # Left-Cerebral-White-Matter
    lut = {2: "Left-Cerebral-White-Matter", 17: "Left-Hippocampus"}

    # sitk indexes (x, y, z); the volume is [z, y, x].
    image = _FakeImage({(0.0, 0.0, 0.0): (0, 2, 2), (1.0, 0.0, 0.0): (4, 2, 2)})
    flags = grey_matter_flags(image, volume, lut, [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)])
    assert flags == [True, False]


def test_point_outside_the_parcellation_stays_visible():
    volume = np.full((3, 3, 3), 17, dtype=np.int32)
    lut = {17: "Left-Hippocampus"}

    class _Raising:
        def TransformPhysicalPointToIndex(self, point):  # noqa: N802
            raise RuntimeError("outside the image")

    assert grey_matter_flags(_Raising(), volume, lut, [(9.0, 9.0, 9.0)]) == [True]


def test_no_grey_label_in_the_lut_keeps_everything_visible():
    volume = np.full((3, 3, 3), 2, dtype=np.int32)
    lut = {2: "Left-Cerebral-White-Matter"}
    image = _FakeImage({(0.0, 0.0, 0.0): (1, 1, 1)})
    assert grey_matter_flags(image, volume, lut, [(0.0, 0.0, 0.0)]) == [True]


def test_numpy_array_of_points_is_accepted():
    """The oblique page projects contacts as a numpy (N, 3) array.

    Testing the truth value of such an array raises, so the function must never
    do it. This is the shape that broke the oblique slice in 1.2.0.
    """
    volume = np.zeros((5, 5, 5), dtype=np.int32)
    volume[:, :, :2] = 17     # Left-Hippocampus
    volume[:, :, 2:] = 2      # Left-Cerebral-White-Matter
    lut = {2: "Left-Cerebral-White-Matter", 17: "Left-Hippocampus"}
    points = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=np.float64)
    image = _FakeImage({(0.0, 0.0, 0.0): (0, 2, 2), (1.0, 0.0, 0.0): (4, 2, 2)})

    assert grey_matter_flags(image, volume, lut, points) == [True, False]


def test_no_points_at_all():
    volume = np.zeros((3, 3, 3), dtype=np.int32)
    assert grey_matter_flags(_FakeImage({}), volume, {}, None) == []
    assert grey_matter_flags(_FakeImage({}), volume, {}, []) == []
    assert grey_matter_flags(_FakeImage({}), volume, {}, np.empty((0, 3))) == []
