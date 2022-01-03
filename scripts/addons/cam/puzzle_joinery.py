# blender CAM ops.py (c) 2021 Alain Pelletier
#
# ***** BEGIN GPL LICENSE BLOCK *****
#
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ***** END GPL LICENCE BLOCK *****

# blender operators definitions are in this file. They mostly call the functions from curvecamcreate.py


import bpy
from bpy.props import *
from bpy.types import Operator

from cam import utils, pack, polygon_utils_cam, simple, gcodepath, bridges, parametric, joinery
import shapely
from shapely.geometry import Point, LineString, Polygon
import mathutils
import math

def rotate(angle):
    #  rotate active object by angle in a xy plane.
    #  transformation is applied after rotation
    bpy.context.active_object.rotation_euler.z = angle
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=False)

def duplicate(x=0, y=0):
    if x ==0 and y==0:
        bpy.ops.object.duplicate_move(OBJECT_OT_duplicate={"linked": False, "mode": 'TRANSLATION'},
                                      TRANSFORM_OT_translate={"value": (x, y, 0.0)})
    else:
        bpy.ops.object.duplicate()

def mirrorx():
    bpy.ops.transform.mirror(orient_type='GLOBAL', orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                             orient_matrix_type='GLOBAL', constraint_axis=(True, False, False))

def mirrory():
    bpy.ops.transform.mirror(orient_type='GLOBAL', orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                             orient_matrix_type='GLOBAL', constraint_axis=(False, True, False))

def translate(x=0, y=0):
    bpy.ops.transform.translate(value=(x, y, 0.0))
    bpy.ops.object.transform_apply(location=True)


def finger(diameter, inside, DT=1.025, stem=2):
    # diameter = diameter of the tool for joint creation
    # tolerance = Tolerance in the joint
    # DT = Bit diameter tolerance
    # stem = amount of radius the stem or neck of the joint will have
    RESOLUTION = 12    # Data resolution
    cube_sx = diameter * DT * (2 + stem - 1) + inside
    cube_ty = diameter * DT + inside
    cube_sy = 2 * diameter * DT + inside / 2
    circle_radius = diameter * DT / 2
    c1x = (cube_sx) / 2 + inside
    c2x = (cube_sx + inside) / 2 + inside
    c2y = 3 * circle_radius
    c1y = circle_radius

    bpy.ops.curve.simple(align='WORLD', location=(0, cube_ty, 0), rotation=(0, 0, 0), Simple_Type='Rectangle',
                         Simple_width=cube_sx, Simple_length=cube_sy, use_cyclic_u=True, edit_mode=False)
    bpy.context.active_object.name = "_tmprect"


    bpy.ops.curve.simple(align='WORLD', location=(c2x, c2y, 0), rotation=(0, 0, 0), Simple_Type='Ellipse', Simple_a=circle_radius,
                         Simple_b=circle_radius + inside, Simple_sides=4, use_cyclic_u=True, edit_mode=False)

    bpy.context.active_object.name = "_tmpcirc_add"
    bpy.context.object.data.resolution_u = RESOLUTION

    bpy.ops.curve.simple(align='WORLD', location=(-c2x, c2y, 0), rotation=(0, 0, 0), Simple_Type='Ellipse', Simple_a=circle_radius,
                         Simple_b=circle_radius + inside, Simple_sides=4, use_cyclic_u=True, edit_mode=False)

    bpy.context.active_object.name = "_tmpcirc_add"
    bpy.context.object.data.resolution_u = RESOLUTION
    simple.joinMultiple('_tmpcirc')
    simple.selectMultiple('_tmp')
    bpy.ops.object.curve_boolean(boolean_type='UNION')
    bpy.context.active_object.name = "sum"
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
    bpy.context.object.scale[0] = inside * 3 + 1
    bpy.context.object.scale[1] = inside * 3 + 1
    simple.removeMultiple('_tmp')
    simple.makeActive('sum')
    bpy.context.active_object.name = "_sum"

    rc1 = circle_radius - inside
    bpy.ops.curve.simple(align='WORLD', location=(c1x, c1y, 0), rotation=(0, 0, 0), Simple_Type='Ellipse', Simple_a=circle_radius,
                         Simple_b=rc1, Simple_sides=4, use_cyclic_u=True, edit_mode=False)

    bpy.context.active_object.name = "_circ_delete"
    bpy.context.object.data.resolution_u = RESOLUTION

    bpy.ops.curve.simple(align='WORLD', location=(-c1x, c1y, 0), rotation=(0, 0, 0), Simple_Type='Ellipse', Simple_a=circle_radius,
                         Simple_b=rc1, Simple_sides=4, use_cyclic_u=True, edit_mode=False)
    bpy.context.active_object.name = "_circ_delete"
    bpy.context.object.data.resolution_u = RESOLUTION

    simple.selectMultiple("_")  # select everything starting with _

    bpy.context.view_layer.objects.active = bpy.data.objects['_sum']  # Make the plate base active
    bpy.ops.object.curve_boolean(boolean_type='DIFFERENCE')
    bpy.context.active_object.name = "PUZZLE"
    simple.removeMultiple("_")  # Remove temporary base and holes
    simple.makeActive("PUZZLE")
    bpy.context.active_object.name = "_puzzle"


