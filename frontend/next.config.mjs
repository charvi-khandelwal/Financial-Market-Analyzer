/** @type {import('next').NextConfig} */
const isDev = process.env.NODE_ENV === "development";
const nextConfig = {
  reactStrictMode: true,
  // Prevent dev/build processes from clobbering the same output directory.
  distDir: isDev ? ".next-dev" : ".next",
};
export default nextConfig;
