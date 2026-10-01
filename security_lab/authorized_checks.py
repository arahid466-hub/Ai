"""Defensive checks for applications and APIs owned by the operator.
No exploit, credential theft, bypass, persistence, or evasion functionality is provided.
"""
from pathlib import Path
import hashlib, json, re, shutil, urllib.parse, zipfile

def apk_integrity(path: str, expected_sha256: str | None = None) -> dict:
    p = Path(path).resolve()
    if not p.is_file() or p.suffix.lower() != '.apk':
        raise ValueError('An owned APK file is required')
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    result = {
        'check': 'apk_integrity', 'status': 'PASS' if not expected_sha256 or digest.lower() == expected_sha256.lower() else 'FAIL',
        'sha256': digest, 'size': p.stat().st_size, 'expected_sha256': expected_sha256,
        'evidence': ['SHA-256 calculated from the supplied APK bytes']
    }
    return result

def apk_surface(path: str) -> dict:
    p = Path(path).resolve()
    if not p.is_file() or p.suffix.lower() != '.apk':
        raise ValueError('An owned APK file is required')
    suspicious = []
    urls = []
    permissions = []
    exported_markers = []
    with zipfile.ZipFile(p) as z:
        for name in z.namelist():
            try: text = z.read(name).decode('utf-8', 'ignore')
            except Exception: continue
            permissions += re.findall(r'android\.permission\.[A-Z_]+', text)
            urls += re.findall(r'https?://[^\s"<>]+', text)
            if 'android:exported="true"' in text: exported_markers.append(name)
            if any(x in text.lower() for x in ('debuggable="true"', 'trust anchors', 'cleartexttraffic="true"')):
                suspicious.append(name)
    return {
        'check': 'apk_surface', 'status': 'WARNING' if suspicious or exported_markers else 'PASS',
        'permissions': sorted(set(permissions)), 'urls': sorted(set(urls))[:200],
        'exported_markers': exported_markers[:100], 'suspicious_configuration_files': suspicious[:100],
        'evidence': ['Static archive inspection only; native code is not executed']
    }

def api_target_guard(url: str) -> dict:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or '').lower()
    allowed = host in {'localhost', '127.0.0.1', '::1'} or host.endswith('.local') or host.endswith('.test')
    return {'check': 'api_target_guard', 'status': 'PASS' if allowed else 'WARNING', 'target': url,
            'authorized_scope_required': True, 'safe_default': allowed,
            'message': 'Only local/test targets are safe by default; obtain explicit authorization before testing any other host.'}

def toolchain_status() -> dict:
    names = ('apktool','jadx','aapt','aapt2','apksigner','adb','gradle','ffmpeg')
    return {name: {'available': bool(shutil.which(name)), 'path': shutil.which(name)} for name in names}