def fingers(diameter, inside, amount, stem=1, DT=1.025):
    # diameter = diameter of the tool for joint creation
    # inside = Tolerance in the joint receptacle
    # DT = Bit diameter tolerance
    # stem = amount of radius the stem or neck of the joint will have
    # amount = the amount of fingers

    translate = -(4+2*(stem-1)) * (amount - 1) * diameter * DT/2
    finger(diameter, 0, DT=DT, stem=stem)   # generate male finger
    bpy.context.active_object.name = "puzzlem"
    bpy.ops.object.curve_remove_doubles()
    bpy.ops.transform.translate(value=(translate, -0.00002, 0.0))

    if amount > 1:
        # duplicate translate the amount needed (faster than generating new)
        for i in range(amount-1):
            bpy.ops.object.duplicate_move(OBJECT_OT_duplicate={"linked": False, "mode": 'TRANSLATION'},
                                      TRANSFORM_OT_translate={"value": ((4+2*(stem-1)) * diameter * DT, 0, 0.0)})

        simple.selectMultiple('puzzle')
        bpy.ops.object.curve_boolean(boolean_type='UNION')
        bpy.context.active_object.name = "fingers"
        simple.removeMultiple("puzzle")
    else:
        bpy.context.active_object.name = "fingers"
    simple.makeActive('fingers')
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')


    #  receptacle is smaller by the inside tolerance amount
    finger(diameter, inside, DT=DT, stem=stem)
    bpy.context.active_object.name = "puzzle"
    bpy.ops.object.curve_remove_doubles()
    bpy.ops.transform.translate(value=(translate, -inside * 1.05, 0.0))

    if amount > 1:
        # duplicate translate the amount needed (faster than generating new)
        for i in range(amount - 1):
            bpy.ops.object.duplicate_move(OBJECT_OT_duplicate={"linked": False, "mode": 'TRANSLATION'},
                                          TRANSFORM_OT_translate={
                                              "value": ((4 + 2 * (stem - 1)) * diameter * DT, 0, 0.0)})

        simple.selectMultiple('puzzle')
        bpy.ops.object.curve_boolean(boolean_type='UNION')
        simple.activeName("receptacle")
        simple.removeMultiple("puzzle")
    else:
        simple.activeName("receptacle")
    simple.makeActive('receptacle')
    bpy.ops.transform.translate(value=(0, -inside * 1.05, 0.0))
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
    bpy.ops.object.curve_remove_doubles()


