import React from 'react';
import {
  AbsoluteFill,
  Sequence,
  Img,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Easing,
} from 'remotion';

export const FPS = 30;

// --- real brand tokens, lifted directly from build_report.py's design system -
const PAPER = '#e6dfd0';
const INK = '#1a1816';
const INK_FADED = '#4a4742';
const INK_BLUE = '#2d3748';
const HERO_FONT = "'Helvetica Neue', Helvetica, Arial, sans-serif";
const ACCENT_FONT = "'Times New Roman', Times, serif";

// --- scene durations (frames @ 30fps) ---------------------------------------
const HOOK = 210; // 7s - three years of real Xero data, Fat Hamster Tavern
const SIGNATURE = 90; // 3s - animated brand mark (the squiggle + fork/knife draw-on)
const PROBLEM = 270; // 9s - the actual problem: multi-site owners, playing catch-up
const SOLUTION = 240; // 8s - LLM + API + MCP surfaces it
const XERO_REAL = 210; // 7s - the actual real Xero UI
const XERO_API_PROOF = 180; // 6s - "Received through the Xero API from The Pass"
const MISSION_CONTROL = 210; // 7s
const MODULE = 210; // 7s
const CHAT = 300; // 10s
const RESCAN = 210; // 7s
const CHASE = 210; // 7s
const ACCOUNTANT = 210; // 7s - the second output, for the controller
const OUTPUT = 240; // 8s - both outputs, framed together
const CLOSE = 210; // 7s

export const TOTAL_DURATION_FRAMES =
  HOOK + SIGNATURE + PROBLEM + SOLUTION + XERO_REAL + XERO_API_PROOF + MISSION_CONTROL +
  MODULE + CHAT + RESCAN + CHASE + ACCOUNTANT + OUTPUT + CLOSE;

// --- helpers -----------------------------------------------------------------
function useFadeIn(durationFrames = 20) {
  const frame = useCurrentFrame();
  return interpolate(frame, [0, durationFrames], [0, 1], { extrapolateRight: 'clamp' });
}

