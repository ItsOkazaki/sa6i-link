# SPDX-License-Identifier: GPL-3.0-or-later
# Replace the guide QML in the exact v5 release. Run: python3 patch-guide-v6.py v5.exe LocalGuide.qml out.exe
import hashlib,struct,zlib,sys
src,qml,out=sys.argv[1:]; b=bytearray(open(src,'rb').read());
assert hashlib.sha256(b).hexdigest()=='0dc2b6ed038a8502799dd3ad410d49c4180faf2320785d37a742dd6539e06585', 'wrong input version'
pos=0x1d6b5fd;n=struct.unpack_from('>I',b,pos-8)[0]; original=zlib.decompress(b[pos:pos+n-4]);assert b'signal showMeRequested' in original
raw=open(qml,'rb').read();packed=zlib.compress(raw,9);assert len(packed)<=n-4, 'QML resource slot too small'
# Qt's qUncompress accepts padding after the zlib stream; resource allocation stays unchanged.
struct.pack_into('>I',b,pos-4,len(raw)); b[pos:pos+n-4]=packed+bytes(n-4-len(packed))
key='/qt/qml/app/nectarlink/qml/pages/FeaturesGuidePage.qml'.encode('utf-16le');a=0x1d8c0e0;assert b[a:a+len(key)]==key
j=a+len('/qt/qml/app/nectarlink/qml/pages/'.encode('utf-16le'));assert b[j:j+2]==b'F\0';b[j]=ord('G')
open(out,'wb').write(b);print('sha256',hashlib.sha256(b).hexdigest())
