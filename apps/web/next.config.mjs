/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@demo-trade/contracts", "@demo-trade/config"],
  experimental: { typedRoutes: false }
};
export default nextConfig;
