"""Small authored USD sources for macOS/visionOS rendering-risk experiments.

These are data generators, not renderer replacements. No images/models are
committed. The Room fixture builder supplies the ordinary Room contract.
"""
import math
import struct
import zlib

from tests.room_fixtures import Room, room_usda, usdz_bytes


def backface_room(explicit_back_face=False):
    room = Room()
    room.box('Floor')['size'] = (8, .16, 8)
    room.boxes = [b for b in room.boxes if b['name'] != 'Back_Wall']
    counts = '4, 4' if explicit_back_face else '4'
    indices = '0, 1, 2, 3, 3, 2, 1, 0' if explicit_back_face else '0, 1, 2, 3'
    room.extra_usda = '''    def Mesh "Back_Wall" (prepend apiSchemas = ["MaterialBindingAPI"]) {
        int[] faceVertexCounts = [%s]
        int[] faceVertexIndices = [%s]
        point3f[] points = [(-2,0,-1.95),(2,0,-1.95),(2,2.6,-1.95),(-2,2.6,-1.95)]
        uniform token subdivisionScheme = "none"
        uniform bool doubleSided = 1
        rel material:binding = </root/_materials/Light_Plaster>
    }
''' % (counts, indices)
    room.seats = [
        {'id':'seat.primary','title':'Wall front','anchorXZ':[.5,.65], 'sourceFloorOffset':.16,'eyeHeight':1.2,'yawRadians':0},
        {'id':'seat.back','title':'Wall back','anchorXZ':[.5,.125], 'sourceFloorOffset':.16,'eyeHeight':1.2,'yawRadians':math.pi},
    ]
    return room


def png(rgb):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    rows = (b'\0' + bytes(rgb) * 2) * 2
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB',2,2,8,2,0,0,0)) + chunk(b'IDAT',zlib.compress(rows)) + chunk(b'IEND',b'')


class TextureRoom(Room):
    def __init__(self, split=False):
        super().__init__()
        self.split = split

    def usdz(self):
        source = room_usda(self.boxes, self.materials, self.extra_usda).decode()
        start = source.index('        def Material "Warm_Wood"')
        end = source.index('        def Material ', start + 1)
        block = source[start:end]
        block = block.replace('float inputs:roughness = 0.7', 'float inputs:roughness.connect = </root/_materials/Warm_Wood/Rough.outputs:r>' if self.split else 'float inputs:roughness.connect = </root/_materials/Warm_Wood/Rough.outputs:g>')
        block = block.replace('float inputs:metallic = 0', 'float inputs:metallic.connect = </root/_materials/Warm_Wood/Metal.outputs:r>' if self.split else 'float inputs:metallic.connect = </root/_materials/Warm_Wood/Metal.outputs:b>')
        shaders = ''
        for name, path in [('Rough','rough.png' if self.split else 'orm.png'),('Metal','metal.png' if self.split else 'orm.png')]:
            shaders += '''        def Shader "%s" {
            uniform token info:id = "UsdUVTexture"
            asset inputs:file = @%s@
            token inputs:sourceColorSpace = "raw"
            float outputs:r
            float outputs:g
            float outputs:b
        }
''' % (name,path)
        at = block.rfind('        }')
        block = block[:at] + shaders + block[at:]
        source = source[:start] + block + source[end:]
        layers = {'scene.usda': source.encode()}
        layers.update({'rough.png':png((180,180,180)), 'metal.png':png((0,0,0))} if self.split else {'orm.png':png((255,180,0))})
        return usdz_bytes(layers)
