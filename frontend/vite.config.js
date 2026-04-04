import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/student": "http://localhost:8000",
      "/add-interest": "http://localhost:8000",
    },
  },
});
