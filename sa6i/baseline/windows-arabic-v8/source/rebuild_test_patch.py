import hashlib,struct,zlib,base64,sys,re,os
p=sys.argv[1] if len(sys.argv)>1 else 'nectarlink-desktop.exe'
d=bytearray(open(p,'rb').read())
assert hashlib.sha256(d).hexdigest()=='670e24bf1c4938bd3199351f84e4391f4649eef07517105502a56faa3979a365'
# Windows 7 v3 loader patches
assert d[0xf04a27:0xf04a2d]==bytes.fromhex('ff15d389bf00')
assert d[0xa605fd:0xa60603]==bytes.fromhex('ff15bdc80901')
assert d[0x1ce1888:0x1ce1888+34]==b'QT_QPA_DISABLE_REDIRECTION_SURFACE'
d[0x1ce1888+33]=ord('X')
d[0x24eedc8+8:0x24eedc8+16]=d[0x24eedc8:0x24eedc8+8]
d[0x1afc8b8+8:0x1afc8b8+16]=d[0x1afc8b8:0x1afc8b8+8]
d[0x24ef310:0x24ef318]=d[0x24ef318:0x24ef320]
d[0x1afce00:0x1afce08]=d[0x1afce08:0x1afce10]
d[0x1afac3f:0x1afac45]=bytes.fromhex('b801400080c3')
struct.pack_into('<I',d,0x240,0x1afa83f+6)
for off,rva in [(0xf04a27,0xf05627),(0xa605fd,0xa611fd)]:
 d[off]=0xe8;struct.pack_into('<i',d,off+1,0x1afb83f-(rva+5));d[off+5]=0x90
# Replace the embedded compressed MainWindow QML only, no relocation
pos=0x1d53d2d
uncompressed=struct.unpack_from('>I',d,pos-4)[0]; stored=struct.unpack_from('>I',d,pos-8)[0]
s=zlib.decompress(d[pos:pos+stored-4]).decode(); assert len(s.encode())==uncompressed
old='''            color: Theme.graphite ? Theme.surfaceContent : Theme.primary
            Icon {
                anchors.centerIn: parent
                path: Icons.mark
                stroke: 2.4
                color: Theme.graphite ? Theme.surface : Theme.primaryContent
            }'''
assert s.count(old)==1
b64=base64.b64encode(open(os.path.join(os.path.dirname(__file__),'logo.png'),'rb').read()).decode()
s=s.replace(old,'color: "black"\nImage { anchors.fill: parent; anchors.margins: 2; fillMode: Image.PreserveAspectFit; source: "data:image/png;base64,'+b64+'" }')
assert s.count('title: "NectarLink"')==1
s=s.replace('title: "NectarLink"','title: "Sa6i Link"')
s='\n'.join(line.lstrip() for line in s.split('\n') if not line.lstrip().startswith('//'))
c=zlib.compress(s.encode(),9);assert len(c)<=stored-4,(len(c),stored)
struct.pack_into('>I',d,pos-8,len(c)+4);struct.pack_into('>I',d,pos-4,len(s.encode()))
d[pos:pos+stored-4]=c+b'\0'*(stored-4-len(c))
assert zlib.decompress(d[pos:pos+len(c)])==s.encode()
# Change app names in selected visible QML messages, leaving internal names,
# update URLs, Windows component names, paths and credits intact.
for pos in [0x1d4bc48,0x1d50a65,0x1d52670,0x1d5d24e,0x1d5dde3,0x1d66977,0x1d6b5fd,0x1d6d580,0x1d87e17]:
    n=struct.unpack_from('>I',d,pos-8)[0]; oldbytes=struct.unpack_from('>I',d,pos-4)[0]
    raw=zlib.decompress(d[pos:pos+n-4]); assert len(raw)==oldbytes
    text=raw.decode()
    def rebrand(m):
        a=m.group(1)
        if 'Virtual Camera' in a or 'virtual camera' in a or 'in Windows Settings' in a: return m.group(0)
        return 'qsTr("'+a.replace('NectarLink','Sa6i Link')+'")'
    text=re.sub(r'qsTr\("([^"\\]*(?:\\.[^"\\]*)*)"\)',rebrand,text)
    compressed=zlib.compress(text.encode(),9)
    if len(compressed)>n-4:
        text='\n'.join(line.lstrip() for line in text.split('\n') if not line.lstrip().startswith('//'))
        compressed=zlib.compress(text.encode(),9)
    assert len(compressed)<=n-4,(hex(pos),len(compressed),n-4)
    struct.pack_into('>I',d,pos-8,len(compressed)+4);struct.pack_into('>I',d,pos-4,len(text.encode()))
    d[pos:pos+n-4]=compressed+b'\0'*(n-4-len(compressed))
    print('Rebranded UI resource:',hex(pos),'size',n-4,'->',len(compressed))
# Rebrand the first-run welcome screen as well. It is an uncompressed RCC entry.
pos=0x1d73447
n=struct.unpack_from('>I',d,pos-4)[0]
s=d[pos:pos+n].decode()
assert 'Welcome to NectarLink' in s
old='''            color: Theme.graphite ? Theme.surfaceContent : Theme.primary
            Icon {
                anchors.centerIn: parent
                width: 26; height: 26
                path: Icons.mark
                stroke: 2.4
                color: Theme.graphite ? Theme.surface : Theme.primaryContent
            }'''
assert s.count(old)==1
b64=base64.b64encode(open(os.path.join(os.path.dirname(__file__),'logo-welcome.png'),'rb').read()).decode()
s=s.replace(old,'color: "black"\nImage { anchors.fill: parent; anchors.margins: 2; fillMode: Image.PreserveAspectFit; source: "data:image/png;base64,'+b64+'" }')
s=s.replace('Welcome to NectarLink','Welcome to Sa6i Link').replace("NectarLink couldn't start", "Sa6i Link couldn't start")
s='\n'.join(line.lstrip() for line in s.split('\n') if not line.lstrip().startswith('//'))
b=s.encode(); assert len(b)<=n, (len(b),n)
d[pos:pos+n]=b+b' '*(n-len(b))
out=sys.argv[2] if len(sys.argv)>2 else 'Sa6i-Link-Win7-UI-TEST.exe'
open(out,'wb').write(d)
print(out,'compressed',len(c),'was',stored-4,'sha256',hashlib.sha256(d).hexdigest())
