import * as Switch from "@radix-ui/react-switch";

export default function Toggle({ checked, onCheckedChange, label, hint }) {
  return (
    <label className="flex items-center justify-between gap-3 py-2 cursor-pointer select-none">
      <div className="flex flex-col">
        <span className="text-sm font-sans font-medium text-foreground">{label}</span>
        {hint && <span className="text-xs font-mono text-muted-foreground">{hint}</span>}
      </div>
      <Switch.Root
        checked={checked}
        onCheckedChange={onCheckedChange}
        className="w-10 h-6 bg-black/10 data-[state=checked]:bg-primary rounded-full relative transition-colors outline-none"
      >
        <Switch.Thumb className="block w-4 h-4 bg-white rounded-full shadow-sm translate-x-1 data-[state=checked]:translate-x-5 transition-transform" />
      </Switch.Root>
    </label>
  );
}
