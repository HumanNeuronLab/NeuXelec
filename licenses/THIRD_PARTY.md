# Third-party components

NeuXelec is released under the GNU General Public License v3.0 or later
(see [LICENSE](../LICENSE)). This file lists everything NeuXelec ships or links
against, and the terms each one comes with.

GPL-3.0 is the strictest licence in this list. Every other component below is
permissive or LGPL, and all of them may be combined into a GPL-3.0 work, so
there is no conflict. The obligation runs one way: NeuXelec as a whole is
distributed under GPL-3.0, and its complete source must be made available to
anyone who receives a binary.

## Python libraries

Versions are those pinned in `requirements.txt`.

| Component | Licence | How it is used |
|---|---|---|
| PySide6, shiboken6 | LGPL-3.0 | Qt bindings, the whole interface |
| VTK | BSD-3-Clause | 3D rendering |
| PyVista, pyvistaqt | MIT | 3D scene built on VTK |
| SimpleITK | Apache-2.0 | Volume reading, resampling, DICOM |
| NiBabel | MIT | NIfTI, MGZ, FreeSurfer surfaces |
| NumPy, SciPy, scikit-image | BSD-3-Clause | Arrays, morphology, image processing |
| Matplotlib | PSF-based (BSD-compatible) | Colour maps, figures |
| imageio | BSD-2-Clause | GIF export |
| Pillow | MIT-CMU (HPND) | Image export |
| openpyxl | MIT | Spreadsheet export |
| neo | BSD-3-Clause | Reading Micromed TRC recordings |

`neo` is the one that reads the EEG. MNE carries thirty readers and none of
them is Micromed, so `neo.rawio.MicromedRawIO` is what the TRC reader is built
on. It brings only `numpy`, `packaging` and `quantities` with it, and BSD-3
places no condition beyond keeping the notice.

LGPL-3.0 deserves a word, because it is the only non-permissive one. It allows
use in a GPL-3.0 application without further conditions, and it also requires
that whoever receives the binary be able to replace the Qt libraries with their
own build. Shipping NeuXelec's full source under GPL-3.0, as is already the
case, satisfies that.

## Bundled executables

**ANTs** (Advanced Normalization Tools), Apache-2.0, see
[ANTs-Apache-2.0.txt](ANTs-Apache-2.0.txt).

NeuXelec starts three of them as separate processes: `antsRegistration`,
`antsApplyTransforms` and `antsApplyTransformsToPoints`. They are invoked, not
linked, so they remain independent programs under their own licence.

> Avants BB, Tustison NJ, Song G, Cook PA, Klein A, Gee JC. A reproducible
> evaluation of ANTs similarity metric performance in brain image registration.
> NeuroImage. 2011;54(3):2033-2044.

## Templates and atlases

**ICBM 152 Nonlinear Asymmetric 2009c**, the MNI reference volume and its brain
mask, used for normalisation, the template brain mask and the defacing mask.
Permissive, BSD-style; redistribution and commercial use are allowed, provided
the copyright notice travels with the files. See
[MNI-ICBM152-2009.txt](MNI-ICBM152-2009.txt).

The provenance is recorded in the files themselves: the NIfTI `descrip` field
reads `mnc2nii mni_icbm152_nlin_asym_09c/mni_icbm152_t1_tal_nlin_asym_09c.mnc`,
so these come from the original MINC release of the McConnell Brain Imaging
Centre, not from a redistribution with different terms.

> Fonov V, Evans AC, Botteron K, Almli CR, McKinstry RC, Collins DL. Unbiased
> average age-appropriate atlases for pediatric studies. NeuroImage.
> 2011;54(1):313-327.

**Schaefer 2018 cortical parcellation** (`template_parcellation1`), 400 parcels,
7 networks, in MNI152NLin2009cAsym space. MIT, commercial use allowed. See
[Schaefer2018-CBIG-MIT.txt](Schaefer2018-CBIG-MIT.txt).

> Schaefer A, Kong R, Gordon EM, Laumann TO, Zuo XN, Holmes AJ, Eickhoff SB,
> Yeo BTT. Local-global parcellation of the human cerebral cortex from
> intrinsic functional connectivity MRI. Cerebral Cortex. 2018;28(9):3095-3114.

### Removed: the Brainnetome Atlas

NeuXelec used to ship the Brainnetome Atlas, 246 regions, as the second MNI
parcellation. **It is no longer distributed, and it is no longer loaded.**

Its terms grant use to academic and not-for-profit institutions "for use for
non-commercial purposes", with attribution and share alike, and a commercial
licence has to be requested separately from the Brainnetome Center. GPL-3.0
section 7 does not allow passing a restriction of that kind on to whoever
receives a covered work: shipping the atlas inside the installer quietly
narrowed what a recipient could do with NeuXelec, which is the opposite of what
the GPL-3.0 badge tells them.

So there is now one MNI parcellation, Schaefer, and the second slot is gone from
the interface. When the MNI parcellations become loadable like the native ones,
the slot comes back as an empty one: whoever wants Brainnetome fetches it from
atlas.brainnetome.org and accepts those terms in their own name, which is the
only way those terms can be accepted at all.

> Fan L, Li H, Zhuo J, Zhang Y, Wang J, Chen L, Yang Z, Chu C, Xie S, Laird AR,
> Fox PT, Eickhoff SB, Yu C, Jiang T. The Human Brainnetome Atlas: a new brain
> atlas based on connectional architecture. Cerebral Cortex.
> 2016;26(8):3508-3526.

**FreeSurferColorLUT.txt**, the FreeSurfer label colour table, used to name and
colour the structures of a parcellation. FreeSurfer is distributed under its own
licence, which permits redistribution for research purposes.

## Prior work

NeuXelec reimplements, in Python and as a standalone application, the two-point
localization approach of **Voxeloc** (Monney et al., 2024), a MATLAB tool from
the Human Neuron Lab. The approach is reused; the implementation is NeuXelec's
own.

> Monney J, Dallaire SE, Stoutah L, Fanda L, Megevand P. Voxeloc: a time-saving
> graphical user interface for localizing and visualizing stereo-EEG electrodes.
> Journal of Neuroscience Methods. 2024;407:110154.
