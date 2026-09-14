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
