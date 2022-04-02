# -*- mode: python ; coding: utf-8 -*-

import os.path
import glob

block_cipher = None

from os.path import expanduser

# build platform files
pfdir = expanduser("~/anaconda3/envs/pcot/plugins/platforms")
pfs = glob.glob(pfdir+"/libq*")
pfs = [os.path.basename(x) for x in pfs]
pfs = [(f'{pfdir}/{x}','.') for x in pfs]

# build xform imports (which are hidden)
xforms = [os.path.basename(x)[:-3] for x in glob.glob('../src/pcot/xforms/xform*.py')]
print(xforms)
# here we save them out to a data file which xforms/__init__ can read
# in a frozen install
with open('../src/pcot/xformlist.txt','w') as f:
    for x in xforms:
        f.write(x+'\n')

xformsfull = [f"pcot.xforms.{x}" for x in xforms]
print(xformsfull)

a = Analysis(['../src/pcot/__main__.py'],
             pathex=[os.path.expanduser('~')],
             binaries=[],
             datas=[
                ('../src/pcot/assets/*.ui','pcot/assets'),
                ('../src/pcot/assets/*.css','pcot/assets'),
                ('../src/pcot/assets/*.md','pcot/assets'),
                ('../src/pcot/assets/*.ini','pcot/assets'),
                ('../src/pcot/VERSION.txt','pcot'),
                ('../src/pcot/xformlist.txt','pcot')
             ] + pfs,
             hiddenimports=[
                'pcot.assets',
                
                'pcot.ui.smallwidgets',
                'pcot.ui.textedit',
                'pcot.ui.variantwidget',
                'pcot.ui.mplwidget',
                'pcot.ui.linear',
                'pcot.ui.gradient',
                'pcot.ui.namedialog',
                'pcot.ui.canvas',

                'markdown.extensions.tables',

                'scipy.spatial.transform._rotation_groups',
                'scipy.special.cython_special',

                
             ]+xformsfull,
             
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts, # + [('v', '', 'OPTION')],
          a.binaries,
          a.zipfiles,
          a.datas,  
          [],
          name='pcot',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=True,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None )

