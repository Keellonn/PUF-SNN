/*
this queue separates frame-time XR capture from later window processing and file writing
it is a small plain C# class so the complete queue-to-JSONL path can be tested in EditMode
*/

using System.Collections.Concurrent;
using System.Collections.Generic;

namespace PufSnn.QuestLogger {
    public sealed class RawPoseBuffer {
        private readonly ConcurrentQueue<RawHeadPoseSample> samples = new ConcurrentQueue<RawHeadPoseSample>();

        public void Enqueue(RawHeadPoseSample sample) {
            if (sample == null)
                throw new System.ArgumentNullException(nameof(sample));

            samples.Enqueue(sample);
        }

        public void Clear() {
            // this removes every sample left by the previous trial
            while (samples.TryDequeue(out _)) {
            }
        }

        public List<RawHeadPoseSample> Drain() {
            List<RawHeadPoseSample> captured = new List<RawHeadPoseSample>();

            while (samples.TryDequeue(out RawHeadPoseSample sample)) {
                captured.Add(sample);
            }

            return captured;
        }
    }
}
