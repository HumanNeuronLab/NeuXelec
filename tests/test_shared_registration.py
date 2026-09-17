"""One T1 to template registration, shared by the three features that need it.

The brain mask, the defacing and the MNI coordinates each used to run their own
antsRegistration with, argument for argument, the same command. These tests pin
down that they now share one, and that it is only reused when it really is the
right one.

ANTs itself is not run: a fake runner records the command and writes the files
ANTs would write, which is enough to check the caching, the invalidation and the
shape of the command.
"""

import json
import os

import pytest

from neuxelec import coregistration as coreg


@pytest.fixture
def template(tmp_path):
    path = tmp_path / "templates" / "template_T1.nii"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"template" * 10)
    return str(path)


@pytest.fixture
def t1(tmp_path):
    path = tmp_path / "patient" / "T1.nii"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"subject" * 20)
    return str(path)


class FakeAnts:
    """Writes what antsRegistration writes, and remembers the command."""

    def __init__(self):
        self.commands = []

    def __call__(self, cmd, cwd):
        self.commands.append(list(cmd))
        prefix = cmd[cmd.index("--output") + 1].strip("[]")
        for suffix in ("0GenericAffine.mat", "1Warp.nii.gz", "1InverseWarp.nii.gz"):
            with open(prefix + suffix, "wb") as handle:
                handle.write(b"transform")

    @property
    def runs(self):
        return len(self.commands)


def test_the_registration_runs_once_and_is_reused(tmp_path, t1, template):
    ants = FakeAnts()
    first = coreg.ensure_t1_to_template_registration(
        t1, tmp_path / "work", template_t1_path=template, runner=ants
    )
    assert ants.runs == 1
    assert os.path.exists(first["affine"])
    assert os.path.exists(first["warp"])
    assert os.path.exists(first["inverse_warp"])

    second = coreg.ensure_t1_to_template_registration(
        t1, tmp_path / "work", template_t1_path=template, runner=ants
    )
    assert ants.runs == 1, "the second call must reuse, not recompute"
    assert second == first


def test_the_three_features_share_one_registration(tmp_path, t1, template):
    """Brain mask, defacing and MNI coordinates, same folder, one registration."""
    ants = FakeAnts()
    for _feature in range(3):
        coreg.ensure_t1_to_template_registration(
            t1, tmp_path / "work", template_t1_path=template, runner=ants
        )
    assert ants.runs == 1


def test_only_the_transforms_are_asked_for(tmp_path, t1, template):
    """The two resampled volumes ANTs writes on demand are 50 MB nobody reads."""
    ants = FakeAnts()
    coreg.ensure_t1_to_template_registration(
        t1, tmp_path / "work", template_t1_path=template, runner=ants
    )
    output = ants.commands[0][ants.commands[0].index("--output") + 1]
    assert output.count(",") == 0, output
    assert "Warped" not in output


def test_the_command_is_the_one_it_replaced(tmp_path, t1, template):
    """The registration itself must not change: same transforms, same metrics."""
    ants = FakeAnts()
    coreg.ensure_t1_to_template_registration(
        t1, tmp_path / "work", template_t1_path=template, runner=ants
    )
    cmd = ants.commands[0]
    assert cmd[cmd.index("--initial-moving-transform") + 1] == f"[{template},{t1},1]"
    transforms = [cmd[i + 1] for i, a in enumerate(cmd) if a == "--transform"]
    assert transforms == ["Affine[0.1]", "SyN[0.1,3,0]"]
    metrics = [cmd[i + 1] for i, a in enumerate(cmd) if a == "--metric"]
    assert metrics == [
        f"MI[{template},{t1},1,32,Regular,0.25]",
        f"CC[{template},{t1},1,4]",
    ]
    convergences = [cmd[i + 1] for i, a in enumerate(cmd) if a == "--convergence"]
    assert convergences == ["[500x250x100,1e-6,10]", "[80x40x20,1e-6,10]"]


def test_a_different_mri1_invalidates_the_registration(tmp_path, t1, template):
    """The old code never checked this: another T1 reused its predecessor's warp."""
    ants = FakeAnts()
    coreg.ensure_t1_to_template_registration(
        t1, tmp_path / "work", template_t1_path=template, runner=ants
    )

    other = tmp_path / "patient" / "T1_other.nii"
    other.write_bytes(b"a completely different subject")
    coreg.ensure_t1_to_template_registration(
        str(other), tmp_path / "work", template_t1_path=template, runner=ants
    )
    assert ants.runs == 2


