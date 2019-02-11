from mathutils import Matrix, Vector
import bpy
import importlib
import sys
from math import pi
import os
import json
'''
Copyright (C) 2018 Dawid Huczyński
dawid.huczynski@gmail.com

Created by Dawid Huczyński

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

bl_info = {
    "name": "Meshroom importer",
    "description": "Imports from .mg file cameras, images, sparse and obj",
    "author": "Dawid Huczyński",
    "version": (0, 0, 1),
    "blender": (2, 80, 0),
    "location": "File > Import > Import Meshroom",
    "warning": "This addon is still in development.",
    "wiki_url": "",
    "category": "Import-Export"}


filepath = r'D:\Koszyk\koszyk.mg'

# module import https://github.com/uhlik/bpy/blob/master/view3d_point_cloud_visualizer.py
# thanks to Jakub Uhlik
vis_mod = 'view3d_point_cloud_visualizer'
if vis_mod in sys.modules.keys() and sys.modules[vis_mod].bl_info['version'] <= (0, 7, 0):
    local_visualizer = False
else:
    from . import view3d_point_cloud_visualizer as point_cloud
    point_cloud.register()
    local_visualizer = True


def find_view_layer(coll, lay_coll=None):
    if lay_coll is None:
        lay_coll = bpy.context.view_layer.layer_collection
    if lay_coll.collection == coll:
        return lay_coll
    else:
        for child in lay_coll.children:
            a = find_view_layer(coll, child)
            if a:
                return a
        return None


def read_meshlab(filepath):
    'Handle meshlab file'

    cache = os.path.join(os.path.dirname(filepath), 'MeshroomCache')
    data = json.load(open(filepath, 'r'))
    try:
        nodeSFM = data['graph']['StructureFromMotion_1']
        nodeType = nodeSFM['nodeType']
        uid0 = nodeSFM['uids']['0']
        # sfm = nodeSFM['outputs']['output'].format(
        #     cache=cache, nodeType=nodeType, uid0=uid0)
        cameras_sfm = nodeSFM['outputs']['outputViewsAndPoses'].format(
            cache=cache, nodeType=nodeType, uid0=uid0)
        cloud = os.path.join(cache, nodeType, uid0, 'cloud_and_poses.ply')
    except KeyError:
        cameras_sfm = cloud = None
    try:
        nodeMesh = data['graph']['Meshing_1']
        dense_obj = nodeMesh['outputs']['output'].format(
            cache=cache, nodeType=nodeMesh['nodeType'], uid0=nodeMesh['uids']['0'])
    except KeyError:
        dense_obj = None
    try:
        nodeTex = data['graph']['Texturing_1']
        tex_obj = nodeTex['outputs']['outputMesh'].format(
            cache=cache, nodeType=nodeTex['nodeType'], uid0=nodeTex['uids']['0'])
    except KeyError:
        tex_obj = None
    return (cameras_sfm, cloud, dense_obj, tex_obj)


def import_cameras(cameras_sfm, img_depth):
    'read camera sfm and imports to blender'
    data = json.load(open(cameras_sfm, 'r'))
    poses = {x['poseId']: x['pose'] for x in data['poses']}
    intrinsics = {x['intrinsicId']: x for x in data['intrinsics']}

    render = bpy.context.scene.render
    render.resolution_x = int(data['views'][0]['width'])
    render.resolution_y = int(data['views'][0]['height'])

    for view in data['views']:
        view_id = view['viewId']
        path = view['path']
        width, height = int(view['width']), int(view['height'])
        focal_length = float(view['metadata']['Exif:FocalLength'])
        pose = poses[view['poseId']]['transform']
        intrinsic = intrinsics[view['intrinsicId']]
        pxFocalLength = float(intrinsic['pxFocalLength'])
        principalPoint = [float(x) for x in intrinsic['principalPoint']]
        
        # camera
        bcam = bpy.data.cameras.new(f'View {view_id}')
        bcam.display_size = .25
        bcam.sensor_width = focal_length
        bcam.lens_unit = 'MILLIMETERS'
        bcam.lens = (pxFocalLength/max((width,height)))*focal_length
        bcam.shift_x = (principalPoint[0] - width/2)/width
        bcam.shift_y = (principalPoint[1] - height/2)/height
        
        # image
        bcam.show_background_images = True
        bg = bcam.background_images.new()
        bg.image = bpy.data.images.load(path)
        bg.display_depth = img_depth
        
        # camera object
        ob = bpy.data.objects.new(f'View {view_id}', bcam)
        bpy.context.collection.objects.link(ob)
        loc = [float(x) for x in pose['center']]
        rot = [float(x) for x in pose['rotation']]
        rotation = [rot[:3], rot[3:6], rot[6:]]
        m = Matrix(rotation)
        ob.matrix_world = m.to_4x4() @ Matrix().Rotation(pi, 4, 'X')
        ob.location = Vector(loc)


def import_sparse_depricated(cloud):
    '''Depricated. Use view3d_point_cloud_visualizer instead.'''
    # read .ply file
    f = open(cloud, 'r')
    ply = f.read()
    header = ply[:1000].split('end_header\n')[0].split('\n')
    header
    assert header[0] == 'ply'
    assert header[1].startswith('format ascii')
    elements = []
    tmp_prop = []
    for x in header[2:]:
        a = x.split(' ')
        if a[0] == 'element':
            if tmp_prop:
                elements[-1]['props'] = list(tmp_prop)
                tmp_prop = []
            el = {'name': a[1], 'nr': a[2]}
            elements.append(el)
        elif a[0] == 'property':
            prop = {'name': a[2], 'type': a[1]}
            tmp_prop.append(prop)

    elements[-1]['props'] = list(tmp_prop)

    points = ply.split('end_header\n')[1].split('\n')
    if points[-1] == '':
        points.pop()

    verts = []
    for point in points:
        verts.append((float(x) for x in point.split()[:3]))

    mesh = bpy.data.meshes.new('sparse cloud SFM')
    mesh.from_pydata(verts, [], [])
    obj = bpy.data.objects.new('sparse cloud SFM', mesh)
    bpy.context.collection.objects.link(obj)


def import_object(filepath):
    bpy.ops.import_scene.obj(filepath=filepath)
    bpy.context.selected_objects[0].matrix_world = Matrix()


class import_meshroom(bpy.types.Operator):
    bl_idname = "import_scene.meshroom"
    bl_label = "Import Meshroom"
    bl_description = "Imports cameras, images, sparse and obj from meshroom .mg file"
    # bl_options = {"REGISTER"}

    files: bpy.props.CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'})

    directory: bpy.props.StringProperty(
        maxlen=1024, subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'})

    cameras: bpy.props.BoolProperty(default=True, name='Views', description='Import views as cameras and images')
    
    undistorted: bpy.props.BoolProperty(default=True, name='Undistorted', description='Better, but heavy images')
    
    DEPTH = [
        ('FRONT', 'FRONT', 'Preview semi transparent image in front of the objects', '', 0),
        ('BACK', 'BACK', 'Preview image behing objects', '', 1)
    ]
    img_front: bpy.props.EnumProperty(items=DEPTH, name='Depth', description='', default='FRONT')

    sparse: bpy.props.BoolProperty(default=True, name='Import SFM', description='')

    dense: bpy.props.BoolProperty(default=False, name='Import dense mesh', description='')

    textured: bpy.props.BoolProperty(default=True, name='Import textured mesh', description='')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        file = self.files[0].name
        directory = self.directory
        filepath = os.path.join(directory, file)
        # container collection for import
        col = bpy.data.collections.new(file)
        camera_col = bpy.data.collections.new('Views')
        col.children.link(camera_col)
        context.scene.collection.children.link(col)
        lay_col = find_view_layer(camera_col)
        context.view_layer.active_layer_collection = lay_col
        # filepath = PATH
        cameras_sfm, cloud, dense_obj, tex_obj = read_meshlab(filepath)
        if self.cameras:
            import_cameras(cameras_sfm, self.img_front)
        lay_col = find_view_layer(col)
        context.view_layer.active_layer_collection = lay_col
        if self.sparse:
            empty = bpy.data.objects.new('sparse cloud SFM', None)
            col.objects.link(empty)
            empty.select_set(True)
            context.view_layer.objects.active = empty
            bpy.ops.point_cloud_visualizer.load_ply_to_cache(filepath=cloud)
            bpy.ops.point_cloud_visualizer.draw()
        if self.dense and dense_obj:
            import_object(dense_obj)
        if self.textured and tex_obj:
            import_object(tex_obj)
        return {"FINISHED"}


class meshroom_update_focal(bpy.types.Operator):
    bl_idname = "view3d.update_focal"
    bl_label = "Meshroom: update focal"
    bl_description = "Updates Focal Length from active camera to other cameras"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        ob = context.active_object
        if ob.type == 'CAMERA':
            lens = ob.data.lens
            shift_x = ob.data.shift_x
            shift_y = ob.data.shift_y
            sensor_width = ob.data.sensor_width

            for cam in bpy.data.cameras:
                if cam.name.startswith('View '):
                    cam.lens = lens
                    cam.shift_x = shift_x
                    cam.shift_y = shift_y
                    cam.sensor_width = sensor_width
        return {"FINISHED"}


def import_meshroom_button(self, context):
    self.layout.operator(import_meshroom.bl_idname,
                         text="Import Meshroom")


classes = (
    import_meshroom,
    meshroom_update_focal,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file_import.append(import_meshroom_button)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(import_meshroom_button)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    if local_visualizer:
        point_cloud.unregister()


if __name__ == "__main__":
    register()
