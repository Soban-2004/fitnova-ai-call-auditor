import { VoiceAgentPanel } from "@/components/agent/VoiceAgentPanel";

export default function VoiceAgentPage() {
  return (
    <div className="p-6 lg:p-8">
      <header className="mb-6">
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Voice Intake Agent
        </h1>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          A closed-loop voice agent (STT → LLM → Cartesia TTS) that runs an actual intake conversation with a
          prospective member — greets them, asks their goal, any injuries, and availability, then hands off to a
          human advisor.
        </p>
      </header>
      <VoiceAgentPanel />
    </div>
  );
}
