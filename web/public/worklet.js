// Capture microphone audio as 16-bit PCM for the Live API.
//
// An AudioWorklet rather than the deprecated ScriptProcessor: this runs on the
// audio thread, so a slow main thread cannot drop her words mid-sentence.
class PcmCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    // ~64 ms at 16 kHz. Small enough to stay responsive, large enough that we
    // are not posting a message every 128 frames.
    this.target = 1024;
    this.buffer = new Int16Array(this.target);
    this.filled = 0;
  }

  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;

    for (let i = 0; i < channel.length; i++) {
      // Float [-1,1] to int16, clamped: the Live API rejects anything else.
      const sample = Math.max(-1, Math.min(1, channel[i]));
      this.buffer[this.filled++] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;

      if (this.filled === this.target) {
        this.port.postMessage(this.buffer.buffer.slice(0));
        this.filled = 0;
      }
    }
    return true;
  }
}

registerProcessor("pcm-capture", PcmCapture);
