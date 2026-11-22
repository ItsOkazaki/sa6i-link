# Version-checked cosmetic QML patch: draw vector caption icons on Windows 7.
# Run: python patch-caption-v5.py <exact-v4.exe> <output-v5.exe>
import hashlib,sys,struct
p,out=sys.argv[1:3];b=bytearray(open(p,'rb').read()); assert hashlib.sha256(b).hexdigest()=='ee16449064b547208d1903de55da06295de1d281bdda0d6e1d3d11aef9fee075'
pos=0x1d7b872;n=struct.unpack_from('>I',b,pos-4)[0];s=bytes(b[pos:pos+n]);assert s.startswith(b'// SPDX-License-Identifier:')
for old,new in [(b'visible: Qt.platform.os === "windows"',b'visible: false'), (b'visible: Qt.platform.os !== "windows"',b'visible: true')]:
 assert s.count(old)==1; assert len(new)<=len(old); s=s.replace(old,new+b' '*(len(old)-len(new)))
b[pos:pos+n]=s
# Bypass only the cached compiled unit for CaptionButtons, so modified source is used.
key='/qt/qml/app/sa6i-link/qml/components/CaptionButtons.qml'.encode('utf-16le');pos=0x1d8b330
assert b[pos:pos+len(key)]==key
j=pos+len('/qt/qml/app/sa6i-link/qml/components/'.encode('utf-16le')); assert b[j:j+2]==b'C\0';b[j]=ord('D')
open(out,'wb').write(b); print('sha256',hashlib.sha256(b).hexdigest())
