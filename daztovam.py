#!/usr/bin/env python

import gzip
import zlib
import json
import sys
import os
from pathlib import Path

home = os.environ['HOME']
daz_libraries = [
    home + '/Documents/DAZ 3D/Studio/My Library',
    home + '/Documents/DAZ 3D/Studio/Alternate Library',
    home + '/.wine64/drive_c/users/Public/Documents/My DAZ 3D Library'
    ]

vam_overrides = { 'Nipples': 1.0,
                  'Labia majora-relaxation': 0.60,
                  'Labia majora-spread-LLow': 0.25,
                  'Labia majora-spread-RLow': 0.25,
                  'Labia minora-relaxation': 0.60,
                  'Labia minora-size': -0.30,
                  'Labia minora-thinkness': 2.00,
                  'Pubic Area Size': 0.20,
                  'Navel': 1.00,
                }

def load_compressed( filename ):
    with gzip.GzipFile( filename, 'r' ) as filein:
        data = json.loads( filein.read().decode( 'utf-8' ) )
    return data

def load_uncompressed( filename ):
    with open( filename, 'r' ) as filein:
        data = json.loads( filein.read() )
    return data

def load_json( filename ):
    try:
        return load_uncompressed( filename )
    except UnicodeDecodeError:
        return load_compressed( filename )
    except Exception as e:
        raise Exception( "in '{}'".format( filename ) )

class DAZMorph( object ):
    def __init__( self, j ):
        self.id = j['id']
        self.label = j['channel']['label']
        self.default = j['channel']['value']

    def __str__( self ):
        return "{} (default: {})".format( self.label, self.default )

def list_morph_files( morphtypedir ):
    for lib in daz_libraries:
        datadir = os.path.join( lib, morphtypedir )
        for dsf in Path( datadir ).rglob( "*.[Dd][Ss][Ff]" ):
            yield dsf

def load_all_morphs( morphtypedir ):
    for dsf in list_morph_files( morphtypedir ):
        j = load_json( dsf )
        for mod in j['modifier_library']:
            try:
                if mod['presentation']['type'] == 'Modifier/Shape':
                    yield DAZMorph( mod )
            except: pass

dazmorphs = dict()
for morph in load_all_morphs( 'data/DAZ 3D/Genesis 2/Female/Morphs' ):
    if morph.label in vam_overrides:
        morph.default = vam_overrides[morph.label]
    dazmorphs[ morph.id ] = morph

genmorphs = dict()
for morph in load_all_morphs( 'data/3feetwolf/New Genitalia For Victoria 6/Genitalia-default/Morphs' ):
    if morph.label in vam_overrides:
        morph.default = vam_overrides[morph.label]
    genmorphs[ morph.id ] = morph

class DAZCharacter( object ):
    def __init__( self, scenefile ):
        self.scene = load_json( scenefile )

    def g2fmorphs( self ):
        for mod in self.scene['scene']['modifiers']:
            if mod['id'] not in dazmorphs: continue
            if mod['parent'] != '#GenesisFemale': continue
            current_value = mod['channel']['current_value']

            morph = dazmorphs[ mod['id'] ]
            if current_value != morph.default:
                yield (morph, current_value)

    def genmorphs( self ):
        for mod in self.scene['scene']['modifiers']:
            if mod['id'] not in genmorphs: continue
            morph = genmorphs[ mod['id'] ]
            if ( (mod['parent'] == '#Genitalia-default') and
                 (mod['channel']['current_value'] != morph.default) ):
                yield (morph, mod['channel']['current_value'])

    def vam_morphs( self ):
        morphs = dict()
        # First, zero out the VAM-default morphs
        for override in vam_overrides.keys():
            morphs[ override ] = 0

        # Next, include the changed g2f and gen morphs
        for (morph, value) in self.g2fmorphs():
            morphs[ morph.label ] = value
        for (morph, value) in self.genmorphs():
            morphs[ morph.label ] = value

        return morphs

    def name( self ):
        g2fnode = [x for x in self.scene['scene']['nodes']
                   if x['id'] == 'Genesis2Female'][0]
        return g2fnode['label']

class VAMLook( object ):
    def __init__( self, filename ):
        self.look = load_json( filename )

    def match_daz( self, dazchar ):
        self.look['atoms'][0]['id'] = dazchar.name()

        newmorphs = dazchar.vam_morphs()
        self.look['atoms'][0]['storables'] = [
            self.replace_morph_storable( s, newmorphs )
            for s in self.look['atoms'][0]['storables'] ]

    def replace_morph_storable( self, storable, newmorphs ):
        if storable['id'] != 'geometry': return storable

        storable['morphs'] = [ {'name': label, 'value': val}
                               for label, val in newmorphs.items() ]
        return storable

scene = DAZCharacter( sys.argv[2] )
look = VAMLook( sys.argv[1] )

look.match_daz( scene )
print( json.dumps( look.look ) )
