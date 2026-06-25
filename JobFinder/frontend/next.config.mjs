/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "*.blob.core.windows.net",
      },
    ],
  },
  webpack: (config) => {
    // pdfjs-dist v3 references the 'canvas' npm package for Node.js environments.
    // We use pdfjs in the browser only — alias it to false to skip it.
    config.resolve.alias.canvas = false;
    return config;
  },
};

export default nextConfig;
