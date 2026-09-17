"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertCircle, Mic, MicOff, Sparkles } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { api, WS_URL } from "@/lib/api";
import type { Advisor } from "@/lib/types";

type ConnectionState = "idle" | "connecting" | "live" | "error" | "ended";

interface TranscriptLine {
  id: number;
  text: string;
  isFinal: boolean;
}

interface Nudge {
  id: number;
  text: string;
}

type ServerMessage =
  | { type: "transcript"; text: string; is_final: boolean }
  | { type: "nudge"; text: string }
  | { type: "speech_started" }
  | { type: "utterance_end" }
  | { type: "error"; message: string };

let nextLineId = 0;
let nextNudgeId = 0;

export function LiveCallPanel({ initialAdvisorId }: { initialAdvisorId?: string } = {}) {
  const [state, setState] = useState<ConnectionState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [lines, setLines] = useState<TranscriptLine[]>([]);
  const [nudges, setNudges] = useState<Nudge[]>([]);
  const [advisors, setAdvisors] = useState<Advisor[]>([]);
  // Pre-filled when arriving from a Lead's "Call now" link (/live?advisor_id=…)
  // so assigning a lead to an advisor and starting the call is a single click,
  // not a second manual lookup of the same advisor in this dropdown.
  const [advisorId, setAdvisorId] = useState(initialAdvisorId ?? "");
  // Backend's own turn-detection signal (Deepgram VAD, see routers/live.py)
  // -- not diarization-aware yet, so this just means "someone is talking",
  // not "the advisor" or "the customer" specifically.
  const [isSpeaking, setIsSpeaking] = useState(false);
  // Live mic input level (0..1), sampled off a Web Audio analyser -- drives
  // the level meter bars so "the mic is live" is instrumented, not a fixed
  // decorative pulse.
  const [micLevel, setMicLevel] = useState(0);

  // Real audio/socket resources, not React state -- they must survive
  // re-renders untouched and be reachable from cleanup() regardless of
  // which render closure created them.
  const wsRef = useRef<WebSocket | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const levelRafRef = useRef<number | null>(null);

  const cleanup = useCallback(() => {
    if (levelRafRef.current !== null) cancelAnimationFrame(levelRafRef.current);
    levelRafRef.current = null;
    analyserRef.current = null;
    setMicLevel(0);
    workletNodeRef.current?.disconnect();
    workletNodeRef.current = null;
    audioContextRef.current?.close().catch(() => {});
    audioContextRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  useEffect(() => {
    api.listAdvisors().then(setAdvisors).catch(() => {});
  }, []);

  // Stop everything (mic + socket) if the user navigates away mid-call --
  // otherwise the mic would stay hot and the socket open with nothing
  // listening on the React side.
  useEffect(() => () => cleanup(), [cleanup]);

  // Keep the newest line in view -- a live transcript that silently scrolls
  // past the visible area defeats the point of watching it in real time.
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ block: "nearest" });
  }, [lines]);

  async function start() {
    if (!advisorId) return;
    setError(null);
    setLines([]);
    setNudges([]);
    setIsSpeaking(false);
    setState("connecting");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true, noiseSuppression: true },
      });
      streamRef.current = stream;

      // Requesting sampleRate here asks the browser to deliver (or resample
      // to) 16kHz directly -- matches backend/app/services/live_call.py's
      // SAMPLE_RATE exactly, so the worklet below only needs to do the
      // Float32 -> Int16 conversion, not resampling too.
      const audioContext = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = audioContext;
      await audioContext.audioWorklet.addModule("/live-pcm-processor.js");

      const ws = new WebSocket(`${WS_URL}/ws/live?advisor_id=${encodeURIComponent(advisorId)}`);
      wsRef.current = ws;

      ws.onopen = () => {
        const source = audioContext.createMediaStreamSource(stream);
        const worklet = new AudioWorkletNode(audioContext, "live-pcm-processor");
        workletNodeRef.current = worklet;
        worklet.port.onmessage = (event: MessageEvent<ArrayBuffer>) => {
          if (ws.readyState === WebSocket.OPEN) ws.send(event.data);
        };
        source.connect(worklet);

        // Separate tap for the level meter -- doesn't touch the PCM path
        // sent to the backend, just reads the same signal for display.
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.6;
        source.connect(analyser);
        analyserRef.current = analyser;

        const timeDomain = new Uint8Array(analyser.frequencyBinCount);
        const sampleLevel = () => {
          if (!analyserRef.current) return;
          analyserRef.current.getByteTimeDomainData(timeDomain);
          let sumSquares = 0;
          for (let i = 0; i < timeDomain.length; i++) {
            const centered = (timeDomain[i] - 128) / 128;
            sumSquares += centered * centered;
          }
          const rms = Math.sqrt(sumSquares / timeDomain.length);
          setMicLevel(Math.min(1, rms * 4)); // mic RMS runs low; scale up for a readable meter
          levelRafRef.current = requestAnimationFrame(sampleLevel);
        };
        sampleLevel();

        setState("live");
      };

      ws.onmessage = (event: MessageEvent<string>) => {
        const data = JSON.parse(event.data) as ServerMessage;

        if (data.type === "transcript") {
          setLines((prev) => {
            // The last line is still being revised (interim) until a final
            // arrives for it -- update it in place rather than appending a
            // new line on every partial update, whether this event is
            // itself another interim or the finalizing one.
            if (prev.length > 0 && !prev[prev.length - 1].isFinal) {
              const updated = { ...prev[prev.length - 1], text: data.text, isFinal: data.is_final };
              return [...prev.slice(0, -1), updated];
            }
            return [...prev, { id: nextLineId++, text: data.text, isFinal: data.is_final }];
          });
        } else if (data.type === "nudge") {
          setNudges((prev) => [{ id: nextNudgeId++, text: data.text }, ...prev]);
        } else if (data.type === "speech_started") {
          setIsSpeaking(true);
        } else if (data.type === "utterance_end") {
          setIsSpeaking(false);
        } else if (data.type === "error") {
          setError(data.message);
        }
      };

      ws.onerror = () => {
        setError("Connection to the live pipeline was lost.");
        setState("error");
      };

      ws.onclose = () => {
        setState((s) => (s === "live" ? "ended" : s));
      };
    } catch (e) {
      cleanup();
      setState("error");
      setError(e instanceof Error ? e.message : "Could not access the microphone.");
    }
  }

  function stop() {
    cleanup();
    setIsSpeaking(false);
    setState("ended");
  }

  const isLive = state === "live";

  return (
    <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
      <Card
        className="transition-shadow duration-500"
        style={
          isLive
            ? {
                boxShadow: isSpeaking
                  ? "0 0 0 1px var(--series-1), 0 0 28px -4px color-mix(in srgb, var(--series-1) 55%, transparent)"
                  : "0 0 0 1px var(--series-1), 0 0 16px -6px color-mix(in srgb, var(--series-1) 35%, transparent)",
              }
            : undefined
        }
      >
        <CardHeader className="flex-col items-start">
          <CardTitle>Live transcript</CardTitle>
          <CardDescription>
            Streams to Deepgram in real time (not the batch API the Upload flow uses) — interim words update
            in place until each utterance finalizes.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {(state === "idle" || state === "error" || state === "ended") && (
            <div className="mb-3">
              <label className="mb-1 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                Advisor
              </label>
              <select
                required
                value={advisorId}
                onChange={(e) => setAdvisorId(e.target.value)}
                className="w-full max-w-xs rounded-lg border px-2.5 py-1.5 text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--series-1)]"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--text-primary)" }}
              >
                <option value="">Select advisor…</option>
                {advisors.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({a.team_name})
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="mb-4 flex items-center gap-2">
            {state === "idle" || state === "error" || state === "ended" ? (
              <Button variant="primary" onClick={start} disabled={!advisorId}>
                <Mic size={16} />
                Start speaking
              </Button>
            ) : (
              <Button variant="destructive" onClick={stop} disabled={state === "connecting"}>
                <MicOff size={16} />
                {state === "connecting" ? "Connecting…" : "Stop"}
              </Button>
            )}
            <StatusBadge state={state} />
            {isLive && (
              <span
                className="flex items-center gap-2 text-xs font-medium"
                style={{ color: isSpeaking ? "var(--series-1)" : "var(--text-muted)" }}
              >
                <AudioLevelMeter level={micLevel} active={isSpeaking} />
                {isSpeaking ? "Voice detected" : "Silent"}
              </span>
            )}
          </div>

          {error && (
            <div
              className="mb-3 flex items-start gap-2 rounded-lg border px-3 py-2 text-sm"
              style={{ borderColor: "var(--status-critical)", color: "var(--status-critical)" }}
            >
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              {error}
            </div>
          )}

          {state === "ended" && lines.length > 0 && (
            <p className="mb-3 text-sm" style={{ color: "var(--status-good)" }}>
              Session ended — if it covered a real exchange, it&apos;ll show up in this advisor&apos;s call history
              shortly, scored the same way an uploaded recording would be.
            </p>
          )}

          <div
            className="h-80 overflow-y-auto rounded-lg border p-3 text-sm leading-relaxed"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            aria-live="polite"
          >
            {lines.length === 0 ? (
              <p style={{ color: "var(--text-muted)" }}>
                {isLive ? "Listening…" : "Transcript will appear here once you start speaking."}
              </p>
            ) : (
              lines.map((line) => (
                <p
                  key={line.id}
                  className="mb-1.5"
                  style={{ color: line.isFinal ? "var(--text-primary)" : "var(--text-muted)" }}
                >
                  {line.text}
                  {!line.isFinal && <span className="animate-pulse">▋</span>}
                </p>
              ))
            )}
            <div ref={transcriptEndRef} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-col items-start">
          <CardTitle>Coaching nudges</CardTitle>
          <CardDescription>A short, actionable tip whenever the model finds one worth surfacing.</CardDescription>
        </CardHeader>
        <CardContent>
          {nudges.length === 0 ? (
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              {isLive ? "Watching the conversation — nudges show up here." : "No nudges yet."}
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {nudges.map((nudge) => (
                <li
                  key={nudge.id}
                  className="flex items-start gap-2 rounded-lg border px-3 py-2 text-sm animate-[fadeIn_0.25s_ease-out]"
                  style={{ borderColor: "var(--status-warning)", color: "var(--text-primary)" }}
                >
                  <Sparkles size={15} className="mt-0.5 shrink-0" style={{ color: "var(--status-warning)" }} />
                  {nudge.text}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

/** Five-bar mic level meter driven by the analyser's live RMS reading --
 * each bar has a different sensitivity so the row moves organically instead
 * of all bars ticking in lockstep. */
const METER_BAR_WEIGHTS = [0.5, 0.8, 1, 0.8, 0.5];

function AudioLevelMeter({ level, active }: { level: number; active: boolean }) {
  return (
    <span className="flex items-end gap-[2px]" style={{ height: 13 }} aria-hidden>
      {METER_BAR_WEIGHTS.map((weight, i) => {
        const height = Math.max(2, Math.min(13, level * weight * 16));
        return (
          <span
            key={i}
            className="w-[3px] rounded-full transition-[height] duration-75"
            style={{
              height,
              backgroundColor: active ? "var(--series-1)" : "var(--text-muted)",
              opacity: active ? 1 : 0.4,
            }}
          />
        );
      })}
    </span>
  );
}

function StatusBadge({ state }: { state: ConnectionState }) {
  const label: Record<ConnectionState, string> = {
    idle: "Not started",
    connecting: "Connecting…",
    live: "Live",
    error: "Error",
    ended: "Call ended",
  };
  const color: Record<ConnectionState, string> = {
    idle: "var(--text-muted)",
    connecting: "var(--status-warning)",
    live: "var(--status-good)",
    error: "var(--status-critical)",
    ended: "var(--text-muted)",
  };
  return (
    // The dot carries the color coding; the label stays on the app's
    // regular text color -- var(--status-warning) as *text* on this card's
    // near-white background comes out under 2:1 contrast (checked against
    // WCAG's 4.5:1 minimum), fine as a small dot but not as legible text.
    <span className="flex items-center gap-1.5 text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
      <span
        className={state === "live" ? "h-2 w-2 rounded-full animate-pulse" : "h-2 w-2 rounded-full"}
        style={{ backgroundColor: color[state] }}
      />
      {label[state]}
    </span>
  );
}
