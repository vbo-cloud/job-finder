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
  webpack: (config, { dev }) => {
    // pdfjs-dist v3 references the 'canvas' npm package for Node.js environments.
    // We use pdfjs in the browser only — alias it to false to skip it.
    config.resolve.alias.canvas = false;
    // Avoid eval()-based source maps in dev: some Chrome extensions modify eval
    // strings and break the bundle. cheap-module-source-map inlines source maps
    // as data URIs without eval(), fixing the SyntaxError in those environments.
    if (dev) config.devtool = "cheap-module-source-map";
    return config;
  },
};

export default nextConfig;
