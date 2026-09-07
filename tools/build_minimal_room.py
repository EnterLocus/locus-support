"""Build the one-seat Room used by the public authoring walkthrough.

Run inside Blender 5.2 with --background --factory-startup --python-exit-code 1
--python tools/build_minimal_room.py -- --output /absolute/path/to/new-directory.
The script refuses an existing output directory and uses no downloaded assets.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys

import bpy
from mathutils import Vector
from pxr import Usd, UsdGeom


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"

    def material(name, color, roughness):
        result = bpy.data.materials.new(name)
        result.use_nodes = True
        surface = result.node_tree.nodes.get("Principled BSDF")
        surface.inputs["Base Color"].default_value = (*color, 1)
        surface.inputs["Roughness"].default_value = roughness
        return result

    wood = material("Warm_Wood", (.38, .20, .09), .7)
    plaster = material("Light_Plaster", (.73, .69, .59), .85)
    metal = material("Dark_Metal", (.06, .075, .08), .65)
    glow = material("Lamp_Glow", (1, .64, .30), .5)
    surface = glow.node_tree.nodes.get("Principled BSDF")
    surface.inputs["Emission Color"].default_value = (1, .64, .30, 1)
    surface.inputs["Emission Strength"].default_value = 1

    model_objects = []

    def box(name, position, dimensions, mat):
        bpy.ops.mesh.primitive_cube_add(size=1, location=position)
        obj = bpy.context.object
        obj.name = name
        obj.data.name = name + "_Geometry"
        obj.dimensions = dimensions
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.data.materials.append(mat)
        model_objects.append(obj)
        return obj

    box("Floor", (0, 0, -.08), (4, 4, .16), wood)
    box("Back_Wall", (0, -1.95, 1.3), (4, .1, 2.6), plaster)
    box("Left_Wall", (-1.95, 0, 1.3), (.1, 4, 2.6), plaster)
    box("Roof", (0, 0, 2.65), (4, 4, .1), plaster)
    box("Table_Top", (0, .4, .70), (1.5, .7, .08), wood)
    for number, (x, y) in enumerate([(-.65, .12), (.65, .12), (-.65, .68), (.65, .68)]):
        box(f"Table_Leg_{number}", (x, y, .33), (.07, .07, .66), metal)
    box("Chair_Seat", (0, -.45, .44), (.5, .5, .08), wood)
    box("Chair_Back", (0, -.69, .70), (.5, .06, .55), wood)
    for number, (x, y) in enumerate([(-.2, -.65), (.2, -.65), (-.2, -.25), (.2, -.25)]):
        box(f"Chair_Leg_{number}", (x, y, .2), (.06, .06, .4), metal)
    box("Pendant_Stem", (0, .4, 2.42), (.035, .035, .36), metal)
    box("Pendant_Glow", (0, .4, 2.21), (.32, .32, .06), glow)
    for obj in model_objects:
        obj["locus_ui_fade"] = obj.name.startswith(("Table_", "Chair_"))
    # Export only architecture and furnishings. Cameras and preview lights are
    # added afterward; the app creates the explicit metadata-owned light.
    bpy.ops.object.select_all(action="DESELECT")
    for obj in model_objects:
        obj.select_set(True)
    model_path = out / "scene.usdz"
    bpy.ops.wm.usd_export(
        filepath=str(model_path), selected_objects_only=True,
        export_materials=True, generate_preview_surface=True,
        generate_materialx_network=False, convert_orientation=True,
        export_global_forward_selection="NEGATIVE_Z", export_global_up_selection="Y",
        export_textures_mode="NEW", export_lights=False, export_cameras=False,
        triangulate_meshes=True, meters_per_unit=1)

    # The authored seat is (0, -.45, 1.2) in Blender Z-up; after conversion it
    # is (0, 1.2, .45). Compute normalized XZ from the delivered USDZ, not guesses.
    stage = Usd.Stage.Open(str(model_path))
    bounds = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_]).ComputeWorldBound(
        stage.GetPseudoRoot()).ComputeAlignedRange()
    lo, hi = bounds.GetMin(), bounds.GetMax()
    anchor = [(0 - lo[0]) / (hi[0] - lo[0]), (.45 - lo[2]) / (hi[2] - lo[2])]

    bpy.ops.object.camera_add(location=(6, 8, 5))
    camera = bpy.context.object
    camera.name = "Review_Camera"
    scene.camera = camera
    camera.data.lens = 46
    world = bpy.data.worlds.new("Review_World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (.65, .73, .85, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = .5
    scene.world = world
    bpy.ops.object.light_add(type="AREA", location=(2, 4, 5))
    fill = bpy.context.object
    fill.data.energy = 900
    fill.data.shape = "DISK"
    fill.data.size = 4
    fill.rotation_euler = (Vector((0, .4, .7)) - fill.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 24
    scene.cycles.seed = 0
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "JPEG"

    def render(path, position, direction):
        camera.location = position
        camera.rotation_euler = Vector(direction).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)

    render(out / "thumbnail.jpg", (6, 8, 5), (-6, -8, -3.8))
    review = out / "review"
    review.mkdir()
    camera.data.lens = 18
    seat = Vector((0, -.45, 1.2))
    for name, direction in {"front": (0, 1, 0), "right": (1, 0, 0), "back": (0, -1, 0),
                            "left": (-1, 0, 0), "up": (0, .01, 1), "down": (0, .01, -1)}.items():
        render(review / f"seat-{name}.jpg", seat, direction)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "MinimalReadingRoom.blend"))

    skill = Path(__file__).resolve().parents[1] / ".agents/skills/build-original-locus-room"
    command = ["python3", str(skill / "scripts/scaffold_locus_room.py"), str(out / "room"),
               "--scene", str(model_path), "--thumbnail", str(out / "thumbnail.jpg"),
               "--display-name", "Minimal Reading Room", "--caption", "One desk, one seat, and one light.",
               "--creator", "EnterLocus.com", "--requested-credit", "EnterLocus.com",
               "--modification-notes", "Original geometry built by the public walkthrough script; no external assets.",
               "--license-id", "LicenseRef-EnterLocus-Proprietary",
               "--license-name", "EnterLocus Proprietary Asset License",
               "--license-url", "https://enterlocus.com/asset-rights/", "--ai-provider", "OpenAI Codex",
               "--seat-title", "Reading Desk", "--seat-anchor", *map(str, anchor),
               "--source-floor-offset", str(-lo[1]), "--eye-height", "1.2",
               "--desk-entity", "Table_Top", "--wall-entity", "Back_Wall", "--wall-entity", "Left_Wall",
               "--roof-entity", "Roof", "--light-body", "Pendant_Glow", "--light-anchor", "Pendant_Glow",
               "--light-direction", "0", "-1", "0", "--light-lumens", "650"]
    for obj in model_objects:
        if obj["locus_ui_fade"]:
            command.extend(["--ui-fade-entity", obj.name])
    subprocess.run(command, check=True)
    (out / "review/bounds.json").write_text(json.dumps({"min": list(lo), "max": list(hi),
        "seatAnchorXZ": anchor, "sourceFloorOffset": -lo[1], "eyeY": 1.2, "tabletopY": .74}, indent=2) + "\n")
    print("BUILT", out / "room", flush=True)


if __name__ == "__main__":
    main()