def test_the_same_t1_moved_to_another_folder_is_still_the_same_t1(tmp_path, t1, template):
    """Identity is the file's content, not its path: a moved project must not
    pay three minutes for a registration it already has."""
    ants = FakeAnts()
    coreg.ensure_t1_to_template_registration(
        t1, tmp_path / "work", template_t1_path=template, runner=ants
    )

    moved = tmp_path / "elsewhere" / "T1.nii"
    moved.parent.mkdir(parents=True, exist_ok=True)
    moved.write_bytes(open(t1, "rb").read())
    coreg.ensure_t1_to_template_registration(
        str(moved), tmp_path / "work", template_t1_path=template, runner=ants
    )
    assert ants.runs == 1


def test_a_different_template_invalidates_the_registration(tmp_path, t1, template):
    ants = FakeAnts()
    coreg.ensure_t1_to_template_registration(
        t1, tmp_path / "work", template_t1_path=template, runner=ants
    )

    other = tmp_path / "templates" / "template_T1_v2.nii"
    other.write_bytes(b"another template entirely")
    coreg.ensure_t1_to_template_registration(
        t1, tmp_path / "work", template_t1_path=str(other), runner=ants
    )
    assert ants.runs == 2


def test_transforms_without_a_stamp_are_not_trusted(tmp_path, t1, template):
    """Folders written by earlier versions say nothing about what made them."""
    ants = FakeAnts()
    coreg.ensure_t1_to_template_registration(
        t1, tmp_path / "work", template_t1_path=template, runner=ants
    )
    stamp = tmp_path / "work" / coreg.SHARED_REG_SUBDIR / "T1_to_MNI_source.json"
    assert stamp.exists()
    stamp.unlink()

    coreg.ensure_t1_to_template_registration(
        t1, tmp_path / "work", template_t1_path=template, runner=ants
    )
    assert ants.runs == 2


def test_a_missing_transform_forces_a_recomputation(tmp_path, t1, template):
    ants = FakeAnts()
    result = coreg.ensure_t1_to_template_registration(
        t1, tmp_path / "work", template_t1_path=template, runner=ants
    )
    os.remove(result["inverse_warp"])
    coreg.ensure_t1_to_template_registration(
        t1, tmp_path / "work", template_t1_path=template, runner=ants
    )
    assert ants.runs == 2


def test_force_recomputes_even_when_everything_matches(tmp_path, t1, template):
    ants = FakeAnts()
    coreg.ensure_t1_to_template_registration(
        t1, tmp_path / "work", template_t1_path=template, runner=ants
    )
    coreg.ensure_t1_to_template_registration(
        t1, tmp_path / "work", template_t1_path=template, runner=ants, force=True
    )
    assert ants.runs == 2


def test_the_transforms_keep_the_names_earlier_projects_stored(tmp_path, t1, template):
    """Projects saved before this refactor point at these exact paths."""
    ants = FakeAnts()
    result = coreg.ensure_t1_to_template_registration(
        t1, tmp_path / "work", template_t1_path=template, runner=ants
    )
    folder = tmp_path / "work" / "mni"
    assert result["affine"] == str(folder / "T1_to_MNI_0GenericAffine.mat")
    assert result["warp"] == str(folder / "T1_to_MNI_1Warp.nii.gz")
    assert result["inverse_warp"] == str(folder / "T1_to_MNI_1InverseWarp.nii.gz")


def test_a_registration_that_produced_nothing_is_an_error(tmp_path, t1, template):
    def _silent(cmd, cwd):
        return None

    with pytest.raises(RuntimeError, match="did not produce"):
        coreg.ensure_t1_to_template_registration(
            t1, tmp_path / "work", template_t1_path=template, runner=_silent
        )


def test_the_stamp_records_both_inputs(tmp_path, t1, template):
    ants = FakeAnts()
    coreg.ensure_t1_to_template_registration(
        t1, tmp_path / "work", template_t1_path=template, runner=ants
    )
    stamp = json.loads(
        (tmp_path / "work" / "mni" / "T1_to_MNI_source.json").read_text(encoding="utf-8")
    )
    assert stamp["t1"]["path"] == t1
    assert stamp["template"]["path"] == template
    assert stamp["t1"]["fingerprint"]["size"] == os.path.getsize(t1)


def test_a_missing_t1_or_template_is_reported(tmp_path, template):
    with pytest.raises(FileNotFoundError):
        coreg.ensure_t1_to_template_registration(
            str(tmp_path / "nothing.nii"), tmp_path / "work", template_t1_path=template
        )
    real = tmp_path / "t1.nii"
    real.write_bytes(b"x")
    with pytest.raises(FileNotFoundError):
        coreg.ensure_t1_to_template_registration(
            str(real), tmp_path / "work", template_t1_path=str(tmp_path / "no_template.nii")
        )


# ---------------------------------------------------------------------------
# the three features together
# ---------------------------------------------------------------------------


