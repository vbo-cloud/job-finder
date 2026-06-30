export default function CVCardPlaceholder() {
  return (
    <div className="flex w-44 flex-shrink-0 flex-col">
      <div className="flex flex-col gap-2.5 rounded-xl border border-dashed border-subtle p-4">
        <div className="aspect-[3/4] w-full" />
        <div className="h-4" />
        <div className="h-3.5" />
        <div className="h-3.5" />
      </div>
      <div className="h-[42px]" />
    </div>
  );
}
