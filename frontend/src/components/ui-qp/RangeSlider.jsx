import * as RSlider from "@radix-ui/react-slider";

export default function RangeSlider({ value, onValueChange, min = 0, max = 100, step = 1, infeasible = false }) {
  const trackColor = infeasible ? "bg-destructive" : "bg-primary";
  const thumbBorder = infeasible ? "border-destructive" : "border-primary";
  return (
    <RSlider.Root
      value={value}
      onValueChange={onValueChange}
      min={min}
      max={max}
      step={step}
      minStepsBetweenThumbs={1}
      className="relative flex items-center select-none touch-none w-full h-5"
    >
      <RSlider.Track className="bg-black/[0.08] relative grow rounded-full h-1.5">
        <RSlider.Range className={`absolute rounded-full h-full ${trackColor}`} />
      </RSlider.Track>
      {value.map((_, i) => (
        <RSlider.Thumb
          key={i}
          className={`block w-4 h-4 bg-white border-2 rounded-full shadow-sm hover:scale-110 transition-transform outline-none focus:ring-2 focus:ring-primary/30 ${thumbBorder}`}
        />
      ))}
    </RSlider.Root>
  );
}
