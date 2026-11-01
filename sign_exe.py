# -*- coding: utf-8 -*-
"""
sign_exe.py
يوقّع ملف BADAWI PROJECT.exe بشهادة محلية (Authenticode).

السبب: Smart App Control في ويندوز 11 يمنع تشغيل أي exe جديد غير موقّع،
فتظهر رسالة "An Application Control policy has blocked this file".
التوقيع يجعل الملف مقبولاً بدون أخطاء على جهاز المستخدم.

ملاحظة: الشهادة self-signed — المتصفح/ويندوز قد يعرض تحذير "Unknown publisher"
في بعض الأجهزة، لكنه يعمل. لوwanted trust على جهاز آخر:
Import-Certificate -FilePath BADAWI PROJECT.cer
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(HERE, "dist", "BADAWI PROJECT.exe")
CERT_NAME = "BADAWI PROJECT"

PS = r"""
$ErrorActionPreference = 'Stop'
$exe = $args[0]
$certName = $args[1]

# 1) أنشئ الشهادة لو مش موجودة
$cert = Get-ChildItem "Cert:\CurrentUser\My" | Where-Object { $_.Subject -like "*$certName*" } | Select-Object -First 1
if (-not $cert) {
    $cert = New-SelfSignedCertificate -Subject "CN=$certName" -Type CodeSigningCert -CertStoreLocation "Cert:\CurrentUser\My" -NotAfter (Get-Date).AddYears(10)
}

# 2) وقّع الـ exe
$before = (Get-AuthenticodeSignature -FilePath $exe).Status
Set-AuthenticodeSignature -FilePath $exe -Certificate $cert -HashAlgorithm SHA256 | Out-Null
$after = (Get-AuthenticodeSignature -FilePath $exe)

# 3) صدّر الشهادة public-so user can trust it on another machine
$cer = Join-Path (Split-Path $exe -Parent) "$certName.cer"
Export-Certificate -Cert $cert -FilePath $cer | Out-Null

Write-Output ("SIGN_STATUS=" + $after.Status)
Write-Output ("SIGNER=" + $after.SignerCertificate.Subject)
Write-Output ("CER=" + $cer)
Write-Output ("WAS=" + $before)
"""


def main():
    if not os.path.exists(EXE):
        raise SystemExit("exe not found: %s" % EXE)

    ps = os.path.join(HERE, "sign_exe.ps1")
    with open(ps, "w", encoding="utf-8-sig") as f:
        f.write(PS)

    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps, EXE, CERT_NAME],
        capture_output=True, text=True,
    )
    print(r.stdout)
    if r.stderr.strip():
        print("STDERR:", r.stderr.strip())
    try:
        os.remove(ps)
    except OSError:
        pass
    return 0 if "SIGNER=" in (r.stdout or "") else 1


if __name__ == "__main__":
    sys.exit(main())
