import { Composition } from "remotion";
import { Bedroom } from "./Bedroom";
import { FPS as BED_FPS, totalFrames as bedFrames } from "./bedroom-edit";
import { Heist } from "./Heist";
import { FPS, totalFrames } from "./edit";

export const Root: React.FC = () => (
  <>
    <Composition id="Heist" component={Heist} durationInFrames={totalFrames()} fps={FPS} width={1920} height={1080} />
    <Composition id="Bedroom" component={Bedroom} durationInFrames={bedFrames()} fps={BED_FPS} width={1920}
      height={1080} />
  </>
);
