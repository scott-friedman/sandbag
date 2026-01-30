import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  Easing,
} from "remotion";

export const Tagline: React.FC = () => {
  const frame = useCurrentFrame();

  // "shows" slams in from left
  const showsX = interpolate(frame, [0, 15], [-500, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.back(1.2)),
  });
  const showsOpacity = interpolate(frame, [0, 10], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Screen shake on impact
  const impact1Shake = interpolate(frame, [15, 20, 25], [0, 6, 0], {
    extrapolateRight: "clamp",
  });

  // Divider line grows
  const lineWidth = interpolate(frame, [25, 45], [0, 100], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  // URL types out
  const url = "foobos.net";
  const urlChars = interpolate(frame, [50, 85], [0, url.length], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const displayedUrl = url.slice(0, Math.max(0, Math.floor(urlChars)));
  const showCursor = frame >= 50 && frame <= 90 && frame % 8 < 4;

  // Final bracket flourish
  const bracketOpacity = interpolate(frame, [90, 100], [0, 1], {
    extrapolateRight: "clamp",
  });
  const leftBracketX = interpolate(frame, [90, 105], [-30, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const rightBracketX = interpolate(frame, [90, 105], [30, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  const shakeX = Math.sin(frame * 2) * impact1Shake;
  const shakeY = Math.cos(frame * 2.5) * impact1Shake;

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        backgroundColor: "#ffffff",
        fontFamily: "Times New Roman, Times, serif",
        transform: `translate(${shakeX}px, ${shakeY}px)`,
      }}
    >
      {/* Main tagline */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 15,
        }}
      >
        <div
          style={{
            opacity: showsOpacity,
            transform: `translateX(${showsX}px)`,
            fontSize: 80,
            fontWeight: 900,
            color: "#000000",
            fontFamily: "Arial Black, Helvetica, sans-serif",
            textTransform: "lowercase",
            display: "flex",
            alignItems: "center",
            gap: 15,
          }}
        >
          <span style={{ fontWeight: 400, fontFamily: "Times New Roman, Times, serif" }}>[</span>
          foobos
          <span style={{ fontWeight: 400, fontFamily: "Times New Roman, Times, serif" }}>]</span>
        </div>
        <div
          style={{
            opacity: showsOpacity,
            fontSize: 28,
            fontStyle: "italic",
            color: "#000000",
            fontFamily: "Times New Roman, Times, serif",
          }}
        >
          find local concerts
        </div>

        {/* Divider line */}
        <div
          style={{
            width: `${lineWidth}%`,
            maxWidth: 400,
            height: 4,
            backgroundColor: "#000000",
          }}
        />

        {/* URL with typewriter */}
        <div
          style={{
            fontSize: 32,
            fontWeight: 400,
            color: "#0000EE",
            textDecoration: "underline",
            fontFamily: "Times New Roman, Times, serif",
            display: "flex",
            alignItems: "center",
          }}
        >
          <span
            style={{
              opacity: bracketOpacity,
              transform: `translateX(${leftBracketX}px)`,
              color: "#000000",
              textDecoration: "none",
              marginRight: 8,
            }}
          >
            [
          </span>
          <span>{displayedUrl}</span>
          <span style={{ opacity: showCursor ? 1 : 0, color: "#000000", textDecoration: "none" }}>|</span>
          <span
            style={{
              opacity: bracketOpacity,
              transform: `translateX(${rightBracketX}px)`,
              color: "#000000",
              textDecoration: "none",
              marginLeft: 8,
            }}
          >
            ]
          </span>
        </div>
      </div>

      {/* Bottom corner branding */}
      <div
        style={{
          position: "absolute",
          bottom: 40,
          right: 50,
          fontSize: 24,
          fontWeight: 900,
          color: "#000000",
          fontFamily: "Arial Black, Helvetica, sans-serif",
          opacity: bracketOpacity,
        }}
      >
        foobos
      </div>

      {/* Decorative dots */}
      <div
        style={{
          position: "absolute",
          bottom: 40,
          left: 50,
          fontSize: 16,
          color: "#888888",
          opacity: bracketOpacity,
        }}
      >
        ● ● ●
      </div>
    </AbsoluteFill>
  );
};