def bar(width, thick, diameter, tolerance, amount=0, stem=1, twist=False, tneck=0.5, tthick=0.01, which='MF'):
    # width = length of the bar
    # thick = thickness of the bar
    # diameter = diameter of the tool for joint creation
    # tolerance = Tolerance in the joint
    # amount = amount of fingers in the joint 0 means auto generate
    # stem = amount of radius the stem or neck of the joint will have
    # twist = twist lock addition
    # tneck = percentage the twist neck will have compared to thick
    # tthick = thicknest of the twist material
    # Which M,F, MF, MM, FF

    DT = 1.025
    if amount == 0:
        amount = round(thick / ((4+2*(stem-1)) * diameter * DT))-1
    bpy.ops.curve.simple(align='WORLD', location=(0, 0, 0), rotation=(0, 0, 0), Simple_Type='Rectangle',
                         Simple_width=width, Simple_length=thick, use_cyclic_u=True, edit_mode=False)
    simple.activeName('tmprect')

    fingers(diameter, tolerance, amount, stem=stem)

    if which == 'MM' or which == 'M' or which == 'MF':
        simple.rename('fingers', '_tmpfingers')
        rotate(-math.pi/2)
        bpy.ops.transform.translate(value=(width/2, 0, 0.0))
        simple.rename('tmprect', '_tmprect')
        simple.union('_tmp')
        simple.activeName("tmprect")

    if twist:
        joinery.interlock_twist(thick, tthick, tolerance, cx=width/2+2*diameter*DT-tthick/2+0.00001, percentage=tneck)
        joinery.interlock_twist(thick, tthick, tolerance, cx=-width/2+2*diameter*DT-tthick/2+0.00001, percentage=tneck)
        simple.joinMultiple('_groove')
        bpy.ops.object.curve_remove_doubles()


    simple.rename('receptacle', '_tmpreceptacle')
    if which == 'FF' or which == 'F' or which == 'MF':
        rotate(-math.pi/2)
        bpy.ops.transform.translate(value=(-width/2, 0, 0.0))
        if twist:
            simple.rename('tmprect', '_tmprect')
            simple.union('_')
            simple.activeName('tmprect')

        simple.rename('tmprect', '_tmprect')
        simple.difference('_tmp', '_tmprect')
        simple.activeName("tmprect")

    simple.removeMultiple("_")  # Remove temporary base and holes
    simple.removeMultiple("fingers")  # Remove temporary base and holes
    simple.rename('tmprect', 'Puzzle_bar')
    simple.removeMultiple("tmp")  # Remove temporary base and holes
    simple.makeActive('Puzzle_bar')


def arc(radius, thick, angle, diameter, tolerance, amount=0, stem=1, twist=False, tneck=0.5, tthick=0.01, which='MF'):
    # radius = radius of the curve
    # thick = thickness of the bar
    # angle = angle of the arc
    # diameter = diameter of the tool for joint creation
    # tolerance = Tolerance in the joint
    # amount = amount of fingers in the joint 0 means auto generate
    # stem = amount of radius the stem or neck of the joint will have
    # twist = twist lock addition
    # tneck = percentage the twist neck will have compared to thick
    # tthick = thicknest of the twist material
    # which = which joint to generate, Male Female MaleFemale M, F, MF

    if angle == 0:  # angle cannot be 0
        angle = 0.01

    negative = False
    if angle < 0:   # if angle < 0 then negative is true
        angle = -angle
        negative = True

    DT = 1.025  # diameter tolerance for diameter of finger creation
    if amount == 0:
        amount = round(thick / ((4+2*(stem-1)) * diameter * DT))-1

    # generate arc
    bpy.ops.curve.simple(align='WORLD', location=(0, 0, 0), rotation=(0, 0, 0), Simple_Type='Segment', Simple_a=radius-thick/2,
                         Simple_b=radius+thick/2, Simple_startangle=-0.0001,  Simple_endangle=math.degrees(angle), Simple_radius=radius, use_cyclic_u=False, edit_mode=False)
    bpy.context.active_object.name = "tmparc"

    fingers(diameter, tolerance, amount, stem=stem)
    simple.rename('fingers', '_tmpfingers')

    rotate(math.pi)
    bpy.ops.transform.translate(value=(radius, 0, 0.0))
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')

    simple.rename('tmparc', '_tmparc')
    if which == 'MF' or which == 'M':
        simple.selectMultiple('_tmp')
        bpy.ops.object.curve_boolean(boolean_type='UNION')
        bpy.context.active_object.name = "base"
        simple.removeMultiple('_tmp')
        simple.rename('base', '_tmparc')

    if twist:
        joinery.interlock_twist(thick, tthick, tolerance, cx=width/2+2*diameter*DT-tthick/2+0.00001, percentage=tneck)
        joinery.interlock_twist(thick, tthick, tolerance, cx=-width/2+2*diameter*DT-tthick/2+0.00001, percentage=tneck)
        simple.joinMultiple('_groove')
        bpy.ops.object.curve_remove_doubles()


    simple.rename('receptacle', '_tmpreceptacle')
    rotate(math.pi)
    bpy.ops.transform.translate(value=(radius, 0, 0.0))
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
    rotate(angle)

    if twist:
        bpy.ops.object.curve_boolean(boolean_type='UNION')
        simple.activeName('_tmpreceptacle')


    simple.selectMultiple("_tmp")  # select everything starting with plate_
    bpy.context.view_layer.objects.active = bpy.data.objects['_tmparc']
    if which == 'MF' or which == 'F':
        bpy.ops.object.curve_boolean(boolean_type='DIFFERENCE')
    bpy.context.active_object.name = "PUZZLE_arc"
    bpy.ops.object.curve_remove_doubles()
    simple.removeMultiple("_")  # Remove temporary base and holes
    simple.makeActive('PUZZLE_arc')
    if which == 'M':
        rotate(-angle)
        bpy.ops.transform.mirror(orient_type='GLOBAL', orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                                 orient_matrix_type='GLOBAL', constraint_axis=(False, True, False))
        bpy.ops.transform.translate(value=(-radius, 0, 0.0))
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=False)
        rotate(-math.pi / 2)
        simple.rename('PUZZLE_arc', 'PUZZLE_arc_male')
    elif which == 'F':
        bpy.ops.transform.mirror(orient_type='LOCAL', orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)), orient_matrix_type='LOCAL', constraint_axis=(True, False, False))
        bpy.ops.transform.translate(value=(radius, 0, 0.0))
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=False)
        rotate(math.pi / 2)
        simple.rename('PUZZLE_arc', 'PUZZLE_arc_receptacle')
    else:
        bpy.ops.transform.translate(value=(-radius, 0, 0.0))

    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False, properties=False)

    if negative:    # mirror if angle is negative
        bpy.ops.transform.mirror(orient_type='GLOBAL', orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                                 orient_matrix_type='GLOBAL', constraint_axis=(False, True, False))

    bpy.ops.object.curve_remove_doubles()

