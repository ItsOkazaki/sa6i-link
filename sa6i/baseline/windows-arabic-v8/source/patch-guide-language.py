# After patch-v6-arabic-test.py, bind local guide language to Preferences.language.
import zlib,struct,sys,hashlib
b=bytearray(open(sys.argv[1],'rb').read());q=open(sys.argv[2],'rb').read();p=0x1d6b5fd;n=struct.unpack_from('>I',b,p-8)[0];old=zlib.decompress(b[p:p+n-4]);assert b'property bool arabic: false' in old
packed=zlib.compress(q,9);assert len(packed)<=n-4
struct.pack_into('>I',b,p-4,len(q));b[p:p+n-4]=packed+bytes(n-4-len(packed));open(sys.argv[3],'wb').write(b);print('SHA256',hashlib.sha256(b).hexdigest())
