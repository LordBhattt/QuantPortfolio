import * as RSlider from "@radix-ui/react-slider";

export default function Slider({ value, onValueChange, min = 0, max = 1, step = 0.01, className = "" }) {
  return (
    <RSlider.Root
      value={[value]}
      onValueChange={(v) => onValueChange(v[0])}
      min={min}
      max={max}
      step={step}
      className={`relative flex items-center select-none touch-none w-full h-5 ${className}`}
    >
      <RSlider.Track className="bg-black/[0.08] relative grow rounded-full h-1.5">
        <RSlider.Range className="absolute bg-primary rounded-full h-full" />
      </RSlider.Track>
      <RSlider.Thumb className="block w-4 h-4 bg-white border-2 border-primary rounded-full shadow-sm hover:scale-110 transition-transform outline-none focus:ring-2 focus:ring-primary/30" />
    </RSlider.Root>
  );
}
