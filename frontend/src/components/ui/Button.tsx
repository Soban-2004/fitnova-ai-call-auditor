import { cn } from "@/lib/utils";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "destructive";

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: "text-white",
  secondary: "border",
  ghost: "",
  destructive: "text-white",
};

export function Button({
  variant = "secondary",
  className,
  style,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  const variantStyle: React.CSSProperties =
    variant === "primary"
      ? { backgroundColor: "var(--series-1)" }
      : variant === "destructive"
        ? { backgroundColor: "var(--status-critical)" }
        : variant === "secondary"
          ? { borderColor: "var(--border)", color: "var(--text-primary)" }
          : { color: "var(--text-primary)" };

  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-opacity",
        "disabled:cursor-not-allowed disabled:opacity-50",
        !disabled && "hover:opacity-90",
        VARIANT_CLASSES[variant],
        className
      )}
      style={{ ...variantStyle, ...style }}
      disabled={disabled}
      {...props}
    />
  );
}
