"""Reject engine payloads and generated artifacts in the public source tree."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {'.dll', '.exe', '.lib', '.obj', '.nvda-addon', '.zip', '.cab',
             '.chm', '.wav', '.pcm', '.dic', '.pyc'}
files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')
assert any(files), 'No tracked files to check'
for name in filter(None, files):
    path = Path(name)
    assert path.suffix.lower() not in FORBIDDEN, f'Binary/data artifact: {name}'
    assert path.parts[0] not in ('build', 'dist', 'private', 'src', 'lang', 'rom', 'analysis'), name
    assert 'openevv_engine' not in path.parts, name
    content = (ROOT / path).read_bytes()
    assert b'\0' not in content, f'Non-text content: {name}'
    content.decode('utf-8')
print('PASS: tracked repository contains UTF-8 source/documentation only; no engine payloads')