def arcbararc(length, radius, thick, angle, angleb, diameter, tolerance, amount=0, stem=1, twist=False,
              tneck=0.5, tthick=0.01, which='MF'):
    # length is the total width of the segments including 2 * radius and thick
    # radius = radius of the curve
    # thick = thickness of the bar
    # angle = angle of the female part
    # angleb = angle of the male part
    # diameter = diameter of the tool for joint creation
    # tolerance = Tolerance in the joint
    # amount = amount of fingers in the joint 0 means auto generate
    # stem = amount of radius the stem or neck of the joint will have
    # twist = twist lock addition
    # tneck = percentage the twist neck will have compared to thick
    # tthick = thicknest of the twist material
    # which = which joint to generate, Male Female MaleFemale M, F, MF

    length -= (radius * 2 + thick)  # adjust length to include 2x radius + thick

    # generate base rectangle
    bpy.ops.curve.simple(align='WORLD', location=(0, 0, 0), rotation=(0, 0, 0), Simple_Type='Rectangle',
                         Simple_width=length*1.005, Simple_length=thick, use_cyclic_u=True, edit_mode=False)
    simple.activeName("tmprect")

    #  Generate male section and join to the base
    if which == 'M' or which == 'MF':
        arc(radius, thick, angleb, diameter, tolerance, amount=amount, stem=stem, twist=twist, tneck=tneck,
            tthick=tthick, which='M')
        bpy.ops.transform.translate(value=(length / 2, 0, 0.0))
        simple.activeName('tmp_male')
        simple.selectMultiple('tmp')
        bpy.ops.object.curve_boolean(boolean_type='UNION')
        simple.activeName('male')
        simple.removeMultiple('tmp')
        simple.rename('male', 'tmprect')

    # Generate female section and join to base
    if which == 'F' or which == 'MF':
        arc(radius, thick, angle, diameter, tolerance, amount=amount, stem=stem, twist=twist, tneck=tneck, tthick=tthick, which='F')
        bpy.ops.transform.translate(value=(-length / 2, 0, 0.0))
        simple.activeName('tmp_receptacle')
        simple.selectMultiple('tmp')
        bpy.ops.object.curve_boolean(boolean_type='UNION')
        simple.removeMultiple('tmp')

    simple.activeName('arcBarArc')
    simple.makeActive('arcBarArc')


