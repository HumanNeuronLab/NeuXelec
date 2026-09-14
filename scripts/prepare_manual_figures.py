"""Prepare the figures of the printed manual, once.

The pictures come from the NeuXelec website (already public): the animated GIFs
recorded on real cases and the logos. A single frame is extracted, cropped to
the useful area and written to ``resources/docs/figures``, which is bundled with
the application and read by ``scripts/build_manual.py``.

Run it again only when the source assets change:

    python scripts/prepare_manual_figures.py [path/to/Neuxelec_site/assets]
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "resources" / "docs" / "figures"
DEFAULT_ASSETS = ROOT.parent / "Neuxelec_site" / "assets"

#: name -> (source, frame index, relative crop box (l, t, r, b) in 0..1)
GIF_FIGURES = {
    "reconstruction.png": ("recon-3d.gif", 20, (0.30, 0.05, 1.00, 0.95)),
    "view3d_electrodes.png": ("3d-electrodes.gif", 18, (0.30, 0.05, 1.00, 0.95)),
    "view3d_pial.png": ("3d-pial.gif", 18, (0.28, 0.00, 1.00, 0.92)),
    "oblique_pet.png": ("obl-pet.gif", 10, (0.10, 0.02, 0.98, 0.98)),
    "oblique_parcellation.png": ("obl-parcellation.gif", 10, (0.10, 0.02, 0.98, 0.98)),
}

#: name -> source file copied as is
COPIED = {
    "logo_neuxelec.png": "neuxelec-logo.png",
    "logo_hnl.png": "logo-hnl.png",
    "coreg_review.png": "coreg-ct.png",
}

#: Logos drawn for the dark website: their black background has to go before
#: they can be printed on white paper.
WHITEN = {
    "logo_hug.png": "logo-hug.png",
    "logo_unige.png": "logo-unige.png",
}

MAX_WIDTH = 1400  # more than enough at 300 dpi for a half-page figure


def drop_black_background(image: Image.Image, low: int = 28, high: int = 90):
    """Turn the black backdrop of a dark-theme logo into white.

    Pixels darker than ``low`` become white, pixels between ``low`` and ``high``
    are blended towards white so the anti-aliased edges keep no dark halo. The
    coloured marks and the grey text are left alone.
    """
    import numpy as np

    rgba = np.asarray(image.convert("RGBA")).astype(float)
    rgb = rgba[..., :3]
    lum = rgb.max(axis=2)
    out = rgb.copy()
    out[lum <= low] = 255.0
    middle = (lum > low) & (lum < high)
    if middle.any():
        weight = ((high - lum[middle]) / (high - low))[:, None]
        out[middle] = out[middle] * (1.0 - weight) + 255.0 * weight
    result = np.concatenate(
        [out, np.full(lum.shape + (1,), 255.0)], axis=2
    ).clip(0, 255)
    return Image.fromarray(result.astype("uint8"), "RGBA")


def crop_relative(image: Image.Image, box) -> Image.Image:
    left, top, right, bottom = box
    w, h = image.size
    return image.crop(
        (int(left * w), int(top * h), int(right * w), int(bottom * h))
    )


def main(assets_dir: Path) -> int:
    if not assets_dir.is_dir():
        print(f"Assets directory not found: {assets_dir}")
        return 1
    FIGURES.mkdir(parents=True, exist_ok=True)

    for name, (source, frame, box) in GIF_FIGURES.items():
        path = assets_dir / source
        if not path.exists():
            print(f"  missing {source}, skipped")
            continue
        image = Image.open(path)
        image.seek(min(frame, getattr(image, "n_frames", 1) - 1))
        out = crop_relative(image.convert("RGB"), box)
        if out.width > MAX_WIDTH:
            ratio = MAX_WIDTH / out.width
            out = out.resize(
                (MAX_WIDTH, int(out.height * ratio)), Image.LANCZOS
            )
        out.save(FIGURES / name)
        print(f"  {name:28s} {out.size[0]}x{out.size[1]}")

    for name, source in COPIED.items():
        path = assets_dir / source
        if not path.exists():
            print(f"  missing {source}, skipped")
            continue
        image = Image.open(path)
        if image.width > MAX_WIDTH:
            ratio = MAX_WIDTH / image.width
            image = image.resize(
                (MAX_WIDTH, int(image.height * ratio)), Image.LANCZOS
            )
        image.save(FIGURES / name)
        print(f"  {name:28s} {image.size[0]}x{image.size[1]}")

    for name, source in WHITEN.items():
        path = assets_dir / source
        if not path.exists():
            print(f"  missing {source}, skipped")
            continue
        image = drop_black_background(Image.open(path))
        if image.width > MAX_WIDTH:
            ratio = MAX_WIDTH / image.width
            image = image.resize(
                (MAX_WIDTH, int(image.height * ratio)), Image.LANCZOS
            )
        image.save(FIGURES / name)
        print(f"  {name:28s} {image.size[0]}x{image.size[1]}  (background removed)")

    print(f"Figures written to {FIGURES}")
    return 0


if __name__ == "__main__":
    assets = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ASSETS
    raise SystemExit(main(assets))
