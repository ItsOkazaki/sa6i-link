# Version-specific resource patch; only guide text changes, not the app's engine.
import sys,hashlib,zlib,struct
inp,qml,out=sys.argv[1:];b=bytearray(open(inp,'rb').read());assert hashlib.sha256(b).hexdigest()=='d0738ad6fe7d60fc0a0a5241eb9616cc29d168a57045c477bcf2d1c854aac016'
p=0x1d6b5fd;n=struct.unpack_from('>I',b,p-8)[0];old=zlib.decompress(b[p:p+n-4]);assert b'Preferences.language' in old;raw=open(qml,'rb').read();c=zlib.compress(raw,9);assert len(c)<=n-4
struct.pack_into('>I',b,p-4,len(raw));b[p:p+n-4]=c+bytes(n-4-len(c));assert zlib.decompress(b[p:p+n-4])==raw
open(out,'wb').write(b);print('SHA256',hashlib.sha256(b).hexdigest())
