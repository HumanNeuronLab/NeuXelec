"""Binding TRC channels to reconstructed electrodes.

Everything else in the EEG reader fails loudly. This is the part that can fail
quietly: bind HAG3 to the wrong contact and the trace shown for a hippocampal
electrode comes from somewhere else, with nothing on screen to say so.

The names here are the real ones from a recorded session, 198 channels, 16
electrodes, fourteen channels that were never in a brain.
"""

from __future__ import annotations

import pytest

from neuxelec.utils.eeg_channel_match import (
    ElectrodeMatch,
    MatchReport,
    bind,
    group_trc_channels,
    is_contact_channel,
    normalise,
    propose,
    split_channel,
)


def electrode(name: str, contacts: int) -> dict:
    return {"name": name, "contacts_lps": [[0.0, 0.0, 0.0]] * contacts}


@pytest.mark.parametrize(
    "name, expected",
    [
        ("HAG1", ("HAG", 1)),
        ("IAG18", ("IAG", 18)),
        ("TPG8", ("TPG", 8)),
        ("A'3", ("A'", 3)),       # the other common Micromed convention
        ("HAG 2", ("HAG", 2)),
    ],
)
def test_a_channel_splits_into_electrode_and_contact(name, expected):
    assert split_channel(name) == expected


@pytest.mark.parametrize(
    "name",
    ["MKR1+", "MKR4+", "X1", "X8", "ECG+", "ECG-", "EMG2", "EOG1", "RESP", "REF"],
)
def test_what_was_never_in_a_brain_is_not_a_contact(name):
    """Fourteen of the 198 on that session. Reported as unmatched they would be
    fourteen false alarms per patient."""
    assert is_contact_channel(name) is False
    assert split_channel(name) is None


def test_a_contact_starting_with_x_is_still_a_contact():
    """The rule is on the whole name: X1 is an unused input, XG1 an electrode."""
    assert split_channel("XG1") == ("XG", 1)


@pytest.mark.parametrize(
    "a, b",
    [("HAG", "hag"), ("HAG", "H_A_G"), ("HAG", "HA-G"), ("IAD", "i.a.d")],
)
def test_one_electrode_written_four_ways_is_one_electrode(a, b):
    assert normalise(a) == normalise(b)


def test_the_real_montage_groups_into_sixteen_electrodes():
    channels = []
    for prefix, count in [
        ("TPG", 8), ("AG", 9), ("HAG", 9), ("TBG", 12), ("TSG", 5), ("OFG", 8),
        ("OPG", 8), ("CAG", 12), ("FLG", 8), ("FMG", 15), ("IAG", 18),
        ("IMG", 18), ("IPG", 18), ("AD", 9), ("HAD", 9), ("IAD", 18),
    ]:
        channels += [f"{prefix}{i}" for i in range(1, count + 1)]
    channels += ["MKR1+", "MKR2+", "MKR3+", "MKR4+", "ECG+", "ECG-"]
    channels += [f"X{i}" for i in range(1, 9)]

    groups, ignored = group_trc_channels(channels)
    assert len(groups) == 16
    assert len(ignored) == 14
    assert len(channels) == 198


def test_an_exact_name_matches_and_counts_its_pairs():
    report = propose([f"HAG{i}" for i in range(1, 10)], [electrode("HAG", 9)])
    one = report.electrodes[0]
    assert one.matched
    assert one.bipolar_pairs() == [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9)]
    assert report.total_pairs == 8
    assert report.warnings() == []


def test_a_contact_missing_in_the_middle_costs_two_pairs():
    """The number a user actually needs: one hole, two pairs gone."""
    channels = [f"HAG{i}" for i in range(1, 10) if i != 5]
    report = propose(channels, [electrode("HAG", 9)])
    one = report.electrodes[0]
    assert one.missing_in_trc == [5]
    assert (4, 5) not in one.bipolar_pairs()
    assert (5, 6) not in one.bipolar_pairs()
    assert len(one.bipolar_pairs()) == 6  # eight would be the full shaft


def test_more_contacts_localised_than_recorded_is_named_and_counted():
    report = propose([f"AG{i}" for i in range(1, 10)], [electrode("AG", 12)])
    assert report.electrodes[0].missing_in_trc == [10, 11, 12]
    assert "localised but not recorded" in " ".join(report.warnings())


def test_more_recorded_than_localised_is_the_other_warning():
    report = propose([f"AG{i}" for i in range(1, 13)], [electrode("AG", 9)])
    assert report.electrodes[0].extra_in_trc == [10, 11, 12]
    assert "beyond the" in " ".join(report.warnings())


def test_an_electrode_absent_from_the_recording_is_reported():
    report = propose([f"HAG{i}" for i in range(1, 10)], [electrode("ZZZ", 6)])
    assert report.unmatched[0].recon_name == "ZZZ"
    assert "no channel found" in " ".join(report.warnings())


def test_a_recorded_electrode_nobody_reconstructed_is_reported():
    report = propose(
        [f"HAG{i}" for i in range(1, 10)] + [f"OFG{i}" for i in range(1, 9)],
        [electrode("HAG", 9)],
    )
    assert report.unused_trc_prefixes == ["OFG"]
    assert "no electrode of that name" in " ".join(report.warnings())


def test_nothing_is_bound_twice():
    """A prefix serves one electrode. Taking it releases it from the other."""
    channels = [f"HAG{i}" for i in range(1, 10)]
    report = propose(channels, [electrode("HAG", 9), electrode("HAG_bis", 9)])
    bind(report, "HAG_bis", "HAG", channels)

    holders = [e.recon_name for e in report.electrodes if e.trc_prefix == "HAG"]
    assert holders == ["HAG_bis"]
    assert report.electrodes[0].trc_prefix is None


def test_unbinding_puts_the_prefix_back_in_the_unused_list():
    channels = [f"HAG{i}" for i in range(1, 10)]
    report = propose(channels, [electrode("HAG", 9)])
    bind(report, "HAG", None, channels)
    assert report.electrodes[0].matched is False
    assert report.unused_trc_prefixes == ["HAG"]


def test_the_report_survives_a_round_trip_through_the_project():
    channels = [f"HAG{i}" for i in range(1, 10)]
    report = propose(channels, [electrode("HAG", 9), electrode("ZZZ", 6)])
    again = MatchReport.from_dict(report.to_dict())
    assert [e.recon_name for e in again.electrodes] == ["HAG", "ZZZ"]
    assert again.total_pairs == report.total_pairs
    assert again.ignored == report.ignored


def test_channel_names_come_back_for_a_bound_contact():
    report = propose([f"IAD{i}" for i in range(1, 19)], [electrode("IAD", 18)])
    one = report.electrodes[0]
    assert one.channel_names(7) == "IAD7"
    assert one.channel_names(99) is None