def arcbar(length, radius, thick, angle, diameter, tolerance, amount=0, stem=1, twist=False,
              tneck=0.5, tthick=0.01, which='MF'):
    # length is the total width of the segments including 2 * radius and thick
    # radius = radius of the curve
    # thick = thickness of the bar
    # angle = angle of the female part
    # diameter = diameter of the tool for joint creation
    # tolerance = Tolerance in the joint
    # amount = amount of fingers in the joint 0 means auto generate
    # stem = amount of radius the stem or neck of the joint will have
    # twist = twist lock addition
    # tneck = percentage the twist neck will have compared to thick
    # tthick = thicknest of the twist material
    # which = which joint to generate, Male Female MaleFemale M, F, MF
    if which == 'M':
        which = 'MM'
    elif which == 'F':
        which = 'FF'
    length -= (radius * 2 + thick)  # adjust length to include 2x radius + thick

    # generate base rectangle
    #  Generate male section and join to the base
    if which == 'MM' or which == 'MF':
        bar(length, thick, diameter, tolerance, amount=amount, stem=stem, twist=twist, tneck=tneck, tthick=tthick,
            which='M')
        simple.activeName('tmprect')

    if which == 'FF' or which == 'FM':
        bar(length, thick, diameter, tolerance, amount=amount, stem=stem, twist=twist, tneck=tneck, tthick=tthick,
            which='F')
        rotate(math.pi)
        simple.activeName('tmprect')

    # Generate female section and join to base
    if which == 'FF' or which == 'MF':
        arc(radius, thick, angle, diameter, tolerance, amount=amount, stem=stem, twist=twist, tneck=tneck, tthick=tthick, which='F')
        bpy.ops.transform.translate(value=(-length / 2*0.998, 0, 0.0))
        simple.activeName('tmp_receptacle')
        simple.union('tmp')
        simple.activeName('arcBar')
        simple.removeMultiple('tmp')

    if which == 'MM':
        arc(radius, thick, angle, diameter, tolerance, amount=amount, stem=stem, twist=twist, tneck=tneck, tthick=tthick, which='M')
        bpy.ops.transform.mirror(orient_type='GLOBAL', orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                                 orient_matrix_type='GLOBAL', constraint_axis=(True, False, False))
        bpy.ops.transform.translate(value=(-length / 2*0.998, 0, 0.0))
        simple.activeName('tmp_receptacle')
        simple.union('tmp')
        simple.activeName('arcBar')
        simple.removeMultiple('tmp')

    simple.makeActive('arcBar')

def multiangle(radius, thick, angle, diameter, tolerance, amount=0, stem=1, twist=False,
              tneck=0.5, tthick=0.01, combination='MFF'):
    # length is the total width of the segments including 2 * radius and thick
    # radius = radius of the curve
    # thick = thickness of the bar
    # angle = angle of the female part
    # diameter = diameter of the tool for joint creation
    # tolerance = Tolerance in the joint
    # amount = amount of fingers in the joint 0 means auto generate
    # stem = amount of radius the stem or neck of the joint will have
    # twist = twist lock addition
    # tneck = percentage the twist neck will have compared to thick
    # tthick = thicknest of the twist material
    # which = which joint to generate, Male Female MaleFemale M, F, MF

    bpy.ops.curve.simple(align='WORLD', location=(0, (radius+thick/2)*.707+((radius/thick)/170)/2, 0), rotation=(0, 0, 0), Simple_Type='Rectangle',
                         Simple_width=(radius-thick/2), Simple_length=(radius/thick)/170, use_cyclic_u=True, edit_mode=False)
    simple.activeName('rect')

    arc(radius, thick, angle, diameter, tolerance, amount=amount, stem=stem, twist=twist, tneck=tneck, tthick=tthick,
        which='MF')
    simple.activeName('tmp_arc')
    duplicate()
    mirrorx()
    simple.union("tmp_arc")

def t(length,thick, diameter, tolerance, amount=0, stem=1, twist=False, tneck=0.5, tthick=0.01, combination='MF', base_gender='M', corner=False):
    if corner:
        if combination == 'MF':
            base_gender = 'M'
            combination = 'f'
        elif combination == 'F':
            base_gender = 'F'
            combination = 'f'
        elif combination == 'M':
            base_gender = 'M'
            combination = 'm'

    bar(length, thick, diameter, tolerance, amount=amount, stem=stem, twist=twist, tneck=tneck,
        tthick=tthick, which=base_gender)
    simple.activeName('tmp')
    fingers(diameter, tolerance, amount=amount, stem=stem)
    if combination == 'MF' or combination == 'M' or combination == 'm':
        simple.makeActive('fingers')
        translate(y=thick / 2)
        duplicate()
        simple.activeName('tmp')
        simple.union('tmp')

    if combination == 'M':
        simple.makeActive('fingers')
        mirrory()
        simple.activeName('tmp')
        simple.union('tmp')

    if combination == 'MF' or combination == 'F' or combination == 'f':
        simple.makeActive('receptacle')
        translate(y=-thick / 2)
        duplicate()
        simple.activeName('tmp')
        simple.difference('tmp', 'tmp')

    if combination == 'F':
        simple.makeActive('receptacle')
        mirrory()
        simple.activeName('tmp')
        simple.difference('tmp', 'tmp')

    simple.removeMultiple('receptacle')
    simple.removeMultiple('fingers')

    simple.rename('tmp', 't')
    simple.makeActive('t')

