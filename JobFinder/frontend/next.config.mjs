/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  images: {
    remotePatterns: [], // à compléter lors du déploiement
  },
};

export default nextConfig;
