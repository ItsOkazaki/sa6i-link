# TEST ONLY, version-specific, not a release. Extends native language list and validation.
import hashlib,struct,sys,pefile
src,out=sys.argv[1:]; b=bytearray(open(src,'rb').read()); assert hashlib.sha256(b).hexdigest()=='ed0b566add5b749ab5241011625c53757e85162e88a038aa6817f7c1034cc6c2'
p=pefile.PE(data=bytes(b),fast_load=True); base=p.OPTIONAL_HEADER.ImageBase
va=lambda o:base+p.get_rva_from_offset(o)
# Existing Rust array of five (&str,&str) entries; copy into spare rdata tail, adding Arabic.
old=0x1c14900; arr=0x24f90d0; extra=arr+192
assert not any(b[arr:extra+32]); assert struct.unpack_from('<Q',b,old+32)[0]==va(0x1c148d4)
b[arr:arr+160]=b[old:old+160]
code=b'ar'; name='العربية'.encode(); b[extra:extra+len(code)]=code;b[extra+2:extra+2+len(name)]=name
struct.pack_into('<QQQQ',b,arr+160,va(extra),2,va(extra+2),len(name))
# Fix iterator begin/end LEAs used to construct Settings language picker.
for operand,target,expected in [(0xfca7d0,arr,old),(0xfca7db,arr+192,old+160)]:
 olddisp=struct.unpack_from('<i',b,operand)[0]; assert va(operand+4)+olddisp==va(expected)
 struct.pack_into('<i',b,operand,va(target)-va(operand+4))
# Add PE base relocations for nonempty pointers so ASLR still works.
ptrs=[arr+i*32+k for i in range(1,6) for k in (0,16)]
page=p.get_rva_from_offset(arr)&~0xfff
entries=[0xa000|(p.get_rva_from_offset(o)-page) for o in ptrs]
assert all(0<=x-0xa000<0x1000 for x in entries)
block=struct.pack('<II',page,8+2*len(entries))+b''.join(struct.pack('<H',e) for e in entries)
r=p.sections[-1];rel=r.PointerToRawData+r.Misc_VirtualSize
assert not any(b[rel:rel+len(block)]); b[rel:rel+len(block)]=block
# Expand section sizes / relocation directory to include appended block.
rdata=p.sections[1]; struct.pack_into('<I',b,rdata.get_file_offset()+8,rdata.SizeOfRawData)
struct.pack_into('<I',b,r.get_file_offset()+8,r.Misc_VirtualSize+len(block))
directory=p.OPTIONAL_HEADER.DATA_DIRECTORY[5];struct.pack_into('<I',b,directory.get_file_offset()+4,directory.Size+len(block))
# is_known() is optimized to literal comparisons; branch to code cave and accept both Turkish and Arabic.
check=0xde6d4b;cave=0x162154e;assert b[check:check+5]==bytes.fromhex('66 81 39 74 72');assert b[cave:cave+32]==b'\xcc'*32
valid=0xde6d70;invalid=0xde6d69
buf=bytearray()
def emit(x):buf.extend(x)
def je(t):emit(b'\x0f\x84'+struct.pack('<i',va(t)-va(cave+len(buf)+6)))
def jmp(t):emit(b'\xe9'+struct.pack('<i',va(t)-va(cave+len(buf)+5)))
emit(bytes.fromhex('66 81 39 74 72'));je(valid);emit(bytes.fromhex('66 81 39 61 72'));je(valid);jmp(invalid)
b[cave:cave+len(buf)]=buf;b[check:check+5]=b'\xe9'+struct.pack('<i',va(cave)-va(check+5))
open(out,'wb').write(b);print('draft binary SHA256:',hashlib.sha256(b).hexdigest(),'new relocations',len(ptrs))
