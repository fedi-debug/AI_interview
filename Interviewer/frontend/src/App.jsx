/**
 * HireNest — turn-based AI interview (question audio+text → user speaks → answer shown)
 */
import { useCallback, useEffect, useRef, useState } from 'react';

const isDev = import.meta.env.DEV;
const API = import.meta.env.VITE_API_URL || (isDev ? '' : 'http://127.0.0.1:8000');
const wsUrl = (sessionId) => {
  if (import.meta.env.VITE_WS_URL) {
    return `${import.meta.env.VITE_WS_URL}/ws/interview/${sessionId}`;
  }
  if (isDev) {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${window.location.host}/ws/interview/${sessionId}`;
  }
  return `ws://127.0.0.1:8000/ws/interview/${sessionId}`;
};

function resampleTo16k(float32, sourceSampleRate) {
  if (sourceSampleRate === 16000) return float32;
  const ratio = sourceSampleRate / 16000;
  const outLen = Math.floor(float32.length / ratio);
  const out = new Float32Array(outLen);
  for (let i = 0; i < outLen; i++) out[i] = float32[Math.floor(i * ratio)];
  return out;
}

function floatTo16BitPCM(float32) {
  const buf = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    buf[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return buf.buffer;
}

async function getInterviewMedia() {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('Browser media devices are not available. Use Chrome or Edge over localhost.');
  }

  const audio = { echoCancellation: true, noiseSuppression: true };
  const attempts = [
    { audio, video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' } },
    { audio, video: { width: { ideal: 640 }, height: { ideal: 480 } } },
    { audio, video: true },
  ];

  let lastError = null;
  for (const constraints of attempts) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      if (!stream.getVideoTracks().length) {
        stream.getTracks().forEach((track) => track.stop());
        throw new Error('Camera track was not created.');
      }
      return { stream };
    } catch (err) {
      lastError = err;
    }
  }

  const devices = await navigator.mediaDevices.enumerateDevices().catch(() => []);
  const hasCamera = devices.some((device) => device.kind === 'videoinput');
  const hasMic = devices.some((device) => device.kind === 'audioinput');
  if (!hasCamera) throw new Error('Camera not found. Connect or enable a webcam, then restart the interview.');
  if (!hasMic) throw new Error('Microphone not found. Connect or enable a microphone, then restart the interview.');
  throw new Error(lastError?.message || 'Camera permission failed. Allow camera access and restart the interview.');
}

function playQuestionAudio(msg, onDone) {
  if (msg.audio_base64) {
    const audio = new Audio(`data:audio/wav;base64,${msg.audio_base64}`);
    audio.onended = onDone;
    audio.onerror = onDone;
    audio.play().catch(onDone);
    return audio;
  }
  if (msg.use_browser_tts !== false && window.speechSynthesis) {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(msg.text);
    u.rate = 1;
    u.onend = onDone;
    u.onerror = onDone;
    window.speechSynthesis.speak(u);
    return null;
  }
  onDone();
  return null;
}

