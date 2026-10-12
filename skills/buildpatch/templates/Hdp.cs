using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;

namespace PatchInstaller;

static class Hdp {
 static readonly byte[] Magic="HDPATCH1"u8.ToArray();
 static byte[] ReadExact(BinaryReader r,int n){var b=r.ReadBytes(n);if(b.Length!=n)throw new EndOfStreamException();return b;}
 static byte[] Sha(string path){using var s=File.OpenRead(path);return SHA256.HashData(s);}
 static byte[] Hex(string value){try{return Convert.FromHexString(value);}catch{throw new InvalidDataException("Invalid manifest SHA-256.");}}
 public static void Apply(string source,string patch,string output,long sourceSizeExpected,string sourceHashExpected,long targetSizeExpected,string targetHashExpected){
  if(new FileInfo(source).Length!=sourceSizeExpected||!CryptographicOperations.FixedTimeEquals(Sha(source),Hex(sourceHashExpected)))throw new InvalidDataException("Delta source size/hash mismatch.");
  Directory.CreateDirectory(Path.GetDirectoryName(output)!);
  try{
   using var p=new BinaryReader(new FileStream(patch,FileMode.Open,FileAccess.Read,FileShare.Read,1<<20,FileOptions.SequentialScan));
   if(!ReadExact(p,8).SequenceEqual(Magic)||p.ReadUInt32()!=1)throw new InvalidDataException("Invalid delta header.");
   var sourceSize=p.ReadUInt64();var targetSize=p.ReadUInt64();var sourceHash=ReadExact(p,32);var targetHash=ReadExact(p,32);var count=p.ReadUInt32();
   if(sourceSize!=(ulong)sourceSizeExpected||targetSize!=(ulong)targetSizeExpected||!CryptographicOperations.FixedTimeEquals(sourceHash,Hex(sourceHashExpected))||!CryptographicOperations.FixedTimeEquals(targetHash,Hex(targetHashExpected))||count>10_000_000)throw new InvalidDataException("Delta header/manifest mismatch.");
   using var src=new FileStream(source,FileMode.Open,FileAccess.Read,FileShare.Read,1<<20,FileOptions.RandomAccess);
   using var dst=new FileStream(output,FileMode.Create,FileAccess.Write,FileShare.None,1<<20,FileOptions.SequentialScan);
   var buffer=new byte[1<<20];ulong written=0;
   for(uint i=0;i<count;i++){
    var type=p.ReadByte();
    if(type==0){var off=p.ReadUInt64();var len=p.ReadUInt64();if(off>sourceSize||len>sourceSize-off||len>targetSize-written)throw new InvalidDataException("Delta copy out of range.");src.Position=(long)off;var left=len;while(left>0){var take=(int)Math.Min((ulong)buffer.Length,left);var got=src.Read(buffer,0,take);if(got!=take)throw new EndOfStreamException();dst.Write(buffer,0,got);left-=(ulong)got;}written+=len;}
    else if(type==1){var len=p.ReadUInt64();if(len>targetSize-written)throw new InvalidDataException("Delta literal out of range.");var left=len;while(left>0){var take=(int)Math.Min((ulong)buffer.Length,left);var got=p.Read(buffer,0,take);if(got!=take)throw new EndOfStreamException();dst.Write(buffer,0,got);left-=(ulong)got;}written+=len;}
    else throw new InvalidDataException("Unknown delta command.");
   }
   if(written!=targetSize||p.BaseStream.Position!=p.BaseStream.Length)throw new InvalidDataException("Delta length/trailing-data mismatch.");dst.Flush(true);
  }catch{try{File.Delete(output);}catch{}throw;}
  if(new FileInfo(output).Length!=targetSizeExpected||!CryptographicOperations.FixedTimeEquals(Sha(output),Hex(targetHashExpected))){File.Delete(output);throw new InvalidDataException("Delta target size/hash mismatch.");}
 }
}
