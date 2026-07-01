/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // react-force-graph pulls in three.js; nothing special needed, but keep
  // transpilePackages ready in case a nested ESM dep needs it.
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;
