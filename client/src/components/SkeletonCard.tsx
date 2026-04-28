interface Props {
  className?: string;
  width?: string | number;
  height?: string | number;
}

export function SkeletonBar({ className = '', width = '100%', height = 12 }: Props) {
  return (
    <div
      className={`skeleton ${className}`}
      style={{ width, height }}
    />
  );
}

export function SkeletonBlock() {
  return (
    <div className="space-y-2">
      <SkeletonBar width="90%" height={12} />
      <SkeletonBar width="95%" height={12} />
      <SkeletonBar width="60%" height={12} />
    </div>
  );
}
