// Turns microphone audio into PCM16 mono chunks of 100 ms (2400 frames at 24 kHz).
// Adapted from beyondelastic/foundry-voice-agent (MIT).
const pcm16 = (s) => (s < 0 ? Math.max(-1, s) * 0x8000 : Math.min(1, s) * 0x7fff);

class MicCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Int16Array(2400);
    this.length = 0;
  }

  process(inputs) {
    const mic = inputs[0][0];
    if (!mic) return true;
    for (let i = 0; i < mic.length; i++) {
      this.buffer[this.length++] = pcm16(mic[i]);
      if (this.length === this.buffer.length) {
        this.port.postMessage(this.buffer.buffer.slice(0));
        this.length = 0;
      }
    }
    return true;
  }
}

registerProcessor("mic-capture", MicCapture);
