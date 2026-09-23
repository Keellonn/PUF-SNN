// TEST ONLY / SYNTHETIC PUBLIC FIXTURE / NOT RUNTIME SECRET MATERIAL.
using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using NUnit.Framework;
using UnityEngine;
using PufSnn.QuestLogger;

public class BinaryWindowMessageWriterTests {
    [Serializable] public class Scalar {
        public string id; public string[] words; public bool valid;
        public string expected_hex; public string sha256; public string hmac;
    }
    [Serializable] public class WindowVector {
        public string id; public string position_word; public int tracking_count;
        public bool quaternion; public bool valid; public int length;
        public string expected_hex; public string sha256; public string hmac;
    }
    [Serializable] public class Vectors { public string key_hex; public Scalar[] scalars; public WindowVector[] windows; }
    private static byte[] Hex(string text) {
        return Enumerable.Range(0, text.Length / 2).Select(i => Convert.ToByte(text.Substring(i*2,2),16)).ToArray();
    }
    private static Vectors Load() {
        DirectoryInfo root = new DirectoryInfo(Application.dataPath);
        while (root != null && !File.Exists(Path.Combine(root.FullName,"tests/auth/fixtures/binary-v2/vectors.json"))) root = root.Parent;
        Assert.IsNotNull(root, "Run in repository checkout: shared immutable fixtures are required.");
        return JsonUtility.FromJson<Vectors>(File.ReadAllText(Path.Combine(root.FullName,"tests/auth/fixtures/binary-v2/vectors.json")));
    }
    private static void Digests(byte[] actual, string sha, string tag, byte[] key) {
        using (SHA256 hash = SHA256.Create()) CollectionAssert.AreEqual(Hex(sha), hash.ComputeHash(actual));
        using (HMACSHA256 hmac = new HMACSHA256(key)) CollectionAssert.AreEqual(Hex(tag), hmac.ComputeHash(actual));
    }
    [Test] public void ScalarBytesAndLiteralTags() {
        Vectors vectors = Load();
        foreach (Scalar v in vectors.scalars) {
            if (!v.valid) {
                foreach (string word in v.words) {
                    float value = BinaryWindowMessageWriter.FromBits(Convert.ToUInt32(word,16));
                    Assert.Throws<InvalidDataException>(() => BinaryWindowMessageWriter.EncodeFloat(value));
                    Assert.Throws<InvalidDataException>(() => BinaryWindowMessageWriter.ParseFloat(Hex(word)));
                }
                continue;
            }
            byte[] actual = v.words.SelectMany(w => BinaryWindowMessageWriter.EncodeFloat(BinaryWindowMessageWriter.FromBits(Convert.ToUInt32(w,16)))).ToArray();
            CollectionAssert.AreEqual(Hex(v.expected_hex),actual,v.id);
            Digests(actual,v.sha256,v.hmac,Hex(vectors.key_hex));
        }
        Assert.Throws<InvalidDataException>(() => BinaryWindowMessageWriter.ParseFloat(Hex("80000000")));
    }
    [Test] public void CompleteWindowRawBytesMatchSharedPythonFixtures() {
        Vectors vectors = Load();
        foreach (WindowVector v in vectors.windows) {
            BinaryWindow w = new BinaryWindow { device_id="quest-02",session_id=Enumerable.Range(0,16).Select(i=>(byte)i).ToArray(),
                sequence_number=0,window_id="binary-golden-000",capture_start_ns=1000000000,capture_end_ns=3000000000,
                samples=new BinaryWindowSample[120] };
            for (int i=0;i<120;i++) {
                float half=BinaryWindowMessageWriter.FromBits(0x3f3504f3);
                w.samples[i]=new BinaryWindowSample { sample_index=i,capture_time_ns=1000000000L+i*16666667L,
                    position_m=i==0 ? new float[] { BinaryWindowMessageWriter.FromBits(Convert.ToUInt32(v.position_word,16)),-0.25f,0 } : new float[3],
                    orientation_xyzw=v.quaternion ? new float[] {0,half,0,half} : new float[] {0,0,0,1},tracking_valid=i<v.tracking_count };
            }
            if (!v.valid) { Assert.Throws<InvalidDataException>(() => BinaryWindowMessageWriter.BuildCanonicalProtectedBytes(w)); continue; }
            byte[] actual=BinaryWindowMessageWriter.BuildCanonicalProtectedBytes(w);
            CollectionAssert.AreEqual(Hex(v.expected_hex),actual,v.id);
            Assert.AreEqual(v.length,actual.Length);
            Digests(actual,v.sha256,v.hmac,Hex(vectors.key_hex));
        }
    }
}
