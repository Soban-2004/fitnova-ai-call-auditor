"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertCircle, Bot, Mic, MicOff, User } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { WS_URL } from "@/lib/api";

type ConnectionState = "idle" | "connecting" | "live" | "done" | "error" | "ended";

interface ConversationLine {
  id: number;
  role: "agent" | "caller";
  text: string;
  isFinal: boolean; // only meaningful for caller lines -- agent lines are always complete on arrival
}

type ServerMessage =
  | { type: "transcript"; text: string; is_final: boolean }
  | { type: "agent_text"; text: string }
  | { type: "interrupt" }
  | { type: "speech_started" }
  | { type: "utterance_end" }
  | { type: "done" }
  | { type: "error"; message: string };

let nextLineId = 0;

export function VoiceAgentPanel() {
  const [state, setState] = useState<ConnectionState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [lines, setLines] = useState<ConversationLine[]>([]);
  const [isSpeaking, setIsSpeaking] = useState(false); // caller's mic, via Deepgram VAD
  const [isAgentTalking, setIsAgentTalking] = useState(false); // agent's own audio playback

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const playbackRef = useRef<HTMLAudioElement | null>(null);
  const playbackUrlRef = useRef<string | null>(null);
  const conversationEndRef = useRef<HTMLDivElement | null>(null);

  const cleanup = useCallback(() => {
    workletNodeRef.current?.disconnect();
    workletNodeRef.current = null;
    audioContextRef.current?.close().catch(() => {});
    audioContextRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    wsRef.current?.close();
    wsRef.current = null;
    stopPlayback();
  }, []);

  function stopPlayback() {
    playbackRef.current?.pause();
    playbackRef.current = null;
    if (playbackUrlRef.current) {
      URL.revokeObjectURL(playbackUrlRef.current);
      playbackUrlRef.current = null;
    }
    setIsAgentTalking(false);
  }

  function playAgentAudio(data: ArrayBuffer) {
    stopPlayback(); // a new turn's audio always supersedes anything still playing
    const url = URL.createObjectURL(new Blob([data], { type: "audio/wav" }));
    playbackUrlRef.current = url;
    const audio = new Audio(url);
    playbackRef.current = audio;
    setIsAgentTalking(true);
    audio.onended = () => setIsAgentTalking(false);
    audio.play().catch(() => setIsAgentTalking(false)); // autoplay can be blocked pre-interaction; Start already required a click
  }

  useEffect(() => () => cleanup(), [cleanup]);

  // Keep the newest turn in view -- same reasoning as LiveCallPanel's
  // transcript auto-scroll.
  useEffect(() => {
    conversationEndRef.current?.scrollIntoView({ block: "nearest" });
  }, [lines]);

  async function start() {
    setError(null);
    setLines([]);
    setIsSpeaking(false);
    setState("connecting");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true, noiseSuppression: true },
      });
      streamRef.current = stream;

      const audioContext = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = audioContext;
      await audioContext.audioWorklet.addModule("/live-pcm-processor.js");

      const ws = new WebSocket(`${WS_URL}/ws/agent`);
      ws.binaryType = "arraybuffer"; // this socket receives binary audio, unlike /ws/live's send-only mic stream
      wsRef.current = ws;

      ws.onopen = () => {
        const source = audioContext.createMediaStreamSource(stream);
        const worklet = new AudioWorkletNode(audioContext, "live-pcm-processor");
        workletNodeRef.current = worklet;
        worklet.port.onmessage = (event: MessageEvent<ArrayBuffer>) => {
          if (ws.readyState === WebSocket.OPEN) ws.send(event.data);
        };
        source.connect(worklet);
        setState("live");
      };

      ws.onmessage = (event: MessageEvent<string | ArrayBuffer>) => {
        if (event.data instanceof ArrayBuffer) {
          playAgentAudio(event.data);
          return;
        }
        const data = JSON.parse(event.data) as ServerMessage;

        if (data.type === "transcript") {
          setLines((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.role === "caller" && !last.isFinal) {
              return [...prev.slice(0, -1), { ...last, text: data.text, isFinal: data.is_final }];
            }
            return [...prev, { id: nextLineId++, role: "caller", text: data.text, isFinal: data.is_final }];
          });
        } else if (data.type === "agent_text") {
          setLines((prev) => [...prev, { id: nextLineId++, role: "agent", text: data.text, isFinal: true }]);
        } else if (data.type === "interrupt") {
          // Barge-in: the caller started talking while the agent's own
          // audio was still playing -- cut it off immediately rather than
          // let two voices talk over each other.
          stopPlayback();
        } else if (data.type === "speech_started") {
          setIsSpeaking(true);
        } else if (data.type === "utterance_end") {
          setIsSpeaking(false);
        } else if (data.type === "done") {
          setState("done");
        } else if (data.type === "error") {
          setError(data.message);
        }
      };

      ws.onerror = () => {
        setError("Connection to the voice agent was lost.");
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

  const isLive = state === "live" || state === "done";

  return (
    <Card className="max-w-2xl">
      <CardHeader className="flex-col items-start">
        <CardTitle>FitNova intake agent</CardTitle>
        <CardDescription>
          A real closed-loop voice agent — it listens, decides what to say, and speaks back (Cartesia TTS), not
          just a silent coaching companion like the Live Call page. Talk over it and it stops to listen.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="mb-4 flex flex-wrap items-center gap-2">
          {state === "idle" || state === "error" || state === "ended" ? (
            <Button variant="primary" onClick={start}>
              <Mic size={16} />
              Call the intake agent
            </Button>
          ) : (
            <Button variant="destructive" onClick={stop} disabled={state === "connecting"}>
              <MicOff size={16} />
              {state === "connecting" ? "Connecting…" : "Hang up"}
            </Button>
          )}
          <StatusBadge state={state} />
          {isLive && (
            <>
              <span
                className="flex items-center gap-1.5 text-xs font-medium"
                style={{ color: isSpeaking ? "var(--series-1)" : "var(--text-muted)" }}
              >
                <Mic size={13} className={isSpeaking ? "animate-pulse" : undefined} />
                {isSpeaking ? "You're talking" : "Silent"}
              </span>
              {isAgentTalking && (
                <span className="flex items-center gap-1.5 text-xs font-medium" style={{ color: "var(--series-1)" }}>
                  <Bot size={13} className="animate-pulse" />
                  Agent speaking
                </span>
              )}
            </>
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

        <div
          className="flex h-96 flex-col gap-2 overflow-y-auto rounded-lg border p-3 text-sm leading-relaxed"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          aria-live="polite"
        >
          {lines.length === 0 ? (
            <p style={{ color: "var(--text-muted)" }}>
              {isLive ? "Connecting you to the agent…" : "The conversation will appear here once you call in."}
            </p>
          ) : (
            lines.map((line) => (
              <div key={line.id} className={line.role === "agent" ? "flex justify-start" : "flex justify-end"}>
                <div
                  className="flex max-w-[80%] items-start gap-2 rounded-xl border px-3 py-2"
                  style={{
                    // var(--surface-1) alone was nearly invisible here --
                    // it and the container's var(--surface-2) are
                    // deliberately close in value (subtle layering, not
                    // built for contrast: #fcfcfb vs #ffffff in light mode,
                    // #1a1a19 vs #202020 in dark). A visible border carries
                    // the distinction instead of relying on fill contrast.
                    backgroundColor:
                      line.role === "agent" ? "var(--surface-1)" : "color-mix(in srgb, var(--series-1) 12%, transparent)",
                    borderColor: line.role === "agent" ? "var(--border)" : "transparent",
                    color: line.isFinal ? "var(--text-primary)" : "var(--text-muted)",
                  }}
                >
                  {line.role === "agent" ? (
                    <Bot size={14} className="mt-0.5 shrink-0" style={{ color: "var(--series-1)" }} />
                  ) : (
                    <User size={14} className="mt-0.5 shrink-0" />
                  )}
                  <span>
                    {line.text}
                    {line.role === "caller" && !line.isFinal && <span className="animate-pulse">▋</span>}
                  </span>
                </div>
              </div>
            ))
          )}
          <div ref={conversationEndRef} />
        </div>

        {state === "done" && (
          <p className="mt-3 text-sm" style={{ color: "var(--status-good)" }}>
            Intake complete — a FitNova advisor will follow up. You can hang up now.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function StatusBadge({ state }: { state: ConnectionState }) {
  const label: Record<ConnectionState, string> = {
    idle: "Not started",
    connecting: "Connecting…",
    live: "In call",
    done: "Intake complete",
    error: "Error",
    ended: "Call ended",
  };
  const color: Record<ConnectionState, string> = {
    idle: "var(--text-muted)",
    connecting: "var(--status-warning)",
    live: "var(--status-good)",
    done: "var(--status-good)",
    error: "var(--status-critical)",
    ended: "var(--text-muted)",
  };
  return (
    // Dot carries the color coding; label stays on the regular text color --
    // see LiveCallPanel's StatusBadge for why (var(--status-warning) as text
    // fails WCAG contrast on this card background).
    <span className="flex items-center gap-1.5 text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
      <span
        className={state === "live" ? "h-2 w-2 rounded-full animate-pulse" : "h-2 w-2 rounded-full"}
        style={{ backgroundColor: color[state] }}
      />
      {label[state]}
    </span>
  );
}