def mitre(length, thick, angle, angleb, diameter, tolerance, amount=0, stem=1, twist=False,
              tneck=0.5, tthick=0.01, which='MF'):
    # length is the total width of the segments including 2 * radius and thick
    # radius = radius of the curve
    # thick = thickness of the bar
    # angle = angle of the female part
    # angleb = angle of the male part
    # diameter = diameter of the tool for joint creation
    # tolerance = Tolerance in the joint
    # amount = amount of fingers in the joint 0 means auto generate
    # stem = amount of radius the stem or neck of the joint will have
    # twist = twist lock addition
    # tneck = percentage the twist neck will have compared to thick
    # tthick = thicknest of the twist material
    # which = which joint to generate, Male Female MaleFemale M, F, MF

    # generate base rectangle
    bpy.ops.curve.simple(align='WORLD', location=(0, -thick/2, 0), rotation=(0, 0, 0), Simple_Type='Rectangle',
                         Simple_width=length*1.005+4*thick, Simple_length=thick, use_cyclic_u=True, edit_mode=False,
                         shape='3D')
    simple.activeName("tmprect")

    # generate cutout shapes
    bpy.ops.curve.simple(align='WORLD', location=(0, 0, 0), rotation=(0, 0, 0), Simple_Type='Rectangle',
                         Simple_width=4*thick, Simple_length=6*thick, use_cyclic_u=True, edit_mode=False, shape='3D')
    translate(x=2*thick)
    rotate(angle)
    translate(x=length/2)
    simple.activeName('tmpmitreright')

    bpy.ops.curve.simple(align='WORLD', location=(0, 0, 0), rotation=(0, 0, 0), Simple_Type='Rectangle',
                         Simple_width=4*thick, Simple_length=6*thick, use_cyclic_u=True, edit_mode=False, shape='3D')
    translate(x=2*thick)
    rotate(angleb)
    translate(x=length/2)
    mirrorx()
    simple.activeName('tmpmitreleft')
    simple.difference('tmp', 'tmprect')
    simple.makeActive('tmprect')

    fingers(diameter, tolerance, amount, stem=stem)

    #  Generate male section and join to the base
    if which == 'M' or which == 'MF':
        simple.makeActive('fingers')
        duplicate()
        simple.activeName('tmpfingers')
        rotate(angle-math.pi/2)
        h = thick/math.cos(angle)
        h /= 2
        translate(x=length/2+h*math.sin(angle), y=-thick/2)
        if which == 'M':
            simple.rename('fingers', 'tmpfingers')
            rotate(angleb-math.pi/2)
            h = thick/math.cos(angleb)
            h /= 2
            translate(x=length/2+h*math.sin(angleb), y=-thick/2)
            mirrorx()

        simple.union('tmp')
        simple.activeName('tmprect')

    # Generate female section and join to base
    if which == 'MF' or which == 'F':
        simple.makeActive('receptacle')
        mirrory()
        duplicate()
        simple.activeName('tmpreceptacle')
        rotate(angleb-math.pi/2)
        h = thick/math.cos(angleb)
        h /= 2
        translate(x=length/2+h*math.sin(angleb), y=-thick/2)
        mirrorx()
        if which == 'F':
            simple.rename('receptacle', 'tmpreceptacle2')
            rotate(angle-math.pi/2)
            h = thick/math.cos(angle)
            h /= 2
            translate(x=length/2+h*math.sin(angle), y=-thick/2)
        simple.difference('tmp', 'tmprect')

    simple.removeMultiple('receptacle')
    simple.removeMultiple('fingers')
    simple.rename('tmprect', 'mitre')



