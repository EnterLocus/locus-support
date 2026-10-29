"""Shared Package-v2 water validation.  Keep this independent of renderer code."""

import math

MINIMUM_APP = (1, 3, 0)
VIEW_CAPABILITY = "locus.view.water.v1"
ROOM_CAPABILITY = "locus.room.water.v1"
VIEW_GLOW_DISTURBANCE_CAPABILITY = "locus.view.water.glow-disturbance.v1"
VIEW_REFLECTION_REGISTRATION_CAPABILITY = "locus.view.water.reflection-registration.v1"
VIEW_LAYERED_REFLECTION_CAPABILITY = "locus.view.water.reflection-registration.layered.v1"
VIEW_BED_DEEPENING_CAPABILITY = "locus.view.water.bed-deepening.v1"
VIEW_CONTACT_CALIBRATION_CAPABILITY = "locus.view.water.contact-calibration.v1"
REFLECTION_REGISTRATION_MINIMUM_APP = (1, 3, 1)
BED_DEEPENING_MINIMUM_APP = (1, 3, 1)
CONTACT_CALIBRATION_MINIMUM_APP = (1, 3, 2)
REFLECTION_REGISTRATION_TEXTURE_BYTES = 4096 * (256 + 1) * 4
MAXIMUM_TEXTURE_BYTES = 64 * 1024 * 1024


def deepens(region):
    """True when the region's bed opts into `bed.deepening`."""
    bed = region.get("bed")
    return isinstance(bed, dict) and "deepening" in bed


def has_contact_calibration(region):
    """True when a View declares a source-side water-contact reprojection."""
    return "contactCalibration" in region


def minimum_app(value):
    """Highest required app floor among the explicitly authored water features."""
    if any(has_contact_calibration(region) for region in value["regions"]):
        return CONTACT_CALIBRATION_MINIMUM_APP
    if any("reflectionRegistration" in region for region in value["regions"]):
        return REFLECTION_REGISTRATION_MINIMUM_APP
    if any(deepens(region) for region in value["regions"]):
        return BED_DEEPENING_MINIMUM_APP
    return MINIMUM_APP


def capabilities(value, owner):
    """A paired-reader gate is needed even when App versions are identical."""
    result = [VIEW_CAPABILITY if owner == "view" else ROOM_CAPABILITY]
    if owner == "view" and any(
        "mover" in (region.get("glow") or {}) for region in value["regions"]
    ):
        result.append(VIEW_GLOW_DISTURBANCE_CAPABILITY)
    if owner == "view" and any(
        "reflectionRegistration" in region for region in value["regions"]
    ):
        result.append(VIEW_REFLECTION_REGISTRATION_CAPABILITY)
    if owner == "view" and any(
        (r.get("reflectionRegistration") or {}).get("model") == "mask-layered-v1" for r in value["regions"]
    ):
        result.append(VIEW_LAYERED_REFLECTION_CAPABILITY)
    if owner == "view" and any(deepens(region) for region in value["regions"]):
        result.append(VIEW_BED_DEEPENING_CAPABILITY)
    if owner == "view" and any(has_contact_calibration(region) for region in value["regions"]):
        result.append(VIEW_CONTACT_CALIBRATION_CAPABILITY)
    return result


