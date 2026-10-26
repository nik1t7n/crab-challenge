import { Composition } from "remotion";
import { Bedroom } from "./Bedroom";
import { FPS as BED_FPS, totalFrames as bedFrames } from "./bedroom-edit";
import { Heist } from "./Heist";
import { Rocky } from "./Rocky";
import { Stealth } from "./Stealth";
import { FPS as STEALTH_FPS, totalFrames as stealthFrames } from "./stealth-edit";
import { FPS as ROCKY_FPS, totalFrames as rockyFrames } from "./rocky-edit";
import { FPS, totalFrames } from "./edit";

export const Root: React.FC = () => (
  <>
    <Composition id="Heist" component={Heist} durationInFrames={totalFrames()} fps={FPS} width={1920} height={1080} />
    <Composition id="Bedroom" component={Bedroom} durationInFrames={bedFrames()} fps={BED_FPS} width={1920}
      height={1080} />
    <Composition id="Rocky" component={Rocky} durationInFrames={rockyFrames()} fps={ROCKY_FPS} width={1920}
      height={1080} />
    <Composition id="Stealth" component={Stealth} durationInFrames={stealthFrames()} fps={STEALTH_FPS} width={1920}
      height={1080} />
  </>
);
