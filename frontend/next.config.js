/** @type {import('next').NextConfig} */
const withPWA = require('next-pwa')({
  dest: 'public',
  disable: true, // Disabled for now to fix redirect loop
  register: false,
  skipWaiting: false,
})

const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  images: {
    unoptimized: true,
  },
}

module.exports = withPWA(nextConfig)