def texture_bytes(width, height, mipmaps=False):
    """Conservative RGBA8 residency, including every generated mip level."""
    size = width * height * 4
    while mipmaps and (width > 1 or height > 1):
        width, height = max(1, width // 2), max(1, height // 2)
        size += width * height * 4
    return size


# Shared caustics, foam, and four 1x1 neutral bindings. Wave normals come from FFT.
GENERATED_TEXTURE_BYTES = (
    texture_bytes(256, 256, True) + texture_bytes(64, 64, True) + 16
)
OCEAN_TEXTURE_BYTES = 12 * texture_bytes(256, 256, True)  # Six RGBA16F outputs.
GLOW_TEXTURE_BYTES = texture_bytes(512, 512, True)


def uses_fft(surface):
    """All dynamic root-water surfaces use FFT, including reader-only aliases."""
    return surface.get("motion", "ocean") != "still"


def _finite(value, lo, hi):
    return type(value) in (int, float) and lo <= value <= hi and math.isfinite(value)


def _keys(value, required, optional, field, require):
    require(isinstance(value, dict), field + " must be an object")
    require(
        not set(value) - set(required) - set(optional), field + " has unsupported field"
    )
    require(not set(required) - set(value), field + " is missing required field")


def _array(value, count, lo, hi):
    return (
        isinstance(value, list)
        and len(value) == count
        and all((_finite(v, lo, hi) for v in value))
    )


def validate_definition(
    value,
    *,
    owner,
    require,
    asset,
    field="water",
    sun_path=False,
    allow_future_features=False,
    allow_legacy_motion=True,
):
    _keys(value, {"regions"}, {"preset"}, field, require)
    if "preset" in value:
        require(
            isinstance(value["preset"], str) and value["preset"],
            field + ".preset is invalid",
        )
    regions = value["regions"]
    require(
        isinstance(regions, list) and 1 <= len(regions) <= 4,
        field + ".regions must contain 1...4 entries",
    )
    ids = set()
    oceans = 0
    for i, region in enumerate(regions):
        base = "%s.regions[%d]" % (field, i)
        _keys(
            region,
            {"id", "pose", "sizeMeters"},
            {"shape", "surface", "optics", "bed", "blend", "glow", "reflectionRegistration", "contactCalibration"},
            base,
            require,
        )
        rid = region["id"]
        require(
            isinstance(rid, str)
            and rid.strip()
            and (len(rid.encode()) <= 200)
            and (rid not in ids),
            base + ".id is invalid",
        )
        ids.add(rid)
        pose = region["pose"]
        _keys(
            pose,
            {"translationMeters", "orientationXYZW"},
            set(),
            base + ".pose",
            require,
        )
        require(
            _array(
                pose["translationMeters"],
                3,
                -3.4028234663852886e38,
                3.4028234663852886e38,
            ),
            base + ".pose.translationMeters is invalid",
        )
        require(
            _array(pose["orientationXYZW"], 4, -1.0001, 1.0001),
            base + ".pose.orientationXYZW is invalid",
        )
        require(
            abs(sum((v * v for v in pose["orientationXYZW"])) - 1) <= 0.0001,
            base + ".pose.orientationXYZW must be normalized",
        )
        require(
            _array(region["sizeMeters"], 2, 0, 1000)
            and all((v > 0 for v in region["sizeMeters"])),
            base + ".sizeMeters is invalid",
        )
        shape = region.get("shape", "rectangle")
        require(shape in ("rectangle", "disc"), base + ".shape is invalid")
        if "reflectionRegistration" in region:
            registration = region["reflectionRegistration"]
            name = base + ".reflectionRegistration"
            require(owner == "view", name + " is View-only")
            _keys(registration, {"model"}, set(), name, require)
            require(registration["model"] in ("mask-image-v1", "mask-layered-v1"), name + ".model is unsupported")
            blend = region.get("blend")
            require(isinstance(blend, dict) and "panoramaMask" in blend,
                    name + " requires blend.panoramaMask")
        if "contactCalibration" in region:
            calibration = region["contactCalibration"]
            name = base + ".contactCalibration"
            require(owner == "view", name + " is View-only")
            require(len(value["regions"]) == 1 and region.get("shape", "rectangle") == "disc",
                    name + " requires a single disc region")
            require(region["pose"]["translationMeters"][0] == 0
                    and region["pose"]["translationMeters"][2] == 0
                    and region["pose"]["orientationXYZW"] == [0, 0, 0, 1],
                    name + " requires a floor-relative horizontal reference")
            fields={"model", "referenceEyeHeightMeters", "referenceYawDegrees", "referencePitchDegrees", "referenceSkyCenterMeters", "sourcePanorama", "sourcePanoramaSHA256", "sourceMaskSHA256", "landMesh", "landTexture", "removalMask", "waterCoverage", "reflectionPanorama"}
            _keys(calibration,fields,{"sourceProjection"},name,require)
            require(calibration["model"] == "layered-proxy-v1",name+".model is unsupported")
            require(_finite(calibration["referenceEyeHeightMeters"],.1,5),name+".referenceEyeHeightMeters is invalid")
            require(_finite(calibration["referenceYawDegrees"],-360,360),name+".referenceYawDegrees is invalid")
            require(_finite(calibration["referencePitchDegrees"],0,0),name+" requires rectified zero-pitch source assets")
            center=calibration["referenceSkyCenterMeters"]
            require(isinstance(center,list) and len(center)==3 and all(_finite(v,-100,100) for v in center),name+".referenceSkyCenterMeters is invalid")
            require(center[0]**2 + (center[1]-calibration["referenceEyeHeightMeters"])**2 + center[2]**2 < 80**2,
                    name+" reference eye must lie inside the source sphere")
            # The proxy covers all active eyes in .1...5 m, not just E_ref.
            require(region.get("blend",{}).get("horizonSkirt") is True,name+" requires horizonSkirt")
            if "sourceProjection" in calibration:
                projection=calibration["sourceProjection"]
                require(isinstance(projection,dict),name+".sourceProjection is invalid")
                if projection.get('model') == 'latitude-mobius-v1':
                    _keys(projection,{"model","sourceHorizonElevationDegrees"},set(),name+".sourceProjection",require)
                    require(_finite(projection["sourceHorizonElevationDegrees"],-89,89) and abs(projection["sourceHorizonElevationDegrees"])<89,name+".sourceProjection is invalid")
                else:
                    _keys(projection,{"model","sourceHorizonSamples"},set(),name+".sourceProjection",require)
                    require(projection['model']=='latitude-mobius-profile-v1',name+'.sourceProjection.model is invalid')
                    samples=projection['sourceHorizonSamples']
                    require(isinstance(samples,list) and 3<=len(samples)<=64 and all(
                        isinstance(p,list) and len(p)==2 and _finite(p[0],0,1) and p[0]<1 and _finite(p[1],-89,89) and abs(p[1])<89
                        for p in samples),name+'.sourceProjection.sourceHorizonSamples is invalid')
                    require(samples[0][0]==0 and all(a[0]<b[0] for a,b in zip(samples,samples[1:])),name+'.sourceProjection samples must be ordered periodic U')
                require(center[0]==0 and center[2]==0,name+".sourceProjection requires a vertically centered source sphere")
            require("glow" not in region,name+" does not support glow")
            for key in ("sourcePanoramaSHA256","sourceMaskSHA256"):
                digest=calibration[key]
                require(isinstance(digest,str) and len(digest)==64 and all(c in "0123456789abcdef" for c in digest),name+"."+key+" is invalid")
            require(isinstance(region.get("blend"),dict) and isinstance(region["blend"].get("panoramaMask"),str),name+" requires source panoramaMask")
            for key in ("sourcePanorama","landMesh"):
                asset(calibration[key],name+"."+key)
            asset(calibration["removalMask"],name+".removalMask",png=True,panorama=True,grayscale=True,source_only=True)
            require(calibration["landMesh"].lower().endswith(".locusmesh"),name+".landMesh must be a locusmesh resource")
            asset(calibration["landTexture"],name+".landTexture",png=True)
            asset(calibration["waterCoverage"],name+".waterCoverage",png=True,panorama=True,grayscale=True,raw_gray=True)
            asset(calibration["reflectionPanorama"],name+".reflectionPanorama",png=True,panorama=True)
        surface = region.get("surface", {})
        _keys(
            surface,
            set(),
            {
                "motion",
                "waveHeightMeters",
                "waveLengthMeters",
                "waveSpeed",
                "directionDegrees",
                "flowMetersPerSecond",
                "roughness",
                "detailFadeMeters",
                "normalMap",
            },
            base + ".surface",
            require,
        )
        motion = surface.get("motion", "ocean")
        motions = ("still", "ocean", "lake", "stream") if allow_legacy_motion else ("still", "ocean")
        require(
            motion in motions,
            base + ".surface.motion is invalid",
        )
        oceans += uses_fft(surface)
        maxsize = max(region["sizeMeters"])
        floor = (
            (
                math.pi * region["sizeMeters"][0] / (256 if region.get("contactCalibration") is not None else 64)
                if shape == "disc"
                else maxsize / 64
            )
            * 2
            / 0.61
        )
        for name, default, lo, hi in [
            ("waveHeightMeters", 0.08, 0, 20),
            ("waveLengthMeters", 3, max(0.05, floor), 1000),
            ("waveSpeed", 0.8, -100, 100),
            ("directionDegrees", 0, -360, 360),
            ("roughness", 0.18, 0, 1),
        ]:
            require(
                _finite(surface.get(name, default), lo, hi),
                base + ".surface." + name + " is invalid",
            )
        require(
            _array(surface.get("flowMetersPerSecond", [0, 0]), 2, -100, 100),
            base + ".surface.flowMetersPerSecond is invalid",
        )
        if "detailFadeMeters" in surface:
            require(
                _array(surface["detailFadeMeters"], 2, 1, 5000)
                and surface["detailFadeMeters"][0] < surface["detailFadeMeters"][1],
                base + ".surface.detailFadeMeters is invalid",
            )
        if "normalMap" in surface:
            asset(surface["normalMap"], base + ".surface.normalMap", png=True)
        if "optics" in region:
            o = region["optics"]
            _keys(
                o,
                set(),
                {"color", "absorptionPerMeter", "reflectionBlur", "sunGlint"},
                base + ".optics",
                require,
            )
            require(
                _array(o.get("color", [0.03, 0.18, 0.24]), 3, 0, 1)
                and _array(o.get("absorptionPerMeter", [0.95, 0.28, 0.08]), 3, 0, 50)
                and _finite(o.get("reflectionBlur", 1.5), 0, 8)
                and _finite(o.get("sunGlint", 1), 0, 20),
                base + ".optics is invalid",
            )
        if "bed" in region:
            b = region["bed"]
            _keys(
                b,
                {"albedo", "depthMeters"},
                {
                    "reliefMeters",
                    "tileMeters",
                    "extentMeters",
                    "caustics",
                    "shoreline",
                    "sunVisibility",
                    "deepening",
                },
                base + ".bed",
                require,
            )
            asset(b["albedo"], base + ".bed.albedo", png=True, rgba=True)
            require(
                _finite(b["depthMeters"], -50, 50)
                and _finite(b.get("reliefMeters", 0), 0, 50)
                and _finite(b.get("caustics", 0.6), 0, 4)
                and (not ("tileMeters" in b and "extentMeters" in b)),
                base + ".bed is invalid",
            )
            if "tileMeters" in b:
                require(
                    _finite(b["tileMeters"], 0.1, 1000),
                    base + ".bed.tileMeters is invalid",
                )
            if "extentMeters" in b:
                require(
                    _array(b["extentMeters"], 4, -1000, 1000)
                    and b["extentMeters"][0] < b["extentMeters"][2]
                    and (b["extentMeters"][1] < b["extentMeters"][3]),
                    base + ".bed.extentMeters is invalid",
                )
            if "sunVisibility" in b:
                require(
                    "extentMeters" in b and (not sun_path),
                    base + ".bed.sunVisibility requires extentMeters and no sunPath",
                )
                asset(
                    b["sunVisibility"],
                    base + ".bed.sunVisibility",
                    png=True,
                    grayscale=True,
                    **({"raw_gray": True} if (region.get("reflectionRegistration") or {}).get("model") == "mask-layered-v1" else {}),
                )
            if "deepening" in b:
                d = b["deepening"]
                name = base + ".bed.deepening"
                require(owner == "view", name + " is View-only")
                _keys(d, {"startMeters", "endMeters", "depthMeters"}, {"color", "rmsSlope", "shoreSlope"}, name, require)
                require("extentMeters" not in b, name + " requires a tiled bed")
                require(
                    _finite(d["startMeters"], 0, 5000)
                    and _finite(d["endMeters"], 0, 5000)
                    and d["startMeters"] < d["endMeters"]
                    and _finite(d["depthMeters"], -50, 50)
                    and d["depthMeters"] >= b["depthMeters"]
                    and _array(d.get("color", [0, 0, 0]), 3, 0, 1)
                    and _finite(d.get("rmsSlope", 0), 0, 0.5)
                    and _finite(d.get("shoreSlope", 0.05), 0.005, 1),
                    name + " is invalid",
                )
            if "shoreline" in b:
                sh = b["shoreline"]
                _keys(
                    sh,
                    set(),
                    {"foam", "swashMeters", "swashPeriodSeconds"},
                    base + ".bed.shoreline",
                    require,
                )
                require(
                    _finite(sh.get("foam", 1), 0, 4)
                    and _finite(sh.get("swashMeters", 0.04), 0, 0.5)
                    and _finite(sh.get("swashPeriodSeconds", 5.5), 0.5, 60),
                    base + ".bed.shoreline is invalid",
                )
        if "blend" in region:
            blend = region["blend"]
            _keys(
                blend,
                set(),
                {"panoramaMask", "horizonSkirt", "roomKeepOut"},
                base + ".blend",
                require,
            )
            require(owner == "view", base + ".blend is View-only")
            require(
                type(blend.get("horizonSkirt", False)) is bool
                and type(blend.get("roomKeepOut", False)) is bool,
                base + ".blend is invalid",
            )
            require(
                not blend.get("horizonSkirt", False) or shape == "disc",
                base + ".blend.horizonSkirt requires disc",
            )
            if "panoramaMask" in blend:
                asset(
                    blend["panoramaMask"],
                    base + ".blend.panoramaMask",
                    png=True,
                    panorama=True,
                    grayscale=True,
                    **({"source_only": True} if "contactCalibration" in region else ({"reflection_registration": ("mask-layered-v1" if region["reflectionRegistration"]["model"] == "mask-layered-v1" else True)} if "reflectionRegistration" in region else {})),
                )
        if "glow" in region:
            g = region["glow"]
            _keys(
                g,
                set(),
                {
                    "color",
                    "strength",
                    "density",
                    "pulseHz",
                    "haloSize",
                    "bedAmount",
                    "columnAmount",
                    "depthRangeMeters",
                    "patchiness",
                    "patchMeters",
                    "bedTileMeters",
                    "particleTileMeters",
                    "sparkle",
                    "sparkleWave",
                    "sparkleTileMeters",
                    "surfaceFlashes",
                    "mover",
                },
                base + ".glow",
                require,
            )
            require(
                _array(g.get("color", [0.1, 0.85, 1]), 3, 0, 1)
                and _finite(g.get("strength", 0), 0, 4)
                and _finite(g.get("density", 0.5), 0, 1)
                and _finite(g.get("pulseHz", 0.2), 0.02, 2)
                and _finite(g.get("haloSize", 0.5), 0, 1)
                and _finite(g.get("bedAmount", 1), 0, 2)
                and _finite(g.get("columnAmount", 1), 0, 2)
                and _array(g.get("depthRangeMeters", [0.15, 1.2]), 2, 0, 5)
                and (
                    g.get("depthRangeMeters", [0.15, 1.2])[0]
                    < g.get("depthRangeMeters", [0.15, 1.2])[1]
                )
                and _finite(g.get("patchiness", 0), 0, 1)
                and _finite(g.get("patchMeters", 12), 2, 50)
                and all(
                    (
                        _finite(g.get(k, d), 0.25, 100)
                        for (k, d) in [
                            ("bedTileMeters", 8),
                            ("particleTileMeters", 1.25),
                            ("sparkleTileMeters", 0.625),
                        ]
                    )
                )
                and _finite(g.get("sparkle", 0), 0, 4)
                and _finite(g.get("sparkleWave", 1), 0, 2)
                and _finite(g.get("surfaceFlashes", 0), 0, 2),
                base + ".glow is invalid",
            )
            if "mover" in g:
                mover = g["mover"]
                require(
                    owner == "view"
                    and isinstance(mover, list)
                    and len(mover) == 4
                    and _finite(mover[0], -1000, 1000)
                    and _finite(mover[1], -1000, 1000)
                    and _finite(mover[2], 0.1, 25)
                    and _finite(mover[3], 0, 1),
                    base + ".glow.mover is invalid",
                )
    require(oceans <= 1, field + ".regions has more than one ocean")