class _FakeAntsBinaries:
    """Stands in for antsRegistration and antsApplyTransforms, both."""

    def __init__(self):
        self.registrations = 0
        self.applications = 0

    def __call__(self, cmd, cwd=None):
        import numpy as np
        import SimpleITK as sitk

        joined = " ".join(cmd)
        if "antsRegistration" in joined:
            self.registrations += 1
            prefix = cmd[cmd.index("--output") + 1].strip("[]")
            for suffix in ("0GenericAffine.mat", "1Warp.nii.gz", "1InverseWarp.nii.gz"):
                with open(prefix + suffix, "wb") as handle:
                    handle.write(b"transform")
            return
        self.applications += 1
        volume = np.zeros((12, 12, 12), dtype=np.uint8)
        volume[3:9, 3:9, 3:9] = 1
        sitk.WriteImage(sitk.GetImageFromArray(volume), cmd[cmd.index("-o") + 1])


class _State:
    def __init__(self, t1_path, transforms_dir):
        self.t1_path = t1_path
        self.transforms_dir = str(transforms_dir)
        self.mni_template_path = None
        self.mni_space_name = "MNI152NLin2009cAsym"
        self.t1_to_mni_affine_path = None
        self.t1_to_mni_warp_path = None
        self.t1_to_mni_inverse_warp_path = None
        self.t1_to_mni_warped_path = None


def test_mask_deface_and_mni_together_run_one_registration(tmp_path, monkeypatch):
    """The whole point: three minutes once, not three times."""
    import numpy as np
    import SimpleITK as sitk

    from neuxelec.utils import mni_coordinates

    work = tmp_path / "transforms"
    t1_path = str(tmp_path / "T1.nii.gz")
    sitk.WriteImage(sitk.GetImageFromArray(np.zeros((12, 12, 12), dtype=np.int16)), t1_path)

    template = str(tmp_path / "template_T1.nii.gz")
    sitk.WriteImage(sitk.GetImageFromArray(np.zeros((12, 12, 12), dtype=np.int16)), template)
    mask = str(tmp_path / "template_brain_mask.nii.gz")
    sitk.WriteImage(sitk.GetImageFromArray(np.ones((12, 12, 12), dtype=np.uint8)), mask)

    ants = _FakeAntsBinaries()
    monkeypatch.setattr(coreg, "_run_cmd", ants)
    monkeypatch.setattr(coreg, "_ants_exe", lambda name: name)
    monkeypatch.setattr(
        mni_coordinates,
        "_run_cmd_with_progress",
        lambda cmd, cwd=None, **kwargs: ants(cmd, cwd),
    )

    # 1. the brain mask
    out_mask = coreg.ants_generate_brainmask_t1(
        t1_path, out_dir=str(work), template_t1_path=template, template_mask_path=mask
    )
    assert os.path.exists(out_mask)
    assert ants.registrations == 1

    # 2. the defacing, in the same folder
    deface = coreg.ants_deface_mask_in_subject_space(
        t1_path, out_dir=str(work), template_t1_path=template, deface_mask_path=mask
    )
    assert os.path.exists(deface)
    assert ants.registrations == 1, "the defacing must reuse the registration"

    # 3. the MNI transforms
    transforms = mni_coordinates.ensure_t1_to_mni_transforms(
        _State(t1_path, work), template_t1_path=template
    )
    assert ants.registrations == 1, "the MNI export must reuse the registration"
    assert os.path.exists(transforms["affine"])
    assert os.path.exists(transforms["inverse_warp"])


def test_nothing_writes_the_old_by_products(tmp_path, monkeypatch):
    """brainmask_Warped, brainmask_InverseWarped and their deface twins are gone."""
    import numpy as np
    import SimpleITK as sitk

    work = tmp_path / "transforms"
    t1_path = str(tmp_path / "T1.nii.gz")
    sitk.WriteImage(sitk.GetImageFromArray(np.zeros((12, 12, 12), dtype=np.int16)), t1_path)
    template = str(tmp_path / "template_T1.nii.gz")
    sitk.WriteImage(sitk.GetImageFromArray(np.zeros((12, 12, 12), dtype=np.int16)), template)
    mask = str(tmp_path / "template_brain_mask.nii.gz")
    sitk.WriteImage(sitk.GetImageFromArray(np.ones((12, 12, 12), dtype=np.uint8)), mask)

    ants = _FakeAntsBinaries()
    monkeypatch.setattr(coreg, "_run_cmd", ants)
    monkeypatch.setattr(coreg, "_ants_exe", lambda name: name)

    coreg.ants_generate_brainmask_t1(
        t1_path, out_dir=str(work), template_t1_path=template, template_mask_path=mask
    )

    produced = sorted(p.name for p in work.rglob("*") if p.is_file())
    assert produced == [
        "T1_brainmask.nii.gz",
        "T1_to_MNI_0GenericAffine.mat",
        "T1_to_MNI_1InverseWarp.nii.gz",
        "T1_to_MNI_1Warp.nii.gz",
        "T1_to_MNI_source.json",
    ], produced
