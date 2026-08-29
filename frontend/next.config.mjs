/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // Render supplies env vars at container *runtime*, but Next bakes rewrites
    // into the image at *build* time. Default to the production backend when
    // building for production; keep localhost for local `next dev`.
    const backend =
      process.env.BACKEND_URL ||
      (process.env.NODE_ENV === "development"
        ? "http://localhost:8000"
        : "https://gate2027-backend.onrender.com");
    return [
      {
        source: "/api/:path*",
        destination: `${backend}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