export default function App() {
  const [consent, setConsent] = useState(false);
  const [jobTitle, setJobTitle] = useState('Software Engineer');
  const [sessionId, setSessionId] = useState(null);
  const [phase, setPhase] = useState('idle'); // idle | asking | listening | processing
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [qaHistory, setQaHistory] = useState([]);
  const [listeningHint, setListeningHint] = useState('');
  const [report, setReport] = useState(null);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState(null);
  const [mediaHint, setMediaHint] = useState('');
  const [interviewDone, setInterviewDone] = useState(false);
  const [engines, setEngines] = useState(null);
  const [voicePreset, setVoicePreset] = useState('Jasper');
  const [voiceOptions, setVoiceOptions] = useState([
    { id: 'Bella', label: 'Bella (female)', downloaded: true },
    { id: 'Jasper', label: 'Jasper (male)', downloaded: true },
    { id: 'Luna', label: 'Luna (female)', downloaded: true },
    { id: 'Bruno', label: 'Bruno (male)', downloaded: true },
    { id: 'Rosie', label: 'Rosie (female)', downloaded: true },
    { id: 'Hugo', label: 'Hugo (male)', downloaded: true },
    { id: 'Kiki', label: 'Kiki (female)', downloaded: true },
    { id: 'Leo', label: 'Leo (male)', downloaded: true },
  ]);

  const videoRef = useRef(null);
  const wsRef = useRef(null);
  const audioCtxRef = useRef(null);
  const processorRef = useRef(null);
  const videoIntervalRef = useRef(null);
  const seqAudio = useRef(0);
  const seqVideo = useRef(0);
  const streamRef = useRef(null);
  const canvasRef = useRef(null);
  const canStreamAudioRef = useRef(false);
  const questionAudioRef = useRef(null);

  const stopMedia = useCallback(() => {
    window.speechSynthesis?.cancel();
    questionAudioRef.current?.pause();
    if (videoIntervalRef.current) {
      clearInterval(videoIntervalRef.current);
      videoIntervalRef.current = null;
    }
    processorRef.current?.disconnect();
    processorRef.current = null;
    audioCtxRef.current?.close().catch(() => {});
    audioCtxRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    wsRef.current?.close();
    wsRef.current = null;
    canStreamAudioRef.current = false;
  }, []);

  const sendListen = useCallback(() => {
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'control.listen', session_id: sessionId }));
    }
  }, [sessionId]);

  const sendAnswerDone = useCallback(() => {
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'control.answer_done', session_id: sessionId }));
    }
  }, [sessionId]);

  const setupAudio = useCallback((stream, ws, sid) => {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    audioCtxRef.current = ctx;
    const startGraph = () => {
      const source = ctx.createMediaStreamSource(stream);
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;
      const chunkSamples16k = Math.floor(16000 * 1.5);
      let buffer = [];

      processor.onaudioprocess = (e) => {
        if (!canStreamAudioRef.current || ws.readyState !== WebSocket.OPEN) return;
        const input = e.inputBuffer.getChannelData(0);
        const resampled = resampleTo16k(input, ctx.sampleRate);
        buffer.push(...resampled);
        if (buffer.length >= chunkSamples16k) {
          const chunk = buffer.splice(0, chunkSamples16k);
          const pcm = floatTo16BitPCM(new Float32Array(chunk));
          seqAudio.current += 1;
          ws.send(
            JSON.stringify({
              type: 'audio.chunk',
              session_id: sid,
              seq: seqAudio.current,
              sample_rate: 16000,
              channels: 1,
              duration_ms: 1500,
              timestamp_ms: Date.now(),
            })
          );
          ws.send(pcm);
        }
      };
      source.connect(processor);
      processor.connect(ctx.destination);
    };
    if (ctx.state === 'suspended') ctx.resume().then(startGraph);
    else startGraph();
  }, []);

  const setupVideo = useCallback((ws, sid) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    videoIntervalRef.current = setInterval(() => {
      const v = videoRef.current;
      if (!v || ws.readyState !== WebSocket.OPEN || v.readyState < 2) return;
      const w = v.videoWidth || 640;
      const h = v.videoHeight || 480;
      if (!w || !h) return;
      canvas.width = w;
      canvas.height = h;
      ctx.drawImage(v, 0, 0, w, h);
      canvas.toBlob(
        (blob) => {
          if (!blob) return;
          blob.arrayBuffer().then((buf) => {
            seqVideo.current += 1;
            ws.send(
              JSON.stringify({
                type: 'video.frame',
                session_id: sid,
                seq: seqVideo.current,
                width: w,
                height: h,
                format: 'jpeg',
                timestamp_ms: Date.now(),
              })
            );
            ws.send(buf);
          });
        },
        'image/jpeg',
        0.7
      );
    }, 1000 / 6);
  }, []);

  const handleWsMessage = useCallback(
    (msg, ws, sid) => {
      if (msg.type === 'error') {
        setError(msg.message);
        setStatus('error');
        return;
      }
      if (msg.type === 'control.ack') {
        setMediaHint('Connected. Interviewer will ask the first question…');
      }
      if (msg.type === 'interview.question') {
        canStreamAudioRef.current = false;
        setPhase('asking');
        setCurrentQuestion({ turn: msg.turn_index, text: msg.text });
        setListeningHint('');
        questionAudioRef.current = playQuestionAudio(msg, () => {
          setPhase('listening');
          setListeningHint('Speak your answer now. Pause ~3 seconds when finished.');
          canStreamAudioRef.current = true;
          ws.send(JSON.stringify({ type: 'control.listen', session_id: sid }));
        });
      }
      if (msg.type === 'interview.phase') {
        setPhase(msg.phase);
        if (msg.message) setListeningHint(msg.message);
      }
      if (msg.type === 'interview.listening') {
        setListeningHint(
          msg.speaking
            ? 'Listening… keep speaking.'
            : `Pause detected (${msg.silence_chunks || 0}/2) — finish your thought or stay silent to submit.`
        );
      }
      if (msg.type === 'interview.answer') {
        canStreamAudioRef.current = false;
        setPhase('asking');
        setCurrentQuestion(null);
        setQaHistory((h) => [
          ...h,
          { turn: msg.turn_index, question: msg.question, answer: msg.answer },
        ]);
        setListeningHint('Answer recorded. Next question coming…');
      }
      if (msg.type === 'interview.complete') {
        canStreamAudioRef.current = false;
        setInterviewDone(true);
        setPhase('idle');
        setListeningHint(msg.message || 'All questions complete.');
      }
    },
    []
  );

  const startInterview = useCallback(async () => {
    if (!consent) return;
    setError(null);
    setReport(null);
    setQaHistory([]);
    setCurrentQuestion(null);
    setInterviewDone(false);
    setStatus('starting');
    setPhase('idle');
    setListeningHint('');

    try {
      try {
        const health = await fetch(`${API}/health`);
        if (health.ok) setEngines(await health.json());
      } catch {
        /* ignore */
      }

      const res = await fetch(`${API}/interview/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_title: jobTitle,
          consent: true,
          voice_preset: voicePreset,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setSessionId(data.session_id);

      const { stream } = await getInterviewMedia();
      setMediaHint('Camera and microphone are active.');
      streamRef.current = stream;
      const video = videoRef.current;
      if (video) {
        video.srcObject = stream;
        video.muted = true;
        await new Promise((resolve, reject) => {
          video.onloadedmetadata = () => resolve();
          video.onerror = () => reject(new Error('Video failed'));
          video.play().catch(reject);
        });
      }

      const ws = new WebSocket(wsUrl(data.session_id));
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus('live');
        setupAudio(stream, ws, data.session_id);
        setupVideo(ws, data.session_id);
        ws.send(
          JSON.stringify({ type: 'control.start', session_id: data.session_id })
        );
      };

      ws.onmessage = (ev) => {
        if (typeof ev.data !== 'string') return;
        handleWsMessage(JSON.parse(ev.data), ws, data.session_id);
      };

      ws.onerror = () => {
        setError('WebSocket failed');
        setStatus('error');
      };
    } catch (err) {
      setError(err.message || String(err));
      setStatus('error');
      stopMedia();
    }
  }, [consent, jobTitle, voicePreset, setupAudio, setupVideo, stopMedia, handleWsMessage]);

  const endInterview = async () => {
    if (!sessionId) return;
    stopMedia();
    setStatus('scoring');
    try {
      const res = await fetch(`${API}/interview/${sessionId}/end`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content_score: 70 }),
      });
      setReport(await res.json());
      setStatus('done');
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    fetch(`${API}/interview/voices`)
      .then((r) => r.json())
      .then((data) => {
        if (data.voices?.length) {
          setVoiceOptions(data.voices);
          if (data.default) setVoicePreset(data.default);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => () => stopMedia(), [stopMedia]);

  return (
    <div className="app">
      <h1>HireNest — AI Interview</h1>
      <p className="consent">
        The AI interviewer asks questions (audio + text). Speak your answer; it appears after you
        finish.
        <label>
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />{' '}
          I consent
        </label>
      </p>

      <div className="card">
        <label>
          Job: <input value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} />
        </label>
        <br />
        <br />
        <label>
          Interviewer voice:{' '}
          <select
            value={voicePreset}
            onChange={(e) => setVoicePreset(e.target.value)}
            disabled={status === 'live' || status === 'starting'}
          >
            {voiceOptions.map((v) => (
              <option key={v.id} value={v.id}>
                {v.label}
                {v.downloaded === false ? ' (not downloaded)' : ''}
              </option>
            ))}
          </select>
        </label>
        <p className="hint">
          KittenTTS voices are generated locally. The first question may take longer while the
          model is downloaded and cached.
        </p>
        <br />
        <button
          type="button"
          disabled={!consent || status === 'live' || status === 'starting'}
          onClick={startInterview}
        >
          Start interview
        </button>
        <button type="button" disabled={status !== 'live'} onClick={endInterview}>
          End & score
        </button>
        <button
          type="button"
          disabled={phase !== 'listening'}
          onClick={sendAnswerDone}
          title="Click when you finished speaking"
        >
          I&apos;m done speaking
        </button>
        <p>
          Status: <strong>{status}</strong> · Phase: <strong>{phase}</strong>
        </p>
        {engines && (
          <p className="hint">
            ASR: <strong>{engines.asr_engine}</strong> · TTS: <strong>{engines.tts_engine}</strong>
            {engines.asr_engine === 'mock' && ' — set MOCK_ASR=false and run scripts\\setup_asr_tts.ps1'}
            {engines.tts_engine !== 'kittentts' && ' — install KittenTTS dependencies for local voice'}
          </p>
        )}
        {listeningHint && <p className="hint">{listeningHint}</p>}
        {error && <p className="error">{error}</p>}
      </div>

      <div className="card">
        <video ref={videoRef} autoPlay playsInline muted className="preview" />
        <canvas ref={canvasRef} style={{ display: 'none' }} />
      </div>

      {currentQuestion && (
        <div className="card question-card">
          <h3>Interviewer asks</h3>
          <p className="question-text">{currentQuestion.text}</p>
          {phase === 'asking' && <span className="badge">Playing question…</span>}
        </div>
      )}

      {phase === 'listening' && (
        <div className="card listening-card">
          <h3>Your turn</h3>
          <p>Speak clearly. Stop for ~3 seconds when finished, or click &quot;I&apos;m done speaking&quot;.</p>
        </div>
      )}

      {phase === 'processing' && (
        <div className="card">
          <h3>Processing your answer…</h3>
        </div>
      )}

      {qaHistory.length > 0 && (
        <div className="card">
          <h3>Q &amp; A</h3>
          {qaHistory.map((item) => (
            <div key={item.turn} className="qa-block">
              <p className="q">
                <strong>Q{item.turn + 1}:</strong> {item.question}
              </p>
              <p className="a">
                <strong>Your answer:</strong> {item.answer}
              </p>
            </div>
          ))}
        </div>
      )}

      {interviewDone && (
        <p className="hint">All questions done. Click End &amp; score for the final report.</p>
      )}

      {report && (
        <div className="card report">
          <h3>Final report</h3>
          <pre>{JSON.stringify(report, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
