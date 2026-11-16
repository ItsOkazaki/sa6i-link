# Transparent logo and typeface patch for the specific, verified Windows UI-v3 test.
# Usage: python patch-ui-v4.py UI-v3.exe transparent-ui.png transparent-icon.png output.exe
import sys,hashlib,struct,zlib,base64,re
from PIL import Image
p,ui_png,icon_png,out=sys.argv[1:5]
d=bytearray(open(p,'rb').read()); assert hashlib.sha256(d).hexdigest()=='bd04dcfa0ed380423bd19ea67f2466faa2c612a76920b5e5cbd0977d26a61eb7'
pos=0x1d53d2d; limit=9317;n=struct.unpack_from('>I',d,pos-8)[0]
s=zlib.decompress(d[pos:pos+n-4]).decode()
old='''id: mark
anchors.horizontalCenter: parent.horizontalCenter
y: (Theme.topBarHeight - height) / 2
width: 38; height: 38
radius: Theme.radiusSm
color: "black"'''
assert s.count(old)==1;s=s.replace(old,old.replace('color: "black"','color: "transparent"'))
# Replace exactly the embedded main-rail image, leaving other image data alone.
start=s.index('id: mark\n');end=s.index('\nColumn {',start); fragment=s[start:end]
pattern=r'source: "data:image/png;base64,[^"]+"';assert len(re.findall(pattern,fragment))==1
b64=base64.b64encode(open(ui_png,'rb').read()).decode()
fragment=re.sub(pattern,lambda _: 'source: "data:image/png;base64,'+b64+'"',fragment)
s=s[:start]+fragment+s[end:]
old='''width: visible ? 95 : 0
text: "Sa6i Link"
role: "headline"
size: 17
color: Theme.primary'''
new='''width: visible ? 112 : 0
text: "Sa6i Link"
role: "headline"
font.family: Theme.fontMono
weight: 700
size: 16
color: Theme.primary'''
assert s.count(old)==1;s=s.replace(old,new)
c=zlib.compress(s.encode(),9);assert len(c)<=limit,(len(c),limit)
struct.pack_into('>I',d,pos-8,len(c)+4);struct.pack_into('>I',d,pos-4,len(s.encode()))
d[pos:pos+limit]=c+b'\0'*(limit-len(c))
# Eight fixed-size PE RT_ICON entries; 32-bit DIB pixels are BGRA bottom-up.
# Preserve alpha, and build the conventional one-bit transparency mask.
entries=[(0x26d5e40,16,1128),(0x26d62a8,20,1720),(0x26d6960,24,2440),(0x26d72e8,32,4264),(0x26d8390,40,6760),(0x26d9df8,48,9640),(0x26dc3a0,64,16936),(0x26e05c8,256,270376)]
original=Image.open(icon_png).convert('RGBA')
for off,size,oldsize in entries:
 header=d[off:off+40];assert struct.unpack_from('<IiiHH',header)==(40,size,2*size,1,32)
 pic=original.resize((size,size),Image.Resampling.LANCZOS)
 alpha=pic.getchannel('A').point(lambda x:0 if x<8 else x);pic.putalpha(alpha)
 flip=pic.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
 rgba=flip.tobytes('raw','BGRA');stride=((size+31)//32)*4;mask=bytearray(stride*size)
 for y in range(size):
  for x in range(size):
   if flip.getpixel((x,y))[3]==0:mask[y*stride+x//8]|=0x80>>(x%8)
 data=bytes(header)+rgba+mask;assert len(data)==oldsize
 d[off:off+oldsize]=data
open(out,'wb').write(d)
print('qml_compressed',len(c),'sha256',hashlib.sha256(d).hexdigest())
