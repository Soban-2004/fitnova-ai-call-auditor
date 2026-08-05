import { UploadForm } from "@/components/upload/UploadForm";

export default function UploadPage() {
  return (
    <div className="p-6 lg:p-8">
      <header className="mb-6">
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Upload a Call
        </h1>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          Demo entry point for the file-upload source adapter — a telephony webhook would land here automatically instead.
        </p>
      </header>
      <UploadForm />
    </div>
  );
}
