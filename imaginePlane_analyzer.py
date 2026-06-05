
import maya.cmds as cmds
import os
import struct
import glob
import re


def _read_exr_header(path):
    """Грубое чтение заголовка EXR: compression, channels, parts."""
    info = {}
    try:
        with open(path, 'rb') as f:
            magic = f.read(4)
            if magic != b'\x76\x2f\x31\x01':
                return {'error': 'не EXR (неверная сигнатура)'}
            ver = struct.unpack('<I', f.read(4))[0]
            info['multipart'] = bool(ver & 0x1000)
            info['tiled'] = bool(ver & 0x200)
            data = f.read(8192)  # заголовок обычно небольшой
            comp_map = {0:'NONE',1:'RLE',2:'ZIPS',3:'ZIP',4:'PIZ',
                        5:'PXR24',6:'B44',7:'B44A',8:'DWAA',9:'DWAB'}
            i = data.find(b'compression\x00')
            if i != -1:
                cval = data[i+len(b'compression\x00')+9]
                info['compression'] = comp_map.get(cval, 'код {}'.format(cval))
            chans = re.findall(rb'([A-Za-z0-9_.]+)\x00\x02\x00\x00\x00', data)
            if chans:
                info['channels'] = [c.decode('ascii', 'ignore') for c in chans][:12]
    except Exception as e:
        info['error'] = str(e)
    return info


def diagnose_image_planes(target=None):
    print("=" * 70)
    print("ДИАГНОСТИКА IMAGE PLANE")
    print("=" * 70)

    # Color management (общие настройки сцены)
    print("\n--- Color Management ---")
    try:
        print("  enabled:        {}".format(cmds.colorManagementPrefs(q=True, cmEnabled=True)))
        print("  config:         {}".format(cmds.colorManagementPrefs(q=True, configFilePath=True)))
        print("  rendering space:{}".format(cmds.colorManagementPrefs(q=True, renderingSpaceName=True)))
        print("  view transform: {}".format(cmds.colorManagementPrefs(q=True, viewTransformName=True)))
    except Exception as e:
        print("  не удалось прочитать: {}".format(e))

    planes = cmds.ls(type='imagePlane') or []
    if target:
        planes = [p for p in planes if target in p]
    if not planes:
        print("\nImage plane не найден.")
        return

    for p in planes:
        print("\n" + "-" * 70)
        print("IMAGE PLANE: {}".format(p))
        print("-" * 70)

        def g(attr):
            full = "{}.{}".format(p, attr)
            if cmds.objExists(full):
                try:
                    return cmds.getAttr(full)
                except Exception:
                    return "<err>"
            return "<нет атрибута>"

        img_name = g('imageName')
        print("  imageName:          {}".format(img_name))
        print("  type:               {}".format(g('type')))
        print("  useFrameExtension:  {}".format(g('useFrameExtension')))
        print("  frameOffset:        {}".format(g('frameOffset')))
        print("  frameExtension:     {}".format(g('frameExtension')))
        print("  frameCache:         {}".format(g('frameCache')))
        print("  colorSpace:         {}".format(g('colorSpace')))
        print("  ignoreColorSpaceFileRules: {}".format(g('ignoreColorSpaceFileRules')))
        print("  colorManagementEnabled:    {}".format(g('colorManagementEnabled')))
        print("  displayMode:        {}".format(g('displayMode')))
        print("  textureFilter:      {}".format(g('filterType')))

        # Анализ файлов
        if not isinstance(img_name, str) or not img_name:
            continue

        print("\n  --- Файлы ---")
        base_exists = os.path.exists(img_name)
        print("  путь из imageName существует: {}".format(base_exists))

        # Пробуем собрать секвенцию по паттерну
        folder = os.path.dirname(img_name)
        fname = os.path.basename(img_name)
        seq_files = []
        if os.path.isdir(folder):
            # заменяем номер кадра на маску
            m = re.search(r'(\d+)(\.\w+)$', fname)
            if m:
                prefix = fname[:m.start(1)]
                ext = m.group(2)
                pattern = os.path.join(folder, prefix + '*' + ext)
                seq_files = sorted(glob.glob(pattern))
            elif base_exists:
                seq_files = [img_name]

        print("  найдено файлов в секвенции: {}".format(len(seq_files)))

        # Проверяем размеры — нулевые/сильно разные = битые/недописанные
        if seq_files:
            sizes = [(os.path.basename(f), os.path.getsize(f)) for f in seq_files]
            zero = [n for n, s in sizes if s == 0]
            non_zero = [s for n, s in sizes if s > 0]
            print("  файлов с нулевым размером: {} {}".format(
                len(zero), zero[:5] if zero else ''))
            if non_zero:
                mn, mx = min(non_zero), max(non_zero)
                print("  размер min/max: {:.1f} KB / {:.1f} KB".format(mn/1024.0, mx/1024.0))
                if mx > 0 and mn < mx * 0.5:
                    print("  !! сильный разброс размеров — возможны недописанные кадры")

            # Заголовок первого нормального кадра
            first_good = next((f for f in seq_files if os.path.getsize(f) > 0), None)
            if first_good and first_good.lower().endswith('.exr'):
                print("\n  --- EXR header ({}) ---".format(os.path.basename(first_good)))
                h = _read_exr_header(first_good)
                for k, v in h.items():
                    print("    {}: {}".format(k, v))

    print("\n" + "=" * 70)
    print("ГОТОВО")
    print("=" * 70)


if __name__ == "__main__":
    diagnose_image_planes()  # или diagnose_image_planes("imagePlaneShape1")