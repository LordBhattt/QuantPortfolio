import RangeSlider from "../ui-qp/RangeSlider";
import AssetClassPill from "../ui-qp/AssetClassPill";

const CLASSES = [
  { key: "stocks", label: "Stock" },
  { key: "crypto", label: "Crypto" },
  { key: "gold", label: "Gold" },
  { key: "mf_etf", label: "MF/ETF" },
  { key: "bonds", label: "Bond" },
];

export default function ConstraintSliders({ constraints, onChange, infeasible }) {
  return (
    <div className="space-y-5">
      {CLASSES.map(({ key, label }) => {
        const constraint = constraints[key];
        return (
          <div key={key}>
            <div className="flex items-center justify-between mb-2">
              <AssetClassPill cls={label} />
              <span className="font-mono text-[11px] text-gray-500">
                {constraint.min}% - {constraint.max}%
              </span>
            </div>
            <RangeSlider
              value={[constraint.min, constraint.max]}
              onValueChange={([min, max]) => onChange({ ...constraints, [key]: { min, max } })}
              infeasible={infeasible}
            />
          </div>
        );
      })}
    </div>
  );
}
