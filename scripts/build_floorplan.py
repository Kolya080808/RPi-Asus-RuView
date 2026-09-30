"""Create annotation plans from the supplied Polycam GLB archive.

Requires numpy, scipy, and matplotlib. No device access or network calls.
Coordinates: plan x = GLB x, plan y = -GLB z; GLB y is height.
"""
import hashlib
import json
from pathlib import Path
import struct
import zipfile

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection, LineCollection
from matplotlib.patches import Polygon
import numpy as np
from scipy.spatial import ConvexHull

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'maps' / 'home'


def load_scene(archive):
    with zipfile.ZipFile(archive) as z:
        names = [n for n in z.namelist() if n.lower().endswith('.glb')]
        if len(names) != 1:
            raise ValueError('Expected exactly one GLB in the archive')
        raw = z.read(names[0])
    magic, version, length = struct.unpack_from('<4sII', raw)
    assert magic == b'glTF' and version == 2 and length == len(raw)
    chunks = {}
    pos = 12
    while pos < length:
        size, kind = struct.unpack_from('<II', raw, pos)
        chunks[kind] = raw[pos + 8:pos + 8 + size]
        pos += 8 + size
    doc = json.loads(chunks[0x4e4f534a])
    binary = chunks[0x004e4942]

    def accessor(index):
        a = doc['accessors'][index]
        assert 'sparse' not in a
        view = doc['bufferViews'][a['bufferView']]
        assert view.get('buffer', 0) == 0
        dtype = np.dtype({5120:'i1', 5121:'u1', 5122:'<i2', 5123:'<u2',
                          5125:'<u4', 5126:'<f4'}[a['componentType']])
        width = {'SCALAR':1, 'VEC2':2, 'VEC3':3, 'VEC4':4}[a['type']]
        return np.ndarray((a['count'], width), dtype=dtype, buffer=binary,
                          offset=view.get('byteOffset', 0) + a.get('byteOffset', 0),
                          strides=(view.get('byteStride', width * dtype.itemsize), dtype.itemsize)).copy()

    objects = []

    def visit(index, parent):
        node = doc['nodes'][index]
        if 'matrix' in node:
            local = np.array(node['matrix']).reshape(4, 4, order='F')
        else:
            x,y,z,w = node.get('rotation', [0,0,0,1])
            rotation = np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                                 [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                                 [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
            local = np.eye(4)
            local[:3,:3] = rotation @ np.diag(node.get('scale', [1,1,1]))
            local[:3,3] = node.get('translation', [0,0,0])
        world = parent @ local
        if 'mesh' in node:
            for p in doc['meshes'][node['mesh']]['primitives']:
                assert p.get('mode', 4) == 4
                v = accessor(p['attributes']['POSITION'])
                v = (np.c_[v, np.ones(len(v))] @ world.T)[:,:3]
                idx = accessor(p['indices']).ravel() if 'indices' in p else np.arange(len(v))
                objects.append({'name':node.get('name', str(index)), 'vertices':v, 'faces':idx.reshape(-1,3)})
        for child in node.get('children', []):
            visit(child, world)

    for index in doc['scenes'][doc.get('scene',0)]['nodes']:
        visit(index, np.eye(4))
    return objects, names[0], hashlib.sha256(raw).hexdigest()


def project(v):
    return v[..., [0,2]] * [1,-1]


def section(obj, height=1.0):
    segments = []
    for tri in obj['vertices'][obj['faces']]:
        points = []
        for a,b in zip(tri, np.roll(tri,-1,axis=0)):
            if (a[1] < height) != (b[1] < height):
                points.append(a + (b-a) * ((height-a[1]) / (b[1]-a[1])))
        if len(points) == 2:
            segments.append(project(np.array(points)))
    return segments


def main():
    objects, member, digest = load_scene(ROOT / '3dmodelhome.zip')
    OUT.mkdir(parents=True, exist_ok=True)
    floor = [o for o in objects if o['name'].startswith('Floor_')]
    bounds = np.concatenate([project(o['vertices']) for o in floor])
    lo,hi = bounds.min(axis=0),bounds.max(axis=0)
    rooms = []
    for index,o in enumerate(floor,1):
        triangles = project(o['vertices'][o['faces']])
        heights = o['vertices'][o['faces']][:,:,1]
        top = triangles[np.all(np.isclose(heights, o['vertices'][:,1].max(), atol=1e-4), axis=1)]
        a,b,c = top[:,0],top[:,1],top[:,2]
        area = abs((b[:,0]-a[:,0])*(c[:,1]-a[:,1])-(b[:,1]-a[:,1])*(c[:,0]-a[:,0]))/2
        centroid = np.average(top.mean(axis=1),axis=0,weights=area)
        rooms.append({'id':f'R{index:02}', 'source_name':o['name'],
                      'label_position_m':centroid.tolist(), 'scan_area_m2':float(area.sum()),
                      'floor_triangles_m':top.round(5).tolist()})
    metadata = {'source_archive':'3dmodelhome.zip','source_member':member,'glb_sha256':digest,
                'units':'meters (GLB scale; not independently verified)',
                'coordinate_system':{'x':'GLB x','y':'-GLB z','height':'GLB y','north':'unknown'},
                'wall_section_height_m':1.0,'bounds_m':[lo.tolist(),hi.tolist()],
                'rooms':rooms, 'devices':[]}
    (OUT / 'floorplan.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    for furnished in [False,True]:
        fig,ax = plt.subplots(figsize=(12,12))
        fig.patch.set_facecolor('#ffffff')
        fig.subplots_adjust(left=.08,right=.96,bottom=.12,top=.88)
        for room in rooms:
            ax.add_collection(PolyCollection(room['floor_triangles_m'],facecolor='#f5f7f8',edgecolor='none',zorder=1))
        if furnished:
            for o in objects:
                if o['name'].startswith(('Floor_','Ceiling_','Wall_','Joint_','Door_','Window_')):continue
                points = np.unique(project(o['vertices']).round(5),axis=0)
                if len(points)>2:
                    hull = points[ConvexHull(points).vertices]
                    ax.add_patch(Polygon(hull,facecolor='#dce3e8',edgecolor='#99a7b4',linewidth=.65,zorder=3))
        for o in objects:
            if o['name'].startswith(('Wall_','Joint_')):
                segments = section(o)
                if segments:ax.add_collection(LineCollection(segments,colors='#273442',linewidths=1.5,zorder=5))
            if o['name'].startswith(('Door_','Window_')):
                p=project(o['vertices']);center=p.mean(axis=0)
                _,_,vectors=np.linalg.svd(p-center,full_matrices=False)
                direction=vectors[0];t=(p-center)@direction
                line=np.array([center+direction*t.min(),center+direction*t.max()])
                door=o['name'].startswith('Door_')
                ax.plot(*line.T,color='#bc7833' if door else '#288aae',linewidth=2.5,
                        linestyle='--' if door else '-',zorder=6)
        for room in rooms:
            ax.text(*room['label_position_m'],room['id'],ha='center',va='center',fontsize=11,
                    color='#405263',weight='bold',zorder=8,
                    bbox=dict(boxstyle='round,pad=.24',fc='white',ec='none',alpha=.88))
        ax.set_xlim(lo[0]-.45,hi[0]+.45);ax.set_ylim(lo[1]-.45,hi[1]+.45)
        ax.set_aspect('equal');ax.set_xlabel('Plan x (m)',labelpad=10);ax.set_ylabel('Plan y (m)',labelpad=10)
        ax.set_xticks(np.arange(np.ceil(lo[0]),np.floor(hi[0])+1));ax.set_yticks(np.arange(np.ceil(lo[1]),np.floor(hi[1])+1))
        ax.grid(color='#d9e0e5',linewidth=.45,alpha=.7,zorder=2)
        ax.tick_params(labelsize=9,colors='#667585')
        for spine in ax.spines.values():spine.set_color('#d9e0e5')
        fig.text(.08,.952,'HOME / DEVICE PLACEMENT',fontsize=21,weight='bold',color='#243342')
        fig.text(.08,.92,'Polycam scan · top view · '+('furniture reference' if furnished else 'clear annotation plan'),fontsize=12,color='#637487')
        fig.text(.08,.064,'R01–R08: scan regions, room names to be confirmed.   Dashed amber: doors.   Blue: windows.',fontsize=10,color='#536477')
        fig.text(.08,.041,'Mark router / repeaters and their height above the floor. Scale follows the scan; north is unknown.',fontsize=10,color='#536477')
        stem='floorplan-furnished' if furnished else 'floorplan'
        fig.savefig(OUT/(stem+'.png'),dpi=200)
        fig.savefig(OUT/(stem+'.svg'))
        plt.close(fig)
    print(json.dumps({'output':str(OUT),'regions':len(rooms),'size_m':(hi-lo).round(2).tolist(),'objects':len(objects)}))


if __name__ == '__main__':
    main()
