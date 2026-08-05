"use client";

import { forwardRef, useState } from "react";
import { Card, CardContent } from "@/components/ui/Card";

/** Native <audio> element wired up for the transcript's click-to-seek: the
 * parent holds the ref + currentTime state and passes seeks down to
 * TranscriptViewer, so this component stays a thin, uncontrolled wrapper. */
export const AudioPlayer = forwardRef<HTMLAudioElement, { src: string; onTimeUpdate?: (secs: number) => void }>(
  function AudioPlayer({ src, onTimeUpdate }, ref) {
    const [unavailable, setUnavailable] = useState(false);

    if (unavailable) {
      return (
        <Card>
          <CardContent className="py-3 text-sm" style={{ color: "var(--text-muted)" }}>
            Audio unavailable for this call.
          </CardContent>
        </Card>
      );
    }

    return (
      <Card>
        <CardContent className="py-3">
          {/* eslint-disable-next-line jsx-a11y/media-has-caption -- source recordings have no caption track */}
          <audio
            ref={ref}
            src={src}
            controls
            preload="metadata"
            className="w-full"
            style={{ height: 36 }}
            onTimeUpdate={(e) => onTimeUpdate?.(e.currentTarget.currentTime)}
            onError={() => setUnavailable(true)}
          />
        </CardContent>
      </Card>
    );
  }
);
