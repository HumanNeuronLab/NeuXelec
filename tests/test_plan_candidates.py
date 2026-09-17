"""An electrode that is already reconstructed stops being proposed.

The plan-assisted labelling offers the planned trajectory nearest to the deep
contact just picked. Once an electrode has been reconstructed, offering it again
can only produce a name the reconstruction would then refuse as a duplicate, so
it leaves the list.
"""

import pytest

from neuxelec.pages.reconstruction_page import ReconstructionPage


def _trajectory(name, target_x):
    """A straight trajectory along x, entry further out than the target."""
    return {
        "name": name,
        "reference_key": "DIXI-D08-12AM",
        "contact_count": 8,
        "contact_separation_mm": 1.5,
        "contact_length_mm": 2.0,
        "target_t1_lps": [target_x, 0.0, 0.0],
        "entry_t1_lps": [target_x * 4.0, 0.0, 0.0],
    }


class _State:
    def __init__(self, trajectories):
        self.plan = {"trajectories_t1": trajectories}
        self.electrodes = []


@pytest.fixture
def page():
    page = ReconstructionPage.__new__(ReconstructionPage)
    page.state = _State(
        [
            _trajectory("AD", -10.0),  # left
            _trajectory("BD", -20.0),  # left, further out
            _trajectory("AG", 10.0),  # right
        ]
    )
    page._electrodes = page.state.electrodes
    page._editing_elec_id = None
    page._midline_x = lambda: 0.0
    return page


def _names(ranked):
    return [tr.get("name") for _d, tr in ranked]


def test_every_trajectory_is_a_candidate_when_nothing_is_reconstructed(page):
    assert _names(page._rank_plan_trajectories([-11.0, 0.0, 0.0])) == ["AD", "BD", "AG"]


def test_a_reconstructed_electrode_leaves_the_list(page):
    page._electrodes.append({"name": "AD"})
    assert _names(page._rank_plan_trajectories([-11.0, 0.0, 0.0])) == ["BD", "AG"]


def test_the_match_is_the_one_used_for_duplicates(page):
    """Same normalisation: case and repeated spaces do not make a new electrode."""
    page._electrodes.append({"name": "  a d  "})
    page.state.plan["trajectories_t1"][0]["name"] = "A D"
    assert "A D" not in _names(page._rank_plan_trajectories([-11.0, 0.0, 0.0]))


def test_an_electrode_without_a_name_excludes_nothing(page):
    page._electrodes.append({"name": "   "})
    assert len(page._rank_plan_trajectories([-11.0, 0.0, 0.0])) == 3


def test_the_electrode_being_edited_stays_a_candidate(page):
    """Re-picking the axis of an electrode must still match its own trajectory."""
    page._electrodes.append({"name": "AD"})
    page._editing_elec_id = 0
    assert "AD" in _names(page._rank_plan_trajectories([-11.0, 0.0, 0.0]))


def test_other_electrodes_stay_excluded_while_editing(page):
    page._electrodes.extend([{"name": "AD"}, {"name": "BD"}])
    page._editing_elec_id = 0
    names = _names(page._rank_plan_trajectories([-11.0, 0.0, 0.0]))
    assert "AD" in names
    assert "BD" not in names


def test_the_filter_can_be_turned_off(page):
    page._electrodes.append({"name": "AD"})
    ranked = page._rank_plan_trajectories([-11.0, 0.0, 0.0], skip_reconstructed=False)
    assert _names(ranked) == ["AD", "BD", "AG"]


def test_the_hemisphere_firewall_still_applies(page):
    """Filtering the reconstructed ones must not weaken the side restriction."""
    names = _names(page._rank_plan_trajectories([-11.0, 0.0, 0.0], restrict_hemi="R"))
    assert names == ["AD", "BD"]  # LPS: x < 0 is R in this synthetic midline

    page._electrodes.append({"name": "AD"})
    assert _names(page._rank_plan_trajectories([-11.0, 0.0, 0.0], restrict_hemi="R")) == ["BD"]


def test_all_electrodes_reconstructed_leaves_no_candidate(page):
    page._electrodes.extend([{"name": "AD"}, {"name": "BD"}, {"name": "AG"}])
    assert page._rank_plan_trajectories([-11.0, 0.0, 0.0]) == []


def test_the_nearest_candidate_is_still_first(page):
    """Ordering by distance survives the filter.

    AD spans x in [-40, -10] and BD spans [-80, -20], so a point at -50 sits on
    BD's segment and 10 mm away from AD's nearest end.
    """
    ranked = page._rank_plan_trajectories([-50.0, 0.0, 0.0])
    assert _names(ranked)[0] == "BD"
    page._electrodes.append({"name": "BD"})
    assert _names(page._rank_plan_trajectories([-50.0, 0.0, 0.0]))[0] == "AD"
