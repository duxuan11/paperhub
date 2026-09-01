import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          '"Source Han Sans SC"',
          '"Noto Sans SC"',
          '"PingFang SC"',
          '"Microsoft YaHei"',
          "system-ui",
          "-apple-system",
          "sans-serif",
        ],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      colors: {
        brand: {
          50: "#eef4ff",
          100: "#dbe6fe",
          200: "#bfd3fe",
          300: "#93b4fd",
          400: "#608afa",
          500: "#4f6ef7",
          600: "#3b5bdb",
          700: "#2f4ab8",
          800: "#2a4095",
          900: "#283b76",
        },
      },
    },
  },
  plugins: [],
};

export default config;
