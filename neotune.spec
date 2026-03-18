# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from pathlib import Path

# Get the project root
project_root = Path(SPECPATH).resolve()

block_cipher = None

# Determine platform-specific settings
is_windows = sys.platform.startswith('win')
is_macos = sys.platform == 'darwin'
is_linux = sys.platform.startswith('linux')

print(f"Building for: {sys.platform}")

# Find lupa package
lupa_datas = []
lupa_binaries = []

# Try to find lupa in site-packages
import site
import glob

for site_path in site.getsitepackages():
    lupa_path = Path(site_path) / 'lupa'
    if lupa_path.exists():
        print(f"Found lupa at: {lupa_path}")
        # Collect all .so files as binaries
        for so_file in lupa_path.glob('*.so'):
            print(f"  Adding binary: {so_file}")
            lupa_binaries.append((str(so_file), 'lupa'))
        # Collect Python files as datas
        for py_file in lupa_path.glob('*.py'):
            lupa_datas.append((str(py_file), 'lupa'))
        # Collect __pycache__
        pycache = lupa_path / '__pycache__'
        if pycache.exists():
            for pyc_file in pycache.glob('*.pyc'):
                lupa_datas.append((str(pyc_file), 'lupa/__pycache__'))
        break

# Also check venv
venv_path = project_root / 'venv' / 'lib'
if venv_path.exists():
    for pyver in venv_path.glob('python*'):
        lupa_venv = pyver / 'site-packages' / 'lupa'
        if lupa_venv.exists() and not lupa_binaries:
            print(f"Found lupa in venv at: {lupa_venv}")
            for so_file in lupa_venv.glob('*.so'):
                print(f"  Adding binary: {so_file}")
                lupa_binaries.append((str(so_file), 'lupa'))
            for py_file in lupa_venv.glob('*.py'):
                lupa_datas.append((str(py_file), 'lupa'))
            pycache = lupa_venv / '__pycache__'
            if pycache.exists():
                for pyc_file in pycache.glob('*.pyc'):
                    lupa_datas.append((str(pyc_file), 'lupa/__pycache__'))

print(f"Collected {len(lupa_binaries)} lupa binaries")
print(f"Collected {len(lupa_datas)} lupa data files")

# Data files
data_files = [
    ('styles', 'styles'),
    ('lua', 'lua'),
] + lupa_datas

# Binaries
binaries = lupa_binaries

# Base analysis configuration
analysis_kwargs = {
    'pathex': [str(project_root)],
    'binaries': binaries,
    'datas': data_files,
    'hiddenimports': [
        'spotipy',
        'textual',
        'keyring',
        'keyring.backends',
        'keyring.backends.OS_X',
        'keyring.backends.SecretService',
        'keyring.backends.Windows',
        'keyring.backends.chainer',
        'keyring.backends.fail',
        'keyring.backends.kwallet',
        'keyring.backends.null',
        'keyring.core',
        'keyring.credentials',
        'keyring.errors',
        'keyring.getpassbackend',
        'keyring.util',
        'keyring.util.platform_',
        'keyrings.alt',
        'keyrings.alt.file',
        'lupa',
        'lupa._lupa',
        'psutil',
        'psutil._psutil_linux' if is_linux else 'psutil._psutil_posix',
        'redis',
        'requests',
        'rich',
        'yaml',
        'yaml.loader',
        'yaml.dumper',
        'yaml.representer',
        'yaml.resolver',
        'yaml.constructor',
        'yaml.serializer',
        'yaml.parser',
        'yaml.scanner',
        'yaml.reader',
        'yaml.tokens',
        'yaml.events',
        'yaml.nodes',
        'yaml.error',
        'cryptography',
        'cryptography.hazmat',
        'cryptography.hazmat.backends',
        'cryptography.hazmat.primitives',
        'cffi',
        'fastapi',
        'uvicorn',
        'jinja2',
        'jinja2.runtime',
        'jinja2.debug',
        'jinja2.utils',
        'pydantic',
        'pydantic.main',
        'pydantic.fields',
        'pydantic.types',
        'pydantic.typing',
        'pydantic.utils',
        'pydantic.validators',
        'pydantic.config',
        'pydantic.class_validators',
        'pydantic.schema',
        'pydantic.parse',
        'pydantic.json',
        'pydantic.datetime_parse',
        'pydantic.color',
        'pydantic.networks',
        'pydantic.generics',
        'pydantic.errors',
        'pydantic.env_settings',
        'pydantic.decorator',
        'pydantic.tools',
        'pydantic.mypy',
        'pydantic.version',
        'pkg_resources',
        'pkg_resources._vendor',
        'pkg_resources._vendor.packaging',
        'pkg_resources._vendor.packaging.version',
        'pkg_resources._vendor.packaging.specifiers',
        'pkg_resources._vendor.packaging.requirements',
        'pkg_resources._vendor.packaging.markers',
        'pkg_resources._vendor.packaging.utils',
        'pkg_resources._vendor.packaging.tags',
        'pkg_resources._vendor.packaging._compat',
        'pkg_resources._vendor.packaging._structures',
    ],
    'hookspath': [],
    'hooksconfig': {},
    'runtime_hooks': [],
    'excludes': [
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'Pillow',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'tkinter',
        'wx',
        'wxPython',
        'PyOpenGL',
        'OpenGL',
        'pygame',
        'cv2',
        'tensorflow',
        'torch',
        'torchvision',
        'sklearn',
        'scikit-learn',
        'scikit-image',
        'bokeh',
        'plotly',
        'seaborn',
        'altair',
        'vega',
        'ipywidgets',
        'IPython',
        'jupyter',
        'notebook',
        'nbconvert',
        'nbformat',
        'ipykernel',
        'qtpy',
        'PyQtWebEngine',
        'PyQtChart',
        'tests',
        'pytest',
        'unittest',
        'doctest',
    ],
    'win_no_prefer_redirects': False,
    'win_private_assemblies': False,
    'cipher': block_cipher,
    'noarchive': False,
}

a = Analysis(
    ['app.py'],
    **analysis_kwargs
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Determine executable name
exe_name = 'neotune'
if is_windows:
    exe_name = 'neotune.exe'

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# macOS app bundle
if is_macos:
    app = BUNDLE(
        exe,
        name='NeoTune.app',
        bundle_identifier='com.neotune.app',
        info_plist={
            'CFBundleShortVersionString': '0.1.0',
            'CFBundleVersion': '0.1.0',
            'NSHighResolutionCapable': 'True',
        },
    )
