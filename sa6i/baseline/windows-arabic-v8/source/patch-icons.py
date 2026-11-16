# Replace 8 icon image payloads in the exact previous experimental UI EXE.
# This only changes resource pixels; it does not patch executable code.
import sys,struct,hashlib
from PIL import Image

p=sys.argv[1]
d=bytearray(open(p,'rb').read()); expected='644a40e2295a063ce3ee2dd518295286d14c4e20b30522113711c249e9928106'
assert hashlib.sha256(d).hexdigest()==expected, 'Unexpected input version'
img=Image.open(sys.argv[2]).convert('RGBA').crop((36,145,476,369))
entries=[(0x26d5e40,16,1128),(0x26d62a8,20,1720),(0x26d6960,24,2440),(0x26d72e8,32,4264),(0x26d8390,40,6760),(0x26d9df8,48,9640),(0x26dc3a0,64,16936),(0x26e05c8,256,270376)]
for off,n,size in entries:
 header=d[off:off+40]; assert struct.unpack_from('<IiiHH',header)==(40,n,n*2,1,32)
 # Artwork in a black square; retain aspect ratio. Background makes the logo
 # legible on both light and dark Windows themes.
 canvas=Image.new('RGBA',(n,n),(8,8,20,255))
 w=max(1,round(n*0.95)); h=max(1,round(w*224/440))
 scaled=img.resize((w,h),Image.Resampling.LANCZOS)
 canvas.alpha_composite(scaled,((n-w)//2,(n-h)//2))
 # ICO DIB bottom-up BGRA, plus DWORD-aligned 1-bit AND mask (opaque).
 xor=canvas.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes('raw','BGRA')
 mask=bytes(((n+31)//32)*4*n)
 data=bytes(header)+xor+mask
 assert len(data)==size,(n,len(data),size)
 d[off:off+size]=data
out=sys.argv[3];open(out,'wb').write(d)
print('patched',out,'sha256',hashlib.sha256(d).hexdigest())
