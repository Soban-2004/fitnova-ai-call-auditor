import { LiveCallPanel } from "@/components/live/LiveCallPanel";

type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

export default async function LivePage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const advisorIdParam = sp.advisor_id;
  const initialAdvisorId = Array.isArray(advisorIdParam) ? advisorIdParam[0] : advisorIdParam;

  return (
    <div className="p-6 lg:p-8">
      <header className="mb-6">
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Live Call Coaching
        </h1>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          Real-time voice pipeline — streams your microphone to Deepgram&apos;s live API and surfaces coaching
          nudges as the conversation happens, instead of after the call ends like the Upload flow.
        </p>
      </header>
      <LiveCallPanel initialAdvisorId={initialAdvisorId} />
    </div>
  );
}
