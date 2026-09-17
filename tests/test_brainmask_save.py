"""Saving the brain mask leaves one file on disk, not two.

Generating writes ``T1_brainmask.nii.gz`` into the transforms folder. Saving used
to write a second, byte-for-byte identical copy under the patient's own name, and
both stayed. These tests pin down that the working copy now goes, and, more
importantly, that nothing else ever does.
"""

import os

from neuxelec.pages.files_page import FilesPage


class _State:
    def __init__(self, generated=None):
        self.brainmask_generated_path = generated


def _page(generated=None):
    page = FilesPage.__new__(FilesPage)
    page.state = _State(generated)
    return page


def test_the_working_copy_goes_when_the_mask_is_saved(tmp_path):
    working = tmp_path / "transforms" / "T1_brainmask.nii.gz"
    working.parent.mkdir(parents=True)
    working.write_bytes(b"mask")
    saved = tmp_path / "images" / "PAT_MRI1_brainmask.nii.gz"
    saved.parent.mkdir(parents=True)
    saved.write_bytes(b"mask")

    _page(str(working))._discard_generated_brainmask(str(saved))

    assert not working.exists()
    assert saved.exists()


def test_saving_over_the_working_copy_keeps_it(tmp_path):
    """Save to the very same file: there is nothing to discard."""
    working = tmp_path / "T1_brainmask.nii.gz"
    working.write_bytes(b"mask")

    _page(str(working))._discard_generated_brainmask(str(working))

    assert working.exists()


def test_a_mask_the_user_loaded_is_never_touched(tmp_path):
    """Loading a mask clears the generated path, so nothing may be removed."""
    theirs = tmp_path / "T1_brainmask.nii.gz"
    theirs.write_bytes(b"mask")

    _page(None)._discard_generated_brainmask(str(tmp_path / "copy.nii.gz"))

    assert theirs.exists()


def test_a_file_under_any_other_name_is_left_alone(tmp_path):
    """Only the name ANTs writes. Anything else is the user's own file."""
    other = tmp_path / "my_own_brainmask.nii.gz"
    other.write_bytes(b"mask")

    _page(str(other))._discard_generated_brainmask(str(tmp_path / "saved.nii.gz"))

    assert other.exists()


def test_a_generated_path_that_no_longer_exists_is_harmless(tmp_path):
    _page(str(tmp_path / "gone" / "T1_brainmask.nii.gz"))._discard_generated_brainmask(
        str(tmp_path / "saved.nii.gz")
    )


def test_a_directory_is_never_removed(tmp_path):
    folder = tmp_path / "T1_brainmask.nii.gz"
    folder.mkdir()

    _page(str(folder))._discard_generated_brainmask(str(tmp_path / "saved.nii.gz"))

    assert folder.is_dir()


def test_a_read_only_working_copy_does_not_break_the_save(tmp_path):
    """Whatever happens, the save itself must succeed."""
    import stat

    working = tmp_path / "T1_brainmask.nii.gz"
    working.write_bytes(b"mask")
    os.chmod(working, stat.S_IREAD)
    try:
        _page(str(working))._discard_generated_brainmask(str(tmp_path / "saved.nii.gz"))
    finally:
        os.chmod(working, stat.S_IWRITE | stat.S_IREAD)
