"""Build an independent public Room v5 example from editable Blender geometry.

Blender --background --factory-startup --python-exit-code 1 --python this.py --
  --output <new directory>
The .blend and its render stay beside the flat public source folder. The
archive uses app-assigned identity and no built-in Room names or special flags.
"""
from __future__ import annotations
import argparse,json,math,sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    public=out/'room';public.mkdir(exist_ok=True)
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    scene=bpy.context.scene
    scene.unit_settings.system='METRIC'
    def texture(name, kind):
        n=256;y,x=np.mgrid[0:n,0:n]
        if kind=='grain':
            v=(.5+.12*np.sin(y*.3+np.sin(x*.05))+.02*np.sin(y*4))
            rgb=np.stack([v*.72,v*.43,v*.23],axis=-1)
        elif kind=='normal':rgb=np.full((n,n,3),[.5,.5,1.0])
        else:
            v=.22+.5*((x//32+y//32)%2);rgb=np.repeat(v[:,:,None],3,axis=2)
        rgba=np.concatenate([rgb,np.ones((n,n,1))],axis=2).astype(np.float32)
        image=bpy.data.images.new(name,width=n,height=n)
        image.colorspace_settings.name='sRGB' if kind=='grain' else 'Non-Color'
        image.pixels.foreach_set(rgba.ravel());image.filepath_raw=str(out/f'{name}.png');image.file_format='PNG';image.save();image.pack()
        return image
    rough=texture('roughness-study','rough');grain=texture('grain-study','grain');normal=texture('normal-study','normal')
    def mat(name,color,roughness,alpha=1,coat=0,coat_rough=.2,rough_map=False,coat_map=False,emission=0,grain_map=False):
        m=bpy.data.materials.new(name);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF')
        p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=roughness
        # These panes and water are transmissive surfaces, not alpha cutouts.
        # Blender's PreviewSurface exporter maps transmission to 1-opacity;
        # setting Alpha alone is overwritten by the default zero transmission.
        p.inputs['Transmission Weight'].default_value=1-alpha
        p.inputs['Coat Weight'].default_value=coat;p.inputs['Coat Roughness'].default_value=coat_rough
        if emission:p.inputs['Emission Color'].default_value=(*color,1);p.inputs['Emission Strength'].default_value=emission
        for socket,img in [('Roughness',rough if rough_map else None),('Coat Weight',rough if coat_map else None),('Base Color',grain if grain_map else None)]:
            if img:
                t=m.node_tree.nodes.new('ShaderNodeTexImage');t.image=img;m.node_tree.links.new(t.outputs['Color'],p.inputs[socket])
        if grain_map:
            t=m.node_tree.nodes.new('ShaderNodeTexImage');t.image=normal
            n=m.node_tree.nodes.new('ShaderNodeNormalMap');m.node_tree.links.new(t.outputs['Color'],n.inputs['Color']);m.node_tree.links.new(n.outputs['Normal'],p.inputs['Normal'])
        return m
    plaster=mat('Surface_A',(.66,.63,.57),.85)
    matte=mat('Surface_B',(.35,.20,.09),.82,grain_map=True)
    gloss=mat('Surface_C',(.35,.20,.09),.3,coat=.15,coat_rough=.18,rough_map=True,grain_map=True)
    clear=mat('Surface_D',(.83,.9,.95),.02,alpha=.1)
    frosted=mat('Surface_E',(.83,.9,.95),.62,alpha=.16)
    mapped=mat('Surface_F',(.83,.9,.95),.3,alpha=.22,coat=.5,rough_map=True,coat_map=True)
    water=mat('Surface_G',(.08,.24,.3),.08,alpha=.45)
    dark=mat('Surface_H',(.045,.052,.062),.7)
    warm=mat('Surface_I',(1,.62,.3),.35,emission=2)
    root=bpy.data.objects.new('Study',None);scene.collection.objects.link(root)
    def box(name,pos,size,material,fade=False,soft=False):
        bpy.ops.mesh.primitive_cube_add(size=1,location=pos);obj=bpy.context.object;obj.name=name;obj.dimensions=size
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        obj.data.materials.append(material);obj.parent=root
        obj['locus_ui_fade']=fade;obj['locus_softened_reflection']=soft
        return obj
    box('P201',(-1.75,0,-.08),(3.5,5,.16),matte)
    box('P202',(1.75,0,-.08),(3.5,5,.16),gloss)
    box('P301',(0,2.45,1.45),(7,.1,2.9),plaster)
    box('P302',(-3.45,0,1.45),(.1,5,2.9),plaster)
    box('P303',(3.45,0,1.45),(.1,5,2.9),plaster)
    box('P304',(-2.6,.8,.45),(.7,.7,.9),plaster) # small structural pier: no fade permission
    box('P101',(-2.2,-2.44,1.3),(1.5,.03,2.6),clear)
    box('P102',(0,-2.44,1.3),(1.5,.03,2.6),frosted,soft=True)
    box('P103',(2.2,-2.44,1.3),(1.5,.03,2.6),mapped)
    box('Glass_Art_01',(2.4,.2,.1),(1.3,1.3,.025),water) # name never assigns a glass preset
    box('P401',(0,-.75,.74),(1.5,.7,.08),matte,fade=True)
    for x in [-.62,.62]:
        box('P402' if x<0 else 'P403',(x,-.75,.35),(.08,.55,.7),dark,fade=True)
    box('P404',(0,.15,.42),(.5,.5,.08),dark,fade=True)
    box('P405',(0,.39,.7),(.5,.07,.55),dark,fade=True)
    box('P406',(-.7,1.7,.44),(4.1,.6,.13),matte,fade=True) # >3m authored furniture
    emitter=box('P501',(1.3,1.55,2.45),(.18,.18,.18),warm)
    lamp_data=bpy.data.lights.new('SourceLight','SPOT');lamp_data.energy=500;lamp_data.spot_size=math.radians(60)
    lamp=bpy.data.objects.new('SourceLight',lamp_data);scene.collection.objects.link(lamp);lamp.location=emitter.location
    lamp.rotation_euler=(Vector((0,2.4,1.3))-lamp.location).to_track_quat('-Z','Y').to_euler()
    direction=lamp.rotation_euler.to_quaternion() @ Vector((0,0,-1))
    d=[round(direction.x,8),round(direction.z,8),round(-direction.y,8)]
    metadata={'formatVersion':5,'displayName':'Material Study','caption':'A Room for comparing authored materials and a wall-facing light.',
        'seatedOrigin':{'translationMeters':[0,0,0],'orientationXYZW':[0,0,0,1]},
        'safeHeadVolume':{'centerMeters':[0,1.2,0],'sizeMeters':[1.2,.8,1.2]},
        'viewOpenings':[{'id':'front','transform':{'translationMeters':[0,1.3,2.5],'orientationXYZW':[0,0,0,1]},'widthMeters':6.8,'heightMeters':2.6}],
        'spatialAdaptation':{'wallEntities':['P301','P302','P303'],'roofEntities':[],'deskEntitiesByTeleportID':{'seat.primary':'P401'}},
        'rendering':{'softenedReflectionEntities':['P102'],'uiFadeEntities':[f'P40{i}' for i in range(1,7)]},
        'lighting':{'luminaireGroups':[{'id':'reading-light','displayName':'Reading Light','entities':['P501'],
            'controls':{'brightnessEVRange':[-4,1],'temperatureKelvinRange':[2000,6500],'supportsFullColor':True},
            'proxy':{'type':'spot','anchorEntity':'P501','intensityLumens':650,'attenuationRadiusMeters':4,'innerAngleDegrees':25,'outerAngleDegrees':60,'castsShadow':False,'direction':d}}]}}
    scene['locus_public_room_metadata']=json.dumps(metadata)
    lamp['locus_direction_y_up']=d
    for filename,value in [('space.json',metadata),('teleport-points.json',{'formatVersion':1,'points':[{'id':'seat.primary','title':'Study Desk','anchorXZ':[.5,.47],'sourceFloorOffset':0,'eyeHeight':1.2,'yawRadians':math.pi}]}),('provenance.json',{'formatVersion':1,'creatorOrAgency':'EnterLocus.com','license':{'identifier':'LicenseRef-EnterLocus-Proprietary','name':'EnterLocus proprietary asset license','url':'https://enterlocus.com/asset-rights/'},'requestedCredit':'Locus','modificationNotes':'Original procedural model and textures authored for material-fidelity verification.','aiGenerated':True,'aiProvider':'OpenAI Codex'})]:
        (public/filename).write_text(json.dumps(value,indent=2)+'\n')
    # Source model retains the authored spotlight. Product light comes from metadata.
    bpy.ops.object.select_all(action='DESELECT')
    for obj in scene.objects:
        if obj.type in {'MESH','EMPTY'}:obj.select_set(True)
    bpy.ops.wm.usd_export(filepath=str(public/'scene.usdz'),selected_objects_only=True,export_materials=True,generate_preview_surface=True,generate_materialx_network=False,convert_orientation=True,export_global_forward_selection='NEGATIVE_Z',export_global_up_selection='Y',export_textures_mode='NEW',export_lights=False,export_cameras=False,triangulate_meshes=True,meters_per_unit=1)
    bpy.ops.export_scene.gltf(filepath=str(out/'material-study.glb'),export_format='GLB',use_selection=True,export_yup=True,export_lights=False,export_cameras=False)
    bpy.ops.object.camera_add(location=(9,-13,8));camera=bpy.context.object;camera.name='PreviewCamera';camera.rotation_euler=(Vector((0,0,1))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='PERSP';camera.data.lens=48;scene.camera=camera
    world=bpy.data.worlds.new('PreviewWorld');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.55,.65,.8,1);world.node_tree.nodes['Background'].inputs[1].default_value=.45;scene.world=world
    bpy.ops.object.light_add(type='AREA',location=(0,-4,7));fill=bpy.context.object;fill.data.energy=1300;fill.data.shape='DISK';fill.data.size=6;fill.rotation_euler=(Vector((0,0,0))-fill.location).to_track_quat('-Z','Y').to_euler()
    scene.render.engine='CYCLES';scene.cycles.samples=32;scene.render.resolution_x=1600;scene.render.resolution_y=900;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='JPEG';scene.render.filepath=str(public/'thumbnail.jpg')
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'MaterialStudy.blend'))
    for image in bpy.data.images:
        if image.source == 'FILE':
            image.filepath = '//' + Path(image.filepath).name
            if not image.packed_file:
                image.pack()
            for packed in image.packed_files:
                packed.filepath = image.filepath
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'MaterialStudy.blend'))
    bpy.ops.render.render(write_still=True)
    print('AUTHORED PUBLIC ROOM',public,flush=True)

if __name__=='__main__':main()
