import { Composition } from 'remotion';
import { PitchVideo, TOTAL_DURATION_FRAMES, FPS } from './Video';

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="ThePassPitch"
      component={PitchVideo}
      durationInFrames={TOTAL_DURATION_FRAMES}
      fps={FPS}
      width={1280}
      height={720}
    />
  );
};
