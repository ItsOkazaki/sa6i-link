import hashlib,struct,zlib,sys
p=sys.argv[1]; out=sys.argv[2];d=bytearray(open(p,'rb').read())
assert hashlib.sha256(d).hexdigest()=='3a28af8410aa1ac223e4dded78150d4a0c5b78ad5846a92eb699028fb2981b75'
pos=0x1d53d2d; limit=9317
n=struct.unpack_from('>I',d,pos-8)[0];s=zlib.decompress(d[pos:pos+n-4]).decode()
old='''id: topBar
width: parent.width - captionButtons.width
height: Theme.topBarHeight
IconButton {
id: backToHome
anchors.left: parent.left
anchors.leftMargin: Theme.contentPadding - 6'''
new='''id: topBar
width: parent.width - captionButtons.width
height: Theme.topBarHeight
Txt {
id: brandTitle
anchors.left: parent.left
anchors.leftMargin: Theme.contentPadding
anchors.verticalCenter: parent.verticalCenter
visible: topBar.width > 460
width: visible ? 95 : 0
text: "Sa6i Link"
role: "headline"
size: 17
color: Theme.primary
}
IconButton {
id: backToHome
anchors.left: brandTitle.right
anchors.leftMargin: brandTitle.visible ? 12 : 0'''
assert s.count(old)==1;s=s.replace(old,new)
old='''anchors.left: backToHome.visible ? backToHome.right : parent.left
anchors.leftMargin: backToHome.visible ? 6 : Theme.contentPadding'''
new='''anchors.left: backToHome.visible ? backToHome.right : brandTitle.right
anchors.leftMargin: backToHome.visible ? 6 : (brandTitle.visible ? 16 : 0)'''
assert s.count(old)==1;s=s.replace(old,new)
c=zlib.compress(s.encode(),9);assert len(c)<=limit,(len(c),limit)
struct.pack_into('>I',d,pos-8,len(c)+4);struct.pack_into('>I',d,pos-4,len(s.encode()))
d[pos:pos+limit]=c+b'\0'*(limit-len(c))
# Prevent only MainWindow's original compiled cache entry from being selected;
# the resource URL itself remains unchanged, allowing source-QML fallback.
key='/qt/qml/app/sa6i-link/qml/MainWindow.qml'.encode('utf-16le'); i=0x1d8b050
assert d[i:i+len(key)]==key
j=i+len('/qt/qml/app/sa6i-link/qml/'.encode('utf-16le')); assert d[j:j+2]==b'M\0';d[j]=ord('N')
# Likewise fall back to our edited source for the welcome screen.
key='/qt/qml/app/sa6i-link/qml/pages/WelcomePage.qml'.encode('utf-16le'); i=0x1d8c440
assert d[i:i+len(key)]==key
j=i+len('/qt/qml/app/sa6i-link/qml/pages/'.encode('utf-16le'));assert d[j:j+2]==b'W\0';d[j]=ord('V')
open(out,'wb').write(d); print('compressed',len(c),'max',limit,'sha256',hashlib.sha256(d).hexdigest())
