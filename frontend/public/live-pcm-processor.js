// Converts the browser's native Float32 audio samples to 16-bit signed PCM
// (linear16) on the audio render thread, then hands the raw bytes to the
// main thread over a transferable ArrayBuffer -- zero-copy, keeps the
// conversion off the main thread so it never competes with React rendering.
// Paired with backend/app/routers/live.py's expected wire format exactly:
// 16kHz mono linear16 (see backend/app/services/live_call.py's
// SAMPLE_RATE/ENCODING/CHANNELS).
class LivePcmProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const channelData = inputs[0]?.[0];
    if (channelData && channelData.length > 0) {
      const pcm16 = new Int16Array(channelData.length);
      for (let i = 0; i < channelData.length; i++) {
        const clamped = Math.max(-1, Math.min(1, channelData[i]));
        pcm16[i] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
      }
      this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
    }
    return true; // keep the processor alive for the life of the stream
  }
}

registerProcessor("live-pcm-processor", LivePcmProcessor);
