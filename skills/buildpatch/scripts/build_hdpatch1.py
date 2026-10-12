#!/usr/bin/env python
"""Build and self-verify an HDPATCH1 copy/literal delta."""
from pathlib import Path
import argparse,hashlib,json,struct
MAGIC=b'HDPATCH1';VERSION=1;BLOCK=256;KEY=16
HEADER=struct.Struct('<8sIQQ32s32sI');COPY=struct.Struct('<BQQ');ADD=struct.Struct('<BQ')
sha=lambda b:hashlib.sha256(b).digest()

def lcp(a,b,ai,bi,n):
 limit=min(len(a)-ai,len(b)-bi);step=1<<20
 while step:
  while n+step<=limit and a[ai+n:ai+n+step]==b[bi+n:bi+n+step]:n+=step
  step//=2
 return n

def build(source,target,out):
 a=source.read_bytes();b=target.read_bytes();index={}
 for off in range(0,len(a)-BLOCK+1,BLOCK):
  k=a[off:off+KEY];v=index.get(k)
  if v is None:index[k]=off
  elif isinstance(v,int):index[k]=[v,off]
  elif len(v)<8:v.append(off)
  else:v[-1]=off
 cmds=[];pos=lit=0
 while pos+BLOCK<=len(b):
  v=index.get(b[pos:pos+KEY]);cands=[] if v is None else ([v] if isinstance(v,int) else v);best=(0,0)
  for off in cands:
   if a[off:off+BLOCK]==b[pos:pos+BLOCK]:
    n=lcp(a,b,off,pos,BLOCK)
    if n>best[1]:best=(off,n)
  if best[1]>=BLOCK:
   if lit<pos:cmds.append((1,b[lit:pos]))
   cmds.append((0,best[0],best[1]));pos+=best[1];lit=pos
  else:pos+=1
 if lit<len(b):cmds.append((1,b[lit:]))
 with out.open('wb') as f:
  f.write(HEADER.pack(MAGIC,VERSION,len(a),len(b),sha(a),sha(b),len(cmds)))
  for c in cmds:
   if c[0]==0:f.write(COPY.pack(*c))
   else:f.write(ADD.pack(1,len(c[1])));f.write(c[1])
 return a,b,cmds

def apply(source,patch):
 a=source.read_bytes()
 with patch.open('rb') as f:
  magic,ver,ss,ts,sh,th,count=HEADER.unpack(f.read(HEADER.size));assert magic==MAGIC and ver==VERSION and ss==len(a) and sh==sha(a)
  out=bytearray()
  for _ in range(count):
   typ=f.read(1)
   if typ==b'\0':off,n=struct.unpack('<QQ',f.read(16));assert off+n<=len(a);out+=a[off:off+n]
   elif typ==b'\1':n=struct.unpack('<Q',f.read(8))[0];chunk=f.read(n);assert len(chunk)==n;out+=chunk
   else:raise ValueError('bad command')
  assert not f.read() and len(out)==ts and sha(out)==th
 return bytes(out)

def main():
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('target',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.parent.mkdir(parents=True,exist_ok=True)
 src,tgt,cmds=build(a.source,a.target,a.output);rebuilt=apply(a.source,a.output);assert rebuilt==tgt
 print(json.dumps({'source_size':len(src),'target_size':len(tgt),'patch_size':a.output.stat().st_size,'commands':len(cmds),'literal_bytes':sum(len(c[1]) for c in cmds if c[0]==1),'source_sha256':sha(src).hex(),'target_sha256':sha(tgt).hex(),'patch_sha256':hashlib.sha256(a.output.read_bytes()).hexdigest()},indent=2))
if __name__=='__main__':main()
