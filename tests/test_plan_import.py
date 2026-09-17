import math

from neuxelec.utils.plan_import import (
    build_trajectories_t1,
    hemisphere_from_lps_x,
    summarize_plan,
    theoretical_contacts,
)


def _plan():
    return {
        "source": "NeuroInspire",
        "n_trajectories": 2,
        "plan_info": {"software_version": "6.3.1"},
        "coordinate_system": {"reference_series_uid": "1.2.3", "reference_series_name": "701 T1"},
        "trajectories": [
            {"name": "AD", "reference_key": "DIXI-D08-12AM", "contact_count": 12,
             "entry_mm": [-63.2, -26.8, 19.4], "target_mm": [-20.0, -23.1, 26.8]},
            {"name": "AG", "reference_key": "DIXI-D08-12AM", "contact_count": 12,
             "entry_mm": [57.0, -19.0, 18.1], "target_mm": [16.2, -23.3, 27.2]},
        ],
    }


def test_hemisphere_from_lps_x():
    assert hemisphere_from_lps_x(30.0) == "L"   # LPS +x = Left
    assert hemisphere_from_lps_x(-30.0) == "R"
    assert hemisphere_from_lps_x(2.0) is None


def test_identity_mode_copies_coordinates_and_guesses_hemisphere():
    out = build_trajectories_t1(_plan(), "identity")
    assert [t["name"] for t in out] == ["AD", "AG"]
    assert out[0]["entry_t1_lps"] == [-63.2, -26.8, 19.4]
    assert out[0]["hemisphere_guess"] == "R" and out[1]["hemisphere_guess"] == "L"


def test_theoretical_contacts_spacing():
    pts = theoretical_contacts((0, 0, 0), (10, 0, 0), [3.5, 3.5])
    assert pts[0] == (10.0, 0.0, 0.0)
    assert math.isclose(pts[1][0], 6.5) and math.isclose(pts[2][0], 3.0)


def test_summary_mentions_reference():
    assert "701 T1" in summarize_plan(_plan())


def _euler(translation=(0.0, 0.0, 0.0), angle_z=0.0, center=(0.0, 0.0, 0.0)):
    import SimpleITK as sitk

    t = sitk.Euler3DTransform()
    t.SetCenter(center)
    t.SetRotation(0.0, 0.0, angle_z)
    t.SetTranslation(translation)
    return t


def test_identity_refinement_is_detected():
    from neuxelec.utils.plan_import import is_identity_transform

    assert is_identity_transform(_euler())
    assert not is_identity_transform(_euler(translation=(0.0, 2.0, 0.0)))
    assert not is_identity_transform(_euler(angle_z=math.radians(1.0)))


def test_manual_refinement_moves_points_the_other_way():
    """The console transform resamples the image, so a point takes the inverse.

    A refinement that shifts the sampling by +10 mm in x makes the anatomy
    appear 10 mm lower in x, so the trajectories must follow by -10 mm.
    """
    from neuxelec.utils.plan_import import apply_manual_refinement

    trajs = build_trajectories_t1(_plan(), "identity")
    moved = apply_manual_refinement(trajs, _euler(translation=(10.0, 0.0, 0.0)))

    for before, after in zip(trajs, moved):
        assert math.isclose(after["entry_t1_lps"][0], before["entry_t1_lps"][0] - 10.0,
                            abs_tol=1e-3)
        assert math.isclose(after["target_t1_lps"][0], before["target_t1_lps"][0] - 10.0,
                            abs_tol=1e-3)
        # the other axes are untouched
        assert math.isclose(after["entry_t1_lps"][1], before["entry_t1_lps"][1], abs_tol=1e-3)
        assert math.isclose(after["entry_t1_lps"][2], before["entry_t1_lps"][2], abs_tol=1e-3)


def test_manual_refinement_updates_the_hemisphere():
    from neuxelec.utils.plan_import import apply_manual_refinement

    trajs = build_trajectories_t1(_plan(), "identity")
    # +200 mm on the sampling pushes every point 200 mm the other way, well
    # past the midline, so both trajectories become right-sided.
    moved = apply_manual_refinement(trajs, _euler(translation=(200.0, 0.0, 0.0)))
    assert {t["hemisphere_guess"] for t in moved} == {"R"}
    assert all(t["entry_t1_lps"][0] < -5.0 for t in moved)


def test_manual_refinement_record_is_json_friendly():
    import json

    from neuxelec.utils.plan_import import describe_rigid_transform

    record = describe_rigid_transform(_euler(translation=(1.5, -2.0, 0.25),
                                             angle_z=math.radians(3.0)))
    json.dumps(record)
    assert record["translation_mm"] == [1.5, -2.0, 0.25]
    assert math.isclose(record["angles_deg"][2], 3.0, abs_tol=1e-3)
