import os, tempfile, zipfile
from pathlib import Path
from ai.core.autonomous_agent import AutonomousAgent
from security_lab.apk.analyzer import analyze

def test_agent_classify(): assert AutonomousAgent().classify('build my apk')=='android_builder'
def test_apk_analyzer():
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'x.apk'
        with zipfile.ZipFile(p,'w') as z:z.writestr('AndroidManifest.xml','android.permission.INTERNET https://example.test')
        r=analyze(str(p)); assert r['has_manifest'] and 'android.permission.INTERNET' in r['permissions'] and r['urls']
