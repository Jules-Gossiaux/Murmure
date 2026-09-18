from PyInstaller.utils.hooks import collect_all, collect_data_files

datas, binaries, hiddenimports = [], [], []
for package in ('faster_whisper', 'ctranslate2', 'onnxruntime', 'av', 'tokenizers', 'llama_cpp', '_sounddevice_data'):
    data, binary, hidden = collect_all(package)
    datas += data
    binaries += binary
    hiddenimports += hidden
datas += collect_data_files('huggingface_hub')
a = Analysis(['launch.py'], pathex=[], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports, hookspath=[], runtime_hooks=[],
             excludes=['PySide6.QtQml', 'PySide6.QtQuick', 'tkinter', 'pytest'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Murmure',
          debug=False, strip=False, upx=False, console=False, icon='assets/murmure.ico')
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Murmure')
