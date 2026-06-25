import dynamic from "next/dynamic";

const HomeClient = dynamic(
  () => import("./_components/HomeClient"),
  { ssr: false, loading: () => <div className="h-screen bg-[#0a0a0f]" /> },
);

export default function HomePage() {
  return <HomeClient />;
}