function useSlowZoom(totalFrames: number, fromScale = 1.04, toScale = 1.0) {
  const frame = useCurrentFrame();
  return interpolate(frame, [0, totalFrames], [fromScale, toScale], {
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
}

// bounded-box caption, matching the app's real card grammar: ink border,
// paper fill, sharp corners - not a generic rounded dark pill
const Caption: React.FC<{ children: React.ReactNode; delay?: number; position?: 'top' | 'bottom' }> = ({
  children,
  delay = 8,
  position = 'bottom',
}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [delay, delay + 15], [0, 1], { extrapolateRight: 'clamp' });
  const y = interpolate(frame, [delay, delay + 15], [12, 0], { extrapolateRight: 'clamp' });
  return (
    <div
      style={{
        position: 'absolute',
        ...(position === 'bottom' ? { bottom: 40 } : { top: 28 }),
        left: 0,
        right: 0,
        textAlign: 'center',
        opacity,
        transform: `translateY(${y}px)`,
      }}
    >
      <span
        style={{
          background: PAPER,
          border: `2px solid ${INK}`,
          color: INK,
          fontFamily: HERO_FONT,
          fontSize: 24,
          fontWeight: 700,
          padding: '14px 28px',
          display: 'inline-block',
          maxWidth: '82%',
        }}
      >
        {children}
      </span>
    </div>
  );
};

const ScreenshotScene: React.FC<{
  src: string;
  caption: React.ReactNode;
  totalFrames: number;
  zoom?: boolean;
  captionPosition?: 'top' | 'bottom';
}> = ({ src, caption, totalFrames, zoom = true, captionPosition = 'bottom' }) => {
  const opacity = useFadeIn(15);
  const scale = zoom ? useSlowZoom(totalFrames) : 1;
  return (
    <AbsoluteFill style={{ background: INK }}>
      <AbsoluteFill style={{ opacity, transform: `scale(${scale})` }}>
        <Img src={src} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
      </AbsoluteFill>
      <Caption position={captionPosition}>{caption}</Caption>
    </AbsoluteFill>
  );
};

// --- shared text-scene primitive, on-brand ------------------------------------
const TextScene: React.FC<{ lines: { text: string; accent?: boolean; size?: number }[] }> = ({ lines }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ background: PAPER, justifyContent: 'center', alignItems: 'center' }}>
      <div style={{ maxWidth: 1040, textAlign: 'center' }}>
        {lines.map((line, i) => {
          const s = spring({ frame: frame - i * 22, fps, config: { damping: 200 } });
          return (
            <div
              key={i}
              style={{
                fontSize: line.size ?? 42,
                color: line.accent ? INK_BLUE : INK,
                fontFamily: line.accent ? ACCENT_FONT : HERO_FONT,
                fontStyle: line.accent ? 'italic' : 'normal',
                fontWeight: line.accent ? 400 : 700,
                opacity: s,
                transform: `translateY(${(1 - s) * 20}px)`,
                marginBottom: 16,
              }}
            >
              {line.text}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// --- the animated brand signature - real SVG paths from build_report.py, ------
// drawn on via stroke-dasharray, not a static screenshot
const Signature: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const draw = spring({ frame, fps, config: { damping: 200 }, durationInFrames: 45 });
  const dash = interpolate(draw, [0, 1], [400, 0]);
  const labelIn = spring({ frame: frame - 30, fps, config: { damping: 200 } });

  return (
    <AbsoluteFill style={{ background: PAPER, justifyContent: 'center', alignItems: 'center' }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <svg width="220" height="90" viewBox="0 0 400 150" fill="none" stroke={INK_BLUE} strokeWidth="3">
          <path
            d="M 0,90 C 40,90 60,95 90,92 C 130,88 150,40 175,38 C 200,36 210,90 240,90 C 270,90 280,95 310,93 C 340,91 360,60 400,58"
            strokeDasharray="400"
            strokeDashoffset={dash}
          />
        </svg>
        <div
          style={{
            fontFamily: HERO_FONT,
            fontSize: 40,
            fontWeight: 700,
            color: INK,
            marginTop: 12,
            opacity: labelIn,
            transform: `translateY(${(1 - labelIn) * 12}px)`,
          }}
        >
          the pass <span style={{ fontFamily: ACCENT_FONT, fontStyle: 'italic', color: INK_FADED }}>v.01</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const PitchVideo: React.FC = () => {
  let t = 0;
  const seq = (duration: number) => {
    const from = t;
    t += duration;
    return { from, durationInFrames: duration };
  };

  return (
    <AbsoluteFill style={{ backgroundColor: PAPER }}>
      <Sequence {...seq(HOOK)}>
        <TextScene
          lines={[
            { text: 'three years of real Xero data.' },
            { text: 'Fat Hamster Tavern.', accent: true, size: 48 },
          ]}
        />
      </Sequence>

      <Sequence {...seq(SIGNATURE)}>
        <Signature />
      </Sequence>

      <Sequence {...seq(PROBLEM)}>
        <TextScene
          lines={[
            { text: 'hospitality owners run Xero across every site.' },
            { text: "they're playing catch-up —" },
            { text: 'accountants doing the filing, the strategy, the reporting.', accent: true, size: 34 },
            { text: "you're getting a fraction of the value your own data has." },
          ]}
        />
      </Sequence>

      <Sequence {...seq(SOLUTION)}>
        <TextScene
          lines={[
            { text: 'give an LLM the API and the MCP server,' },
            { text: 'and it can run the data itself —', accent: true, size: 34 },
            { text: 'surfacing the problems, the quirks, the numbers that matter.' },
          ]}
        />
      </Sequence>

      <Sequence {...seq(XERO_REAL)}>
        <ScreenshotScene
          src={staticFile('xero_real_zurich.png')}
          totalFrames={XERO_REAL}
          caption="This is real Xero. Zurich Insurance, paid twice, 3 days apart."
        />
      </Sequence>

      <Sequence {...seq(XERO_API_PROOF)}>
        <ScreenshotScene
          src={staticFile('xero_real_api_proof.png')}
          totalFrames={XERO_API_PROOF}
          captionPosition="top"
          caption='"Received through the Xero API from The Pass" — every transaction here really went through it.'
        />
      </Sequence>

      <Sequence {...seq(MISSION_CONTROL)}>
        <ScreenshotScene
          src={staticFile('01_overview.png')}
          totalFrames={MISSION_CONTROL}
          caption="Mission control — nine areas checked. £23,486 confirmed, found automatically."
        />
      </Sequence>

      <Sequence {...seq(MODULE)}>
        <ScreenshotScene
          src={staticFile('02_module.png')}
          totalFrames={MODULE}
          caption="Same duplicate payment — caught, explained in plain English, linked to the real record."
        />
      </Sequence>

      <Sequence {...seq(CHAT)}>
        <ScreenshotScene
          src={staticFile('04_answer.png')}
          totalFrames={CHAT}
          caption="Ask it anything. It's not a script — it's actually calling Xero, live, right now."
        />
      </Sequence>

      <Sequence {...seq(RESCAN)}>
        <ScreenshotScene
          src={staticFile('06_rescan_done.png')}
          totalFrames={RESCAN}
          caption="And this isn't a snapshot. That terminal just re-ran the whole scan against live Xero data."
        />
      </Sequence>

      <Sequence {...seq(CHASE)}>
        <ScreenshotScene
          src={staticFile('07_chase_draft.png')}
          totalFrames={CHASE}
          caption="It doesn't stop at finding problems — it drafts the chase email too."
        />
      </Sequence>

      <Sequence {...seq(ACCOUNTANT)}>
        <ScreenshotScene
          src={staticFile('08_accountant.png')}
          totalFrames={ACCOUNTANT}
          zoom={false}
          caption="A second output — the same findings, written for the accountant."
        />
      </Sequence>

      <Sequence {...seq(OUTPUT)}>
        <TextScene
          lines={[
            { text: 'one report for the accountant and the financial controller.' },
            { text: 'one for the owner —', accent: true, size: 34 },
            { text: 'real oversight, more value from Xero, more profit.' },
          ]}
        />
      </Sequence>

      <Sequence {...seq(CLOSE)}>
        <TextScene
          lines={[
            { text: 'try it yourself', size: 56 },
            { text: 'open-sandal-rkdw.here.now', accent: true, size: 30 },
          ]}
        />
      </Sequence>
    </AbsoluteFill>
  );
};
