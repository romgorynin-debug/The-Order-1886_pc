"""Synthetic PS4BOOT5 and preparation pipeline checks (no game data needed)."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import order1886
import order1886_qte as qte

META = {'TITLE_ID': 'CUSA00076', 'APP_VER': '01.02'}

def fixture(sites=(48,), prot=5, module_site=False):
    image = bytearray(512)
    for pos in sites:
        image[pos:pos+len(qte.PATTERN)] = qte.PATTERN
    if module_site:
        image[300:300+len(qte.PATTERN)] = qte.PATTERN
    header = struct.pack('<8s6Q', b'PS4BOOT5', len(image), 0, 2, 0, 0, 0)
    header += bytes(40) + struct.pack('<Q', 1)
    header += struct.pack('<7Q', 256, 256, 0, 0, 0, 0, 0)
    header += struct.pack('<Q', 0)
    header += struct.pack('<3Q', 0, 256, prot) + struct.pack('<3Q', 256, 256, 5)
    return header + image

class PersonalQTE(unittest.TestCase):
    def test_exactly_one_byte_and_module_excluded(self):
        data = fixture(module_site=True)
        result, rva, offset = qte.patch_image(data)
        self.assertEqual(rva, 56)
        self.assertEqual([(i,a,b) for i,(a,b) in enumerate(zip(data,result)) if a!=b], [(offset,0x76,0xeb)])
        self.assertEqual(len(data), len(result))
    def test_wrong_or_duplicate_signature_refused(self):
        for data in (fixture(()), fixture((48, 96)), fixture(prot=6), fixture((), module_site=True), fixture()[:-1]):
            with self.subTest(), self.assertRaises(ValueError):
                qte.patch_image(data)
    def test_already_patched_refused(self):
        with self.assertRaises(ValueError):
            qte.patch_image(qte.patch_image(fixture())[0])
    def test_guard(self):
        self.assertTrue(qte.wanted(META, qte.EBOOT_SHA, 60))
        for rate in (30,90,0):
            self.assertFalse(qte.wanted(META,qte.EBOOT_SHA,rate))
        self.assertFalse(qte.wanted(META,'wrong',60))
        self.assertFalse(qte.wanted({**META,'TITLE_ID':'CUSA00035'},qte.EBOOT_SHA,60))
        self.assertFalse(qte.wanted({**META,'APP_VER':'01.00'},qte.EBOOT_SHA,60))
    def test_file_receipt_and_failure_no_write(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'boot-linked.bin'; p.write_bytes(fixture()); receipt=qte.apply(p)
            self.assertEqual(receipt['after_sha256'],hashlib.sha256(p.read_bytes()).hexdigest())
            before=p.read_bytes()
            with self.assertRaises(ValueError): qte.apply(p)
            self.assertEqual(p.read_bytes(),before)
            self.assertEqual(list(Path(t).iterdir()),[p])
    def test_preparation_cache_and_30_fps_rollback(self):
        with tempfile.TemporaryDirectory() as t:
            game=Path(t)/'game'; out=Path(t)/'prepared'
            for name in order1886.REQUIRED_FILES:
                p=game/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(b'fixture')
            original=(game/'eboot.bin').read_bytes()
            def link(_game,target): (target/'boot-linked.bin').write_bytes(fixture())
            def recipe(_path, rate, _meta): return {'engine_fps': rate,'host_fps_limit':rate,'recipe_sha256':str(rate)}
            def apply(_path, profile): return {**profile,'applied':True}
            with patch.object(order1886,'inspect_game',return_value=META), \
                 patch.object(qte,'EBOOT_SHA',hashlib.sha256(original).hexdigest()), \
                 patch.object(order1886.timing,'validate_source',side_effect=recipe), \
                 patch.object(order1886.timing,'apply_prepared',side_effect=apply), \
                 patch.object(order1886.display,'validate_source',return_value={'recipe_sha256':'display'}), \
                 patch.object(order1886.display,'apply_prepared',side_effect=apply), \
                 patch.object(order1886.post_effects,'validate_source',return_value={'recipe_sha256':'effects','disabled':[]}), \
                 patch.object(order1886.post_effects,'apply_prepared',side_effect=apply), \
                 patch.object(order1886.resolution,'validate_source',return_value={'recipe_sha256':'resolution'}), \
                 patch.object(order1886.resolution,'apply_prepared',side_effect=apply), \
                 patch.object(order1886.prepare,'prepare'), \
                 patch.object(order1886.link_modules,'link',side_effect=link) as linker:
                a=order1886.prepare_game(game,out,60)
                b=order1886.prepare_game(game,out,60)
                self.assertEqual(a,b); self.assertEqual(linker.call_count,1)
                self.assertTrue(a['qte_profile']['applied']); self.assertEqual(a['image_sha256'],order1886.sha256(out/'boot-linked.bin'))
                c=order1886.prepare_game(game,out,30)
                self.assertFalse(c['qte_profile']['applied']); self.assertEqual(linker.call_count,2)
                self.assertEqual((out/'boot-linked.bin').read_bytes(),fixture())
            self.assertEqual((game/'eboot.bin').read_bytes(),original)

if __name__ == '__main__': unittest.main()
