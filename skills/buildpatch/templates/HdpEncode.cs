// HdpEncode — build HDPATCH1 copy/literal deltas.
// Usage: HdpEncode <source> <target> <output.patch>
// Format (compatible with templates/Hdp.cs and scripts/build_hdpatch1.py):
//   header: <8s 'HDPATCH1'><I ver><Q srcLen><Q tgtLen><32s srcSha><32s tgtSha><I cmdCount>
//   copy  : <B 0><Q srcOffset><Q len>      add: <B 1><Q len><bytes>
// Matching: aligned 256-byte index for jumps + SIMD window search to follow uniform shifts
// (a rebuilt container differs from the original by a few bytes, which shifts everything after).
using System;
using System.IO;
using System.Security.Cryptography;

static class HdpEncode
{
    const int BLK = 256;        // aligned index granularity
    const int WIN = 32;         // window used for shift search
    const int MINRUN = 64;      // shortest copy worth emitting
    const int STRIDE = 16;      // advance by this much when nothing matches (MINRUN >= STRIDE, so no long run is skipped)
    const long SPAN = 1 << 18;  // how far to look for a shifted match

    static long Extend(byte[] a, byte[] b, long ai, long bi)
    {
        long max = Math.Min(a.Length - ai, b.Length - bi);
        long n = 0;
        while (n < max && a[ai + n] == b[bi + n]) n++;
        return n;
    }

    static void Main(string[] args)
    {
        if (args.Length != 3) { Console.Error.WriteLine("usage: HdpEncode <source> <target> <output>"); Environment.Exit(2); }
        byte[] a = File.ReadAllBytes(args[0]);
        byte[] b = File.ReadAllBytes(args[1]);
        var index = new System.Collections.Generic.Dictionary<int, System.Collections.Generic.List<int>>();
        for (int off = 0; off + BLK <= a.Length; off += BLK)
        {
            int h = 0; for (int k = 0; k < 16; k++) h = h * 31 + a[off + k];
            if (!index.TryGetValue(h, out var list)) { list = new System.Collections.Generic.List<int>(1); index[h] = list; }
            if (list.Count < 4) list.Add(off);
        }

        var ms = new MemoryStream();
        var w = new BinaryWriter(ms);
        long lit = 0, t = 0, srcEnd = -1, tgtEnd = -1;
        int cmdCount = 0;
        while (t + WIN <= b.Length)
        {
            long bestOff = -1, bestLen = 0;
            int h = 0; for (int k = 0; k < 16; k++) h = h * 31 + b[t + k];
            if (index.TryGetValue(h, out var cands))
                foreach (int off in cands)
                    if (off + BLK <= a.Length)
                    {
                        long n = Extend(a, b, off, t);
                        if (n > bestLen) { bestLen = n; bestOff = off; }
                    }
            if (bestLen < MINRUN)
            {
                long est = srcEnd >= 0 ? srcEnd + (t - tgtEnd) : t;
                long lo = Math.Max(0, est - SPAN), hi = Math.Min(a.Length - WIN, est + SPAN);
                if (hi > lo)
                {
                    int found = a.AsSpan((int)lo, (int)(hi - lo)).IndexOf(b.AsSpan((int)t, WIN));
                    if (found >= 0)
                    {
                        long off = lo + found;
                        long n = Extend(a, b, off, t);
                        if (n > bestLen) { bestLen = n; bestOff = off; }
                    }
                }
            }
            if (bestLen >= MINRUN)
            {
                if (t > lit) { w.Write((byte)1); w.Write((ulong)(t - lit)); w.Write(b, (int)lit, (int)(t - lit)); cmdCount++; }
                w.Write((byte)0); w.Write((ulong)bestOff); w.Write((ulong)bestLen);
                cmdCount++;
                srcEnd = bestOff + bestLen; tgtEnd = t + bestLen;
                t += bestLen; lit = t;
            }
            else t += STRIDE;
        }
        if (lit < b.Length) { w.Write((byte)1); w.Write((ulong)(b.Length - lit)); w.Write(b, (int)lit, (int)(b.Length - lit)); cmdCount++; }
        w.Flush();
        byte[] body = ms.ToArray();
        using (var fs = File.Create(args[2]))
        using (var bw = new BinaryWriter(fs))
        {
            bw.Write(System.Text.Encoding.ASCII.GetBytes("HDPATCH1"));
            bw.Write((uint)1);
            bw.Write((ulong)a.Length);
            bw.Write((ulong)b.Length);
            using (var sha = SHA256.Create()) bw.Write(sha.ComputeHash(a));
            using (var sha = SHA256.Create()) bw.Write(sha.ComputeHash(b));
            bw.Write((uint)cmdCount);
            bw.Write(body);
        }
        Console.WriteLine($"commands={cmdCount} literalBody={body.Length:N0} patch={new FileInfo(args[2]).Length:N0} B");
    }
}
