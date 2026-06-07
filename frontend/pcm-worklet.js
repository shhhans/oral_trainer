'use strict';

// AudioWorklet:把麦克风 Float32 采样转成 16-bit PCM(小端)并 post 给主线程。
// AudioContext 以 sampleRate:16000 创建,源已被重采样到 16k,这里无需再降采样,
// 只做 Float32[-1,1] → Int16 转换,正好满足 DashScope Paraformer 的 pcm/16k 输入。
class PCMWorklet extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (channel && channel.length) {
      const pcm = new Int16Array(channel.length);
      for (let i = 0; i < channel.length; i++) {
        const s = Math.max(-1, Math.min(1, channel[i]));
        pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      // 转移 buffer 所有权,零拷贝传给主线程
      this.port.postMessage(pcm.buffer, [pcm.buffer]);
    }
    return true;  // 保持处理器存活
  }
}

registerProcessor('pcm-worklet', PCMWorklet);
