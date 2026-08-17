import { useCallback, useRef, useState } from 'react';
import { KEY, ME } from './api';
import type { RecordState } from './types';

/* The voice loop: mic -> AudioWorklet -> WebSocket -> ADK -> Live API, and
 * native audio back. Kept out of the components because none of it is
 * rendering, and because every one of these handles has to be released on the
 * way out — an AudioContext left open keeps the microphone indicator lit on
 * her phone long after she thinks she has finished talking.
 */

interface Recorder {
  state: RecordState;
  /** What to show her: whose turn it is, or why it did not start. */
  said: string;
  toggle: () => Promise<void>;
}

export function useRecorder(onFinished: () => void): Recorder {
  const [state, setState] = useState<RecordState>('idle');
  const [said, setSaid] = useState('');

  const ws = useRef<WebSocket | null>(null);
  const ctx = useRef<AudioContext | null>(null);
  const playCtx = useRef<AudioContext | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const playAt = useRef(0);

  const play = useCallback((bytes: Uint8Array, rate: number) => {
    playCtx.current ??= new AudioContext();
    const out = playCtx.current;
    const pcm = new Int16Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / 2);
    const buf = out.createBuffer(1, pcm.length, rate);
    const ch = buf.getChannelData(0);
    for (let i = 0; i < pcm.length; i++) ch[i] = (pcm[i] ?? 0) / 32768;
    const src = out.createBufferSource();
    src.buffer = buf;
    src.connect(out.destination);
    playAt.current = Math.max(playAt.current, out.currentTime);
    src.start(playAt.current);
    playAt.current += buf.duration;
  }, []);

  const stop = useCallback(() => {
    ws.current?.close();
    void ctx.current?.close();
    void playCtx.current?.close();
    stream.current?.getTracks().forEach((t) => t.stop());
    ws.current = ctx.current = playCtx.current = null;
    stream.current = null;
    playAt.current = 0;
    setState('idle');
    setSaid('Saved. Xiao Chuan will listen again later.');
    onFinished();
  }, [onFinished]);

  const start = useCallback(async () => {
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
    } catch (err) {
      setSaid('Cannot open the microphone: ' + (err as Error).message);
      return;
    }

    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const socket = new WebSocket(
      `${proto}://${location.host}/ws/talk?key=${encodeURIComponent(KEY)}&user=${encodeURIComponent(ME)}`,
    );
    ws.current = socket;
    socket.onmessage = (e: MessageEvent<string>) => {
      const m = JSON.parse(e.data) as {
        audio?: string;
        sample_rate?: number;
        agent_transcript?: string;
        user_transcript?: string;
        interrupted?: boolean;
      };
      if (m.audio) {
        play(Uint8Array.from(atob(m.audio), (c) => c.charCodeAt(0)), m.sample_rate ?? 24000);
      }
      if (m.agent_transcript) setSaid('Xiao Chuan: ' + m.agent_transcript);
      if (m.user_transcript) setSaid(m.user_transcript);
      if (m.interrupted) playAt.current = 0;
    };
    socket.onclose = () => stop();

    const audio = new AudioContext({ sampleRate: 16000 });
    ctx.current = audio;
    await audio.audioWorklet.addModule('/worklet.js');
    const node = new AudioWorkletNode(audio, 'pcm-capture');
    node.port.onmessage = (e: MessageEvent<ArrayBuffer>) => {
      if (socket.readyState === WebSocket.OPEN) socket.send(e.data);
    };
    audio.createMediaStreamSource(stream.current).connect(node);
    node.connect(audio.destination);

    setState('live');
    setSaid('Xiao Chuan is listening');
  }, [play, stop]);

  const toggle = useCallback(async () => {
    if (state === 'live') stop();
    else await start();
  }, [state, start, stop]);

  return { state, said, toggle };
}
