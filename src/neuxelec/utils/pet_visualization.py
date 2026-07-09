import matplotlib.cm as cm
import numpy as np

# Preferred colormaps for scalar overlays, in priority order. Used to give every
# overlay layer (SISCOM, PET, ictal SPECT, inter-ictal SPECT) a distinct default
# colormap automatically, picking the first one not already taken. This is the
# same set offered for PET / SISCOM so the choices are consistent everywhere.
OVERLAY_CMAP_PREFERENCE = [
    "hot",
    "inferno",
    "plasma",
    "jet",
    "turbo",
    "viridis",
    "gray",
]


def pick_free_colormap(used, preference=None):
    """Return the first colormap in ``preference`` not present in ``used``.

    ``used`` is an iterable of colormap names already assigned to other overlays.
    Falls back to the first preference when all are taken. Comparison is
    case-insensitive.
    """
    prefs = list(preference) if preference else list(OVERLAY_CMAP_PREFERENCE)
    used_set = {str(u).lower() for u in (used or []) if u}
    for name in prefs:
        if name.lower() not in used_set:
            return name
    return prefs[0] if prefs else "hot"


def get_pet_window(values, pmin, pmax):
    if values is None:
        return 0.0, 1.0

    values = np.asarray(values, dtype=np.float32)
    values = values[np.isfinite(values)]
    values = values[values > 0]

    if values.size == 0:
        return 0.0, 1.0

    lo = float(np.percentile(values, pmin))
    hi = float(np.percentile(values, pmax))
    if hi <= lo:
        hi = lo + 1e-6
    return lo, hi


def compute_pet_reference(pet_values):
    """Reference intensity for ratio normalization.

    Returns the median of the positive PET voxels supplied (the caller should
    restrict them to the brain mask when available). This median represents the
    average brain metabolism, so dividing the PET by it turns the color scale
    into an interpretable ratio where 1.0 = brain average, < 1.0 = hypometabolism.
    Returns None when no usable value is available.
    """
    v = np.asarray(pet_values, dtype=np.float32)
    v = v[np.isfinite(v)]
    v = v[v > 0]
    if v.size == 0:
        return None
    ref = float(np.median(v))
    if not np.isfinite(ref) or ref <= 1e-6:
        return None
    return ref


def get_pet_ratio_window(ref, ratio_lo, ratio_hi):
    """Window bounds in RAW intensity units from ratio bounds.

    ``ratio_lo``/``ratio_hi`` are fractions of the reference (e.g. 0.4 and 1.6),
    so the returned (lo, hi) = (ratio_lo * ref, ratio_hi * ref) can be fed to
    ``normalize_pet_slice`` unchanged while the scale is anchored to the brain
    median. Displaying lo/ref and hi/ref gives back the ratio bounds.
    """
    ref = float(ref)
    lo = float(ratio_lo) * ref
    hi = float(ratio_hi) * ref
    if hi <= lo:
        hi = lo + 1e-6
    return lo, hi


def normalize_pet_slice(pet_slice, lo, hi, gamma=1.0, mask=None):
    pet_slice = np.asarray(pet_slice, dtype=np.float32)

    den = max(1e-6, float(hi) - float(lo))
    pet_norm = (pet_slice - float(lo)) / den
    pet_norm = np.clip(pet_norm, 0.0, 1.0)

    gamma = max(0.1, float(gamma))
    if abs(gamma - 1.0) > 1e-6:
        pet_norm = pet_norm ** (1.0 / gamma)

    pet_norm[~np.isfinite(pet_slice)] = 0.0

    if mask is not None:
        pet_norm[np.asarray(mask) <= 0] = 0.0

    pet_norm = np.nan_to_num(pet_norm, nan=0.0, posinf=1.0, neginf=0.0)
    pet_norm = np.clip(pet_norm, 0.0, 1.0)

    return pet_norm


def pet_norm_to_colormap(pet_norm, cmap_name="hot"):
    pet_norm = np.asarray(pet_norm, dtype=np.float32)
    cmap = cm.get_cmap(cmap_name)
    rgb = cmap(np.clip(pet_norm, 0.0, 1.0))[..., :3]
    return rgb.astype(np.float32)  # 0..1


def blend_pet_on_rgba(base_rgba, pet_rgb, pet_norm, alpha_scale=1.0):
    """
    Build an RGBA PET overlay texture for display as a SEPARATE plane actor.
    RGB stores the colormap directly, and alpha controls transparency.
    """
    out = np.asarray(base_rgba, dtype=np.float32).copy()
    pet_rgb = np.asarray(pet_rgb, dtype=np.float32)

    if pet_rgb.max() <= 1.0:
        pet_rgb = pet_rgb * 255.0

    alpha = np.clip(np.asarray(pet_norm, dtype=np.float32) * float(alpha_scale), 0.0, 1.0)
    mask = alpha > 0.0

    for c in range(3):
        out[..., c][mask] = pet_rgb[..., c][mask]

    if out.shape[-1] >= 4:
        out[..., 3][mask] = 255.0 * alpha[mask]

    out = np.nan_to_num(out, nan=0.0, posinf=255.0, neginf=0.0)
    out = np.clip(out, 0, 255)

    return out.astype(np.uint8)


def blend_pet_on_rgb(base_rgb, pet_rgb, pet_norm, alpha_scale=1.0):
    """
    Blend a PET colormap onto an RGB base image.
    This is still used by oblique_slice_page.py.
    """
    out = np.asarray(base_rgb, dtype=np.float32).copy()
    pet_rgb = np.asarray(pet_rgb, dtype=np.float32)

    if pet_rgb.max() <= 1.0:
        pet_rgb = pet_rgb * 255.0

    alpha = np.clip(np.asarray(pet_norm, dtype=np.float32) * float(alpha_scale), 0.0, 1.0)
    mask = alpha > 0.0

    for c in range(3):
        out[..., c][mask] = (1.0 - alpha[mask]) * out[..., c][mask] + alpha[mask] * pet_rgb[..., c][
            mask
        ]

    out = np.nan_to_num(out, nan=0.0, posinf=255.0, neginf=0.0)
    out = np.clip(out, 0, 255)
    return out.astype(np.uint8)


def normalize_threshold_map(values, lo, hi, gamma=1.0, mask=None):
    values = np.asarray(values, dtype=np.float32)

    den = max(1e-6, float(hi) - float(lo))
    norm = (values - float(lo)) / den
    norm = np.clip(norm, 0.0, 1.0)

    gamma = max(0.1, float(gamma))
    if abs(gamma - 1.0) > 1e-6:
        norm = norm ** (1.0 / gamma)

    norm[~np.isfinite(values)] = 0.0

    if mask is not None:
        norm[np.asarray(mask) <= 0] = 0.0

    norm = np.nan_to_num(norm, nan=0.0, posinf=1.0, neginf=0.0)
    norm = np.clip(norm, 0.0, 1.0)
    return norm
