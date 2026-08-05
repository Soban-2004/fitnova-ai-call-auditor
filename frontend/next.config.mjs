/** @type {import('next').NextConfig} */
const nextConfig = {
  // Windows dev-mode workaround: jest-worker's child-process pool was
  // observed crashing on every SSR request to certain routes ("Jest worker
  // encountered 2 child process exceptions, exceeding retry limit"), even
  // after a clean cache + successful compile — consistent with a known
  // Windows-specific jest-worker/AV interaction, not application code.
  // Pinning to a single in-process worker avoids the child-process spawn
  // path entirely. Gated to win32 so a Linux build (Vercel, CI, Docker)
  // keeps full build parallelism instead of inheriting a workaround it
  // doesn't need.
  ...(process.platform === "win32"
    ? { experimental: { workerThreads: false, cpus: 1 } }
    : {}),
};

export default nextConfig;
