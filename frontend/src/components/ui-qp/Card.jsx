export default function Card({ children, className = "", hover = true, as: Tag = "div" }) {
  return (
    <Tag
      className={`bg-card rounded-xl border border-black/[0.08] shadow-card ${
        hover ? "hover:shadow-card-hover transition-shadow duration-300" : ""
      } ${className}`}
    >
      {children}
    </Tag>
  );
}
